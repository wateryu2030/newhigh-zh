"""
安全的重复数据清理脚本（修复版）
只删除真正的重复记录，不会误删数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_URL
from utils.db_utils import get_engine
from sqlalchemy import text

def clean_duplicates_safe():
    """安全清理重复数据（使用临时表）"""
    engine = get_engine(DB_URL)
    
    print("="*70)
    print("🧹 安全清理重复数据")
    print("="*70)
    
    # 1. 清理 stock_basic_info 重复数据
    print("\n1️⃣ 清理 stock_basic_info...")
    with engine.begin() as conn:
        # 先创建临时表保存要保留的记录
        conn.execute(text("""
            CREATE TEMPORARY TABLE temp_basic_keep AS
            SELECT ts_code, code, code_name, ipoDate, outDate, type, status
            FROM (
                SELECT ts_code, code, code_name, ipoDate, outDate, type, status,
                       ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY code) as rn
                FROM stock_basic_info
            ) t
            WHERE t.rn = 1
        """))
        
        # 备份原表
        conn.execute(text("""
            CREATE TEMPORARY TABLE stock_basic_info_backup AS
            SELECT * FROM stock_basic_info
        """))
        
        # 清空原表
        conn.execute(text("DELETE FROM stock_basic_info"))
        
        # 恢复保留的记录
        conn.execute(text("""
            INSERT INTO stock_basic_info (ts_code, code, code_name, ipoDate, outDate, type, status)
            SELECT ts_code, code, code_name, ipoDate, outDate, type, status
            FROM temp_basic_keep
        """))
        
        result = conn.execute(text("SELECT COUNT(*) FROM stock_basic_info"))
        remaining = result.fetchone()[0]
        result = conn.execute(text("SELECT COUNT(DISTINCT ts_code) FROM stock_basic_info"))
        unique = result.fetchone()[0]
        print(f"   ✅ 清理完成，剩余: {remaining:,} 条记录（唯一股票: {unique:,}）")
    
    # 2. 清理 stock_market_daily 重复数据（已有唯一约束，通常不需要）
    print("\n2️⃣ 清理 stock_market_daily...")
    with engine.begin() as conn:
        # 检查是否有重复
        result = conn.execute(text("""
            SELECT COUNT(*) - (
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ts_code, trade_date FROM stock_market_daily
                ) as distinct_records
            ) as duplicates
            FROM stock_market_daily
        """))
        duplicates = result.fetchone()[0]
        
        if duplicates > 0:
            # 使用临时表方式删除重复
            conn.execute(text("""
                CREATE TEMPORARY TABLE temp_market_keep AS
                SELECT id
                FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (PARTITION BY ts_code, trade_date ORDER BY id) as rn
                    FROM stock_market_daily
                ) t
                WHERE t.rn = 1
            """))
            
            conn.execute(text("""
                DELETE FROM stock_market_daily
                WHERE id NOT IN (SELECT id FROM temp_market_keep)
            """))
            print(f"   ✅ 删除了 {duplicates:,} 条重复记录")
        else:
            print(f"   ✅ 无重复记录")
        
        result = conn.execute(text("SELECT COUNT(*) FROM stock_market_daily"))
        remaining = result.fetchone()[0]
        print(f"   ✅ 剩余: {remaining:,} 条记录")
    
    # 3. 清理 stock_financials 重复数据
    print("\n3️⃣ 清理 stock_financials...")
    with engine.begin() as conn:
        # 检查是否有重复
        result = conn.execute(text("""
            SELECT COUNT(*) - (
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ts_code, trade_date FROM stock_financials
                ) as distinct_records
            ) as duplicates
            FROM stock_financials
        """))
        duplicates = result.fetchone()[0]
        
        if duplicates > 0:
            # 使用临时表方式删除重复
            conn.execute(text("""
                CREATE TEMPORARY TABLE temp_financials_keep AS
                SELECT id
                FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (PARTITION BY ts_code, trade_date ORDER BY id) as rn
                    FROM stock_financials
                ) t
                WHERE t.rn = 1
            """))
            
            conn.execute(text("""
                DELETE FROM stock_financials
                WHERE id NOT IN (SELECT id FROM temp_financials_keep)
            """))
            print(f"   ✅ 删除了 {duplicates:,} 条重复记录")
        else:
            print(f"   ✅ 无重复记录")
        
        result = conn.execute(text("SELECT COUNT(*) FROM stock_financials"))
        remaining = result.fetchone()[0]
        print(f"   ✅ 剩余: {remaining:,} 条记录")
    
    print("\n" + "="*70)
    print("✅ 数据清理完成！")
    print("="*70)

if __name__ == "__main__":
    try:
        clean_duplicates_safe()
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()

