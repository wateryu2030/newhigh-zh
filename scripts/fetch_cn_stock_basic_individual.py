#!/usr/bin/env python3
"""
备用方案：逐只股票获取A股完整数据
当stock_zh_a_spot_em接口失败时，使用此方法逐只获取财务数据
虽然较慢，但更可靠
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime
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
    
    conn.commit()
    conn.close()
    print(f"  ✅ 数据库初始化完成: {DB_PATH}")
    return True


def setup_no_proxy_requests():
    """彻底设置requests库不使用代理"""
    try:
        import requests
        import urllib3
        urllib3.disable_warnings()
        
        original_request = requests.Session.request
        def no_proxy_request(self, method, url, **kwargs):
            kwargs['proxies'] = {'http': None, 'https': None}
            kwargs['verify'] = False
            if 'headers' not in kwargs or kwargs['headers'] is None:
                kwargs['headers'] = {}
            headers = kwargs['headers']
            if 'User-Agent' not in headers:
                headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            if 'timeout' not in kwargs:
                kwargs['timeout'] = (10, 120)
            return original_request(self, method, url, **kwargs)
        
        requests.Session.request = no_proxy_request
        
        original_init = requests.Session.__init__
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.trust_env = False
            self.proxies = {'http': None, 'https': None}
            self.verify = False
        
        requests.Session.__init__ = new_init
        requests.packages.urllib3.disable_warnings()
        return True
    except Exception as e:
        print(f"  ⚠️ 设置无代理模式失败: {e}")
        return False


def get_stock_individual_info(code: str, retries: int = 3):
    """
    获取单只股票的详细信息（包含PE、PB等）
    
    Args:
        code: 股票代码（如"000001"）
        retries: 重试次数
    
    Returns:
        dict: 股票信息字典
    """
    import akshare as ak
    
    for attempt in range(retries):
        try:
            # 方法1: 使用stock_individual_info_em获取个股信息
            info = ak.stock_individual_info_em(symbol=code)
            
            if info is not None and not info.empty:
                # 解析信息（通常是两列格式：指标名称和数值）
                result = {
                    'stock_code': code,
                    'stock_name': None,
                    'price': None,
                    'pe': None,
                    'pb': None,
                    'market_cap': None,
                    'float_cap': None,
                    'industry': None,
                    'area': None,
                    'market': 'SZ' if code.startswith('0') else 'SH',
                }
                
                # 如果info是DataFrame，尝试解析
                if isinstance(info, pd.DataFrame):
                    # 检查是否是键值对格式
                    if len(info.columns) >= 2:
                        # 假设第一列是指标名，第二列是值
                        info_dict = {}
                        for idx, row in info.iterrows():
                            key = str(row.iloc[0]).strip() if len(row) > 0 else None
                            value = row.iloc[1] if len(row) > 1 else None
                            if key:
                                info_dict[key] = value
                        
                        # 提取关键信息
                        for key, val in info_dict.items():
                            key_lower = str(key).lower()
                            if '名称' in key or 'name' in key_lower:
                                result['stock_name'] = str(val) if pd.notna(val) else None
                            elif '市盈率' in key or 'pe' in key_lower or '市盈' in key:
                                try:
                                    val_str = str(val).replace('倍', '').replace(',', '').strip()
                                    result['pe'] = float(val_str) if val_str and val_str != '--' else None
                                except:
                                    result['pe'] = None
                            elif '市净率' in key or 'pb' in key_lower or '市净' in key:
                                try:
                                    val_str = str(val).replace('倍', '').replace(',', '').strip()
                                    result['pb'] = float(val_str) if val_str and val_str != '--' else None
                                except:
                                    result['pb'] = None
                            elif '总市值' in key or 'market cap' in key_lower:
                                try:
                                    val_str = str(val).replace('元', '').replace('万', '').replace(',', '').strip()
                                    if '万' in str(val):
                                        result['market_cap'] = float(val_str) * 10000 if val_str else None
                                    else:
                                        result['market_cap'] = float(val_str) if val_str else None
                                except:
                                    result['market_cap'] = None
                            elif '流通市值' in key or 'circ' in key_lower:
                                try:
                                    val_str = str(val).replace('元', '').replace('万', '').replace(',', '').strip()
                                    if '万' in str(val):
                                        result['float_cap'] = float(val_str) * 10000 if val_str else None
                                    else:
                                        result['float_cap'] = float(val_str) if val_str else None
                                except:
                                    result['float_cap'] = None
                            elif '行业' in key or 'industry' in key_lower:
                                result['industry'] = str(val) if pd.notna(val) else None
                            elif '地区' in key or 'area' in key_lower:
                                result['area'] = str(val) if pd.notna(val) else None
                
                return result
            
        except Exception as e:
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                print(f"  ⚠️  {code} 第{attempt+1}次失败，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ {code} 获取失败: {str(e)[:80]}")
                return None
    
    return None


def fetch_stock_data_individual():
    """
    备用方案：逐只股票获取数据
    虽然慢但更可靠
    """
    print("📥 开始使用备用方案：逐只股票获取数据...")
    
    # 设置无代理模式
    setup_no_proxy_requests()
    
    try:
        import akshare as ak
    except ImportError:
        print("❌ AKShare未安装，请运行: pip install akshare")
        return pd.DataFrame()
    
    # 步骤1: 获取所有股票代码
    print("\n1️⃣ 获取所有股票代码列表...")
    try:
        stock_list = ak.stock_info_a_code_name()
        print(f"  ✅ 获取到 {len(stock_list)} 只股票")
        
        if stock_list.empty:
            return pd.DataFrame()
    except Exception as e:
        print(f"  ❌ 获取股票列表失败: {e}")
        return pd.DataFrame()
    
    # 确定代码列
    code_col = 'code' if 'code' in stock_list.columns else stock_list.columns[0]
    name_col = 'name' if 'name' in stock_list.columns else stock_list.columns[1]
    
    # 步骤2: 逐只获取详细信息（限制数量，避免太慢）
    print("\n2️⃣ 逐只获取股票详细信息（包含PE、PB等）...")
    print("  ⚠️  注意：此方法较慢，将先处理前100只股票作为示例")
    print("  💡 如果要获取全部，可以取消限制或分批处理")
    
    results = []
    total = len(stock_list)
    limit = 100  # 先测试100只，避免太慢
    processed = 0
    
    for idx, row in stock_list.head(limit).iterrows():
        code = str(row[code_col]).strip()
        name = str(row[name_col]).strip() if name_col in row else None
        
        processed += 1
        if processed % 10 == 0:
            print(f"  ⏳ 进度: {processed}/{min(limit, total)} ({processed/min(limit, total)*100:.1f}%)")
        
        # 获取详细信息
        info = get_stock_individual_info(code, retries=2)
        
        if info:
            info['stock_code'] = code
            if not info.get('stock_name'):
                info['stock_name'] = name
            results.append(info)
        else:
            # 即使获取失败，也保存基础信息
            results.append({
                'stock_code': code,
                'stock_name': name,
                'market': 'SZ' if code.startswith('0') else 'SH',
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # 控制请求频率（避免被限流）
        time.sleep(0.5)  # 每只股票间隔0.5秒
    
    if not results:
        print("  ❌ 未获取到任何数据")
        return pd.DataFrame()
    
    # 步骤3: 转换为DataFrame
    print("\n3️⃣ 整理数据...")
    df = pd.DataFrame(results)
    
    # 确保所有必需的列都存在
    required_cols = ['stock_code', 'stock_name', 'price', 'market_cap', 'float_cap',
                    'pe', 'pb', 'ps', 'pcf', 'change_pct', 'volume', 'turnover',
                    'industry', 'area', 'market', 'list_date', 'update_time']
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    
    # 添加更新时间
    df['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 数据完整性检查
    print("\n4️⃣ 数据完整性检查：")
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
        print("🚀 A股基础数据下载脚本（备用方案：逐只获取）")
        print("=" * 60)
        print("\n💡 此方案通过逐只股票获取数据，虽然较慢但更可靠")
        print("   适合在stock_zh_a_spot_em接口失败时使用\n")
        
        # 初始化数据库
        init_database()
        
        # 获取数据
        df = fetch_stock_data_individual()
        
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
        print("\n💡 提示：这是备用方案，只处理了部分股票")
        print("   如需获取全部数据，可以修改limit参数或分批处理")
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断下载")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

