#!/usr/bin/env python3
"""
拉取A股基础资料
使用AkShare获取A股股票基本信息并保存为CSV
"""

from pathlib import Path
import pandas as pd
import sys
import os
import time
import sqlite3
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 禁用代理（避免代理连接错误）
def disable_proxy():
    """临时禁用代理设置"""
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
                  'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    saved_proxy = {}
    for var in proxy_vars:
        if var in os.environ:
            saved_proxy[var] = os.environ[var]
            del os.environ[var]
    return saved_proxy

def restore_proxy(saved_proxy):
    """恢复代理设置"""
    for var, value in saved_proxy.items():
        os.environ[var] = value

# 临时禁用代理
saved_proxy_env = disable_proxy()

try:
    import akshare as ak
    # 如果akshare内部使用requests，也禁用代理
    try:
        import requests
        # 保存原始的get方法
        original_get = requests.Session.get if hasattr(requests.Session, 'get') else None
    except:
        pass
except ImportError:
    print("❌ 错误: 未安装 akshare，请运行: pip install akshare")
    sys.exit(1)

OUT = Path("data/stock_basic.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)

# 数据库路径
DB_PATH = project_root / "data" / "a_share_basic.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def retry_call(func, retries=6, backoff=1.5, allowed_exceptions=(Exception,), func_name="未知函数"):
    """
    重试包装函数，使用指数退避
    参考ChatGPT推荐的方案，能够大幅减少RemoteDisconnected错误影响
    
    Args:
        func: 要执行的函数（无参数）
        retries: 最大重试次数
        backoff: 初始退避时间（秒）
        allowed_exceptions: 允许重试的异常类型
        func_name: 函数名称（用于日志）
    """
    for attempt in range(retries):
        try:
            return func()
        except allowed_exceptions as e:
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)  # 指数退避：1.5s, 3s, 6s, 12s, 24s, 48s
                print(f"  ⚠️  [{func_name}] 第 {attempt+1}/{retries} 次尝试失败: {repr(e)[:80]}")
                print(f"  💤 等待 {wait:.1f} 秒后重试...")
                time.sleep(wait)
            else:
                print(f"  ❌ [{func_name}] 所有 {retries} 次重试均失败")
                raise RuntimeError(f"所有 {retries} 次重试均失败: {func_name}") from e
    raise RuntimeError(f"重试逻辑错误: {func_name}")


