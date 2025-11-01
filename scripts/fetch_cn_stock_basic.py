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


def fetch_cn_stock_basic() -> pd.DataFrame:
    """
    获取A股股票基本信息
    
    Returns:
        pd.DataFrame: 包含股票代码、名称、最新价、市值等信息
    """
    print("📥 开始拉取A股基础资料...")
    
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
                # 注意：不设置trust_env，因为Session.request()不接受这个参数
                # trust_env只在Session初始化时设置
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
    def retry_on_error(func, max_retries=3, delay=2):
        """重试机制（自动处理代理错误）"""
        # 设置无代理模式
        setup_no_proxy_requests()
        
        for attempt in range(max_retries):
            try:
                result = func()
                return result
            except Exception as e:
                error_msg = str(e).lower()
                if attempt < max_retries - 1:
                    if "proxy" in error_msg or "连接" in error_msg or "disconnected" in error_msg:
                        print(f"  ⚠️ 第 {attempt + 1} 次尝试失败（代理/网络问题）: {str(e)[:100]}")
                        print(f"  🔄 {delay} 秒后重试（已禁用代理）...")
                        # 再次确保代理已禁用
                        disable_proxy()
                        setup_no_proxy_requests()
                    else:
                        print(f"  ⚠️ 第 {attempt + 1} 次尝试失败: {str(e)[:100]}")
                        print(f"  🔄 {delay} 秒后重试...")
                    time.sleep(delay)
                    delay *= 2  # 指数退避
                else:
                    raise
    
    try:
        # 获取股票代码与名称（带重试）
        print("  - 获取股票代码与名称...")
        code_name = retry_on_error(
            lambda: ak.stock_info_a_code_name(),
            max_retries=3,
            delay=2
        )
        print(f"  ✅ 获取到 {len(code_name)} 条股票代码")
        
        # 获取实时股票信息，包括最新价、市值等（带重试）
        print("  - 获取实时股票信息...")
        spot = retry_on_error(
            lambda: ak.stock_zh_a_spot_em(),
            max_retries=3,
            delay=2
        )
        print(f"  ✅ 获取到 {len(spot)} 条实时信息")
        
        # 合并数据
        print("  - 合并数据...")
        df = code_name.merge(
            spot, 
            left_on="code", 
            right_on="代码", 
            how="left"
        )
        
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
        print(f"❌ 网络连接错误: {e}")
        print("💡 建议:")
        print("  1. 检查网络连接")
        print("  2. 检查是否需要代理/VPN")
        print("  3. 稍后重试（可能是数据源服务器临时不可用）")
        import traceback
        traceback.print_exc()
        raise
    except Exception as e:
        error_msg = str(e)
        if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            print(f"❌ 网络连接错误: {e}")
            print("💡 建议:")
            print("  1. 检查网络连接是否稳定")
            print("  2. 检查防火墙/代理设置")
            print("  3. 稍后重试（可能是数据源服务器繁忙）")
        elif "rate limit" in error_msg.lower() or "频率" in error_msg:
            print(f"❌ 请求频率过高: {e}")
            print("💡 建议:")
            print("  1. 等待一段时间后重试")
            print("  2. 数据源可能有访问频率限制")
        else:
            print(f"❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        df = fetch_cn_stock_basic()
        
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

