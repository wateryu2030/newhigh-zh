#!/usr/bin/env python3
"""
检查A股基础数据完整性
"""

import sqlite3
import pandas as pd
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DB_PATH = project_root / "data" / "a_share_basic.db"
CSV_PATH = project_root / "data" / "stock_basic.csv"

def check_data():
    """检查数据完整性"""
    print("=" * 60)
    print("📊 A股基础数据完整性检查")
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
    
    # 检查数据库
    if db_exists:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            
            # 检查表结构
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            print(f"\n📊 数据库结构:")
            print(f"   表: {', '.join([t for t in tables if not t.startswith('sqlite')])}")
            
            # 检查记录数
            if 'stock_data' in tables:
                df = pd.read_sql_query("SELECT COUNT(*) as total FROM stock_data", conn)
                total = df['total'].iloc[0]
                print(f"\n📈 记录统计:")
                print(f"   总记录数: {total}")
                
                # 检查数据完整性
                df_all = pd.read_sql_query("SELECT * FROM stock_data", conn)
                
                print(f"\n📊 数据完整性检查:")
                key_fields = {
                    'stock_code': '股票代码',
                    'stock_name': '股票名称',
                    'price': '当前价格',
                    'pe': '市盈率(PE)',
                    'pb': '市净率(PB)',
                    'ps': '市销率(PS)',
                    'market_cap': '总市值',
                    'float_cap': '流通市值',
                    'volume': '成交量',
                    'turnover': '成交额',
                    'industry': '行业',
                    'market': '市场'
                }
                
                for field, name in key_fields.items():
                    if field in df_all.columns:
                        non_null = df_all[field].notna().sum()
                        percentage = (non_null / total * 100) if total > 0 else 0
                        status = "✅" if percentage > 80 else "⚠️" if percentage > 0 else "❌"
                        print(f"   {status} {name}: {non_null}/{total} ({percentage:.1f}%)")
                
                # 显示样本数据
                print(f"\n📋 样本数据（前5条有效个股）:")
                # 过滤掉指数，只显示个股
                individual_stocks = df_all[
                    df_all['stock_code'].astype(str).str.match(r'^(6[0-9]{5}|00[0-9]{4}|30[0-9]{4})$')
                ].head(5)
                
                if not individual_stocks.empty:
                    display_cols = ['stock_code', 'stock_name', 'price', 'pe', 'pb', 'market_cap']
                    available_cols = [col for col in display_cols if col in individual_stocks.columns]
                    print(individual_stocks[available_cols].to_string(index=False))
                else:
                    print("   未找到有效个股数据")
                
            conn.close()
            
        except Exception as e:
            print(f"\n❌ 检查数据库失败: {e}")
    
    # 检查CSV
    if csv_exists:
        try:
            df_csv = pd.read_csv(CSV_PATH)
            print(f"\n📄 CSV文件:")
            print(f"   记录数: {len(df_csv)}")
            print(f"   文件大小: {CSV_PATH.stat().st_size / 1024:.1f} KB")
        except Exception as e:
            print(f"\n❌ 读取CSV失败: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 检查完成")
    print("=" * 60)

if __name__ == "__main__":
    check_data()