def fetch_cn_stock_basic(use_tushare: bool = False) -> pd.DataFrame:
    """
    获取A股股票基本信息（优先使用AKShare，稳定且免费）
    
    Args:
        use_tushare: 是否尝试使用Tushare（默认False，使用AKShare）
    
    Returns:
        pd.DataFrame: 包含股票代码、名称、最新价、市值等信息
    """
    print("📥 开始拉取A股基础资料...")
    
    # 彻底清除代理环境变量（防止代理导致的连接中断）
    print("  🔧 清除代理环境变量...")
    proxy_vars = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 
                  'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    for var in proxy_vars:
        os.environ.pop(var, None)
    print("  ✅ 代理环境变量已清除")
    
    # 方法1：优先使用AKShare（推荐，免费且稳定）
    print("  📊 使用AKShare获取数据（免费，无需Token）...")
    
    # 方法2：可选，如果用户明确要使用Tushare
    if use_tushare:
        try:
            from tradingagents.dataflows.tushare_adapter import get_tushare_adapter
            adapter = get_tushare_adapter()
            
            if adapter.provider and adapter.provider.connected:
                print("  ✅ 检测到Tushare配置，尝试使用Tushare获取完整数据...")
                try:
                    return _fetch_with_tushare(adapter)
                except Exception as e:
                    print(f"  ⚠️  Tushare获取失败: {e}")
                    print("  💡 降级使用AKShare...")
        except Exception as e:
            print(f"  ⚠️  Tushare初始化失败: {e}")
            print("  💡 使用AKShare作为数据源...")
    
    # 设置无代理模式（修改requests库配置）
    def setup_no_proxy_requests():
        """设置requests库不使用代理（参考ChatGPT方案）"""
        try:
            import requests
            import urllib3
            
            # 1. 禁用环境变量中的代理
            disable_proxy()
            
            # 2. 禁用urllib3的代理检测
            try:
                urllib3.disable_warnings()
            except:
                pass
            
            # 3. 修改requests.Session的request方法
            original_request = requests.Session.request
            def no_proxy_request(self, method, url, **kwargs):
                # 强制设置不使用代理
                kwargs['proxies'] = {'http': None, 'https': None}
                
                # 添加更真实的浏览器请求头
                if 'headers' not in kwargs or kwargs['headers'] is None:
                    kwargs['headers'] = {}
                
                headers = kwargs['headers']
                if 'User-Agent' not in headers or not headers.get('User-Agent'):
                    headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                if 'Accept' not in headers:
                    headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                if 'Accept-Language' not in headers:
                    headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
                if 'Connection' not in headers:
                    headers['Connection'] = 'close'  # 每次请求后关闭连接
                
                # 增加超时时间
                if 'timeout' not in kwargs or kwargs.get('timeout') is None:
                    kwargs['timeout'] = (10, 120)
                
                return original_request(self, method, url, **kwargs)
            
            requests.Session.request = no_proxy_request
            
            # 4. 修改requests.get/post等快捷方法
            original_get = requests.get
            original_post = requests.post
            
            def patched_get(url, **kwargs):
                kwargs['proxies'] = {'http': None, 'https': None}
                return original_get(url, **kwargs)
            
            def patched_post(url, **kwargs):
                kwargs['proxies'] = {'http': None, 'https': None}
                return original_post(url, **kwargs)
            
            requests.get = patched_get
            requests.post = patched_post
            
            # 5. 修改Session的默认配置
            original_init = requests.Session.__init__
            def new_init(self, *args, **kwargs):
                original_init(self, *args, **kwargs)
                if hasattr(self, 'trust_env'):
                    self.trust_env = False
                self.proxies = {'http': None, 'https': None}
            
            requests.Session.__init__ = new_init
            
            return True
        except Exception as e:
            print(f"  ⚠️ 设置无代理模式失败: {e}")
            return False
    
    # 设置无代理模式
    setup_no_proxy_requests()
    
    # 注意：retry_call函数已定义在函数外部，使用ChatGPT推荐的指数退避方案
    
    try:
        # 使用改进的重试机制获取股票代码与名称
        print("  - 获取股票代码与名称表（stock_info_a_code_name）...")
        code_name = retry_call(
            lambda: ak.stock_info_a_code_name(),
            retries=6,
            backoff=1.5,
            func_name="stock_info_a_code_name"
        )
        print(f"  ✅ 获取到 {len(code_name)} 条股票代码")
        
        # 在两次API调用之间添加延迟，避免请求过快
        print("  - 等待 3 秒后获取实时数据（避免请求过快）...")
        time.sleep(3)
        
        # 获取当日A股现货行情（包含价格、市值等）
        print("  - 获取当日A股现货行情（stock_zh_a_spot_em）...")
        print("  ⚠️  注意：此接口需要获取所有A股实时数据（5000+只），可能需要较长时间...")
        
        spot = None
        try:
            spot = retry_call(
                lambda: ak.stock_zh_a_spot_em(),
                retries=6,
                backoff=2.0,  # 对于大数据量请求，初始退避时间更长
                func_name="stock_zh_a_spot_em"
            )
            print(f"  ✅ 获取到 {len(spot)} 条实时信息")
        except Exception as e:
            print(f"  ⚠️  实时数据接口失败: {e}")
            print(f"  💡 使用降级方案：只使用基础信息（代码和名称）")
            print(f"  💡 价格、市值等数据将留空，可后续单独获取")
            spot = pd.DataFrame()  # 空DataFrame，后续合并时使用left join
        
        # 合并数据
        print("  - 合并数据...")
        if not spot.empty:
            df = code_name.merge(
                spot, 
                left_on="code", 
                right_on="代码", 
                how="left"
            )
        else:
            # 降级方案：只使用基础信息
            df = code_name.copy()
            print("  ℹ️  使用降级方案：仅包含股票代码和名称")
        
        # 字段清洗，重命名（参考a_share_downloader.py的实际列名）
        # AKShare的stock_zh_a_spot_em返回的列名可能有多种变体
        column_mapping = {}
        available_columns = df.columns.tolist()
        
        # 打印实际列名以便调试
        print(f"  📋 实际获取到的列名: {available_columns[:20]}...")
        
        # 定义多种可能的列名映射（应对AKShare不同版本或接口变化）
        mapping_candidates = {
            "code": ["code", "代码", "symbol", "股票代码"],
            "name": ["name", "名称"],
            "price": ["最新价", "现价", "close", "price"],
            "market_cap": ["总市值", "总市值(元)", "market_cap", "total_mv"],
            "float_cap": ["流通市值", "流通市值(元)", "float_cap", "circ_mv"],
            "pe": ["市盈率-动态", "市盈率", "PE", "动态市盈率", "pe", "pe_ttm"],
            "pb": ["市净率", "PB", "pb"],
            "ps": ["市销率", "PS", "ps"],
            "pcf": ["市现率", "PCF", "pcf"],
            "change_pct": ["涨跌幅", "涨跌%", "pct_chg", "change_pct"],
            "volume": ["成交量", "volume"],
            "turnover": ["成交额", "amount", "turnover"],
        }
        
        # 匹配列名
        for new_col, candidates in mapping_candidates.items():
            matched = False
            for candidate in candidates:
                if candidate in available_columns:
                    column_mapping[candidate] = new_col
                    matched = True
                    break
            if not matched:
                print(f"  ⚠️  未找到 {new_col} 的列，将设为空值")
        
        # 执行重命名
        df = df.rename(columns=column_mapping)
        
        # 确保所有期望的列都存在（即使为空）
        expected_columns = ["code", "name", "price", "market_cap", "float_cap", 
                           "pe", "pb", "ps", "pcf", "change_pct", "volume", "turnover"]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None
                print(f"  ℹ️  添加空列: {col}（数据源中不存在）")
        
        # 尝试获取财务指标（ROE等）
        print("  - 尝试获取财务指标（ROE等）...")
        try:
            # 使用akshare获取基本面数据
            for idx, row in df.head(100).iterrows():  # 先测试前100只股票
                code = row.get("code", "")
                if not code:
                    continue
                try:
                    # 获取股票财务指标
                    basic_info = ak.stock_individual_info_em(symbol=code)
                    if not basic_info.empty and "净资产收益率" in basic_info.values:
                        # 这里可以添加ROE等财务指标
                        pass
                except:
                    pass
        except Exception as e:
            print(f"  ⚠️ 财务指标获取部分失败（不影响主流程）: {e}")
        
        # 选择需要的列
        expected_columns = ["code", "name", "price", "market_cap", "float_cap", 
                           "pe", "pb", "ps", "pcf", "change_pct", "volume", "turnover"]
        columns_to_keep = [col for col in expected_columns if col in df.columns]
        df = df[columns_to_keep]
        
        # 数据清洗
        df = df.dropna(subset=["code", "name"]).drop_duplicates(subset=["code"])
        
        # 数值列转换（处理各种格式：字符串、带单位等）
        numeric_columns = ["price", "market_cap", "float_cap", "pe", "pb", "ps", "pcf", 
                         "change_pct", "volume", "turnover"]
        for col in numeric_columns:
            if col in df.columns:
                # 先转换为字符串，清理单位
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace('元', '').str.replace('万', '').str.replace(',', '').str.replace(' ', '')
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # 检查数据完整性
        print(f"\n  📊 数据完整性检查：")
        for col in ["pe", "pb", "market_cap", "price"]:
            if col in df.columns:
                non_null_count = df[col].notna().sum()
                print(f"     - {col}: {non_null_count}/{len(df)} 条有数据 ({non_null_count/len(df)*100:.1f}%)")
            else:
                print(f"     - {col}: 列不存在")
        
        print(f"  ✅ 数据清洗完成，共 {len(df)} 条有效记录")
        return df
        
    except ConnectionError as e:
        print(f"\n❌ 网络连接错误: {e}")
        print("💡 建议:")
        print("  1. 检查网络连接是否稳定")
        print("  2. 数据源服务器可能临时不可用，请稍后重试")
        print("  3. 如果是频繁的连接中断，可能是数据源限流，请等待5-10分钟后重试")
        import traceback
        traceback.print_exc()
        raise
    except Exception as e:
        error_msg = str(e).lower()
        error_type = type(e).__name__
        
        if "disconnected" in error_msg or "aborted" in error_msg:
            print(f"\n❌ 连接中断: {e}")
            print("💡 问题分析: 数据源服务器主动关闭了连接")
            print("💡 可能原因:")
            print("  1. 数据源服务器临时负载过高")
            print("  2. 请求频率过快被限流")
            print("  3. 网络不稳定导致连接中断")
            print("💡 解决方案:")
            print("  1. 等待5-10分钟后重试")
            print("  2. 检查网络连接稳定性")
            print("  3. 如果问题持续，可以尝试在非高峰时段下载")
        elif "connection" in error_msg or "timeout" in error_msg:
            print(f"\n❌ 网络连接错误: {e}")
            print("💡 建议:")
            print("  1. 检查网络连接是否稳定")
            print("  2. 检查防火墙/代理设置")
            print("  3. 稍后重试（可能是数据源服务器繁忙）")
        elif "rate limit" in error_msg or "频率" in error_msg:
            print(f"\n❌ 请求频率过高: {e}")
            print("💡 建议:")
            print("  1. 等待一段时间后重试")
            print("  2. 数据源可能有访问频率限制")
        else:
            print(f"\n❌ 下载失败: {e}")
            print(f"💡 错误类型: {error_type}")
            print("💡 请检查错误信息并重试")
        import traceback
        traceback.print_exc()
        raise


