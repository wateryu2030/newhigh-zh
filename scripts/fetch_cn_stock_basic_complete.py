#!/usr/bin/env python3
"""
完整的A股基础数据下载脚本
参考GitHub项目方案，确保获取包含PE、PB等完整财务数据，并保存到数据库
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import time

# 清除代理环境变量（防止连接中断）
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


def retry_call(func, retries=6, backoff=1.5, func_name="未知函数"):
    """
    重试包装函数，使用指数退避
    """
    for attempt in range(retries):
        try:
            return func()
        except Exception as e:
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                print(f"  ⚠️  [{func_name}] 第 {attempt+1}/{retries} 次尝试失败")
                print(f"  💤 等待 {wait:.1f} 秒后重试...")
                time.sleep(wait)
            else:
                print(f"  ❌ [{func_name}] 所有 {retries} 次重试均失败")
                raise RuntimeError(f"所有 {retries} 次重试均失败: {func_name}") from e


def init_database():
    """
    初始化数据库表结构
    参考用户提供的方案
    """
    print("📊 初始化数据库...")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 创建股票数据表（参考用户提供的SQL结构）
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
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code)
        )
    """)
    
    # 创建索引以提高查询速度
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_code ON stock_data(stock_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_name ON stock_data(stock_name)")
    
    conn.commit()
    conn.close()
    print(f"  ✅ 数据库初始化完成: {DB_PATH}")
    return True


def setup_no_proxy_requests():
    """
    彻底设置requests库不使用代理
    确保在AKShare内部调用时也生效
    """
    try:
        import requests
        import urllib3
        
        # 禁用urllib3警告
        urllib3.disable_warnings()
        
        # 保存原始方法
        original_request = requests.Session.request
        original_get = requests.get
        original_post = requests.post
        original_init = requests.Session.__init__
        
        # 包装request方法
        def no_proxy_request(self, method, url, **kwargs):
            kwargs['proxies'] = {'http': None, 'https': None}
            kwargs['verify'] = False  # 禁用SSL验证（某些情况下需要）
            if 'headers' not in kwargs or kwargs['headers'] is None:
                kwargs['headers'] = {}
            headers = kwargs['headers']
            if 'User-Agent' not in headers:
                headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            if 'timeout' not in kwargs:
                kwargs['timeout'] = (10, 120)
            return original_request(self, method, url, **kwargs)
        
        # 包装get/post方法
        def no_proxy_get(url, **kwargs):
            kwargs['proxies'] = {'http': None, 'https': None}
            kwargs['verify'] = False
            return original_get(url, **kwargs)
        
        def no_proxy_post(url, **kwargs):
            kwargs['proxies'] = {'http': None, 'https': None}
            kwargs['verify'] = False
            return original_post(url, **kwargs)
        
        # 修改Session初始化
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.trust_env = False
            self.proxies = {'http': None, 'https': None}
            self.verify = False
        
        # 应用修改
        requests.Session.request = no_proxy_request
        requests.get = no_proxy_get
        requests.post = no_proxy_post
        requests.Session.__init__ = new_init
        
        # 修改requests模块级别的配置
        requests.packages.urllib3.disable_warnings()
        
        print("  ✅ 代理已彻底禁用")
        return True
    except Exception as e:
        print(f"  ⚠️ 设置无代理模式失败: {e}")
        return False


def fetch_stock_data_complete():
    """
    获取完整的A股数据（包含PE、PB等财务指标）
    参考用户提供的方案
    """
    print("📥 开始获取A股完整数据...")
    
    # 设置无代理模式
    setup_no_proxy_requests()
    
    try:
        import akshare as ak
    except ImportError:
        print("❌ AKShare未安装，请运行: pip install akshare")
        return pd.DataFrame()
    
    # 步骤1: 获取A股基础信息（代码、名称）
    print("\n1️⃣ 获取A股股票基本信息...")
    try:
        stock_info = retry_call(
            lambda: ak.stock_info_a_code_name(),
            retries=6,
            backoff=1.5,
            func_name="stock_info_a_code_name"
        )
        print(f"  ✅ 获取到 {len(stock_info)} 只股票基本信息")
        
        # 检查列名
        print(f"  📋 基础信息列名: {list(stock_info.columns)}")
    except Exception as e:
        print(f"  ❌ 获取基础信息失败: {e}")
        return pd.DataFrame()
    
    # 等待3秒，避免请求过快
    print("  ⏳ 等待3秒后获取实时行情数据...")
    time.sleep(3)
    
    # 步骤2: 获取A股实时行情数据（包含市盈率、PB、PS等）
    print("\n2️⃣ 获取A股实时行情数据（包含PE、PB、PS等财务指标）...")
    print("  ⚠️  注意：此接口需要获取所有A股实时数据（5000+只），可能需要较长时间...")
    print("  🔧 确保代理已禁用...")
    
    # 再次确保代理禁用（在AKShare调用前）
    setup_no_proxy_requests()
    
    stock_fundamentals = None
    max_retries = 8  # 增加重试次数
    retry_success = False
    
    for attempt in range(max_retries):
        try:
            print(f"  🔄 尝试 {attempt + 1}/{max_retries}...")
            stock_fundamentals = ak.stock_zh_a_spot_em()
            
            if stock_fundamentals is not None and not stock_fundamentals.empty:
                retry_success = True
                print(f"  ✅ 获取到 {len(stock_fundamentals)} 条实时行情数据")
                print(f"  📋 实时行情列名 ({len(stock_fundamentals.columns)}个):")
                for i, col in enumerate(stock_fundamentals.columns[:30], 1):
                    print(f"      {i:2d}. {col}")
                
                # 查找包含PE、PB的列
                pe_pb_cols = [col for col in stock_fundamentals.columns 
                             if 'pe' in col.lower() or 'pb' in col.lower() or '市盈' in col or '市净' in col]
                print(f"\n  🎯 包含PE/PB相关的列: {pe_pb_cols}")
                
                # 显示前2行数据示例
                if len(stock_fundamentals) > 0:
                    print(f"\n  📊 前2行数据示例（关键列）:")
                    key_cols = ['代码', '名称', '最新价', '总市值', '流通市值', '市盈率-动态', '市净率']
                    available_key_cols = [col for col in key_cols if col in stock_fundamentals.columns]
                    if available_key_cols:
                        print(stock_fundamentals[available_key_cols].head(2).to_string())
                
                break  # 成功获取，退出循环
        except Exception as e:
            error_msg = str(e).lower()
            if attempt < max_retries - 1:
                wait_time = 2.0 * (2 ** attempt)  # 指数退避
                print(f"  ⚠️  第 {attempt + 1} 次尝试失败: {str(e)[:100]}")
                print(f"  💤 等待 {wait_time:.1f} 秒后重试...")
                
                # 如果是因为代理问题，重新设置代理禁用
                if 'proxy' in error_msg:
                    print(f"  🔧 检测到代理问题，重新禁用代理...")
                    setup_no_proxy_requests()
                
                time.sleep(wait_time)
            else:
                print(f"  ❌ 所有 {max_retries} 次尝试均失败")
                print(f"  💡 将只使用基础信息（代码和名称）")
                stock_fundamentals = pd.DataFrame()
    
    if not retry_success:
        print(f"  ⚠️  实时行情接口失败，将只使用基础信息")
        stock_fundamentals = pd.DataFrame()
    
    # 步骤3: 合并数据
    print("\n3️⃣ 合并数据...")
    
    # 确定合并键
    if 'code' in stock_info.columns:
        info_code_col = 'code'
    elif stock_info.columns[0] == 'code':
        info_code_col = 'code'
    else:
        info_code_col = stock_info.columns[0]  # 使用第一列作为代码
    
    if not stock_fundamentals.empty and '代码' in stock_fundamentals.columns:
        # 合并数据
        df = stock_info.merge(
            stock_fundamentals,
            left_on=info_code_col,
            right_on='代码',
            how='left'
        )
        print(f"  ✅ 合并完成，共 {len(df)} 条记录")
    else:
        # 降级方案：只使用基础信息
        df = stock_info.copy()
        print(f"  ⚠️  使用降级方案：仅包含股票代码和名称")
    
    # 步骤4: 字段映射和清洗
    print("\n4️⃣ 字段映射和清洗...")
    
    # 定义列名映射（参考a_share_downloader.py的实际列名）
    column_mapping = {}
    available_columns = df.columns.tolist()
    
    # 代码和名称
    if info_code_col in available_columns:
        column_mapping[info_code_col] = 'stock_code'
    if '代码' in available_columns:
        column_mapping['代码'] = 'stock_code'
    if 'name' in available_columns:
        column_mapping['name'] = 'stock_name'
    if '名称' in available_columns:
        column_mapping['名称'] = 'stock_name'
    
    # 财务指标映射
    mapping_candidates = {
        "price": ["最新价", "现价", "close"],
        "market_cap": ["总市值", "总市值(元)", "market_cap"],
        "float_cap": ["流通市值", "流通市值(元)", "float_cap", "circ_mv"],
        "pe": ["市盈率-动态", "市盈率", "PE", "动态市盈率", "pe"],
        "pb": ["市净率", "PB", "pb"],
        "ps": ["市销率", "PS", "ps"],
        "pcf": ["市现率", "PCF", "pcf"],
        "change_pct": ["涨跌幅", "涨跌%", "pct_chg"],
        "volume": ["成交量", "volume"],
        "turnover": ["成交额", "amount", "turnover"],
    }
    
    # 匹配列名
    for new_col, candidates in mapping_candidates.items():
        for candidate in candidates:
            if candidate in available_columns and candidate not in column_mapping:
                column_mapping[candidate] = new_col
                break
    
    # 执行重命名
    df = df.rename(columns=column_mapping)
    
    # 确保所有必需的列都存在
    required_columns = {
        'stock_code': None,
        'stock_name': None,
        'price': None,
        'market_cap': None,
        'float_cap': None,
        'pe': None,
        'pb': None,
        'ps': None,
        'pcf': None,
        'change_pct': None,
        'volume': None,
        'turnover': None,
    }
    
    for col in required_columns:
        if col not in df.columns:
            df[col] = None
            print(f"  ⚠️  添加空列: {col}（数据源中不存在）")
    
    # 只保留需要的列
    df = df[[col for col in required_columns.keys() if col in df.columns]]
    
    # 步骤5: 数据清洗和类型转换
    print("\n5️⃣ 数据清洗和类型转换...")
    
    # 删除重复和空记录
    df = df.dropna(subset=['stock_code', 'stock_name']).drop_duplicates(subset=['stock_code'])
    
    # 数值列转换
    numeric_columns = ['price', 'market_cap', 'float_cap', 'pe', 'pb', 'ps', 'pcf', 
                      'change_pct', 'volume', 'turnover']
    
    for col in numeric_columns:
        if col in df.columns:
            # 转换为字符串，清理单位
            if df[col].dtype == 'object':
                df[col] = (df[col].astype(str)
                          .str.replace('元', '')
                          .str.replace('万', '')
                          .str.replace(',', '')
                          .str.replace(' ', '')
                          .str.replace('--', '')
                          .str.replace('-', ''))
            # 转换为数值
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 添加更新时间
    df['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 步骤6: 数据完整性检查
    print("\n6️⃣ 数据完整性检查：")
    for col in ['pe', 'pb', 'market_cap', 'price']:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            total_count = len(df)
            coverage = (non_null_count / total_count * 100) if total_count > 0 else 0
            print(f"     - {col}: {non_null_count}/{total_count} 条有数据 ({coverage:.1f}%)")
    
    print(f"\n  ✅ 数据清洗完成，共 {len(df)} 条有效记录")
    return df


def save_to_database(df: pd.DataFrame):
    """
    将数据保存到数据库
    参考用户提供的方案（使用SQLAlchemy或直接使用pandas）
    """
    if df.empty:
        print("  ⚠️  数据为空，跳过保存")
        return
    
    print("\n💾 保存数据到数据库...")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        
        # 使用pandas直接保存到数据库（参考用户方案）
        df.to_sql('stock_data', conn, if_exists='replace', index=False)
        
        conn.commit()
        conn.close()
        
        print(f"  ✅ 数据已保存到数据库: {len(df)} 条记录")
        print(f"  📍 数据库路径: {DB_PATH}")
        
    except Exception as e:
        print(f"  ❌ 保存到数据库失败: {e}")
        raise


def save_to_csv(df: pd.DataFrame):
    """同时保存到CSV文件作为备份"""
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
        print("🚀 A股基础数据完整下载脚本")
        print("=" * 60)
        
        # 初始化数据库
        init_database()
        
        # 获取完整数据
        df = fetch_stock_data_complete()
        
        if df.empty:
            print("\n❌ 未获取到数据，请检查网络连接和数据源")
            sys.exit(1)
        
        # 保存到数据库
        save_to_database(df)
        
        # 保存到CSV
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

