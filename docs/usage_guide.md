# 完整使用指南

## 🚀 快速开始

### 1. 初始化A股数据库（首次必须）

```bash
# 方法1：命令行
python scripts/download_a_share_data.py

# 方法2：Web界面
# 访问"🔎 股票搜索"页面 → 侧边栏 → "🔄 更新股票数据"
```

### 2. 使用智能选股

1. **访问选股页面**
   - Web界面 → "🔍 智能选股"

2. **输入股票列表**
   - 在"股票列表"输入框输入：`000001,600519,002701`

3. **（可选）上传LLM事件CSV**
   ```
   ticker,event_text
   600519,"Q3业绩超预期 positive"
   000001,"监管政策利好 positive"
   ```

4. **设置参数**
   - 换手上限：0.3（30%）
   - 行业上限：0.3（30%）
   - 单票上限：0.2（20%）

5. **点击"生成Alpha与权重"**
   - 系统自动获取行业信息（从数据库）
   - 计算因子得分
   - 生成LLM事件评分
   - 计算最终Alpha和权重

### 3. 使用量化交易

1. **初始化交易器**
   - 设置初始资金（如100万）
   - 选择策略（如"趋势跟踪"）
   - 设置最大持仓数和风险比例

2. **生成交易信号**
   - 输入股票代码
   - 输入当前价格
   - 点击"生成交易信号"
   - 系统自动获取历史数据并计算信号

3. **执行交易**
   - 查看信号详情
   - 确认价格和数量
   - 点击"执行交易"

### 4. 搜索股票

1. **访问搜索页面**
   - Web界面 → "🔎 股票搜索"

2. **设置搜索条件**
   - 关键字：如"平安"、"000001"
   - 行业：如"银行"、"科技"
   - 市值：最小市值（亿元）
   - PE/PB：最大市盈率/市净率

3. **查看结果**
   - 表格展示
   - 可下载CSV
   - 点击代码查看详细信息

## 📋 数据更新

### 手动更新

```bash
python scripts/download_a_share_data.py
```

### 自动更新（推荐）

设置cron定时任务，每天收盘后更新：

```bash
# 编辑crontab
crontab -e

# 添加以下行（周一到周五，每天18:00更新）
0 18 * * 1-5 cd /path/to/TradingAgents-CN && source env/bin/activate && python scripts/scheduled_update.py >> logs/a_share_update.log 2>&1
```

## 🔧 高级功能

### 使用Python API

```python
# 1. 搜索股票
from tradingagents.dataflows.stock_search import get_searcher

searcher = get_searcher()
result = searcher.search(industry="银行", max_pe=10)

# 2. 运行选股
from scripts.run_selection import run_selection
run_selection('2025-10-29')

# 3. 运行回测
from scripts.run_backtest import run_backtest
run_backtest()

# 4. 获取股票信息
info = searcher.get_info("000001")
print(f"名称：{info['name']}, 行业：{info['industry']}, PE：{info['pe']}")
```

### LLM评分配置

在`.env`文件中配置：

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
```

LLM会自动输出结构化JSON：
```json
{
  "score": 0.35,
  "rationale": "订单增长，业绩超预期",
  "event_type": "earnings"
}
```

## 📊 工作流程示例

### 完整选股流程

```
1. 更新A股数据 → scripts/download_a_share_data.py
2. 搜索候选股票 → Web界面"股票搜索"或Python API
3. 导出股票列表 → CSV格式
4. 上传到智能选股 → 输入股票代码列表
5. 上传LLM事件 → （可选）包含事件文本
6. 设置约束条件 → 换手/行业/单票上限
7. 生成权重 → 查看Alpha和权重结果
8. 执行建仓 → 根据权重计算持仓数量
```

### 量化交易流程

```
1. 初始化交易器 → 设置资金和策略
2. 生成信号 → 输入股票代码和价格
3. 查看信号详情 → 买入/卖出/持有
4. 执行交易 → 确认价格和数量
5. 监控持仓 → 查看盈亏情况
6. 查看历史 → 分析交易记录
```

## 💡 最佳实践

1. **定期更新数据**
   - A股基础数据每天更新一次
   - 确保PE、PB、市值等指标最新

2. **合理设置约束**
   - 换手上限：30-50%（避免过度交易）
   - 行业上限：20-40%（分散风险）
   - 单票上限：5-20%（控制集中度）

3. **LLM事件质量**
   - 事件文本要简洁明确
   - 包含关键信息（利好/利空）
   - 可批量处理多条事件

4. **回测验证**
   - 新策略先回测验证
   - 关注最大回撤和夏普比率
   - 调整参数后再实盘

## 🔍 常见问题

### Q: 数据库在哪里？
A: `data/a_share_basic.db`（SQLite格式）

### Q: 如何查看数据库内容？
A: 可以使用SQLite客户端，或使用Python：
```python
import sqlite3
conn = sqlite3.connect('data/a_share_basic.db')
df = pd.read_sql_query("SELECT * FROM stock_basic LIMIT 10", conn)
```

### Q: 首次下载需要多长时间？
A: 根据API速度，通常需要5-15分钟（5000+只股票）

### Q: 如何只更新特定股票？
A: 目前支持全量更新，增量更新功能待开发

### Q: 行业信息如何获取？
A: 优先从Tushare获取，失败则尝试AKShare

## 📚 相关文档

- [选股模块详细说明](SELECTION.md)
- [A股数据管理](A_SHARE_DATA.md)
- [故障排除指南](../troubleshooting/rate_limit_handling.md)

