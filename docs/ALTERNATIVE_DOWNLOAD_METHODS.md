# A股数据下载备用方案

## 📋 问题说明

当 `stock_zh_a_spot_em()` 批量接口失败时（如代理问题、网络不稳定），数据中的PE、PB等财务指标会缺失。

## 🔄 备用方案

### 方案1: 逐只股票获取（推荐）

**优点**：
- ✅ 更可靠，单只股票请求不容易失败
- ✅ 可以获取到PE、PB、行业等完整信息
- ✅ 失败时只影响单只股票，不影响整体

**缺点**：
- ⚠️ 速度较慢（需要逐只请求）
- ⚠️ 有请求频率限制风险

**使用方法**：
```bash
python scripts/fetch_cn_stock_basic_individual.py
```

**特点**：
- 先处理前100只股票作为示例
- 如需全部数据，可以修改脚本中的`limit`参数
- 或分批处理（如每次处理1000只）

### 方案2: 使用Tushare（需要Token和实名认证）

**优点**：
- ✅ 数据更完整和准确
- ✅ 官方数据源，稳定性好
- ✅ 有历史数据支持

**缺点**：
- ⚠️ 需要注册账号并完成实名认证
- ⚠️ 免费账号有积分限制
- ⚠️ 部分接口需要积分

**配置方法**：
1. 访问 https://tushare.pro 注册账号
2. 完成实名认证
3. 获取Token并添加到`.env`文件：
   ```
   TUSHARE_TOKEN=你的token
   TUSHARE_ENABLED=true
   ```

### 方案3: 使用项目内的AKShareProvider

项目中已有 `tradingagents/dataflows/akshare_utils.py`，提供了：
- `get_financial_data(symbol)`: 获取单只股票的完整财务数据
- 包含主要财务指标（main_indicators），可以解析出PE、PB、ROE等

**示例代码**：
```python
from tradingagents.dataflows.akshare_utils import AKShareProvider

provider = AKShareProvider()
financial_data = provider.get_financial_data("000001")

main_indicators = financial_data.get('main_indicators')
# 从main_indicators中解析PE、PB等指标
```

### 方案4: 组合使用（推荐用于生产环境）

1. **优先使用批量接口**：`stock_zh_a_spot_em()` 快速获取大部分数据
2. **失败时降级**：对失败的股票使用逐只获取
3. **定期补全**：定期运行逐只获取脚本，补充缺失的数据

## 🚀 推荐工作流程

### 快速获取（每日更新）
```bash
# 使用批量接口（快，但可能不完整）
python scripts/fetch_cn_stock_basic_complete.py
```

### 完整获取（每周或每月）
```bash
# 使用逐只获取（慢，但完整）
python scripts/fetch_cn_stock_basic_individual.py
```

### 增量更新（推荐）
```bash
# 先批量获取所有股票的基础信息
python scripts/fetch_cn_stock_basic_complete.py

# 然后对缺失PE/PB的股票，使用逐只获取补充
python scripts/fetch_cn_stock_basic_individual.py  # 修改脚本，只处理PE/PB为空的股票
```

## 📝 注意事项

1. **请求频率**：逐只获取时，建议每只股票间隔0.5-1秒，避免被限流
2. **分批处理**：对于5000+只股票，建议分批处理（如每次1000只）
3. **错误处理**：单只股票失败不影响其他股票
4. **数据持久化**：及时保存已获取的数据，避免重复请求

## 💡 未来优化方向

1. **智能重试**：批量接口失败时，自动切换到逐只获取
2. **增量更新**：只更新缺失字段，不重复获取已有数据
3. **并发请求**：使用多线程/异步，提高逐只获取的速度
4. **缓存机制**：缓存已获取的数据，避免重复请求

