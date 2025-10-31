#!/usr/bin/env python3
"""
A股数据下载脚本
定期下载和更新A股基本信息
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.a_share_downloader import AShareDownloader
from tradingagents.utils.logging_init import get_logger

logger = get_logger('scripts.download_a_share')


def main():
    """主函数"""
    print("🚀 开始下载A股基础数据...")
    
    # 创建下载器
    downloader = AShareDownloader()
    
    # 下载所有股票数据
    df = downloader.download_all_stocks(use_cache=True)
    
    if df.empty:
        print("❌ 下载失败或未获取到数据")
        return
    
    print(f"✅ 成功下载 {len(df)} 只股票数据")
    print(f"📊 数据库位置: {downloader.db_path}")
    print("\n📋 数据预览（前10条）:")
    print(df[['symbol', 'name', 'industry', 'pe', 'pb', 'total_mv']].head(10))
    
    # 统计信息
    print("\n📈 统计信息:")
    print(f"- 总股票数: {len(df)}")
    print(f"- 有PE数据的股票: {df['pe'].notna().sum()}")
    print(f"- 有PB数据的股票: {df['pb'].notna().sum()}")
    print(f"- 有市值数据的股票: {df['total_mv'].notna().sum()}")
    print(f"- 行业数: {df['industry'].nunique()}")
    
    # 测试搜索
    print("\n🔍 搜索测试:")
    result = downloader.search_stocks(keyword="平安", limit=5)
    if not result.empty:
        print(result[['symbol', 'name', 'industry', 'pe', 'pb']])


if __name__ == "__main__":
    main()