def _fetch_with_tushare(adapter) -> pd.DataFrame:
    """
    使用Tushare获取A股完整数据
    
    Args:
        adapter: TushareDataAdapter实例
    
    Returns:
        pd.DataFrame: 包含完整数据的DataFrame
    """
    try:
        from datetime import datetime
        import pandas as pd
        
        # 修复: 使用api而不是pro_api
        pro = adapter.provider.api
        today = datetime.now().strftime('%Y%m%d')
        
        print("  - 测试Tushare接口权限...")
        
        # 先测试基础接口是否可用
        try:
            test_basic = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name', limit=5)
            if test_basic.empty:
                raise Exception("stock_basic接口返回空数据")
            print("  ✅ stock_basic接口可用")
        except Exception as e:
            error_msg = str(e)
            if '权限' in error_msg or '积分' in error_msg:
                print(f"  ⚠️  Tushare权限不足: {error_msg[:80]}")
                print(f"  💡 请访问 https://tushare.pro 完成实名认证获取积分")
                raise Exception("Tushare权限不足，需要实名认证")
            else:
                raise
        
        print("  - 获取股票列表...")
        # 获取股票基本信息
        stock_list = pro.stock_basic(
            exchange='', 
            list_status='L', 
            fields='ts_code,symbol,name,area,industry,market,list_date'
        )
        
        if stock_list.empty:
            print("  ❌ 未获取到股票列表")
            return pd.DataFrame()
        
        print(f"  ✅ 获取到 {len(stock_list)} 只股票基本信息")
        
        print("  - 尝试获取每日指标数据（PE、PB、市值）...")
        # 测试daily_basic接口是否可用
        daily_basic_available = False
        try:
            test_daily = pro.daily_basic(trade_date=today, fields='ts_code,pe,pb', limit=5)
            if not test_daily.empty:
                daily_basic_available = True
                print("  ✅ daily_basic接口可用，可以获取PE、PB、市值等数据")
        except Exception as e:
            error_msg = str(e)
            if '权限' in error_msg or '积分' in error_msg:
                print(f"  ⚠️  daily_basic接口需要更高权限或积分")
                print(f"  💡 将只使用基础信息（代码和名称），PE、PB等数据将留空")
                print(f"  💡 完成实名认证后可获取完整数据，访问：https://tushare.pro")
            else:
                print(f"  ⚠️  daily_basic接口测试失败: {error_msg[:80]}")
        
        # 分批获取每日指标（包含PE、PB、市值）
        all_data = []
        batch_size = 500
        
        if daily_basic_available:
            for i in range(0, len(stock_list), batch_size):
                batch = stock_list.iloc[i:i+batch_size]
                ts_codes = ','.join(batch['ts_code'].tolist())
                
                try:
                    # 获取每日指标
                    daily_basic = pro.daily_basic(
                        trade_date=today,
                        ts_code=ts_codes,
                        fields='ts_code,pe,pb,ps,total_mv,circ_mv'
                    )
                    
                    # 合并数据
                    merged = batch.merge(daily_basic, on='ts_code', how='left')
                    all_data.append(merged)
                    
                    # 控制请求频率（Tushare有频率限制）
                    if (i + batch_size) % 1000 == 0:
                        print(f"  ⏳ 已处理 {i + batch_size}/{len(stock_list)} 只股票")
                        time.sleep(0.5)  # 每1000只股票等待0.5秒
                        
                except Exception as e:
                    error_msg = str(e)
                    if '权限' in error_msg or '积分' in error_msg:
                        print(f"  ⚠️  批次 {i//batch_size + 1} 权限不足，使用基础信息")
                        # 只保存基本信息
                        all_data.append(batch)
                        break  # 如果权限不足，不再尝试后续批次
                    else:
                        print(f"  ⚠️  批次 {i//batch_size + 1} 获取失败: {e}")
                        # 即使失败也保存基本信息
                        all_data.append(batch)
                        time.sleep(1)  # 失败后等待更长时间
        else:
            # 如果没有daily_basic权限，只使用基础信息
            print("  ℹ️  仅使用基础信息（无PE、PB、市值数据）")
            all_data = [stock_list]
        
        # 合并所有数据
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            
            # 映射字段名
            column_mapping = {
                'ts_code': 'ts_code',
                'symbol': 'code',
                'name': 'name',
                'industry': 'industry',
                'pe': 'pe',
                'pb': 'pb',
                'ps': 'ps',
                'total_mv': 'market_cap',  # 总市值（万元）
                'circ_mv': 'float_cap',     # 流通市值（万元）
            }
            
            # 重命名列
            result = result.rename(columns=column_mapping)
            
            # 转换市值单位（Tushare返回的是万元，转换为元）
            if 'market_cap' in result.columns:
                result['market_cap'] = result['market_cap'] * 10000
            if 'float_cap' in result.columns:
                result['float_cap'] = result['float_cap'] * 10000
            
            # 填充缺失字段（为了与AKShare格式一致）
            for col in ['price', 'change_pct', 'volume', 'turnover', 'pcf']:
                if col not in result.columns:
                    result[col] = None
            
            # 填充PE、PB等字段（如果权限不足可能为空）
            for col in ['pe', 'pb', 'ps', 'market_cap', 'float_cap']:
                if col not in result.columns:
                    result[col] = None
            
            print(f"  ✅ Tushare数据获取完成，共 {len(result)} 条记录")
            print(f"  📊 数据完整性：")
            
            # 检查数据完整性
            has_pe = result['pe'].notna().sum() if 'pe' in result.columns else 0
            has_pb = result['pb'].notna().sum() if 'pb' in result.columns else 0
            has_mv = result['market_cap'].notna().sum() if 'market_cap' in result.columns else 0
            
            print(f"     - 有PE数据: {has_pe} 只")
            print(f"     - 有PB数据: {has_pb} 只")
            print(f"     - 有市值数据: {has_mv} 只")
            
            if has_pe == 0 and has_pb == 0 and has_mv == 0:
                print(f"  ⚠️  警告：获取的数据不完整（只有代码和名称）")
                print(f"  💡 建议：登录 https://tushare.pro 完成实名认证以获取完整数据")
            
            return result
        else:
            return pd.DataFrame()
            
    except Exception as e:
        print(f"  ❌ Tushare获取数据失败: {e}")
        print(f"  💡 将使用AKShare作为备用...")
        raise


