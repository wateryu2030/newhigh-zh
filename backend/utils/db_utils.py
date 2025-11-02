#!/usr/bin/env python3
"""
数据库工具函数
"""
from sqlalchemy import create_engine
import pandas as pd

def get_engine(db_url: str):
    """获取数据库引擎"""
    return create_engine(db_url, pool_pre_ping=True)

def upsert_df(df: pd.DataFrame, table: str, engine, if_exists="append", chunksize=2000):
    """将DataFrame写入数据库"""
    if df is None or df.empty:
        return 0
    df.to_sql(table, con=engine, if_exists=if_exists, index=False, chunksize=chunksize)
    return len(df)

def read_sql(query: str, engine):
    """从数据库读取数据"""
    return pd.read_sql(query, con=engine)
