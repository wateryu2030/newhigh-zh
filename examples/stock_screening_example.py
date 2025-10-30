#!/usr/bin/env python3
"""
选股模型使用示例
演示如何使用选股模型筛选股票
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.models import StockScreener, create_screener_config
from tradingagents.config.config_manager import ConfigManager


def example_stock_screening():
    """选股模型使用示例"""
    
    print("=" * 60)
    print("📊 选股模型使用示例")
    print("=" * 60)
    
    # 1. 初始化配置
    config = ConfigManager()
    
    # 2. 获取LLM和工具包
    # 注意：这里需要根据实际情况初始化
    # llm = config.get_llm()
    # toolkit = config.get_toolkit()
    
    # 3. 创建选股器（简化版，不依赖LLM）
    screener = StockScreener(llm=None, toolkit=None)
    
    # 4. 准备候选股票列表（示例）
    # 实际使用中，可以从Tushare获取A股列表，或从其他数据源获取
    candidate_stocks = [
        '000001',  # 平安银行
        '600519',  # 贵州茅台
        '000002',  # 万科A
        '002701',  # 奥瑞金
        # 可以添加更多股票代码
    ]
    
    print(f"\n📋 候选股票数量: {len(candidate_stocks)}")
    print(f"候选股票: {', '.join(candidate_stocks)}")
    
    # 5. 选择策略类型
    strategy_type = 'balanced'  # 可选: 'conservative', 'balanced', 'aggressive', 'value', 'growth'
    config_params = create_screener_config(strategy_type)
    
    print(f"\n🎯 使用策略: {strategy_type}")
    print(f"评分权重: {config_params['weights']}")
    print(f"筛选条件: {config_params['score_conditions']}")
    
    # 6. 执行筛选
    print("\n🔍 开始筛选股票...")
    result = screener.screen_stocks(
        stock_list=candidate_stocks,
        screening_conditions={
            'market': ['A股']  # 只筛选A股
        },
        score_conditions=config_params['score_conditions'],
        weights=config_params['weights']
    )
    
    # 7. 输出结果
    print("\n" + "=" * 60)
    print("📊 筛选结果")
    print("=" * 60)
    print(f"筛选日期: {result['screening_date']}")
    print(f"候选股票总数: {result['total_candidates']}")
    print(f"基础筛选后: {result['filtered_count']} 只")
    print(f"最终推荐: {result['recommended_count']} 只")
    
    if result['recommended_stocks']:
        print("\n🏆 推荐股票列表:")
        print("-" * 60)
        for i, stock in enumerate(result['recommended_stocks'][:10], 1):
            scores = stock['scores']
            print(f"\n{i}. {stock['ticker']}")
            print(f"   综合评分: {scores['composite']:.2f}/100")
            print(f"   - 技术面: {scores['technical']:.2f}")
            print(f"   - 基本面: {scores['fundamental']:.2f}")
            print(f"   - 情绪: {scores['sentiment']:.2f}")
            print(f"   - 新闻: {scores['news']:.2f}")
    else:
        print("\n⚠️ 未找到符合条件的推荐股票")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    example_stock_screening()
