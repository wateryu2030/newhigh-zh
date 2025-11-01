# 📖 一体化智能交易使用指南

本文档介绍如何使用新增的一体化智能交易系统。

## 🎯 系统概述

一体化智能交易系统实现了完整的"数据→特征→选股→回测"闭环：

```
数据下载 (DataDownloader)
    ↓
特征工程 (ml_features)
    ↓
ML选股 (SmartSelector)
    ↓
策略信号 (backtest_strategy)
    ↓
回测执行 (BacktestEngine)
    ↓
报告生成 (BacktestReport)
```

## 📦 安装依赖

```bash
# 安装新依赖
pip install scikit-learn pyarrow joblib

# 或重新安装所有依赖
pip install -r requirements.txt
```

## 🚀 快速开始

### 方式1：使用一体化脚本（推荐）

```bash
# 基础用法
python scripts/smart_trading.py \
  --symbols 600519.SH 000001.SZ \
  --start 2020-01-01 \
  --end 2025-10-30

# 使用AKShare数据源
python scripts/smart_trading.py \
  --symbols 600519.SH \
  --start 2020-01-01 \
  --end 2025-10-30 \
  --provider akshare

# 快速模式（不训练ML模型）
python scripts/smart_trading.py \
  --symbols 600519.SH \
  --start 2020-01-01 \
  --end 2025-10-30 \
  --no-train-ml

# 使用ML策略回测
python scripts/smart_trading.py \
  --symbols 600519.SH \
  --start 2020-01-01 \
  --end 2025-10-30 \
  --strategy ml
```

### 方式2：Python API调用

```python
from scripts.smart_trading import run_smart_trading

# 运行完整流程
run_smart_trading(
    symbols=["600519.SH", "000001.SZ"],
    start_date="2020-01-01",
    end_date="2025-10-30",
    provider="tushare",
    train_ml=True,
    strategy_type="ma"
)
```

## 📂 输出文件

运行后会在 `runs/<run_id>/` 目录下生成：

```
runs/20251029_123456/
├── meta.json                    # 运行元数据
├── 600519_SH_features.parquet   # 特征数据
├── scores_today.csv             # 选股评分
├── scores_all.parquet           # 所有回测结果
└── ml_model.pkl                 # 训练好的ML模型（如果训练）
```

## 🔧 模块化使用

### 1. 数据下载

```python
from tradingagents.dataflows.data_downloader import DataDownloader

# 初始化下载器
downloader = DataDownloader(
    save_path="data/stock_daily.parquet",
    provider="tushare"
)

# 更新所有股票数据（增量）
downloader.update_daily()

# 获取单只股票数据
df = downloader.get_stock_data("600519.SH", "20200101", "20251030")

# 检查数据完整性
report = downloader.check_data_completeness()
```

### 2. 特征工程

```python
from tradingagents.models.ml_features import extract_features, select_features

# 提取特征
features_df = extract_features(price_df)

# 选择特征列
feature_cols = select_features(features_df)

# 特征归一化
normalized_features = normalize_features(feature_cols)
```

### 3. ML选股

```python
from tradingagents.models.ml_selector import SmartSelector

# 初始化模型
selector = SmartSelector(
    model_type="classifier",
    n_estimators=100,
    model_path="models/ml_selector.pkl"
)

# 训练模型
metrics = selector.train(train_features, train_labels)
print(metrics)  # {'test_accuracy': 0.65, 'test_f1': 0.68, ...}

# 预测股票收益概率
predictions = selector.predict_stocks(test_features, return_proba=True)

# 查看特征重要性
importance = selector.get_feature_importance(top_n=20)
print(importance)
```

### 4. 策略回测

```python
from tradingagents.backtest.backtest_strategy import create_strategy
from tradingagents.backtest.engine import BacktestEngine
from tradingagents.backtest.backtest_report import BacktestReport

# 创建策略
strategy = create_strategy("ma", fast_period=5, slow_period=20)
# 或
strategy = create_strategy("momentum", period=20, threshold=0.05)

# 生成信号
signals = strategy.generate_signals(data)

# 运行回测
engine = BacktestEngine(
    data=df_with_signals,
    strategies=["ma"],
    initial_capital=100000.0,
    commission_rate=0.0003,
    slippage_rate=0.0001
)
engine.execute()

# 生成报告
report = BacktestReport(engine)
report_dict = report.generate_report("runs/report.json")
report.print_report()
```

