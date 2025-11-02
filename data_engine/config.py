"""
全局配置：数据库连接、数据源开关、抓取窗口等。
按需修改 DB_URL 与 TUSHARE_TOKEN。
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

# ====== 数据抓取窗口（最近3年） ======
TODAY = datetime.now().date()
START_DATE = (TODAY - timedelta(days=365*3)).strftime("%Y-%m-%d")
END_DATE = TODAY.strftime("%Y-%m-%d")

# ====== 数据源开关 ======
USE_BAOSTOCK = True
USE_AKSHARE = True
USE_TUSHARE = False  # Tushare权限不足，暂时禁用

# ====== Tushare Token（如使用请设置环境变量或直接填写） ======
# 从.env文件读取token
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path, override=True)
except:
    pass
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# ====== 运行参数 ======
DATA_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(DATA_DIR, exist_ok=True)

LOG_FILE = os.path.join(DATA_DIR, "update.log")

# 速率控制（Tushare免费额度下建议保守）
SLEEP_SEC_TUSHARE = float(os.getenv("SLEEP_SEC_TUSHARE", "0.35"))
SLEEP_SEC_WEB = float(os.getenv("SLEEP_SEC_WEB", "0.2"))  # 爬取/HTTP默认间隔，降低以避免被限流
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "400"))
