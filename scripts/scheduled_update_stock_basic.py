#!/usr/bin/env python3
"""
定时更新A股基础资料脚本
可用于cron任务或计划任务
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from scripts.fetch_cn_stock_basic import fetch_cn_stock_basic
from tradingagents.utils.logging_init import get_logger

logger = get_logger('scripts.scheduled_update_stock_basic')


def main():
    """定时更新主函数"""
    print(f"🕐 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始定时更新A股基础资料...")
    logger.info("开始定时更新A股基础资料")
    
    try:
        # 调用下载函数
        df = fetch_cn_stock_basic()
        
        if df.empty:
            print("❌ 更新失败：未获取到数据")
            logger.error("定时更新失败：未获取到数据")
            return 1
        
        print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 更新成功：{len(df)} 只股票")
        logger.info(f"定时更新成功：{len(df)} 只股票")
        
        # 统计信息
        print(f"📊 数据统计:")
        print(f"  - 总股票数: {len(df)}")
        if "pe" in df.columns:
            pe_count = df["pe"].notna().sum()
            print(f"  - 有PE数据的股票: {pe_count}")
        if "pb" in df.columns:
            pb_count = df["pb"].notna().sum()
            print(f"  - 有PB数据的股票: {pb_count}")
        
        return 0
        
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H%M%S')}] 更新失败：{e}")
        logger.error(f"定时更新失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())

