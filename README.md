# TradingAgents-CN 股票分析平台

基于大语言模型的智能股票分析系统，支持A股、港股、美股多市场分析。

## ✨ 主要功能

### 📊 股票分析
- **市场分析师**：技术面分析（趋势、指标、支撑阻力）
- **基本面分析师**：财务数据分析和估值评估
- **新闻分析师**：新闻事件和舆情分析
- **社交媒体分析师**：A股使用东方财富股吧、雪球；美股/港股使用Reddit

### 🔍 智能选股
- 多维度评分系统（技术面、基本面、情绪、新闻）
- 5种预设策略（保守、平衡、激进、价值、成长）
- LLM事件评分（OpenAI/Claude结构化输出）
- 组合优化（行业约束、换手控制、单票上限）
- 可视化展示（雷达图、柱状图、评分对比）
- 支持批量筛选和导出
- **自动行业识别**：从本地数据库自动获取行业信息

### 💹 量化交易
- 4种交易策略（趋势跟踪、均值回归、动量、多因子）
- 自动风险管理（止损、止盈、仓位管理）
- 实时信号生成和交易执行
- 交易历史和盈亏追踪
- 回测引擎（T+1规则、涨跌停限制、成本滑点）
- 绩效指标（年化收益、夏普比率、最大回撤）

### 🔎 股票搜索
- **A股基础数据管理**：批量下载和本地存储
- 多条件搜索（代码、名称、行业、市值、PE、PB）
- 快速查询（SQLite数据库，索引优化）
- 定期更新机制
- 自动集成到选股系统

## 🚀 快速开始

### 环境要求
- Python 3.10+
- MongoDB（可选，用于数据缓存）
- Redis（可选，用于会话缓存）

### 安装步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/wateryu2030/newhigh-zh.git
   cd newhigh-zh
   ```

2. **创建虚拟环境**
   ```bash
   python3 -m venv env
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入您的API密钥
   ```

5. **启动应用**
   ```bash
   python start_web.py
   ```

6. **访问应用**
   打开浏览器访问：http://localhost:8501

## 🔑 API密钥配置

在 `.env` 文件中配置以下API密钥（至少需要一个）：

```env
# OpenAI API（推荐）
OPENAI_API_KEY=sk-...

# DeepSeek API（国产替代）
DEEPSEEK_API_KEY=sk-...

# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-...

# 阿里百炼（Dashscope）
DASHSCOPE_API_KEY=sk-...

# Tushare（A股数据）
TUSHARE_TOKEN=your_token

# FinnHub（美股数据）
FINNHUB_API_KEY=your_key
```

## 📖 使用文档

- [快速开始指南](QUICK_START_MODELS.md)
- [集成指南](docs/integration/web_integration_guide.md)
- [故障排除](docs/troubleshooting/rate_limit_handling.md)
- [A股数据管理](docs/A_SHARE_DATA.md)
- [选股模块文档](docs/SELECTION.md)

## 🏗️ 技术架构

- **前端**: Streamlit
- **LLM集成**: OpenAI, DeepSeek, Anthropic, Dashscope
- **数据源**: Tushare（A股）、Yahoo Finance（美股）、AKShare（港股）
- **数据分析**: pandas, numpy, plotly
- **量化交易**: 自定义策略引擎

## 📁 项目结构

```
TradingAgents-CN/
├── tradingagents/          # 核心业务逻辑
│   ├── agents/            # 分析师模块
│   ├── models/            # 选股和量化交易模型
│   ├── dataflows/         # 数据获取和处理
│   └── utils/             # 工具函数
├── web/                    # Web界面
│   ├── components/        # UI组件
│   ├── utils/             # 工具函数
│   └── app.py             # 主应用入口
├── docs/                   # 文档
├── examples/               # 示例代码
└── data/                   # 数据目录（不纳入版本控制）
```

## 🔄 更新日志

### v1.0.0 (2025-01-30)
- ✅ 完成股票分析功能（市场、基本面、新闻、社交媒体）
- ✅ 集成智能选股模型
- ✅ 集成量化交易模型
- ✅ 支持多市场（A股、港股、美股）
- ✅ 完善错误处理和API频率限制处理

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 💬 支持

如有问题，请提交Issue或查看文档。

---

**注意**：本项目仅供学习和研究使用，不构成投资建议。投资有风险，请谨慎决策。