def init_database():
    """初始化数据库"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
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
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON stock_data(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON stock_data(name)")
    conn.commit()
    conn.close()

def save_to_database(df):
    """保存到数据库"""
    if df.empty:
        return
    conn = sqlite3.connect(str(DB_PATH))
    df.to_sql('stock_data', conn, if_exists='replace', index=False)
    conn.close()


if __name__ == "__main__":
    try:
        # 初始化数据库
        init_database()
        
        # 优先尝试使用Tushare（如果配置了Token）
        use_tushare = os.getenv('TUSHARE_ENABLED', 'false').lower() == 'true'
        
        if use_tushare:
            print("🔑 使用Tushare获取数据（完整财务指标）")
        else:
            print("📊 使用AKShare获取数据（免费，无需Token）")
        
        # 使用AKShare获取数据（免费，无需Token，无需实名认证）
        # 如果用户配置了Tushare且想使用，可以设置use_tushare=True
        df = fetch_cn_stock_basic(use_tushare=use_tushare)
        
        # 保存到CSV
        df.to_csv(OUT, index=False, encoding="utf-8-sig")  # 使用utf-8-sig确保Excel能正确打开
        print(f"✅ 已保存 {len(df)} 条记录到 {OUT.absolute()}")
        
        # 保存到数据库
        save_to_database(df)
        print(f"✅ 已保存 {len(df)} 条记录到数据库 {DB_PATH}")
        
        # 显示前几条数据
        print("\n📊 数据预览:")
        print(df.head(10).to_string(index=False))
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断下载")
        restore_proxy(saved_proxy_env)
        sys.exit(1)
    except Exception as e:
        restore_proxy(saved_proxy_env)
        print(f"\n❌ 执行失败: {e}")
        sys.exit(1)
    finally:
        # 确保恢复代理设置
        restore_proxy(saved_proxy_env)

