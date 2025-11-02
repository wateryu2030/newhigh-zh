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
    df.to_sql(table, con=engine, if_exists=if_exists, index=False, chunksize=chunksize, method="multi")
    return len(df)

def read_sql(sql: str, engine) -> pd.DataFrame:
    return pd.read_sql(sql, con=engine)

def exec_sql(sql: str, engine):
    with engine.begin() as conn:
        conn.execute(text(sql))
