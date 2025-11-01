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


def fetch_cn_stock_basic(use_tushare: bool = True) -> pd.DataFrame:
    """
    获取A股股票基本信息
    
    Args:
        use_tushare: 是否优先使用Tushare（需要配置TUSHARE_TOKEN）
    
    Returns:
        pd.DataFrame: 包含股票代码、名称、最新价、市值等信息
    """
    print("📥 开始拉取A股基础资料...")
    
    # 方法1：尝试使用Tushare（如果配置了Token）
    if use_tushare:
        try:
            from tradingagents.dataflows.tushare_adapter import get_tushare_adapter
            adapter = get_tushare_adapter()
            
            if adapter.provider and adapter.provider.connected:
                print("  ✅ 检测到Tushare配置，使用Tushare获取完整数据...")
                return _fetch_with_tushare(adapter)
            else:
                print("  ⚠️  Tushare未配置或连接失败，使用AKShare作为备用...")
        except Exception as e:
            print(f"  ⚠️  Tushare初始化失败: {e}")
            print("  💡 使用AKShare作为备用数据源...")
    
    # 方法2：使用AKShare（备用方案）
    print("  📊 使用AKShare获取数据...")
    
    # 更彻底的代理禁用（修改requests和urllib3的全局配置）
    def setup_no_proxy_requests():
        """设置requests库不使用代理"""
        try:
            import requests
            import urllib3
            
            # 1. 禁用环境变量中的代理
            disable_proxy()
            
            # 2. 禁用urllib3的代理检测
            try:
                urllib3.disable_warnings()
                # 设置urllib3不使用系统代理
                urllib3.util.connection.HAS_IPV6 = False  # 避免某些代理检测
            except:
                pass
            
            # 3. 修改requests.Session的request方法（最核心的方法）
            original_request = requests.Session.request
            def no_proxy_request(self, method, url, **kwargs):
                # 强制设置不使用代理
                kwargs['proxies'] = {'http': None, 'https': None}
                
                # 添加更真实的浏览器请求头，避免被识别为爬虫
                if 'headers' not in kwargs or kwargs['headers'] is None:
                    kwargs['headers'] = {}
                
                headers = kwargs['headers']
                if 'User-Agent' not in headers or not headers.get('User-Agent'):
                    headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                if 'Accept' not in headers:
                    headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                if 'Accept-Language' not in headers:
                    headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
                if 'Accept-Encoding' not in headers:
                    headers['Accept-Encoding'] = 'gzip, deflate, br'
                if 'Connection' not in headers:
                    headers['Connection'] = 'close'  # 每次请求后关闭连接，避免连接复用问题
                if 'Upgrade-Insecure-Requests' not in headers:
                    headers['Upgrade-Insecure-Requests'] = '1'
                
                # 增加超时时间（对于大数据量请求）
                if 'timeout' not in kwargs or kwargs.get('timeout') is None:
                    kwargs['timeout'] = (10, 120)  # (连接超时, 读取超时) 秒
                
                return original_request(self, method, url, **kwargs)
            
            requests.Session.request = no_proxy_request
            
            # 4. 修改requests.get/post等快捷方法（它们也会创建Session）
            original_get = requests.get
            original_post = requests.post
            
            def patched_get(url, **kwargs):
                kwargs['proxies'] = {'http': None, 'https': None}
                # 注意：trust_env只对Session有效，不是request的参数
                return original_get(url, **kwargs)
            
            def patched_post(url, **kwargs):
                kwargs['proxies'] = {'http': None, 'https': None}
                return original_post(url, **kwargs)
            
            requests.get = patched_get
            requests.post = patched_post
            
            # 5. 修改Session的默认配置
            original_init = requests.Session.__init__
            def new_init(self, *args, **kwargs):
                # 先正常初始化
                original_init(self, *args, **kwargs)
                # 然后设置属性（而不是通过参数）
                if hasattr(self, 'trust_env'):
                    self.trust_env = False
                # 设置默认proxies
                self.proxies = {'http': None, 'https': None}
            
            requests.Session.__init__ = new_init
            
            return True
        except Exception as e:
            print(f"  ⚠️ 设置无代理模式失败: {e}")
            return False
    
    # 重试装饰器
    def retry_on_error(func, max_retries=5, initial_delay=2):
        """重试机制（自动处理网络错误）"""
        # 设置无代理模式
        setup_no_proxy_requests()
        
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                result = func()
                return result
            except Exception as e:
                error_msg = str(e).lower()
                error_type = type(e).__name__
                
                # 判断是否是可重试的错误
                is_retryable = (
                    "connection" in error_msg or
                    "disconnected" in error_msg or
                    "aborted" in error_msg or
                    "timeout" in error_msg or
                    "proxy" in error_msg or
                    "连接" in error_msg or
                    "RemoteDisconnected" in error_type or
                    "ConnectionError" in error_type or
                    "ProtocolError" in error_type
                )
                
                if attempt < max_retries - 1 and is_retryable:
                    # 根据错误类型显示不同的消息
                    if "disconnected" in error_msg or "aborted" in error_msg:
                        print(f"  ⚠️ 第 {attempt + 1}/{max_retries} 次尝试失败（连接中断）: {str(e)[:80]}")
                        print(f"  💡 可能是数据源服务器临时关闭连接，或网络不稳定")
                    elif "timeout" in error_msg:
                        print(f"  ⚠️ 第 {attempt + 1}/{max_retries} 次尝试失败（请求超时）: {str(e)[:80]}")
                    elif "proxy" in error_msg:
                        print(f"  ⚠️ 第 {attempt + 1}/{max_retries} 次尝试失败（代理问题）: {str(e)[:80]}")
                        disable_proxy()
                        setup_no_proxy_requests()
                    else:
                        print(f"  ⚠️ 第 {attempt + 1}/{max_retries} 次尝试失败（网络问题）: {str(e)[:80]}")
                    
                    # 指数退避：2秒、4秒、8秒、16秒、32秒
                    print(f"  🔄 等待 {delay} 秒后重试...")
                    time.sleep(delay)
                    delay = min(delay * 2, 32)  # 最大延迟32秒
                    
                    # 对于连接中断，增加额外等待
                    if "disconnected" in error_msg or "aborted" in error_msg:
                        print(f"  💤 连接中断，额外等待 3 秒...")
                        time.sleep(3)
                else:
                    # 最后一次尝试失败，或者不可重试的错误
                    if not is_retryable:
                        print(f"  ❌ 遇到不可重试的错误: {error_type}")
                    raise
    
    try:
        # 获取股票代码与名称（带重试，最多5次）
        print("  - 获取股票代码与名称...")
        code_name = retry_on_error(
            lambda: ak.stock_info_a_code_name(),
            max_retries=5,
            initial_delay=2
        )
        print(f"  ✅ 获取到 {len(code_name)} 条股票代码")
        
        # 在两次API调用之间添加延迟，避免请求过快
        print("  - 等待 5 秒后获取实时数据（避免请求过快，给服务器缓冲时间）...")
        time.sleep(5)
        
        # 获取实时股票信息，包括最新价、市值等（带重试，最多5次）
        # 如果这个接口持续失败，会使用降级方案
        print("  - 获取实时股票信息（包含价格、市值等）...")
        print("  ⚠️  注意：此接口需要获取所有A股实时数据，可能需要较长时间...")
        
        spot = None
        try:
            spot = retry_on_error(
                lambda: ak.stock_zh_a_spot_em(),
                max_retries=5,
                initial_delay=5  # 对于大数据量请求，初始延迟更长
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
        
        # 字段清洗，重命名
        keep = {
            "code": "code",
            "name": "name",
            "最新价": "price",
            "总市值": "market_cap",
            "流通市值": "float_cap",
            "市盈率": "pe",
            "市净率": "pb",
            "市销率": "ps",
            "市现率": "pcf",
            "涨跌幅": "change_pct",
            "成交量": "volume",
            "成交额": "turnover",
        }
        
        # 确保所需的列存在
        available_columns = df.columns.tolist()
        rename_dict = {}
        for old_col, new_col in keep.items():
            if old_col in available_columns:
                rename_dict[old_col] = new_col
            elif new_col in available_columns:
                # 如果已经是目标名称，跳过
                pass
        
        df = df.rename(columns=rename_dict)
        
        # 如果使用了降级方案，确保所有期望的列都存在（即使为空）
        for col in keep.values():
            if col not in df.columns:
                df[col] = None
                print(f"  ℹ️  添加空列: {col}（降级方案）")
        
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
        columns_to_keep = [col for col in keep.values() if col in df.columns]
        df = df[columns_to_keep]
        
        # 数据清洗
        df = df.dropna(subset=["code", "name"]).drop_duplicates(subset=["code"])
        
        # 数值列转换
        numeric_columns = ["price", "market_cap", "float_cap"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
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
        
        pro = adapter.provider.pro_api
        today = datetime.now().strftime('%Y%m%d')
        
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
        
        print("  - 获取每日指标数据（PE、PB、市值）...")
        # 分批获取每日指标（包含PE、PB、市值）
        all_data = []
        batch_size = 500
        today = datetime.now().strftime('%Y%m%d')
        
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
                print(f"  ⚠️  批次 {i//batch_size + 1} 获取失败: {e}")
                # 即使失败也保存基本信息
                all_data.append(batch)
                time.sleep(1)  # 失败后等待更长时间
        
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
            
            print(f"  ✅ Tushare数据获取完成，共 {len(result)} 条记录")
            print(f"  📊 数据完整性：")
            print(f"     - 有PE数据: {result['pe'].notna().sum()} 只")
            print(f"     - 有PB数据: {result['pb'].notna().sum()} 只")
            print(f"     - 有市值数据: {result['market_cap'].notna().sum()} 只")
            
            return result
        else:
            return pd.DataFrame()
            
    except Exception as e:
        print(f"  ❌ Tushare获取数据失败: {e}")
        print(f"  💡 将使用AKShare作为备用...")
        raise


if __name__ == "__main__":
    try:
        # 尝试使用Tushare，如果失败则使用AKShare
        df = fetch_cn_stock_basic(use_tushare=True)
        
        # 保存到CSV
        df.to_csv(OUT, index=False, encoding="utf-8-sig")  # 使用utf-8-sig确保Excel能正确打开
        print(f"✅ 已保存 {len(df)} 条记录到 {OUT.absolute()}")
        
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