## 📊 功能特性

### 数据下载增强

- ✅ **Parquet缓存**：高效存储，支持大数据集
- ✅ **增量更新**：自动检测最新数据，避免重复下载
- ✅ **数据验证**：自动清理异常数据
- ✅ **容错机制**：API失败自动重试

### ML选股

- ✅ **30+特征**：MA、RSI、MACD、动量、波动率等
- ✅ **RandomForest**：稳健的分类器
- ✅ **特征重要性**：可解释的模型
- ✅ **批量预测**：快速评估多只股票

### 策略回测

- ✅ **多种策略**：MA、动量、ML
- ✅ **A股规则**：T+1、涨跌停
- ✅ **成本考虑**：手续费、滑点
- ✅ **详细报告**：年化收益、夏普、回撤

## 🎛️ 参数配置

### DataDownloader

```python
DataDownloader(
    save_path="data/stock_daily.parquet",  # 保存路径
    cache_dir="data/cache",                # 缓存目录
    provider="tushare"                     # 数据源
)
```

### SmartSelector

```python
SmartSelector(
    model_type="classifier",      # 分类器或回归器
    n_estimators=100,             # 树的数量
    max_depth=10,                 # 树深度
    model_path="models/ml.pkl"    # 模型保存路径
)
```

### 策略参数

**MA策略**:
```python
create_strategy("ma", fast_period=5, slow_period=20)
```

**动量策略**:
```python
create_strategy("momentum", period=20, threshold=0.05)
```

**ML策略**:
```python
create_strategy("ml", model=selector.model, threshold=0.5)
```

### BacktestEngine

```python
BacktestEngine(
    data=df_with_signals,
    strategies=["ma"],
    initial_capital=100000.0,      # 初始资金
    commission_rate=0.0003,        # 手续费率（万分之三）
    slippage_rate=0.0001           # 滑点率（万分之一）
)
```

## 📈 完整示例

```python
#!/usr/bin/env python3
"""
完整的使用示例
"""

from tradingagents.dataflows.data_downloader import DataDownloader
from tradingagents.models.ml_features import extract_features, select_features
from tradingagents.models.ml_selector import SmartSelector
from tradingagents.backtest.backtest_strategy import create_strategy
from tradingagents.backtest.engine import BacktestEngine
from tradingagents.backtest.backtest_report import BacktestReport

# 1. 数据下载
downloader = DataDownloader()
df = downloader.get_stock_data("600519.SH", "20200101", "20251030")

# 2. 特征工程
features = extract_features(df)
feature_cols = select_features(features)

# 3. 训练ML模型
selector = SmartSelector()
metrics = selector.train(feature_cols, features['future_return_binary'])
print(f"模型准确率: {metrics['test_accuracy']:.2%}")

# 4. 生成信号
strategy = create_strategy("ma")
signals = strategy.generate_signals(df)

# 5. 回测
df['signal'] = signals['signal']
engine = BacktestEngine(df, ["ma"])
engine.execute()

# 6. 报告
report = BacktestReport(engine)
report.print_report()
```

## 💡 最佳实践

1. **首次使用**：先用小数据集（3-5只股票）测试
2. **数据质量**：确保数据完整，避免NaN值过多
3. **特征选择**：根据特征重要性筛选最有效的特征
4. **参数调优**：尝试不同策略参数，找到最优配置
5. **定期更新**：每日更新数据，保持模型新鲜

## 🔍 故障排除

### 数据下载失败

```bash
# 检查API配置
export TUSHARE_TOKEN=your_token

# 尝试降级到CSV
# DataDownloader会自动处理
```

### Parquet错误

```bash
# 如果pyarrow安装失败，系统会自动降级到CSV
pip install pyarrow
```

### ML训练失败

```bash
# 检查特征数据
print(feature_cols.describe())
print(feature_cols.isna().sum())

# 确保有足够的数据
print(len(feature_cols))  # 至少需要100条
```

## 📚 参考资料

- [改进方案详细文档](IMPROVEMENTS.md)
- [选股模块文档](SELECTION.md)
- [数据管理文档](A_SHARE_DATA.md)

---

**享受智能交易！** 🎉

