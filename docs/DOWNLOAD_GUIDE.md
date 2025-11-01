# 📥 A股数据一键下载完整指南

## 功能概述

系统提供了一键下载所有A股基本信息的功能，包括：
- ✅ 股票代码、名称
- ✅ 行业分类
- ✅ 市盈率（PE）
- ✅ 市净率（PB）
- ✅ 总市值、流通市值
- ✅ 上市日期、地区等信息

## 🚀 使用方式

### 方式1：Web界面（推荐）

1. **打开股票搜索页面**
   - 访问：`http://localhost:8501`
   - 点击侧边栏的 **"🔎 股票搜索"**

2. **一键下载**
   - 在侧边栏找到 **"📥 数据下载"** 区域
   - 勾选/取消"使用缓存"选项：
     - ✅ 勾选：仅更新缺失数据（更快）
     - ❌ 不勾选：全量更新所有数据（更完整）
   - 点击 **"🔄 一键下载/更新所有A股数据"** 按钮

3. **等待完成**
   - 首次下载可能需要5-15分钟
   - 系统会显示进度和状态
   - 完成后自动刷新页面数据

### 方式2：命令行脚本

```bash
# 进入项目目录
cd /path/to/TradingAgents-CN

# 运行下载脚本
python scripts/download_a_share_data.py
```

### 方式3：Python API

```python
from tradingagents.dataflows.a_share_downloader import AShareDownloader

# 创建下载器
downloader = AShareDownloader()

# 下载所有股票（使用缓存，仅更新新数据）
df = downloader.download_all_stocks(use_cache=True)

# 或强制全量更新
df = downloader.download_all_stocks(use_cache=False)

print(f"下载了 {len(df)} 只股票")
```

## 📊 数据源

系统按以下优先级尝试下载：

### 1. Tushare（优先）
- **优点**：数据全面、准确
- **要求**：需要配置 `TUSHARE_TOKEN`
- **速度**：较快（批量接口）
- **数据量**：5000+股票，包含PE/PB/市值等

### 2. AKShare（备用）
- **优点**：免费、无需密钥
- **要求**：需要安装 `akshare` 包
- **速度**：较慢（可能需要逐个查询）
- **数据量**：5000+股票，基础信息完整

## ⚙️ 配置

### Tushare配置（推荐）

1. **获取Token**
   - 访问：https://tushare.pro
   - 注册账号并获取Token

2. **配置环境变量**
   ```bash
   # 编辑 .env 文件
   TUSHARE_TOKEN=your_token_here
   ```

3. **验证配置**
   ```python
   from tradingagents.dataflows.tushare_adapter import get_tushare_adapter
   adapter = get_tushare_adapter()
   if adapter.provider.connected:
       print("✅ Tushare连接成功")
   ```

### AKShare安装

```bash
pip install akshare
```

## 💾 数据存储

### 存储位置

数据存储在SQLite数据库中：
```
data/a_share_basic.db
```

### 表结构

**stock_basic 表**:
- `ts_code`: Tushare代码
- `symbol`: 股票代码（如 000001）
- `name`: 股票名称
- `industry`: 行业
- `pe`: 市盈率
- `pb`: 市净率
- `total_mv`: 总市值（元）
- `circ_mv`: 流通市值（元）
- `update_time`: 更新时间

## 🔍 使用下载的数据

### 搜索股票

```python
from tradingagents.dataflows.stock_search import get_searcher

searcher = get_searcher()

# 按关键字搜索
result = searcher.search(keyword="平安", limit=10)

# 按行业搜索
result = searcher.search(industry="银行", limit=20)

# 按条件筛选
result = searcher.search(
    industry="科技",
    min_market_cap=100,  # 最小市值100亿
    max_pe=30,          # 最大PE 30
    max_pb=5            # 最大PB 5
)
```

### 获取单只股票信息

```python
info = searcher.get_info("000001")
print(f"名称: {info['name']}")
print(f"行业: {info['industry']}")
print(f"PE: {info['pe']}")
```

## ⚠️ 常见问题

### 1. 下载失败："Too Many Requests"

**原因**：API频率限制

**解决**：
- 等待5-10分钟后重试
- 勾选"使用缓存"选项
- 升级Tushare账户

### 2. 下载缓慢

**原因**：
- 首次下载数据量大（5000+股票）
- API频率限制
- 网络速度慢

**解决**：
- 使用Tushare批量接口（更快）
- 分时段下载（错峰）
- 使用本地网络环境

### 3. 缺少PE/PB数据

**原因**：
- 部分股票当日停牌
- 数据源接口限制
- 某些新股可能暂无估值数据

**解决**：
- 第二天重试（可能已更新）
- 使用Tushare获取更完整数据

### 4. AKShare备用下载无行业信息

**原因**：为避免5000+次API调用，备用方法跳过行业查询

**解决**：
- 使用Tushare作为主数据源
- 或后续使用行业更新脚本单独补充

## 🔄 数据更新

### 自动更新

```bash
# 设置定时任务（每天收盘后更新）
crontab -e

# 添加以下行（周一到周五，18:00更新）
0 18 * * 1-5 cd /path/to/TradingAgents-CN && python scripts/scheduled_update.py
```

### 手动更新

- Web界面：点击"🔄 一键下载/更新所有A股数据"
- 命令行：`python scripts/download_a_share_data.py`

## 📈 数据统计

下载完成后，系统会显示：
- ✅ 总股票数
- ✅ 有PE数据的股票数
- ✅ 有PB数据的股票数
- ✅ 行业数量
- ✅ 数据预览（前10条）

## 💡 最佳实践

1. **首次使用**：
   - 配置Tushare Token（推荐）
   - 使用全量更新（不勾选缓存）
   - 预计需要10-15分钟

2. **日常使用**：
   - 勾选"使用缓存"（仅更新新数据）
   - 每天收盘后更新一次
   - 使用定时任务自动化

3. **数据质量**：
   - 优先使用Tushare数据源
   - 定期检查数据完整性
   - 关注PE/PB等关键指标

## 🔗 相关文档

- [频率限制处理](RATE_LIMIT_GUIDE.md)
- [A股数据管理](A_SHARE_DATA.md)
- [使用指南](usage_guide.md)

---

**一键下载功能已完善，可以开始使用了！** 🎉

