# 数据下载系统升级说明

## 🎯 问题背景

之前系统有多个数据下载链接，但每个链接下载的数据都不够完整，缺少关键财务指标（PE、PB、PS、市值等）。

## ✅ 解决方案

已升级到新的**data_engine**架构，提供完整的数据下载和存储能力。

## 🔧 技术架构

### 新旧系统对比

| 特性 | 旧系统 | 新系统(data_engine) |
|------|--------|---------------------|
| 数据源 | 分散在scripts/ | 统一在data_engine/ |
| 数据库 | a_share_basic.db | stock_database.db |
| 表结构 | stock_data单表 | 多表规范设计 |
| 财务指标 | 经常缺失 | ✅ 完整(PE/PB/PS) |
| 历史数据 | 无 | ✅ 3年K线 |
| 技术指标 | 无 | ✅ MA/RSI/MACD |
| Upsert | 简单append | ✅ 真正的upsert |
| 增量更新 | 否 | ✅ 支持 |

### 数据库设计

```
stock_basic_info         # 基础信息
├── ts_code, name, area, industry, market

stock_market_daily       # 日K线 + 财务指标
├── open, high, low, close, volume, amount
├── peTTM, pbMRQ, psTTM (PE/PB/PS)
└── trade_date

stock_financials         # 财务数据
├── pe, pb, ps, roe, roa
└── total_mv, circ_mv

stock_technical_indicators # 技术指标
├── ma5, ma20, ma60
├── rsi, macd, kdj
└── atr, volatility
```

## 📝 使用方法

### 方式1：通过Streamlit UI（推荐）

1. 访问 http://localhost:8501
2. 点击侧边栏「Data Center」
3. 选择数据源：
   - **Tushare（推荐）**：数据最完整，需要Token
   - **BaoStock**：免费，数据完整可靠
4. 点击「🚀 下载/更新 A股基础资料」
5. 等待下载完成

### 方式2：命令行执行

```bash
cd TradingAgents-CN
source env/bin/activate

# 使用SQLite（默认）
python3 -m data_engine.update_all

# 使用MySQL
export DB_TYPE='mysql'
python3 -m data_engine.update_all
```

## 🎁 新功能

### 1. 完整财务数据
- ✅ PE (市盈率) - peTTM
- ✅ PB (市净率) - pbMRQ  
- ✅ PS (市销率) - psTTM
- ✅ ROE, ROA, EPS, BPS

### 2. 历史K线数据
- ✅ 默认下载最近3年
- ✅ 每日开高低收、成交量、成交额
- ✅ 涨跌幅、换手率、振幅

### 3. 技术指标自动计算
- ✅ 移动平均线 (MA5/20/60)
- ✅ RSI、MACD、KDJ
- ✅ ATR、波动率

### 4. 智能Upsert
- MySQL: REPLACE INTO（批量）
- SQLite: DELETE+INSERT（事务）
- 自动去重，支持增量更新

## 📊 数据流程

```
UI选择数据源
    ↓
data_engine/update_all.py
    ↓
fetch_data.py (下载)
    ↓
compute_indicators.py (计算指标)
    ↓
stock_database.db (保存)
    ↓
UI读取并显示
```

## 🔍 数据验证

下载完成后，可以在UI中看到：

```
✅ 总记录数: 5673
✅ 股票代码数: 5670
✅ 平均价格: 实际值（不再是N/A）
✅ 总市值: 实际值（不再是0.00万亿）
✅ PE数据: ✓完整
✅ PB数据: ✓完整
```

## ⚙️ 配置说明

### 环境变量

```bash
# .env文件
DB_TYPE=sqlite  # 或 mysql
STOCK_DB_URL=mysql+pymysql://root:password@localhost:3306/stock_db?charset=utf8mb4
TUSHARE_TOKEN=your_token_here

# 数据源开关
USE_BAOSTOCK=true
USE_AKSHARE=true
USE_TUSHARE=false
```

### 修改数据源

编辑 `data_engine/config.py`:

```python
# 切换数据源
USE_BAOSTOCK = True  # 推荐：免费且稳定
USE_TUSHARE = False  # 需要Token和权限
USE_AKSHARE = True   # 备用

# 修改抓取窗口
START_DATE = "2022-01-01"  # 3年前
END_DATE = "2025-01-01"    # 今天

# 速率控制
SLEEP_SEC_WEB = 0.2  # BaoStock请求间隔
SLEEP_SEC_TUSHARE = 0.35  # Tushare请求间隔
```

## 🐛 故障排除

### 问题1：PE/PB数据为空

**原因**: Tushare权限不足  
**解决**: 
- 检查Tushare Token是否有效
- 切换到BaoStock（推荐）
- 确保网络连接稳定

### 问题2：UNIQUE constraint failed

**原因**: 数据库upsert失败  
**解决**: 
- 已自动修复，使用真正的upsert
- 删除旧数据库重新下载

### 问题3：下载速度慢

**原因**: 数据量大  
**解决**: 
- 首次下载需要时间（3年数据）
- 后续增量更新很快
- 可以修改config.py限制股票数量

## 📚 相关文件

```
TradingAgents-CN/
├── data_engine/
│   ├── config.py              # 配置
│   ├── fetch_data.py          # 数据下载
│   ├── compute_indicators.py  # 指标计算
│   ├── update_all.py          # 主入口
│   ├── db_init.sql            # MySQL建表
│   └── utils/
│       ├── db_utils.py        # 数据库工具
│       ├── logger.py          # 日志
│       └── retry.py           # 重试
├── web/pages/
│   └── 10_Data_Center.py      # UI界面
└── data/
    └── stock_database.db      # 数据库
```

## ✅ 测试验证

```bash
# 测试upsert功能
cd TradingAgents-CN
source env/bin/activate
python3 -c "
from data_engine.utils.db_utils import get_engine, upsert_df
import pandas as pd

engine = get_engine('sqlite:///test.db')
test_df = pd.DataFrame({
    'ts_code': ['000001.SZ'],
    'trade_date': ['2024-01-01'],
    'close': [10.5]
})
result = upsert_df(test_df, 'stock_market_daily', engine)
print(f'✅ Upsert成功: {result}行')
"
```

## 🎉 总结

新系统完全解决了之前数据不完整的问题：

- ✅ **统一架构**: 一个data_engine替代多个分散脚本
- ✅ **完整数据**: PE/PB/PS/市值等财务指标齐全
- ✅ **历史数据**: 3年K线数据支持技术分析
- ✅ **增量更新**: 智能upsert，高效更新
- ✅ **多数据源**: Tushare/BaoStock/AKShare自动切换
- ✅ **MySQL支持**: 适合生产环境

现在可以放心使用系统进行股票数据分析和选股了！
