# 🚫 API频率限制处理完整指南

## 问题说明

当使用数据源API（特别是Tushare、Yahoo Finance等）时，可能会遇到频率限制错误：

```
Too Many Requests. Rate limited. Try after a while.
```

这表示API请求过于频繁，触发了服务商的限流机制。

## ✅ 已实现的解决方案

### 1. 自动重试机制

**实现位置**: `tradingagents/dataflows/data_downloader.py`

```python
# 重试逻辑
max_retries = 3
for attempt in range(max_retries):
    try:
        df = self.pro.daily(ts_code=code, start_date=start, end_date=end)
        break  # 成功则退出
    except Exception as e:
        if "Too Many Requests" in str(e) or "Rate limited" in str(e):
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)  # 2秒、4秒、6秒
                time.sleep(wait_time)
                continue
        else:
            # 其他错误，直接退出
            break
```

**特性**:
- ✅ 最多重试3次
- ✅ 指数退避：等待时间递增（2秒 → 4秒 → 6秒）
- ✅ 自动识别频率限制错误
- ✅ 智能跳过其他类型的错误

### 2. 请求频率控制

**基础间隔**:
```python
time.sleep(0.3)  # Tushare推荐至少0.2秒间隔
```

**批量处理**:
```python
# 分批下载，每批500只股票
batch_size = 500
for i in range(0, len(code_list), batch_size):
    batch = code_list[i:i+batch_size]
    for code in batch:
        # 处理每只股票
        time.sleep(0.3)  # 每只股票间隔
```

### 3. 缓存机制

**本地缓存**:
```python
# 优先使用缓存
cache_file = f"{code}_{start_date}_{end_date}.parquet"
if cache_file.exists():
    df = load_from_cache(cache_file)
    return df
```

**主数据文件**:
```python
# 使用Parquet格式存储
# 自动检测已有数据，只下载缺失部分
```

## 📊 各数据源限制

### Tushare

**限制**:
- 免费用户：每分钟约60次
- 积分要求：部分高级接口
- 建议间隔：≥0.2秒

**配置**:
```python
# 在使用Tushare前设置
export TUSHARE_TOKEN=your_token
```

### AKShare

**限制**:
- 相对宽松
- 无官方限制（但建议间隔≥0.5秒）
- 依赖目标网站限制

### Yahoo Finance (yfinance)

**限制**:
- 非官方限制
- 通常每分钟100-200次
- 建议间隔：≥0.1秒

## 🔧 使用方法

### 方式1：使用DataDownloader（推荐）

```python
from tradingagents.dataflows.data_downloader import DataDownloader

downloader = DataDownloader(provider="tushare")

# 自动处理频率限制
df = downloader.get_stock_data("600519.SH", "20200101", "20251030")
```

### 方式2：手动处理

```python
import time
from tradingagents.dataflows.tushare_adapter import get_tushare_adapter

adapter = get_tushare_adapter()
pro = adapter.provider.pro_api

for code in stock_list:
    try:
        df = pro.daily(ts_code=code)
        time.sleep(0.3)  # 手动控制间隔
    except Exception as e:
        if "Too Many Requests" in str(e):
            time.sleep(5)  # 等待后重试
            continue
```

## 💡 最佳实践

### 1. 批量处理

```python
# ✅ 推荐：批量下载
downloader.update_daily(code_list=["600519.SH", "000001.SZ"])

# ❌ 不推荐：逐个请求
for code in code_list:
    downloader.get_stock_data(code)  # 频繁调用
```

### 2. 使用缓存

```python
# ✅ 推荐：检查缓存
if cache.exists():
    return load_from_cache()

# ✅ 推荐：增量更新
existing_data = load_existing()
latest_date = existing_data.max()
start_date = latest_date + 1 day  # 只下载新数据
```

### 3. 合理规划

```python
# ✅ 推荐：错峰处理
# 避免在API负载高峰时大量请求
# 建议：上午9-11点、下午2-3点

# ✅ 推荐：分批处理
batch_size = 100  # 小批次
for batch in batches:
    process_batch(batch)
    time.sleep(10)  # 批次间休息
```

## 🚨 遇到频率限制时的处理

### 立即操作

1. **系统自动重试**：等待最多18秒（2+4+6秒）
2. **检查日志**：查看详细错误信息
3. **等待再试**：如果自动重试失败，等待1-5分钟

### 长期解决方案

1. **升级账户**：
   - Tushare：购买积分或升级会员
   - 其他平台：升级到付费账户

2. **优化代码**：
   ```python
   # 减少不必要的请求
   # 优先使用缓存
   # 批量处理
   ```

3. **使用备用数据源**：
   ```python
   # AKShare作为备用
   if tushare_fails:
       use_akshare()
   ```

## 📝 监控和调试

### 检查请求频率

```python
import time
from datetime import datetime

last_call_time = {}
min_interval = 0.3

def call_with_tracking():
    now = time.time()
    if now - last_call_time < min_interval:
        wait = min_interval - (now - last_call_time)
        time.sleep(wait)
    last_call_time = time.time()
    # 执行API调用
```

### 日志分析

```python
# 查看频率限制频率
grep "频率限制" logs/app.log | wc -l

# 检查请求间隔
grep "API调用" logs/app.log | tail -20
```

## ⚠️ 注意事项

1. **不要过度依赖重试**：
   - 如果连续3次都失败，停止请求
   - 等待更长时间后手动重试

2. **遵守服务条款**：
   - 不要使用爬虫暴力抓取
   - 遵守API使用规范

3. **监控账户状态**：
   - 定期检查API配额
   - 避免超出限制

## 🔗 相关文档

- [数据管理文档](A_SHARE_DATA.md)
- [故障排除指南](troubleshooting/rate_limit_handling.md)
- [Tushare使用指南](TUSHARE_USAGE_GUIDE.md)

---

**遇到频率限制是正常的，系统已自动处理！** 🎉

