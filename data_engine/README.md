# data_engine (A股智能选股基础数据库 · v1)

## 1. 准备
- 安装 MySQL，并执行 `db_init.sql`：
  ```sql
  mysql -u root -p < db_init.sql
  ```
- 设置连接串（可用环境变量覆盖）：
  ```bash
  export STOCK_DB_URL="mysql+pymysql://root:password@localhost:3306/stock_db?charset=utf8mb4"
  ```
- （可选）设置 Tushare Token：
  ```bash
  export TUSHARE_TOKEN="你的token"
  ```
- 安装依赖：
  ```bash
  pip install -r requirements.txt
  ```

## 2. 更新数据
```bash
python update_all.py
```

## 3. 与 newhigh-zh 整合
在后端任务或按钮触发逻辑中：
```python
from data_engine.update_all import *
# 或直接 subprocess 调用 `python data_engine/update_all.py`
```

> 初次运行默认仅对前 400 只股票抓取日K与技术指标，稳定后可在 `fetch_data.py` / `compute_indicators.py` 放开限制。

## 4. 注意事项
- 如果未设置 `TUSHARE_TOKEN`，仍可用 Baostock/Akshare 获取大部分数据，但资金流、daily_basic 将跳过或退化。
- 国内网络环境下，适当放慢请求间隔，避免被限流（已内置指数退避重试）。
