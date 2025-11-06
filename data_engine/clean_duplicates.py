"""
数据清理脚本：删除重复记录
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_URL
from utils.db_utils import get_engine
from sqlalchemy import text

def clean_duplicates():
    """清理重复数据"""
    engine = get_engine(DB_URL)
    
    print("="*70)
    print("🧹 开始清理重复数据")
    print("="*70)
    
    # 1. 清理 stock_basic_info 重复数据
    print("\n1️⃣ 清理 stock_basic_info...")
    with engine.begin() as conn:
        # 使用ROW_NUMBER()窗口函数删除重复，保留每个ts_code的第一条记录
        # MySQL 8.0+支持窗口函数
        conn.execute(text("""
            DELETE FROM stock_basic_info
            WHERE (ts_code, code) IN (
                SELECT ts_code, code FROM (
                    SELECT ts_code, code,
                           ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY code) as rn
                    FROM stock_basic_info
                ) t
                WHERE t.rn > 1
            )
        """))
        
        result = conn.execute(text("SELECT COUNT(*) FROM stock_basic_info"))
        remaining = result.fetchone()[0]
        result = conn.execute(text("SELECT COUNT(DISTINCT ts_code) FROM stock_basic_info"))
        unique = result.fetchone()[0]
        print(f"   ✅ 清理完成，剩余: {remaining:,} 条记录（唯一股票: {unique:,}）")
    
    # 2. 清理 stock_market_daily 重复数据
    print("\n2️⃣ 清理 stock_market_daily...")
    with engine.begin() as conn:
        # 检查是否有id字段
        try:
            # 如果有id字段，使用id删除重复
            conn.execute(text("""
                DELETE t1 FROM stock_market_daily t1
                INNER JOIN stock_market_daily t2 
                WHERE t1.ts_code = t2.ts_code 
                AND t1.trade_date = t2.trade_date
                AND t1.id > t2.id
            """))
        except:
            # 如果没有id字段，使用临时表方式
            conn.execute(text("""
                CREATE TEMPORARY TABLE temp_market AS
                SELECT ts_code, trade_date, MIN(ROW_NUMBER() OVER (PARTITION BY ts_code, trade_date ORDER BY trade_date)) as rn
                FROM stock_market_daily
            """))
            
            # 对于MySQL，使用另一种方式
            conn.execute(text("""
                DELETE t1 FROM stock_market_daily t1
                LEFT JOIN (
                    SELECT ts_code, trade_date, MIN(CONCAT(ts_code, trade_date)) as keep_key
                    FROM stock_market_daily
                    GROUP BY ts_code, trade_date
                ) t2 ON t1.ts_code = t2.ts_code AND t1.trade_date = t2.trade_date
                WHERE t2.keep_key IS NULL
            """))
        
        result = conn.execute(text("SELECT COUNT(*) FROM stock_market_daily"))
        remaining = result.fetchone()[0]
        print(f"   ✅ 清理完成，剩余: {remaining:,} 条记录")
    
    # 3. 清理 stock_financials 重复数据
    print("\n3️⃣ 清理 stock_financials...")
    with engine.begin() as conn:
        # 检查是否有id字段
        try:
            # 如果有id字段，使用id删除重复
            conn.execute(text("""
                DELETE t1 FROM stock_financials t1
                INNER JOIN stock_financials t2 
                WHERE t1.ts_code = t2.ts_code 
                AND t1.trade_date = t2.trade_date
                AND t1.id > t2.id
            """))
        except:
            # 如果没有id字段，使用临时表方式
            conn.execute(text("""
                DELETE t1 FROM stock_financials t1
                LEFT JOIN (
                    SELECT ts_code, trade_date, MIN(CONCAT(ts_code, trade_date)) as keep_key
                    FROM stock_financials
                    GROUP BY ts_code, trade_date
                ) t2 ON t1.ts_code = t2.ts_code AND t1.trade_date = t2.trade_date
                WHERE t2.keep_key IS NULL
            """))
        
        result = conn.execute(text("SELECT COUNT(*) FROM stock_financials"))
        remaining = result.fetchone()[0]
        print(f"   ✅ 清理完成，剩余: {remaining:,} 条记录")
    
    print("\n" + "="*70)
    print("✅ 数据清理完成！")
    print("="*70)

if __name__ == "__main__":
    try:
        clean_duplicates()
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()

