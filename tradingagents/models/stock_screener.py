#!/usr/bin/env python3
"""
选股模型核心实现
基于多维度分析能力的智能选股系统
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.stock_utils import StockUtils
from tradingagents.dataflows.interface import (
    get_china_stock_data_unified,
    get_china_stock_info_unified,
    get_YFin_data_online
)
from tradingagents.dataflows.chinese_finance_utils import get_chinese_social_sentiment

logger = get_logger('models.stock_screener')


class StockScreener:
    """智能选股模型"""
    
    def __init__(
        self,
        llm=None,
        toolkit=None,
        default_weights: Optional[Dict[str, float]] = None
    ):
        """
        初始化选股模型
        
        Args:
            llm: LLM模型实例
            toolkit: 工具包实例
            default_weights: 默认评分权重
        """
        self.llm = llm
        self.toolkit = toolkit
        
        # 默认评分权重
        self.default_weights = default_weights or {
            'technical': 0.35,      # 技术面权重35%
            'fundamental': 0.35,    # 基本面权重35%
            'sentiment': 0.15,      # 情绪权重15%
            'news': 0.15            # 新闻权重15%
        }
        
        # 初始化分析师（如果提供）
        if llm and toolkit:
            self.market_analyst = create_market_analyst(llm, toolkit)
            self.fundamentals_analyst = create_fundamentals_analyst(llm, toolkit)
            self.social_analyst = create_social_media_analyst(llm, toolkit)
        else:
            self.market_analyst = None
            self.fundamentals_analyst = None
            self.social_analyst = None
        
        logger.info(f"✅ 选股模型初始化完成，默认权重: {self.default_weights}")
    
    def screen_stocks(
        self,
        stock_list: List[str],
        screening_conditions: Optional[Dict] = None,
        score_conditions: Optional[Dict] = None,
        weights: Optional[Dict[str, float]] = None,
        use_parallel: bool = True
    ) -> Dict[str, Any]:
        """
        筛选股票
        
        Args:
            stock_list: 候选股票列表
            screening_conditions: 基础筛选条件
            score_conditions: 评分筛选条件
            weights: 评分权重（覆盖默认权重）
            use_parallel: 是否并行处理
            
        Returns:
            筛选结果字典
        """
        logger.info(f"🔍 开始筛选股票，候选数量: {len(stock_list)}")
        
        # 使用默认条件
        screening_conditions = screening_conditions or {}
        score_conditions = score_conditions or {}
        weights = weights or self.default_weights
        
        # 第一步：基础筛选
        filtered_stocks = self._apply_basic_screening(stock_list, screening_conditions)
        logger.info(f"📊 基础筛选后剩余: {len(filtered_stocks)} 只股票")
        
        # 第二步：计算评分
        scored_stocks = []
        for ticker in filtered_stocks:
            try:
                scores = self._calculate_scores(ticker, weights)
                if scores:
                    scored_stocks.append({
                        'ticker': ticker,
                        'scores': scores,
                        'composite_score': scores['composite']
                    })
            except Exception as e:
                logger.warning(f"⚠️ 计算 {ticker} 评分失败: {e}")
                continue
        
        # 第三步：应用评分筛选
        recommended = self._apply_score_screening(scored_stocks, score_conditions)
        
        # 第四步：排序
        recommended.sort(key=lambda x: x['composite_score'], reverse=True)
        
        logger.info(f"✅ 筛选完成，推荐股票数量: {len(recommended)}")
        
        return {
            'screening_date': datetime.now().strftime('%Y-%m-%d'),
            'total_candidates': len(stock_list),
            'filtered_count': len(filtered_stocks),
            'recommended_count': len(recommended),
            'recommended_stocks': recommended[:50],  # 返回前50只
            'weights_used': weights,
            'conditions': {
                'screening': screening_conditions,
                'scoring': score_conditions
            }
        }
    
    def _apply_basic_screening(
        self,
        stock_list: List[str],
        conditions: Dict
    ) -> List[str]:
        """应用基础筛选条件"""
        filtered = []
        
        for ticker in stock_list:
            try:
                # 检查市场类型
                if 'market' in conditions:
                    market_info = StockUtils.get_market_info(ticker)
                    if market_info['market_name'] not in conditions['market']:
                        continue
                
                # 其他筛选条件可以在这里添加
                # 例如：市值、成交量、价格等
                
                filtered.append(ticker)
            except Exception:
                continue
        
        return filtered
    
    def _calculate_scores(
        self,
        ticker: str,
        weights: Dict[str, float],
        lookback_days: int = 90
    ) -> Optional[Dict[str, Any]]:
        """计算多维度评分"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            # 获取市场信息
            market_info = StockUtils.get_market_info(ticker)
            
            # 1. 技术面评分
            technical_score = self._calculate_technical_score(ticker, start_date, end_date)
            
            # 2. 基本面评分
            fundamental_score = self._calculate_fundamental_score(ticker, start_date, end_date)
            
            # 3. 情绪评分
            sentiment_score = self._calculate_sentiment_score(ticker, end_date.strftime('%Y-%m-%d'))
            
            # 4. 新闻评分（暂时使用情绪评分的一部分）
            news_score = sentiment_score  # TODO: 单独计算新闻评分
            
            # 计算综合评分
            composite_score = (
                technical_score * weights['technical'] +
                fundamental_score * weights['fundamental'] +
                sentiment_score * weights['sentiment'] +
                news_score * weights['news']
            )
            
            return {
                'composite': round(composite_score, 2),
                'technical': round(technical_score, 2),
                'fundamental': round(fundamental_score, 2),
                'sentiment': round(sentiment_score, 2),
                'news': round(news_score, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ 计算 {ticker} 评分失败: {e}")
            return None
    
    def _calculate_technical_score(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """计算技术面评分"""
        try:
            # 获取市场数据（根据股票类型选择接口）
            market_info = StockUtils.get_market_info(ticker)
            if market_info['is_china']:
                data_str = get_china_stock_data_unified(
                    ticker,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
            else:
                # 非A股使用Yahoo Finance
                data_str = get_YFin_data_online(
                    ticker,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
            
            # 解析数据（简化版，实际需要解析返回的字符串报告）
            # 这里应该解析市场报告，提取技术指标
            
            # 模拟评分逻辑
            score = 70.0  # 默认评分
            
            # TODO: 实际实现应该：
            # 1. 解析技术指标（RSI、MACD、均线等）
            # 2. 评估趋势强度
            # 3. 计算评分
            
            return min(max(score, 0), 100)  # 限制在0-100
            
        except Exception as e:
            logger.warning(f"⚠️ 技术面评分计算失败: {e}")
            return 50.0  # 默认中性评分
    
    def _calculate_fundamental_score(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """计算基本面评分"""
        try:
            # 获取基本面数据（简化版，实际应调用基本面工具）
            # 这里使用股票信息作为替代
            market_info = StockUtils.get_market_info(ticker)
            if market_info['is_china']:
                stock_info = get_china_stock_info_unified(ticker)
                # 从stock_info中提取基本面指标
                data_str = str(stock_info) if stock_info else ""
            else:
                # 非A股暂时返回默认值
                data_str = ""
            
            # 解析基本面数据
            # TODO: 实际实现应该：
            # 1. 提取PE、PB、ROE等指标
            # 2. 与行业平均对比
            # 3. 计算评分
            
            score = 70.0  # 默认评分
            return min(max(score, 0), 100)
            
        except Exception as e:
            logger.warning(f"⚠️ 基本面评分计算失败: {e}")
            return 50.0
    
    def _calculate_sentiment_score(
        self,
        ticker: str,
        curr_date: str
    ) -> float:
        """计算情绪评分"""
        try:
            # 获取社交媒体情绪
            sentiment_str = get_chinese_social_sentiment(ticker, curr_date)
            
            # 解析情绪数据
            # TODO: 实际实现应该：
            # 1. 提取情绪评分
            # 2. 转换为0-100分制
            
            score = 60.0  # 默认评分
            return min(max(score, 0), 100)
            
        except Exception as e:
            logger.warning(f"⚠️ 情绪评分计算失败: {e}")
            return 50.0
    
    def _apply_score_screening(
        self,
        scored_stocks: List[Dict],
        conditions: Dict
    ) -> List[Dict]:
        """应用评分筛选条件"""
        filtered = []
        
        for stock in scored_stocks:
            scores = stock['scores']
            
            # 检查综合评分
            if 'min_composite_score' in conditions:
                if scores['composite'] < conditions['min_composite_score']:
                    continue
            
            # 检查技术面评分
            if 'min_technical_score' in conditions:
                if scores['technical'] < conditions['min_technical_score']:
                    continue
            
            # 检查基本面评分
            if 'min_fundamental_score' in conditions:
                if scores['fundamental'] < conditions['min_fundamental_score']:
                    continue
            
            filtered.append(stock)
        
        return filtered


def create_screener_config(
    strategy_type: str = 'balanced'
) -> Dict[str, Any]:
    """
    创建选股配置
    
    Args:
        strategy_type: 策略类型 ('conservative', 'balanced', 'aggressive', 'value', 'growth')
    
    Returns:
        配置字典
    """
    configs = {
        'conservative': {
            'weights': {
                'technical': 0.25,
                'fundamental': 0.50,
                'sentiment': 0.15,
                'news': 0.10
            },
            'score_conditions': {
                'min_composite_score': 75,
                'min_fundamental_score': 70,
                'max_risk_score': 5.0
            }
        },
        'balanced': {
            'weights': {
                'technical': 0.35,
                'fundamental': 0.35,
                'sentiment': 0.15,
                'news': 0.15
            },
            'score_conditions': {
                'min_composite_score': 70,
                'min_technical_score': 60,
                'min_fundamental_score': 60
            }
        },
        'aggressive': {
            'weights': {
                'technical': 0.40,
                'fundamental': 0.30,
                'sentiment': 0.20,
                'news': 0.10
            },
            'score_conditions': {
                'min_composite_score': 70,
                'min_technical_score': 70
            }
        },
        'value': {
            'weights': {
                'technical': 0.20,
                'fundamental': 0.60,
                'sentiment': 0.10,
                'news': 0.10
            },
            'score_conditions': {
                'min_composite_score': 75,
                'min_fundamental_score': 75
            }
        },
        'growth': {
            'weights': {
                'technical': 0.40,
                'fundamental': 0.30,
                'sentiment': 0.20,
                'news': 0.10
            },
            'score_conditions': {
                'min_composite_score': 70,
                'min_technical_score': 70,
                'growth_rate_min': 0.15
            }
        }
    }
    
    return configs.get(strategy_type, configs['balanced'])
