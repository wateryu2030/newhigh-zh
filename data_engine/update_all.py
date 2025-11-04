"""
统一更新入口：
1) 初始化表结构：请先在 MySQL 执行 db_init.sql
2) 运行本脚本将自动：基础信息 -> 财务/估值 -> 指数 -> 概念行业 -> 日K -> 技术指标
"""
import os
import sys
from pathlib import Path

# Add data_engine directory to path for imports
data_engine_dir = Path(__file__).parent
sys.path.insert(0, str(data_engine_dir))

from utils.logger import setup_logger
from config import DATA_DIR
from fetch_data import main as fetch_main
from compute_indicators import main as compute_main

logger = setup_logger(log_file=os.path.join(DATA_DIR, "update.log"))

def main():
    """主函数：更新所有数据"""
    logger.info("🚀 开始更新 A股智能选股基础数据库（v1）")
    fetch_main()
    
    # 技术指标计算（可选，根据需要启用）
    batch_size = os.getenv("BATCH_SIZE", "400")
    if batch_size.lower() in ["none", "null", "full"]:
        compute_main(limit=None)  # 全量计算
    else:
        try:
            limit = int(batch_size)
            compute_main(limit=limit)
        except ValueError:
            compute_main(limit=400)
    
    logger.info("✅ 全部完成")

if __name__ == "__main__":
    main()
