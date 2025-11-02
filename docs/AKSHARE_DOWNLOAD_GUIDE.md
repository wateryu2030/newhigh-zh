# AKShare下载方案（无需Token和实名认证）

## 📋 概述

按照ChatGPT推荐的方案，我们已经优化了A股基础数据下载功能。**现在默认使用AKShare，完全免费，无需Token和实名认证**。

## ✅ 核心改进

### 1. 指数退避重试机制
使用`retry_call`函数，重试间隔按指数增长：
- 第1次重试：1.5秒
- 第2次重试：3秒
- 第3次重试：6秒
- 第4次重试：12秒
- 第5次重试：24秒
- 第6次重试：48秒

这能**大幅减少RemoteDisconnected错误的影响**。

### 2. 彻底清除代理环境变量
在下载前自动清除所有代理相关环境变量：
- `HTTP_PROXY`, `http_proxy`
- `HTTPS_PROXY`, `https_proxy`
- `ALL_PROXY`, `all_proxy`
- `NO_PROXY`, `no_proxy`

防止代理导致的连接中断。

### 3. 默认使用AKShare
- **免费**：无需注册账号
- **无需Token**：不需要API密钥
- **无需实名认证**：可以直接使用
- **数据稳定**：提供A股代码、名称、价格、市值等信息

### 4. 智能降级机制
如果AKShare的实时数据接口失败，会自动降级到只获取基础信息（代码和名称），确保至少能获取到基本信息。

## 🚀 使用方式

### 方式1：Web界面（推荐）
1. 打开Web应用
2. 进入"数据中心 - 基础资料"页面
3. 点击"下载/更新 A股基础资料"按钮
4. 系统会自动使用AKShare下载数据

### 方式2：命令行
```bash
cd /Users/apple/Ahope/Amarket/TradingAgents-CN
python scripts/fetch_cn_stock_basic.py
```

默认使用AKShare，无需任何配置。

### 方式3：Python代码
```python
from scripts.fetch_cn_stock_basic import fetch_cn_stock_basic

# 使用AKShare（默认，推荐）
df = fetch_cn_stock_basic(use_tushare=False)

# 如果想使用Tushare（需要Token和实名认证）
# df = fetch_cn_stock_basic(use_tushare=True)
```

## 📊 获取的数据

使用AKShare可以获取：
- ✅ 股票代码（`symbol`）
- ✅ 股票名称（`name`）
- ✅ 最新价格（`close`）
- ✅ 总市值（`total_mv`）
- ✅ 流通市值（`circ_mv`）
- ✅ 涨跌幅（`change_pct`）
- ✅ 成交量（`volume`）
- ✅ 成交额（`amount`）

**注意**：部分详细财务指标（如PE、PB、ROE等）可能不如Tushare完整，但对于基础使用已经足够。

## 🔧 错误处理

### 网络错误
如果遇到网络连接错误：
1. 系统会自动重试（最多6次）
2. 使用指数退避，减少服务器压力
3. 如果实时数据失败，会降级到基础信息

### 代理问题
系统会自动：
1. 清除代理环境变量
2. 修改`requests`库配置，强制不使用代理
3. 设置更真实的浏览器请求头

## 💡 优势对比

| 特性 | AKShare（新方案） | Tushare |
|------|------------------|---------|
| 是否需要注册 | ❌ 不需要 | ✅ 需要 |
| 是否需要Token | ❌ 不需要 | ✅ 需要 |
| 是否需要实名认证 | ❌ 不需要 | ✅ 需要 |
| 费用 | ✅ 免费 | ⚠️ 部分接口需要积分 |
| 数据完整性 | ⚠️ 良好 | ✅ 更完整 |
| 稳定性 | ✅ 稳定 | ✅ 稳定 |
| 推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 📝 技术细节

### 重试机制实现
```python
def retry_call(func, retries=6, backoff=1.5, allowed_exceptions=(Exception,), func_name="未知函数"):
    """重试包装函数，使用指数退避"""
    for attempt in range(retries):
        try:
            return func()
        except allowed_exceptions as e:
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)  # 指数退避
                time.sleep(wait)
            else:
                raise
```

### 代理清除
```python
# 清除环境变量
proxy_vars = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', ...]
for var in proxy_vars:
    os.environ.pop(var, None)

# 修改requests库配置
requests.Session.request = no_proxy_request
requests.get = patched_get
requests.post = patched_post
```

## 🎯 总结

**新的AKShare方案完全满足"无需实名认证"的需求**，提供了：
- ✅ 稳定的数据下载
- ✅ 强大的错误恢复能力
- ✅ 完全免费使用
- ✅ 无需任何配置

如果后续需要更完整的数据（如详细的财务指标），可以考虑配置Tushare，但AKShare已经足够日常使用了。

