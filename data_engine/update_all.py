"""
统一更新入口：
1) 初始化表结构：请先在 MySQL 执行 db_init.sql
2) 运行本脚本将自动：基础信息 -> 财务/估值 -> 指数 -> 概念行业 -> 日K -> 技术指标
"""
import os
from utils.logger import setup_logger
from config import DATA_DIR
from fetch_data import main as fetch_main
from compute_indicators import main as compute_main

logger = setup_logger(log_file=os.path.join(DATA_DIR, "update.log"))

if __name__ == "__main__":
    logger.info("🚀 开始更新 A股智能选股基础数据库（v1）")
    fetch_main()
    compute_main(limit=400)   # 初次运行先限制规模，稳定后可放开
    logger.info("✅ 全部完成")
