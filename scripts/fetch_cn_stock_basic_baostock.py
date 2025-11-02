#!/usr/bin/env python3
"""
使用BaoStock (宝stock) 下载A股完整数据
BaoStock是免费的，不需要注册和身份验证
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import time

# 清除代理环境变量
proxy_vars = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 
              'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
for var in proxy_vars:
    os.environ.pop(var, None)

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 数据库路径
DB_PATH = project_root / "data" / "a_share_basic.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# CSV备份路径
CSV_PATH = project_root / "data" / "stock_basic.csv"


def init_database():
    """初始化数据库表结构"""
    print("📊 初始化数据库...")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            price REAL,
            market_cap REAL,
            float_cap REAL,
            pe REAL,
            pb REAL,
            ps REAL,
            pcf REAL,
            change_pct REAL,
            volume INTEGER,
            turnover REAL,
            industry TEXT,
            area TEXT,
            market TEXT,
            list_date TEXT,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_code ON stock_data(stock_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_name ON stock_data(stock_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_industry_data ON stock_data(industry)")
    
    conn.commit()
    conn.close()
    print(f"  ✅ 数据库初始化完成: {DB_PATH}")
    return True


def fetch_stock_list_baostock():
    """
    使用BaoStock获取所有A股股票列表
    返回：DataFrame包含 code, code_name, listing_date等
    """
    print("\n1️⃣ 使用BaoStock获取A股股票列表...")
    
    try:
        import baostock as bs
    except ImportError:
        print("  ❌ BaoStock未安装，请运行: pip install baostock")
        return pd.DataFrame()
    
    try:
        # 登录系统
        print("  🔐 登录BaoStock...")
        lg = bs.login()
        if lg.error_code != '0':
            print(f"  ❌ 登录失败: {lg.error_msg}")
            return pd.DataFrame()
        print(f"  ✅ 登录成功")
        
        # 获取所有股票信息
        print("  📥 获取所有股票信息...")
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 尝试使用今天的数据，如果失败则尝试最近几天的数据
        dates_to_try = [today]
        for i in range(1, 8):  # 尝试过去7天的数据
            test_date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            dates_to_try.append(test_date)
        
        result = pd.DataFrame()
        for test_date in dates_to_try:
            print(f"    🔍 尝试日期: {test_date}")
            rs = bs.query_all_stock(day=test_date)
            
            if rs.error_code != '0':
                print(f"    ❌ 查询失败: {rs.error_msg}")
                continue
            
            # 将结果集转化为 DataFrame
            data_list = []
            count = 0
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
                count += 1
                if count % 1000 == 0:
                    print(f"    ⏳ 已获取 {count} 只股票...")
            
            if data_list:
                result = pd.DataFrame(data_list, columns=rs.fields)
                print(f"  ✅ 获取到 {len(result)} 只股票 (日期: {test_date})")
                break
            else:
                print(f"    ⚠️  该日期无数据，尝试下一天...")
        
        if result.empty:
            print(f"  ❌ 过去7天内均无数据")
        
        # 登出系统
        bs.logout()
        print(f"  🔓 已登出BaoStock")
        
        return result
        
    except Exception as e:
        print(f"  ❌ 获取股票列表失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            bs.logout()
        except:
            pass
        return pd.DataFrame()


def fetch_stock_detail_baostock(code, retries=3):
    """
    获取单只股票的详细信息（包含PE、PB等）
    
    Args:
        code: 股票代码（如"sh.600000"）
        retries: 重试次数
    
    Returns:
        dict: 股票详细信息
    """
    import baostock as bs
    
    for attempt in range(retries):
        try:
            # 添加请求间隔，避免被限流
            if attempt > 0:
                time.sleep(0.5 * attempt)  # 指数退避
            # 获取股票基本信息
            rs = bs.query_stock_basic(code=code)
            if rs.error_code != '0':
                if attempt < retries - 1:
                    time.sleep(0.5)
                    continue
                return None
            
            basic_info = {}
            if rs.next():
                row_data = rs.get_row_data()
                fields = rs.fields
                basic_info = dict(zip(fields, row_data))
            
            # 获取最近交易日的行情数据（包含PE、PB等指标）
            today = datetime.now().strftime('%Y-%m-%d')
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')  # 本月第一天
            
            # 查询最近一个交易日的数据，包含财务指标
            rs_k = bs.query_history_k_data_plus(
                code=code,
                fields="date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=today,
                frequency="d",  # 日线
                adjustflag="3"  # 不复权
            )
            
            detail = {
                'stock_code': code.split('.')[1] if '.' in code else code,  # 提取纯代码
                'stock_name': basic_info.get('code_name', ''),
                'market': 'SH' if code.startswith('sh') else 'SZ',
                'list_date': basic_info.get('ipoDate', ''),
                'industry': '',  # BaoStock基础接口没有行业信息
                'area': '',  # BaoStock基础接口没有地区信息
                'pe': None,
                'pb': None,
                'ps': None,
                'pcf': None,
                'price': None,
                'change_pct': None,
                'volume': None,
                'turnover': None,
            }
            
            if rs_k.error_code == '0' and rs_k.next():
                # 获取最新一条数据
                k_data = rs_k.get_row_data()
                k_fields = rs_k.fields
                k_dict = dict(zip(k_fields, k_data))
                
                # 提取财务指标
                try:
                    detail['price'] = float(k_dict.get('close', 0)) if k_dict.get('close') else None
                    detail['change_pct'] = float(k_dict.get('pctChg', 0)) if k_dict.get('pctChg') else None
                    detail['volume'] = int(float(k_dict.get('volume', 0))) if k_dict.get('volume') else None
                    detail['turnover'] = float(k_dict.get('amount', 0)) if k_dict.get('amount') else None
                    
                    # 财务指标
                    if k_dict.get('peTTM') and str(k_dict.get('peTTM')).strip() != '':
                        detail['pe'] = float(k_dict.get('peTTM'))
                    if k_dict.get('pbMRQ') and str(k_dict.get('pbMRQ')).strip() != '':
                        detail['pb'] = float(k_dict.get('pbMRQ'))
                    if k_dict.get('psTTM') and str(k_dict.get('psTTM')).strip() != '':
                        detail['ps'] = float(k_dict.get('psTTM'))
                    if k_dict.get('pcfNcfTTM') and str(k_dict.get('pcfNcfTTM')).strip() != '':
                        detail['pcf'] = float(k_dict.get('pcfNcfTTM'))
                except (ValueError, TypeError) as e:
                    pass  # 转换失败时保持None
            
            detail['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return detail
            
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return None
    
    return None


def fetch_stock_data_complete():
    """
    获取完整的A股数据（使用BaoStock）
    """
    print("📥 开始使用BaoStock获取A股完整数据...")
    
    # 步骤1: 获取所有股票列表
    stock_list = fetch_stock_list_baostock()
    
    if stock_list.empty:
        print("  ❌ 未获取到股票列表")
        return pd.DataFrame()
    
    print(f"\n2️⃣ 整理股票代码（共 {len(stock_list)} 只）...")
    
    # 确保有code列
    if 'code' not in stock_list.columns:
        if len(stock_list.columns) >= 1:
            stock_list.columns = ['code'] + list(stock_list.columns[1:])
        else:
            print("  ❌ 股票列表格式不正确")
            return pd.DataFrame()
    
    # 步骤2: 逐只获取详细信息（分批处理）
    print(f"\n3️⃣ 逐只获取股票详细信息（包含PE、PB等）...")
    print("  ⚠️  注意：此过程需要一定时间，请耐心等待")
    print("  💡 进度会实时显示")
    
    try:
        import baostock as bs
        
        # 登录
        lg = bs.login()
        if lg.error_code != '0':
            print(f"  ❌ 登录失败: {lg.error_msg}")
            return pd.DataFrame()
        print("  ✅ 已登录BaoStock")
        
        results = []
        total = len(stock_list)
        processed = 0
        failed = 0
        
        for idx, row in stock_list.iterrows():
            code = str(row['code']).strip()
            name = row.get('code_name', '') if 'code_name' in row else ''
            
            processed += 1
            
            if processed % 100 == 0:
                print(f"  ⏳ 进度: {processed}/{total} ({processed/total*100:.1f}%), 失败: {failed}")
            
            # 获取详细信息
            detail = fetch_stock_detail_baostock(code, retries=3)
            
            if detail:
                if not detail.get('stock_name'):
                    detail['stock_name'] = name
                results.append(detail)
            else:
                # 即使获取失败，也保存基础信息
                results.append({
                    'stock_code': code.split('.')[1] if '.' in code else code,
                    'stock_name': name,
                    'market': 'SH' if code.startswith('sh') else 'SZ',
                    'list_date': row.get('ipoDate', '') if 'ipoDate' in row else '',
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                failed += 1
            
            # 控制请求频率（避免被限流）
            if processed % 50 == 0:
                time.sleep(2)  # 每50只股票休息2秒，降低被限流风险
        
        # 登出
        bs.logout()
        print(f"  🔓 已登出BaoStock")
        print(f"  ✅ 完成: 成功 {len(results)-failed}, 失败 {failed}")
        
    except Exception as e:
        print(f"  ❌ 获取详细信息失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            bs.logout()
        except:
            pass
        return pd.DataFrame()
    
    if not results:
        print("  ❌ 未获取到任何数据")
        return pd.DataFrame()
    
    # 步骤3: 转换为DataFrame
    print("\n4️⃣ 整理数据...")
    df = pd.DataFrame(results)
    
    # 确保所有必需的列都存在
    required_cols = ['stock_code', 'stock_name', 'price', 'market_cap', 'float_cap',
                    'pe', 'pb', 'ps', 'pcf', 'change_pct', 'volume', 'turnover',
                    'industry', 'area', 'market', 'list_date', 'update_time']
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    
    # 数据完整性检查
    print("\n5️⃣ 数据完整性检查：")
    for col in ['pe', 'pb', 'market_cap', 'price', 'industry']:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            total_count = len(df)
            coverage = (non_null_count / total_count * 100) if total_count > 0 else 0
            print(f"     - {col}: {non_null_count}/{total_count} 条有数据 ({coverage:.1f}%)")
    
    print(f"\n  ✅ 数据整理完成，共 {len(df)} 条有效记录")
    return df


def save_to_database(df: pd.DataFrame):
    """保存到数据库"""
    if df.empty:
        print("  ⚠️  数据为空，跳过保存")
        return
    
    print("\n💾 保存数据到数据库...")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        df.to_sql('stock_data', conn, if_exists='replace', index=False)
        conn.commit()
        conn.close()
        print(f"  ✅ 数据已保存到数据库: {len(df)} 条记录")
    except Exception as e:
        print(f"  ❌ 保存到数据库失败: {e}")
        raise


def save_to_csv(df: pd.DataFrame):
    """保存到CSV"""
    if df.empty:
        return
    
    try:
        df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
        print(f"  ✅ 数据已保存到CSV: {CSV_PATH}")
    except Exception as e:
        print(f"  ⚠️  保存到CSV失败: {e}")


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("🚀 A股基础数据下载脚本（BaoStock版本）")
        print("=" * 60)
        print("\n💡 BaoStock是免费的，不需要注册和身份验证")
        print("   数据完整、可靠，适合生产环境使用\n")
        
        # 初始化数据库
        init_database()
        
        # 获取数据
        df = fetch_stock_data_complete()
        
        if df.empty:
            print("\n❌ 未获取到数据")
            sys.exit(1)
        
        # 保存
        save_to_database(df)
        save_to_csv(df)
        
        print("\n" + "=" * 60)
        print("✅✅✅ 数据下载完成！")
        print("=" * 60)
        print(f"📊 数据统计：")
        print(f"   - 总记录数: {len(df)}")
        print(f"   - 数据库路径: {DB_PATH}")
        print(f"   - CSV备份路径: {CSV_PATH}")
        print("\n💡 提示：数据已保存，可以在Web界面中查看")
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断下载")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

