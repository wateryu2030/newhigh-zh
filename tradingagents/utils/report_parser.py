#!/usr/bin/env python3
"""
分析报告解析器
将分析师生成的文本报告解析为结构化数据，用于选股和量化交易模型
"""

import re
from typing import Dict, Optional, Any, List
from datetime import datetime

from tradingagents.utils.logging_init import get_logger

logger = get_logger('utils.report_parser')


class ReportParser:
    """分析报告解析器"""
    
    @staticmethod
    def parse_market_report(report_text: str) -> Dict[str, Any]:
        """
        解析市场分析师报告
        
        Args:
            report_text: 市场分析报告文本
        
        Returns:
            包含技术指标和评分的字典
        """
        result = {
            'rsi': None,
            'macd': None,
            'trend': None,
            'support': None,
            'resistance': None,
            'volume': None,
            'score': None
        }
        
        try:
            # 提取RSI
            rsi_match = re.search(r'RSI[:\s]+(\d+(?:\.\d+)?)', report_text, re.IGNORECASE)
            if rsi_match:
                result['rsi'] = float(rsi_match.group(1))
            
            # 提取MACD
            macd_match = re.search(r'MACD[:\s]+([+-]?\d+(?:\.\d+)?)', report_text, re.IGNORECASE)
            if macd_match:
                result['macd'] = float(macd_match.group(1))
            
            # 提取趋势（上涨/下跌/震荡）
            if re.search(r'上涨|上升|看涨|买入', report_text):
                result['trend'] = 'up'
            elif re.search(r'下跌|下降|看跌|卖出', report_text):
                result['trend'] = 'down'
            else:
                result['trend'] = 'neutral'
            
            # 提取支撑位
            support_match = re.search(r'支撑[位点:\s]+[¥$]?(\d+(?:\.\d+)?)', report_text)
            if support_match:
                result['support'] = float(support_match.group(1))
            
            # 提取阻力位
            resistance_match = re.search(r'阻力[位点:\s]+[¥$]?(\d+(?:\.\d+)?)', report_text)
            if resistance_match:
                result['resistance'] = float(resistance_match.group(1))
            
            # 尝试提取评分
            score_match = re.search(r'评分[:\s]+(\d+(?:\.\d+)?)', report_text)
            if score_match:
                result['score'] = float(score_match.group(1))
            else:
                # 如果没有明确评分，根据趋势和指标估算
                result['score'] = ReportParser._estimate_technical_score(result)
            
        except Exception as e:
            logger.warning(f"解析市场报告失败: {e}")
        
        return result
    
    @staticmethod
    def parse_fundamentals_report(report_text: str) -> Dict[str, Any]:
        """
        解析基本面分析师报告
        
        Args:
            report_text: 基本面分析报告文本
        
        Returns:
            包含财务指标和评分的字典
        """
        result = {
            'pe': None,
            'pb': None,
            'roe': None,
            'roa': None,
            'profit_margin': None,
            'debt_ratio': None,
            'score': None
        }
        
        try:
            # 提取PE
            pe_match = re.search(r'PE[比率:\s]+(\d+(?:\.\d+)?)', report_text, re.IGNORECASE)
            if not pe_match:
                pe_match = re.search(r'市盈率[:\s]+(\d+(?:\.\d+)?)', report_text)
            if pe_match:
                result['pe'] = float(pe_match.group(1))
            
            # 提取PB
            pb_match = re.search(r'PB[比率:\s]+(\d+(?:\.\d+)?)', report_text, re.IGNORECASE)
            if not pb_match:
                pb_match = re.search(r'市净率[:\s]+(\d+(?:\.\d+)?)', report_text)
            if pb_match:
                result['pb'] = float(pb_match.group(1))
            
            # 提取ROE
            roe_match = re.search(r'ROE[:\s]+(\d+(?:\.\d+)?)%?', report_text, re.IGNORECASE)
            if not roe_match:
                roe_match = re.search(r'净资产收益率[:\s]+(\d+(?:\.\d+)?)%?', report_text)
            if roe_match:
                result['roe'] = float(roe_match.group(1))
            
            # 提取ROA
            roa_match = re.search(r'ROA[:\s]+(\d+(?:\.\d+)?)%?', report_text, re.IGNORECASE)
            if not roa_match:
                roa_match = re.search(r'总资产收益率[:\s]+(\d+(?:\.\d+)?)%?', report_text)
            if roa_match:
                result['roa'] = float(roa_match.group(1))
            
            # 提取毛利率
            margin_match = re.search(r'毛利率[:\s]+(\d+(?:\.\d+)?)%?', report_text)
            if margin_match:
                result['profit_margin'] = float(margin_match.group(1))
            
            # 提取评分
            score_match = re.search(r'评分[:\s]+(\d+(?:\.\d+)?)', report_text)
            if score_match:
                result['score'] = float(score_match.group(1))
            else:
                result['score'] = ReportParser._estimate_fundamental_score(result)
            
        except Exception as e:
            logger.warning(f"解析基本面报告失败: {e}")
        
        return result
    
    @staticmethod
    def parse_sentiment_report(report_text: str) -> Dict[str, Any]:
        """
        解析情绪分析师报告
        
        Args:
            report_text: 情绪分析报告文本
        
        Returns:
            包含情绪指标和评分的字典
        """
        result = {
            'sentiment_score': None,
            'sentiment_level': None,
            'discussion_count': None,
            'hot_topics': [],
            'score': None
        }
        
        try:
            # 提取情绪评分
            sentiment_match = re.search(r'情绪[评分:\s]+([+-]?\d+(?:\.\d+)?)', report_text)
            if sentiment_match:
                result['sentiment_score'] = float(sentiment_match.group(1))
            
            # 提取情绪等级
            if re.search(r'非常积极|很乐观|强烈看涨', report_text):
                result['sentiment_level'] = 'very_positive'
            elif re.search(r'积极|乐观|看涨', report_text):
                result['sentiment_level'] = 'positive'
            elif re.search(r'中性|平稳', report_text):
                result['sentiment_level'] = 'neutral'
            elif re.search(r'消极|悲观|看跌', report_text):
                result['sentiment_level'] = 'negative'
            elif re.search(r'非常消极|很悲观', report_text):
                result['sentiment_level'] = 'very_negative'
            else:
                result['sentiment_level'] = 'neutral'
            
            # 提取讨论数量
            discussion_match = re.search(r'讨论[数量:\s]+(\d+)', report_text)
            if discussion_match:
                result['discussion_count'] = int(discussion_match.group(1))
            
            # 提取热门话题（简化版）
            topics_match = re.search(r'热门话题[:：]\s*(.+?)(?:\n|$)', report_text)
            if topics_match:
                topics_text = topics_match.group(1)
                result['hot_topics'] = [t.strip() for t in topics_text.split('、') if t.strip()]
            
            # 估算评分
            result['score'] = ReportParser._estimate_sentiment_score(result)
            
        except Exception as e:
            logger.warning(f"解析情绪报告失败: {e}")
        
        return result
    
    @staticmethod
    def parse_news_report(report_text: str) -> Dict[str, Any]:
        """
        解析新闻分析师报告
        
        Args:
            report_text: 新闻分析报告文本
        
        Returns:
            包含新闻事件和评分的字典
        """
        result = {
            'news_count': 0,
            'positive_ratio': None,
            'negative_ratio': None,
            'key_events': [],
            'score': None
        }
        
        try:
            # 提取新闻数量
            news_match = re.search(r'新闻[数量:\s]+(\d+)', report_text)
            if news_match:
                result['news_count'] = int(news_match.group(1))
            
            # 提取正面新闻比例
            positive_match = re.search(r'正面[新闻]?[比例:\s]+(\d+(?:\.\d+)?)%?', report_text)
            if positive_match:
                result['positive_ratio'] = float(positive_match.group(1)) / 100.0
            
            # 提取负面新闻比例
            negative_match = re.search(r'负面[新闻]?[比例:\s]+(\d+(?:\.\d+)?)%?', report_text)
            if negative_match:
                result['negative_ratio'] = float(negative_match.group(1)) / 100.0
            
            # 提取关键事件（简化版，提取包含"事件"、"公告"等的句子）
            event_pattern = r'[^。]*[事件|公告|发布|披露][^。]*。'
            events = re.findall(event_pattern, report_text)
            result['key_events'] = events[:5]  # 最多5个事件
            
            # 估算评分
            result['score'] = ReportParser._estimate_news_score(result)
            
        except Exception as e:
            logger.warning(f"解析新闻报告失败: {e}")
        
        return result
    
    @staticmethod
    def _estimate_technical_score(data: Dict) -> float:
        """估算技术面评分"""
        score = 50.0  # 基准分
        
        # RSI评分
        if data.get('rsi'):
            rsi = data['rsi']
            if 30 <= rsi <= 70:
                score += 20  # 正常区间
            elif rsi > 70:
                score -= 10  # 超买
            elif rsi < 30:
                score += 15  # 超卖区域，可能反弹
        
        # 趋势评分
        trend = data.get('trend', 'neutral')
        if trend == 'up':
            score += 15
        elif trend == 'down':
            score -= 15
        
        # MACD评分
        if data.get('macd'):
            macd = data['macd']
            if macd > 0:
                score += 10
            else:
                score -= 10
        
        return max(0, min(100, score))
    
    @staticmethod
    def _estimate_fundamental_score(data: Dict) -> float:
        """估算基本面评分"""
        score = 50.0  # 基准分
        
        # PE评分（越低越好，但要在合理区间）
        if data.get('pe'):
            pe = data['pe']
            if 10 <= pe <= 25:
                score += 20  # 合理估值
            elif pe < 10:
                score += 15  # 可能低估
            elif pe > 30:
                score -= 15  # 可能高估
        
        # ROE评分
        if data.get('roe'):
            roe = data['roe']
            if roe > 15:
                score += 20
            elif roe > 10:
                score += 10
            elif roe < 5:
                score -= 15
        
        # PB评分
        if data.get('pb'):
            pb = data['pb']
            if pb < 2:
                score += 10
            elif pb > 5:
                score -= 10
        
        return max(0, min(100, score))
    
    @staticmethod
    def _estimate_sentiment_score(data: Dict) -> float:
        """估算情绪评分"""
        score = 50.0  # 基准分
        
        sentiment_level = data.get('sentiment_level', 'neutral')
        level_scores = {
            'very_positive': 90,
            'positive': 75,
            'neutral': 50,
            'negative': 25,
            'very_negative': 10
        }
        
        if sentiment_level in level_scores:
            score = level_scores[sentiment_level]
        
        # 如果有情绪评分，结合使用
        if data.get('sentiment_score'):
            sentiment_score = data['sentiment_score']
            # 将-1到1的评分转换为0-100
            normalized = (sentiment_score + 1) * 50
            score = (score + normalized) / 2
        
        return max(0, min(100, score))
    
    @staticmethod
    def _estimate_news_score(data: Dict) -> float:
        """估算新闻评分"""
        score = 50.0  # 基准分
        
        # 根据正面/负面新闻比例
        if data.get('positive_ratio') and data.get('negative_ratio'):
            positive = data['positive_ratio']
            negative = data['negative_ratio']
            
            if positive > negative:
                score = 50 + (positive - negative) * 50
            else:
                score = 50 - (negative - positive) * 50
        
        return max(0, min(100, score))
    
    @staticmethod
    def parse_analysis_reports(analysis_results: Dict[str, str]) -> Dict[str, Any]:
        """
        解析所有分析报告
        
        Args:
            analysis_results: 包含各分析师报告的字典
        
        Returns:
            结构化的分析数据
        """
        parsed_data = {}
        
        # 解析市场报告
        if 'market_report' in analysis_results:
            parsed_data['technical'] = ReportParser.parse_market_report(
                analysis_results['market_report']
            )
        
        # 解析基本面报告
        if 'fundamentals_report' in analysis_results:
            parsed_data['fundamental'] = ReportParser.parse_fundamentals_report(
                analysis_results['fundamentals_report']
            )
        
        # 解析情绪报告
        if 'sentiment_report' in analysis_results:
            parsed_data['sentiment'] = ReportParser.parse_sentiment_report(
                analysis_results['sentiment_report']
            )
        
        # 解析新闻报告
        if 'news_report' in analysis_results:
            parsed_data['news'] = ReportParser.parse_news_report(
                analysis_results['news_report']
            )
        
        return parsed_data
