"""
全局配置：数据库连接、数据源、抓取窗口等
基于BaoStock数据源
"""
import os
from datetime import datetime, timedelta

# ====== 数据库连接（支持MySQL和SQLite） ======
# 默认使用SQLite便于快速验证，生产环境可切换到MySQL
_DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # sqlite or mysql
if _DB_TYPE == "sqlite":
    # SQLite路径
    SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stock_database.db")
    DB_URL = f"sqlite:///{SQLITE_PATH}"
    print(f"📊 使用SQLite数据库: {SQLITE_PATH}")
else:
    # MySQL连接
    DB_URL = os.getenv("STOCK_DB_URL", "mysql+pymysql://root:password@localhost:3306/stock_db?charset=utf8mb4")
    print(f"📊 使用MySQL数据库")

# ====== 数据抓取窗口 ======
TODAY = datetime.now().date()
START_DATE = (TODAY - timedelta(days=365*3)).strftime("%Y-%m-%d")  # 最近3年
END_DATE = TODAY.strftime("%Y-%m-%d")

# ====== 数据源 ======
# 只使用BaoStock作为唯一数据源（免费、稳定、完整）
USE_BAOSTOCK = True

# ====== 运行参数 ======
DATA_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(DATA_DIR, exist_ok=True)
LOG_FILE = os.path.join(DATA_DIR, "update.log")

# ====== 速率控制 ======
# BaoStock请求间隔（秒）
SLEEP_SEC_WEB = float(os.getenv("SLEEP_SEC_WEB", "0.2"))

# ====== 批量控制 ======
# 每次更新处理的股票数量（可修改为更大值或取消限制）
# 默认400，设置环境变量BATCH_SIZE=none或full表示全量下载
BATCH_SIZE = os.getenv("BATCH_SIZE", "400")
