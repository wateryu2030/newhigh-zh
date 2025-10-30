# 智能选股模块（SELECTION）

该模块基于多个量化因子与 LLM 事件评分融合，生成最终 Alpha 分数并支持组合构建与回测。

## 组成
- 因子层（tradingagents/factors）
  - `BaseFactor` 抽象基类
  - `MomentumFactor`、`VolumeFactor` 等价量基础因子
- LLM Alpha（tradingagents/llm_alpha）
  - `LLMScorer`：对新闻/公告等文本生成事件分数
- 综合打分（tradingagents/selection/scorer.py）
  - `rank_score` 跨行业/日期标准化
  - `calculate_alpha` 融合因子/事件/行业得分
- 组合优化（tradingagents/portfolio/optimizer.py）
  - `PortfolioOptimizer`：基于 alpha/波动率进行简化权重优化
- 回测引擎（tradingagents/backtest/engine.py）
  - `BacktestEngine`：包含 A 股特殊规则（涨跌停、T+1）占位逻辑

## 输入/输出
- 输入：历史行情（OHLCV）、行业/板块、事件文本（经 LLM 得分）
- 输出：Alpha 序列、目标权重、回测绩效

## 使用示例
```bash
python scripts/run_selection.py
python scripts/run_backtest.py
```

## 注意
- 为演示模板，仍需接入真实数据源与完备的约束、风控与交易成本模型。
