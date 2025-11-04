#!/usr/bin/env python3
"""
检查A股基础数据完整性（已更新使用新数据库）
"""

import sqlite3
import pandas as pd
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 使用新的data_engine数据库
DB_PATH = project_root / "data" / "stock_database.db"
CSV_PATH = project_root / "data" / "stock_basic.csv"  # CSV已废弃，但保留检查

def check_data():
    """检查数据完整性"""
    print("=" * 60)
    print("📊 A股基础数据完整性检查（新数据库）")
    print("=" * 60)
    
    # 检查文件
    db_exists = DB_PATH.exists()
    csv_exists = CSV_PATH.exists()
    
    print(f"\n📁 文件检查:")
    print(f"   数据库: {'✅ 存在' if db_exists else '❌ 不存在'} ({DB_PATH})")
    print(f"   CSV备份: {'✅ 存在' if csv_exists else '❌ 不存在'} ({CSV_PATH})")
    
    if not db_exists and not csv_exists:
        print("\n❌ 未找到数据文件，请先下载数据")
        return
    
    # 检查新数据库（data_engine）
    if db_exists:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            # 检查新数据库表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"\n📊 数据库表: {', '.join([t for t in tables if not t.startswith('sqlite')])}")
            
            # 检查stock_basic_info表
            if 'stock_basic_info' in tables:
                cursor.execute("SELECT COUNT(*) FROM stock_basic_info")
                basic_count = cursor.fetchone()[0]
                print(f"\n✅ stock_basic_info: {basic_count:,} 条记录")
                
                # 检查字段
                cursor.execute("PRAGMA table_info(stock_basic_info)")
                columns = [row[1] for row in cursor.fetchall()]
                print(f"   字段: {', '.join(columns)}")
            
            # 检查stock_market_daily表
            if 'stock_market_daily' in tables:
                cursor.execute("SELECT COUNT(*) FROM stock_market_daily")
                market_count = cursor.fetchone()[0]
                print(f"\n✅ stock_market_daily: {market_count:,} 条记录")
                
                # 检查最新日期
                cursor.execute("SELECT MAX(trade_date) FROM stock_market_daily")
                latest_date = cursor.fetchone()[0]
                if latest_date:
                    print(f"   最新日期: {latest_date}")
            
            # 检查PE/PB数据完整性
            if 'stock_market_daily' in tables:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(peTTM) as has_pe,
                        COUNT(pbMRQ) as has_pb,
                        COUNT(psTTM) as has_ps
                    FROM stock_market_daily
                    WHERE trade_date = (SELECT MAX(trade_date) FROM stock_market_daily)
                """)
                stats = cursor.fetchone()
                if stats:
                    total, has_pe, has_pb, has_ps = stats
                    print(f"\n📈 最新日期数据完整性:")
                    print(f"   总记录: {total:,}")
                    if total > 0:
                        print(f"   有PE: {has_pe:,} ({has_pe/total*100:.1f}%)")
                        print(f"   有PB: {has_pb:,} ({has_pb/total*100:.1f}%)")
                        print(f"   有PS: {has_ps:,} ({has_ps/total*100:.1f}%)")
            
            conn.close()
            print("\n✅ 数据库检查完成")
            
        except Exception as e:
            print(f"\n❌ 检查数据库失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 检查CSV（已废弃，仅提示）
    if csv_exists:
        try:
            df_csv = pd.read_csv(CSV_PATH)
            print(f"\n📄 CSV文件（已废弃）:")
            print(f"   记录数: {len(df_csv)}")
            print(f"   文件大小: {CSV_PATH.stat().st_size / 1024:.1f} KB")
            print(f"   ⚠️ 注意: CSV文件已废弃，请使用新数据库")
        except Exception as e:
            print(f"\n❌ 读取CSV失败: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 检查完成")
    print("=" * 60)

if __name__ == "__main__":
    check_data()
