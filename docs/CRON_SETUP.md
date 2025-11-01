# 定时任务配置指南

## 📋 概述

本文档说明如何配置定时任务自动更新A股基础资料。

## 🔧 方法1: Linux/Mac Cron

### 1. 编辑crontab

```bash
crontab -e
```

### 2. 添加定时任务

```bash
# 每天凌晨2点更新A股基础资料
0 2 * * * cd /path/to/TradingAgents-CN && /usr/bin/python3 scripts/scheduled_update_stock_basic.py >> logs/cron_update.log 2>&1

# 或者每天收盘后更新（下午3:30）
30 15 * * 1-5 cd /path/to/TradingAgents-CN && /usr/bin/python3 scripts/scheduled_update_stock_basic.py >> logs/cron_update.log 2>&1
```

### 3. 验证配置

```bash
# 查看crontab
crontab -l

# 测试运行
python3 scripts/scheduled_update_stock_basic.py
```

## 🔧 方法2: Windows计划任务

### 1. 打开任务计划程序

- Win+R → 输入 `taskschd.msc` → 回车

### 2. 创建基本任务

1. 点击「创建基本任务」
2. 名称: "更新A股基础资料"
3. 触发器: 选择「每天」或「工作日」
4. 时间: 设置为收盘后（如15:30）
5. 操作: 「启动程序」
   - 程序: `python.exe`
   - 参数: `scripts/scheduled_update_stock_basic.py`
   - 起始于: `C:\path\to\TradingAgents-CN`

## 🔧 方法3: 使用Python schedule库（推荐开发环境）

### 1. 安装依赖

```bash
pip install schedule
```

### 2. 创建定时任务脚本

创建 `scripts/run_scheduled_tasks.py`:

```python
#!/usr/bin/env python3
import schedule
import time
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.scheduled_update_stock_basic import main

# 每天收盘后更新（15:30）
schedule.every().day.at("15:30").do(main)

# 或者每个工作日下午3:30更新
# schedule.every().monday.at("15:30").do(main)
# schedule.every().tuesday.at("15:30").do(main)
# schedule.every().wednesday.at("15:30").do(main)
# schedule.every().thursday.at("15:30").do(main)
# schedule.every().friday.at("15:30").do(main)

print("⏰ 定时任务已启动...")
print("📅 下次更新: 每天15:30")

while True:
    schedule.run_pending()
    time.sleep(60)  # 每分钟检查一次
```

### 3. 运行

```bash
python scripts/run_scheduled_tasks.py
```

或使用后台进程：

```bash
nohup python scripts/run_scheduled_tasks.py > logs/schedule.log 2>&1 &
```

## 📝 日志配置

确保日志目录存在：

```bash
mkdir -p logs
```

日志文件会自动保存在 `logs/cron_update.log` 或 `logs/schedule.log`

## ✅ 验证

运行一次测试更新：

```bash
python3 scripts/scheduled_update_stock_basic.py
```

检查输出和日志文件确认是否成功。

