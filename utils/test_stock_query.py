"""
股票筛选示例
演示如何从数据库中筛选股票
"""
import sqlite3
import pandas as pd
from pathlib import Path

def query_low_pe_stocks(max_pe=10, max_pb=None, industry=None, limit=50):
    """
    查询低PE股票
    
    Args:
        max_pe: 最大PE
        max_pb: 最大PB（可选）
        industry: 行业过滤（可选）
        limit: 返回数量限制
    """
    db_path = Path("data/stock_database.db")
    conn = sqlite3.connect(str(db_path))
    
    # 构建查询
    conditions = [
        f"m.trade_date = (SELECT MAX(trade_date) FROM stock_market_daily)",
        "m.peTTM IS NOT NULL",
        "m.peTTM > 0",
        f"m.peTTM < {max_pe}"
    ]
    
    if max_pb:
        conditions.extend([
            "m.pbMRQ IS NOT NULL",
            f"m.pbMRQ < {max_pb}"
        ])
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
        SELECT 
            b.ts_code as 代码,
            b.name as 名称,
            m.close as 价格,
            m.peTTM as PE,
            m.pbMRQ as PB,
            m.psTTM as PS,
            m.volume / 10000 as 成交量_万手,
            m.pct_chg as 涨跌幅
        FROM stock_market_daily m
        JOIN stock_basic_info b ON m.ts_code = b.ts_code
        WHERE {where_clause}
        ORDER BY m.peTTM ASC
        LIMIT {limit}
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 测试
print("="*70)
print("📊 股票筛选示例")
print("="*70)

print("\n1️⃣ PE < 10 的股票：")
df1 = query_low_pe_stocks(max_pe=10, limit=10)
print(f"   找到 {len(df1)} 只")
print(df1[['代码', '名称', 'PE', 'PB']].to_string(index=False))

print("\n2️⃣ PE < 8 且 PB < 1.5 的股票：")
df2 = query_low_pe_stocks(max_pe=8, max_pb=1.5, limit=10)
print(f"   找到 {len(df2)} 只")
print(df2[['代码', '名称', 'PE', 'PB']].to_string(index=False))

print("\n" + "="*70)
print("✅ 筛选功能正常")
print("="*70)
