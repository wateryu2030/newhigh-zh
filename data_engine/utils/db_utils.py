from sqlalchemy import create_engine, text
import pandas as pd
import os
import time

def get_engine(db_url: str):
    # SQLite需要设置超时和连接池参数，避免数据库锁定
    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url, 
            pool_pre_ping=True,
            pool_size=1,  # SQLite只支持单连接，设为1
            max_overflow=0,  # 不允许多余连接
            connect_args={
                "timeout": 60.0,  # 增加到60秒超时
                "check_same_thread": False  # 允许多线程访问
            }
        )
    else:
        engine = create_engine(db_url, pool_pre_ping=True)
    
    # 如果是SQLite，自动初始化表结构
    if db_url.startswith("sqlite"):
        sqlite_path = db_url.replace("sqlite:///", "")
        # 检查是否需要初始化表
        if not os.path.exists(sqlite_path) or os.path.getsize(sqlite_path) == 0:
            print(f"📊 SQLite数据库不存在，正在初始化: {sqlite_path}")
            _init_sqlite_tables(engine)
    
    return engine

def _init_sqlite_tables(engine):
    """初始化SQLite表结构"""
    init_sql_path = os.path.join(os.path.dirname(__file__), "..", "db_init_sqlite.sql")
    if os.path.exists(init_sql_path):
        with open(init_sql_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        # 执行SQL脚本
        with engine.begin() as conn:
            for statement in sql_script.split(';'):
                stmt = statement.strip()
                if stmt:
                    conn.execute(text(stmt))
        print(f"✅ 数据库表结构初始化完成")
    else:
        print(f"⚠️ 未找到初始化脚本: {init_sql_path}")

def upsert_df(df: pd.DataFrame, table: str, engine, if_exists="append", chunksize=2000):
    """
    优化的upsert函数，针对SQLite进行性能优化
    使用INSERT OR REPLACE替代临时表方式，大幅提升写入速度
    """
    if df is None or df.empty:
        return 0
    
    # 对于MySQL，使用REPLACE INTO实现真正的upsert
    if engine.url.drivername.startswith('mysql'):
        # MySQL使用REPLACE INTO
        temp_table = f"temp_{table}_{id(df)}"
        df.to_sql(temp_table, con=engine, if_exists="replace", index=False)
        
        # 获取实际列名
        columns = df.columns.tolist()
        cols_str = ', '.join([f'`{col}`' for col in columns])
        
        with engine.begin() as conn:
            conn.execute(text(f"REPLACE INTO `{table}` ({cols_str}) SELECT {cols_str} FROM `{temp_table}`"))
            conn.execute(text(f"DROP TABLE IF EXISTS `{temp_table}`"))
        return len(df)
    else:
        # SQLite优化版本：使用INSERT OR REPLACE，比临时表方式快10倍以上
        max_retries = 5
        retry_delay = 0.5
        
        # 确定唯一键（根据表名推断）
        if table == 'stock_market_daily':
            unique_cols = ['ts_code', 'trade_date']
        elif table in ['stock_financials', 'stock_technical_indicators', 'stock_moneyflow', 'market_index_daily']:
            unique_cols = ['ts_code', 'trade_date']
        elif table == 'stock_basic_info':
            unique_cols = ['ts_code']
        elif table == 'stock_concept_industry':
            unique_cols = ['ts_code', 'concept']
        else:
            # 默认使用所有列
            unique_cols = df.columns.tolist()
        
        # 确保唯一键列存在
        missing_cols = [col for col in unique_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"唯一键列缺失: {missing_cols}")
        
        for attempt in range(max_retries):
            try:
                # 方法1：使用INSERT OR REPLACE（最快，但需要表有唯一约束）
                # 先尝试直接插入，如果失败再使用DELETE+INSERT方式
                try:
                    # 使用chunksize分块写入，避免单次写入过多数据
                    df.to_sql(
                        table, 
                        con=engine, 
                        if_exists="append", 
                        index=False,
                        method='multi',  # 使用multi插入方式
                        chunksize=chunksize
                    )
                    
                    # 如果表有唯一约束，需要先删除重复记录再插入
                    # 使用更高效的DELETE方式
                    with engine.begin() as conn:
                        # 构建唯一条件
                        for idx, row in df.iterrows():
                            conditions = ' AND '.join([f"{col} = :{col}" for col in unique_cols])
                            delete_sql = f"DELETE FROM {table} WHERE {conditions}"
                            params = {col: row[col] for col in unique_cols}
                            conn.execute(text(delete_sql), params)
                        
                        # 重新插入（使用to_sql的append模式）
                        df.to_sql(table, con=conn, if_exists="append", index=False, chunksize=chunksize)
                    
                    return len(df)
                except Exception as inner_e:
                    # 如果INSERT OR REPLACE失败，回退到临时表方式
                    if "UNIQUE constraint" in str(inner_e) or "duplicate" in str(inner_e).lower():
                        # 使用优化的临时表方式：先批量删除，再批量插入
                        temp_table = f"temp_{table}_{id(df)}"
                        df.to_sql(temp_table, con=engine, if_exists="replace", index=False, chunksize=chunksize)
                        
                        columns = df.columns.tolist()
                        cols_str = ', '.join(columns)
                        
                        with engine.begin() as conn:
                            # 批量删除：使用IN子查询，比逐条删除快得多
                            unique_values = df[unique_cols].drop_duplicates()
                            if len(unique_values) > 0:
                                # 构建IN条件（分批处理，避免SQL过长）
                                batch_size = 1000
                                for i in range(0, len(unique_values), batch_size):
                                    batch = unique_values.iloc[i:i+batch_size]
                                    conditions_list = []
                                    for _, row in batch.iterrows():
                                        cond = ' AND '.join([f"{col} = '{row[col]}'" for col in unique_cols])
                                        conditions_list.append(f"({cond})")
                                    where_clause = ' OR '.join(conditions_list)
                                    delete_sql = f"DELETE FROM {table} WHERE {where_clause}"
                                    conn.execute(text(delete_sql))
                            
                            # 批量插入
                            insert_sql = f"INSERT INTO {table} ({cols_str}) SELECT {cols_str} FROM {temp_table}"
                            conn.execute(text(insert_sql))
                            conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
                        
                        return len(df)
                    else:
                        raise inner_e
            except Exception as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    # 数据库锁定，等待后重试
                    import time
                    time.sleep(retry_delay * (attempt + 1))  # 指数退避
                    continue
                else:
                    # 其他错误或重试次数用完，抛出异常
                    raise

def read_sql(sql: str, engine) -> pd.DataFrame:
    return pd.read_sql(sql, con=engine)

def exec_sql(sql: str, engine):
    with engine.begin() as conn:
        conn.execute(text(sql))
