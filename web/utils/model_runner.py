#!/usr/bin/env python3
"""
模型运行工具
用于在Web界面中运行选股和量化交易模型
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.models import StockScreener, QuantitativeTrader, create_screener_config
from tradingagents.utils.stock_utils import StockUtils
from tradingagents.utils.report_parser import ReportParser
from tradingagents.utils.logging_init import get_logger

logger = get_logger('web.model_runner')


def run_stock_screening(
    stock_list: List[str],
    strategy_type: str = 'balanced',
    screening_conditions: Optional[Dict] = None,
    use_llm: bool = False,
    llm=None,
    toolkit=None
) -> Dict[str, Any]:
    """
    运行选股筛选
    
    Args:
        stock_list: 候选股票列表
        strategy_type: 策略类型
        screening_conditions: 筛选条件
        use_llm: 是否使用LLM增强分析
        llm: LLM实例（如果use_llm=True）
        toolkit: 工具包实例（如果use_llm=True）
    
    Returns:
        筛选结果
    """
    try:
        # 创建选股器
        screener = StockScreener(llm=llm if use_llm else None, toolkit=toolkit if use_llm else None)
        
        # 获取策略配置
        config_params = create_screener_config(strategy_type)
        
        # 执行筛选
        result = screener.screen_stocks(
            stock_list=stock_list,
            screening_conditions=screening_conditions or {},
            score_conditions=config_params['score_conditions'],
            weights=config_params['weights']
        )
        
        return result
        
    except Exception as e:
        logger.error(f"选股失败: {e}", exc_info=True)
        raise


def run_quantitative_trading_signal(
    ticker: str,
    strategy_type: str,
    initial_capital: float = 100000.0,
    max_positions: int = 5,
    risk_per_trade: float = 0.02
) -> Dict[str, Any]:
    """
    运行量化交易信号生成
    
    Args:
        ticker: 股票代码
        strategy_type: 策略类型
        initial_capital: 初始资金
        max_positions: 最大持仓数
        risk_per_trade: 单笔风险
    
    Returns:
        交易信号结果
    """
    try:
        from tradingagents.models import StrategyType
        
        # 策略类型映射
        strategy_map = {
            'trend_following': StrategyType.TREND_FOLLOWING,
            'mean_reversion': StrategyType.MEAN_REVERSION,
            'momentum': StrategyType.MOMENTUM,
            'multi_factor': StrategyType.MULTI_FACTOR
        }
        
        strategy = strategy_map.get(strategy_type, StrategyType.MULTI_FACTOR)
        
        # 创建交易器
        trader = QuantitativeTrader(
            initial_capital=initial_capital,
            strategy_type=strategy,
            max_positions=max_positions,
            risk_per_trade=risk_per_trade
        )
        
        # 这里应该获取实际的市场数据和价格
        # 简化处理，返回信号生成接口
        return {
            'trader': trader,
            'strategy': strategy_type
        }
        
    except Exception as e:
        logger.error(f"量化交易信号生成失败: {e}", exc_info=True)
        raise


def enhance_scores_with_analysis_reports(
    ticker: str,
    analysis_reports: Dict[str, str]
) -> Dict[str, float]:
    """
    使用分析报告增强评分（如果已有分析结果）
    
    Args:
        ticker: 股票代码
        analysis_reports: 分析报告字典
    
    Returns:
        增强后的评分字典
    """
    try:
        # 解析报告
        parsed_data = ReportParser.parse_analysis_reports(analysis_reports)
        
        # 提取评分
        scores = {
            'technical': parsed_data.get('technical', {}).get('score', 50.0),
            'fundamental': parsed_data.get('fundamental', {}).get('score', 50.0),
            'sentiment': parsed_data.get('sentiment', {}).get('score', 50.0),
            'news': parsed_data.get('news', {}).get('score', 50.0)
        }
        
        return scores
        
    except Exception as e:
        logger.warning(f"使用分析报告增强评分失败: {e}")
        return {
            'technical': 50.0,
            'fundamental': 50.0,
            'sentiment': 50.0,
            'news': 50.0
        }
