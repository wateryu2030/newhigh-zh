#!/usr/bin/env python3
"""
定时更新脚本
用于定期更新A股基础数据（可配置cron任务）
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.a_share_downloader import AShareDownloader
from tradingagents.utils.logging_init import get_logger

logger = get_logger('scripts.scheduled_update')


def main():
    """定时更新主函数"""
    print(f"🕐 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始定时更新A股数据...")
    
    try:
        downloader = AShareDownloader()
        df = downloader.download_all_stocks(use_cache=False)
        
        if df.empty:
            print("❌ 更新失败：未获取到数据")
            logger.error("定时更新失败：未获取到数据")
            return 1
        
        print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 更新成功：{len(df)} 只股票")
        logger.info(f"定时更新成功：{len(df)} 只股票")
        return 0
        
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 更新失败：{e}")
        logger.error(f"定时更新失败：{e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())

