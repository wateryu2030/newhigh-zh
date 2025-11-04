from sqlalchemy import create_engine, text
import pandas as pd
import os

def get_engine(db_url: str):
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
        # SQLite: 先删除重复记录再插入
        # 创建临时表
        temp_table = f"temp_{table}_{id(df)}"
        df.to_sql(temp_table, con=engine, if_exists="replace", index=False)
        
        # 获取实际列名
        columns = df.columns.tolist()
        cols_str = ', '.join(columns)  # 不使用引号
        
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
            unique_cols = columns
        
        with engine.begin() as conn:
            # 删除已存在的记录（基于唯一键）
            unique_conditions = ' AND '.join([f'{table}.{col} = {temp_table}.{col}' for col in unique_cols if col in columns])
            delete_sql = f"DELETE FROM {table} WHERE EXISTS (SELECT 1 FROM {temp_table} WHERE {unique_conditions})"
            conn.execute(text(delete_sql))
            # 插入新记录
            conn.execute(text(f"INSERT INTO {table} ({cols_str}) SELECT {cols_str} FROM {temp_table}"))
            # 清理临时表
            conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
        return len(df)

def read_sql(sql: str, engine) -> pd.DataFrame:
    return pd.read_sql(sql, con=engine)

def exec_sql(sql: str, engine):
    with engine.begin() as conn:
        conn.execute(text(sql))
