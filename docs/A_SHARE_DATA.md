# A股基础数据管理文档

## 📋 功能概述

系统支持批量下载和本地存储所有A股的基础信息，包括：
- 股票代码、名称
- 所属行业、地区、市场
- 市盈率(PE)、市净率(PB)
- 总市值、流通市值
- 上市日期

## 🔧 使用方法

### 1. 下载数据

#### 方法1：命令行脚本
```bash
python scripts/download_a_share_data.py
```

#### 方法2：Web界面
1. 访问"🔎 股票搜索"页面
2. 在侧边栏点击"🔄 更新股票数据"
3. 等待下载完成

### 2. 搜索股票

#### Python API
```python
from tradingagents.dataflows.stock_search import get_searcher

searcher = get_searcher()

# 关键字搜索
result = searcher.search(keyword="平安", limit=100)

# 行业筛选
result = searcher.search(industry="银行", max_pe=10)

# 组合条件
result = searcher.search(
    keyword="科技",
    min_market_cap=100,  # 最小市值100亿元
    max_pe=30,
    max_pb=5
)

# 获取单只股票信息
info = searcher.get_info("000001")
```

#### Web界面
在"🔎 股票搜索"页面使用筛选条件搜索

### 3. 数据存储位置

- **数据库文件**: `data/a_share_basic.db` (SQLite)
- **表名**: `stock_basic`
- **字段**:
  - `ts_code`: Tushare代码
  - `symbol`: 股票代码（如000001）
  - `name`: 股票名称
  - `industry`: 所属行业
  - `pe`: 市盈率
  - `pb`: 市净率
  - `total_mv`: 总市值（元）
  - `circ_mv`: 流通市值（元）
  - `update_time`: 更新时间

## 🔄 定期更新

### 手动更新
每次运行下载脚本或点击Web界面的"更新股票数据"按钮

### 自动化更新（建议）

可以设置定时任务（crontab）每天更新：

```bash
# 编辑crontab
crontab -e

# 添加每天收盘后更新（18:00）
0 18 * * 1-5 cd /path/to/TradingAgents-CN && source env/bin/activate && python scripts/download_a_share_data.py >> logs/a_share_update.log 2>&1
```

## 📊 数据统计

下载完成后，可以查看：
- 总股票数量
- 有PE/PB数据的股票数
- 行业数量
- 数据更新时间

## 💡 使用场景

### 1. 智能选股
在"🔍 智能选股"页面，系统会自动从数据库获取行业信息，无需手动上传行业CSV

### 2. 股票筛选
根据市值、PE、PB等条件筛选符合投资策略的股票池

### 3. 批量分析
获取股票列表后，可以批量进行技术分析和基本面分析

## ⚠️ 注意事项

1. **首次使用**：需要先运行下载脚本获取数据
2. **数据更新**：建议每天收盘后更新一次，确保数据新鲜
3. **API限制**：Tushare有请求频率限制，批量下载可能需要较长时间
4. **备用数据源**：如果Tushare不可用，系统会自动尝试使用AKShare

## 🔍 搜索示例

```python
# 搜索银行股，PE<10
banks = searcher.search(industry="银行", max_pe=10)

# 搜索市值>500亿的科技股
tech_large = searcher.search(
    industry="科技",
    min_market_cap=500
)

# 搜索所有行业
industries = searcher.get_industry_list()
```

## 📈 性能优化

- 数据库使用索引加速查询（symbol, name, industry）
- 支持模糊搜索（LIKE查询）
- 可设置返回数量限制（limit参数）

