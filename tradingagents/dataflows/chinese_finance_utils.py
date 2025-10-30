#!/usr/bin/env python3
"""
中国财经数据聚合工具
由于微博API申请困难且功能受限，采用多源数据聚合的方式
"""

import requests
import json
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
from bs4 import BeautifulSoup
import pandas as pd

# 导入日志系统
try:
    from tradingagents.utils.logging_init import get_logger
    logger = get_logger('dataflows.chinese_finance')
except:
    import logging
    logger = logging.getLogger('chinese_finance')


class ChineseFinanceDataAggregator:
    """中国财经数据聚合器"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_stock_sentiment_summary(self, ticker: str, days: int = 7) -> Dict:
        """
        获取股票情绪分析汇总
        整合多个可获取的中国财经数据源
        """
        try:
            # 1. 获取财经新闻情绪
            news_sentiment = self._get_finance_news_sentiment(ticker, days)
            
            # 2. 获取股吧讨论热度 (如果可以获取)
            forum_sentiment = self._get_stock_forum_sentiment(ticker, days)
            
            # 3. 获取财经媒体报道
            media_sentiment = self._get_media_coverage_sentiment(ticker, days)
            
            # 4. 综合分析
            overall_sentiment = self._calculate_overall_sentiment(
                news_sentiment, forum_sentiment, media_sentiment
            )
            
            return {
                'ticker': ticker,
                'analysis_period': f'{days} days',
                'overall_sentiment': overall_sentiment,
                'news_sentiment': news_sentiment,
                'forum_sentiment': forum_sentiment,
                'media_sentiment': media_sentiment,
                'summary': self._generate_sentiment_summary(overall_sentiment),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'ticker': ticker,
                'error': f'数据获取失败: {str(e)}',
                'fallback_message': '由于中国社交媒体API限制，建议使用财经新闻和基本面分析作为主要参考',
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_finance_news_sentiment(self, ticker: str, days: int) -> Dict:
        """获取财经新闻情绪分析"""
        try:
            # 搜索相关新闻标题和内容
            company_name = self._get_company_chinese_name(ticker)
            search_terms = [ticker, company_name] if company_name else [ticker]
            
            news_items = []
            for term in search_terms:
                # 这里可以集成多个新闻源
                items = self._search_finance_news(term, days)
                news_items.extend(items)
            
            # 简单的情绪分析
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            
            for item in news_items:
                sentiment = self._analyze_text_sentiment(item.get('title', '') + ' ' + item.get('content', ''))
                if sentiment > 0.1:
                    positive_count += 1
                elif sentiment < -0.1:
                    negative_count += 1
                else:
                    neutral_count += 1
            
            total = len(news_items)
            if total == 0:
                return {'sentiment_score': 0, 'confidence': 0, 'news_count': 0}
            
            sentiment_score = (positive_count - negative_count) / total
            
            return {
                'sentiment_score': sentiment_score,
                'positive_ratio': positive_count / total,
                'negative_ratio': negative_count / total,
                'neutral_ratio': neutral_count / total,
                'news_count': total,
                'confidence': min(total / 10, 1.0)  # 新闻数量越多，置信度越高
            }
            
        except Exception as e:
            return {'error': str(e), 'sentiment_score': 0, 'confidence': 0}
    
    def _get_stock_forum_sentiment(self, ticker: str, days: int) -> Dict:
        """获取股票论坛讨论情绪 - 从东方财富股吧和雪球获取真实数据"""
        try:
            # 判断是否为A股代码（6位数字）
            if not re.match(r'^\d{6}$', ticker):
                # 非A股，返回空数据
                return {
                    'sentiment_score': 0,
                    'discussion_count': 0,
                    'hot_topics': [],
                    'note': f'股票代码 {ticker} 非A股格式，股吧数据仅支持A股',
                    'confidence': 0
                }
            
            # 获取东方财富股吧数据
            forum_data = self._fetch_eastmoney_guba(ticker, days)
            
            # 尝试获取雪球数据作为补充
            xueqiu_data = self._fetch_xueqiu_discussion(ticker, days)
            
            # 合并多个平台的数据
            if xueqiu_data.get('discussion_count', 0) > 0:
                # 合并两个平台的数据
                all_discussions = forum_data.get('discussions', []) + xueqiu_data.get('discussions', [])
                all_hot_topics = forum_data.get('hot_topics', []) + xueqiu_data.get('hot_topics', [])
                
                # 重新计算综合情绪
                if all_discussions:
                    sentiment_scores = []
                    for discussion in all_discussions:
                        content = discussion.get('title', '') + ' ' + discussion.get('content', '')
                        sentiment = self._analyze_text_sentiment(content)
                        sentiment_scores.append(sentiment)
                    
                    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
                    
                    forum_data = {
                        'discussions': all_discussions,
                        'discussion_count': len(all_discussions),
                        'hot_topics': list(set(all_hot_topics))[:15],
                        'source': '东方财富股吧 + 雪球',
                        'platform': '东方财富股吧 + 雪球',
                        'sentiment_score': avg_sentiment
                    }
            
            if not forum_data or forum_data.get('discussion_count', 0) == 0:
                return {
                    'sentiment_score': 0,
                    'discussion_count': 0,
                    'hot_topics': [],
                    'note': '未获取到股吧讨论数据',
                    'confidence': 0
                }
            
            # 分析讨论情绪
            discussions = forum_data.get('discussions', [])
            sentiment_scores = []
            for discussion in discussions:
                content = discussion.get('title', '') + ' ' + discussion.get('content', '')
                sentiment = self._analyze_text_sentiment(content)
                sentiment_scores.append(sentiment)
            
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            
            return {
                'sentiment_score': avg_sentiment,
                'discussion_count': forum_data.get('discussion_count', 0),
                'hot_topics': forum_data.get('hot_topics', [])[:10],  # 前10个热门话题
                'platform': '东方财富股吧',
                'confidence': min(forum_data.get('discussion_count', 0) / 20, 1.0)  # 讨论越多置信度越高
            }
            
        except Exception as e:
            logger.warning(f"⚠️ 获取股吧数据失败: {e}")
            return {
                'sentiment_score': 0,
                'discussion_count': 0,
                'hot_topics': [],
                'note': f'股吧数据获取失败: {str(e)}',
                'confidence': 0
            }
    
    def _fetch_eastmoney_guba(self, ticker: str, days: int) -> Dict:
        """从东方财富股吧获取股票讨论数据"""
        try:
            base_url = "https://guba.eastmoney.com"
            discussions = []
            hot_topics = []
            
            # 方法1: 使用东方财富股吧的JSON API接口
            try:
                # 东方财富股吧实际使用的API接口
                # API格式: https://guba.eastmoney.com/list,{股票代码},f_{页码}.html
                # 但我们可以直接使用JSON API获取数据
                
                # 尝试获取最新的帖子列表（第1页）
                api_url = f"https://guba.eastmoney.com/list,{ticker},f_1.html"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Referer': f'https://quote.eastmoney.com/{ticker}.html',
                    'Connection': 'keep-alive',
                }
                
                response = self.session.get(api_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 东方财富股吧的实际HTML结构
                    # 帖子通常在 <div class="articleh"> 或类似的容器中
                    post_containers = soup.find_all(['div', 'td'], class_=re.compile(r'articleh|title', re.I))
                    
                    # 如果没找到，尝试更通用的选择器
                    if not post_containers:
                        # 查找包含帖子标题的链接
                        post_links = soup.find_all('a', href=re.compile(r'/news,.*\.html'))
                        post_containers = post_links
                    
                    # 如果还是没找到，尝试查找所有包含文本的链接
                    if not post_containers:
                        all_links = soup.find_all('a', href=True)
                        # 过滤出可能是帖子链接的
                        post_containers = [link for link in all_links 
                                          if any(keyword in link.get_text() for keyword in ['讨论', '分析', '公告', '业绩']) 
                                          or len(link.get_text().strip()) > 10]
                    
                    count = 0
                    for container in post_containers[:30]:  # 最多30个帖子
                        try:
                            # 提取标题
                            if hasattr(container, 'get_text'):
                                title = container.get_text(strip=True)
                            elif hasattr(container, 'text'):
                                title = container.text.strip()
                            else:
                                title = str(container).strip()
                            
                            # 提取链接
                            href = ''
                            if hasattr(container, 'get'):
                                href = container.get('href', '')
                            elif hasattr(container, 'find') and container.find('a'):
                                href = container.find('a').get('href', '')
                            
                            # 过滤有效标题
                            if title and len(title) > 5 and len(title) < 200:
                                discussions.append({
                                    'title': title,
                                    'content': title,  # 列表页通常只有标题
                                    'url': f"{base_url}{href}" if href and not href.startswith('http') else (href if href.startswith('http') else ''),
                                    'source': '东方财富股吧'
                                })
                                count += 1
                                
                                # 提取热门话题关键词
                                if any(keyword in title for keyword in ['涨停', '跌停', '利好', '利空', '公告', '业绩', '突破', '回调']):
                                    hot_topics.append(title[:50])  # 限制长度
                        except Exception as e:
                            logger.debug(f"解析单个帖子失败: {e}")
                            continue
                    
                    if discussions:
                        logger.info(f"✅ 从东方财富股吧获取到 {len(discussions)} 条讨论")
                        return {
                            'discussions': discussions,
                            'discussion_count': len(discussions),
                            'hot_topics': list(set(hot_topics))[:15],  # 去重并限制数量
                            'source': '东方财富股吧'
                        }
                    else:
                        logger.warning(f"⚠️ 股吧页面解析成功但未找到有效帖子")
                
            except Exception as e:
                logger.debug(f"股吧API访问失败: {e}")
            
            # 方法2: 尝试使用AKShare获取股票讨论相关的其他信息
            try:
                import akshare as ak
                # AKShare虽然没有直接的股吧API，但可以获取股票公告等信息
                # 这些也可以反映市场讨论热点
                announcements = self._get_stock_announcements_akshare(ticker)
                if announcements:
                    return {
                        'discussions': announcements,
                        'discussion_count': len(announcements),
                        'hot_topics': [a.get('title', '') for a in announcements[:10]],
                        'source': 'AKShare公告数据（补充）'
                    }
            except ImportError:
                pass
            except Exception as e:
                logger.debug(f"AKShare补充数据获取失败: {e}")
            
            # 如果都失败，返回说明
            return {
                'discussions': [],
                'discussion_count': 0,
                'hot_topics': [],
                'note': f'无法直接获取股吧数据，可手动访问: https://guba.eastmoney.com/list,{ticker}.html',
                'source': '东方财富股吧（需要手动访问）'
            }
            
        except Exception as e:
            logger.warning(f"获取股吧数据异常: {e}")
            return {
                'discussions': [],
                'discussion_count': 0,
                'hot_topics': [],
                'error': str(e),
                'source': '东方财富股吧'
            }
    
    def _get_stock_announcements_akshare(self, ticker: str) -> List[Dict]:
        """使用AKShare获取股票公告（可作为讨论热点）"""
        try:
            import akshare as ak
            # 获取股票公告（这些往往会引起讨论）
            # 注意：需要根据AKShare的实际API调整
            announcements = []
            
            # 尝试获取公告数据
            try:
                # AKShare的公告接口（如果存在）
                # 注意：这里需要根据AKShare的实际API文档调整
                announcements_data = ak.stock_notice_report(stock=ticker, indicator="公告")
                if announcements_data is not None and not announcements_data.empty:
                    for _, row in announcements_data.head(10).iterrows():
                        title = str(row.get('公告标题', row.get('title', ''))).strip()
                        if title:
                            announcements.append({
                                'title': title,
                                'content': str(row.get('公告内容', '')),
                                'source': 'AKShare公告',
                                'url': ''
                            })
            except:
                pass
            
            return announcements
        except:
            return []
    
    def _fetch_xueqiu_discussion(self, ticker: str, days: int) -> Dict:
        """从雪球平台获取股票讨论数据"""
        try:
            discussions = []
            hot_topics = []
            
            # 雪球平台的API或页面访问
            # 注意：雪球也有反爬虫机制，需要谨慎处理
            try:
                # 雪球股票讨论页面
                xueqiu_url = f"https://xueqiu.com/S/{ticker}"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Referer': 'https://xueqiu.com/',
                }
                
                response = self.session.get(xueqiu_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 雪球的实际HTML结构可能不同，需要根据实际情况调整
                    # 尝试查找帖子/讨论链接
                    discussion_links = soup.find_all('a', href=re.compile(r'/status/|/article/|/stock/'))
                    
                    for link in discussion_links[:20]:  # 限制数量
                        try:
                            title = link.get_text(strip=True)
                            href = link.get('href', '')
                            
                            if title and len(title) > 5 and len(title) < 200:
                                discussions.append({
                                    'title': title,
                                    'content': title,
                                    'url': f"https://xueqiu.com{href}" if href and not href.startswith('http') else href,
                                    'source': '雪球'
                                })
                                
                                if any(keyword in title for keyword in ['涨', '跌', '利好', '利空', '分析', '观点']):
                                    hot_topics.append(title[:50])
                        except:
                            continue
                    
                    if discussions:
                        logger.info(f"✅ 从雪球获取到 {len(discussions)} 条讨论")
                        return {
                            'discussions': discussions,
                            'discussion_count': len(discussions),
                            'hot_topics': list(set(hot_topics))[:10],
                            'source': '雪球'
                        }
            
            except Exception as e:
                logger.debug(f"雪球数据获取失败: {e}")
            
            return {
                'discussions': [],
                'discussion_count': 0,
                'hot_topics': [],
                'source': '雪球（受限）'
            }
            
        except Exception as e:
            logger.debug(f"雪球数据获取异常: {e}")
            return {
                'discussions': [],
                'discussion_count': 0,
                'hot_topics': [],
                'source': '雪球'
            }
    
    def _get_stock_info_from_akshare(self, ticker: str, days: int) -> Dict:
        """使用AKShare获取股票相关信息作为补充"""
        try:
            import akshare as ak
            # 获取股票基本信息（可以作为讨论的主题）
            stock_info = ak.stock_individual_info_em(symbol=ticker)
            if stock_info is not None and not stock_info.empty:
                return {
                    'discussions': [{
                        'title': f'{ticker}股票信息',
                        'content': '通过AKShare获取的股票信息',
                        'source': 'AKShare'
                    }],
                    'discussion_count': 1,
                    'hot_topics': [],
                    'source': 'AKShare补充数据'
                }
        except:
            pass
        return {
            'discussions': [],
            'discussion_count': 0,
            'hot_topics': [],
            'source': 'AKShare'
        }
    
    def _get_media_coverage_sentiment(self, ticker: str, days: int) -> Dict:
        """获取媒体报道情绪"""
        try:
            # 可以集成RSS源或公开的财经API
            coverage_items = self._get_media_coverage(ticker, days)
            
            if not coverage_items:
                return {'sentiment_score': 0, 'coverage_count': 0, 'confidence': 0}
            
            # 分析媒体报道的情绪倾向
            sentiment_scores = []
            for item in coverage_items:
                score = self._analyze_text_sentiment(item.get('title', '') + ' ' + item.get('summary', ''))
                sentiment_scores.append(score)
            
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            
            return {
                'sentiment_score': avg_sentiment,
                'coverage_count': len(coverage_items),
                'confidence': min(len(coverage_items) / 5, 1.0)
            }
            
        except Exception as e:
            return {'error': str(e), 'sentiment_score': 0, 'confidence': 0}
    
    def _search_finance_news(self, search_term: str, days: int) -> List[Dict]:
        """搜索财经新闻 (示例实现)"""
        # 这里可以集成多个新闻源的API或RSS
        # 例如：财联社、新浪财经、东方财富等
        
        # 模拟返回数据结构
        return [
            {
                'title': f'{search_term}相关财经新闻标题',
                'content': '新闻内容摘要...',
                'source': '财联社',
                'publish_time': datetime.now().isoformat(),
                'url': 'https://example.com/news/1'
            }
        ]
    
    def _get_media_coverage(self, ticker: str, days: int) -> List[Dict]:
        """获取媒体报道 (示例实现)"""
        # 可以集成Google News API或其他新闻聚合服务
        return []
    
    def _analyze_text_sentiment(self, text: str) -> float:
        """简单的中文文本情绪分析"""
        if not text:
            return 0
        
        # 简单的关键词情绪分析
        positive_words = ['上涨', '增长', '利好', '看好', '买入', '推荐', '强势', '突破', '创新高']
        negative_words = ['下跌', '下降', '利空', '看空', '卖出', '风险', '跌破', '创新低', '亏损']
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count + negative_count == 0:
            return 0
        
        return (positive_count - negative_count) / (positive_count + negative_count)
    
    def _get_company_chinese_name(self, ticker: str) -> Optional[str]:
        """获取公司中文名称"""
        # 简单的映射表，实际可以从数据库或API获取
        name_mapping = {
            'AAPL': '苹果',
            'TSLA': '特斯拉',
            'NVDA': '英伟达',
            'MSFT': '微软',
            'GOOGL': '谷歌',
            'AMZN': '亚马逊'
        }
        return name_mapping.get(ticker.upper())
    
    def _calculate_overall_sentiment(self, news_sentiment: Dict, forum_sentiment: Dict, media_sentiment: Dict) -> Dict:
        """计算综合情绪分析"""
        # 根据各数据源的置信度加权计算
        news_weight = news_sentiment.get('confidence', 0)
        forum_weight = forum_sentiment.get('confidence', 0)
        media_weight = media_sentiment.get('confidence', 0)
        
        total_weight = news_weight + forum_weight + media_weight
        
        if total_weight == 0:
            return {'sentiment_score': 0, 'confidence': 0, 'level': 'neutral'}
        
        weighted_sentiment = (
            news_sentiment.get('sentiment_score', 0) * news_weight +
            forum_sentiment.get('sentiment_score', 0) * forum_weight +
            media_sentiment.get('sentiment_score', 0) * media_weight
        ) / total_weight
        
        # 确定情绪等级
        if weighted_sentiment > 0.3:
            level = 'very_positive'
        elif weighted_sentiment > 0.1:
            level = 'positive'
        elif weighted_sentiment > -0.1:
            level = 'neutral'
        elif weighted_sentiment > -0.3:
            level = 'negative'
        else:
            level = 'very_negative'
        
        return {
            'sentiment_score': weighted_sentiment,
            'confidence': total_weight / 3,  # 平均置信度
            'level': level
        }
    
    def _generate_sentiment_summary(self, overall_sentiment: Dict) -> str:
        """生成情绪分析摘要"""
        level = overall_sentiment.get('level', 'neutral')
        score = overall_sentiment.get('sentiment_score', 0)
        confidence = overall_sentiment.get('confidence', 0)
        
        level_descriptions = {
            'very_positive': '非常积极',
            'positive': '积极',
            'neutral': '中性',
            'negative': '消极',
            'very_negative': '非常消极'
        }
        
        description = level_descriptions.get(level, '中性')
        confidence_level = '高' if confidence > 0.7 else '中' if confidence > 0.3 else '低'
        
        return f"市场情绪: {description} (评分: {score:.2f}, 置信度: {confidence_level})"


def get_chinese_social_sentiment(ticker: str, curr_date: str) -> str:
    """
    获取中国社交媒体情绪分析的主要接口函数
    """
    aggregator = ChineseFinanceDataAggregator()
    
    try:
        # 获取情绪分析数据
        sentiment_data = aggregator.get_stock_sentiment_summary(ticker, days=7)
        
        # 格式化输出
        if 'error' in sentiment_data:
            return f"""
中国市场情绪分析报告 - {ticker}
分析日期: {curr_date}

⚠️ 数据获取限制说明:
{sentiment_data.get('fallback_message', '数据获取遇到技术限制')}

建议:
1. 重点关注财经新闻和基本面分析
2. 参考官方财报和业绩指导
3. 关注行业政策和监管动态
4. 考虑国际市场情绪对中概股的影响

注: 由于中国社交媒体平台API限制，当前主要依赖公开财经数据源进行分析。
"""
        
        overall = sentiment_data.get('overall_sentiment', {})
        news = sentiment_data.get('news_sentiment', {})
        forum = sentiment_data.get('forum_sentiment', {})
        
        # 构建报告
        report_lines = [
            f"中国市场情绪分析报告 - {ticker}",
            f"分析日期: {curr_date}",
            f"分析周期: {sentiment_data.get('analysis_period', '7天')}",
            "",
            f"📊 综合情绪评估:",
            f"{sentiment_data.get('summary', '数据不足')}",
            "",
            f"📰 财经新闻情绪:",
            f"- 情绪评分: {news.get('sentiment_score', 0):.2f}",
            f"- 正面新闻比例: {news.get('positive_ratio', 0):.1%}",
            f"- 负面新闻比例: {news.get('negative_ratio', 0):.1%}",
            f"- 新闻数量: {news.get('news_count', 0)}条",
        ]
        
        # 添加股吧讨论数据（如果有）
        if forum.get('discussion_count', 0) > 0:
            report_lines.extend([
                "",
                f"💬 股吧讨论情绪 ({forum.get('platform', '东方财富股吧')}):",
                f"- 情绪评分: {forum.get('sentiment_score', 0):.2f}",
                f"- 讨论数量: {forum.get('discussion_count', 0)}条",
                f"- 数据来源: {forum.get('platform', '东方财富股吧')}",
            ])
            
            hot_topics = forum.get('hot_topics', [])
            if hot_topics:
                report_lines.append(f"- 热门话题: {len(hot_topics)}个")
                report_lines.append("  最近热门讨论:")
                for topic in hot_topics[:5]:  # 只显示前5个
                    report_lines.append(f"    • {topic[:60]}...")
        
        report_lines.extend([
            "",
            "💡 投资建议:",
            "基于当前可获取的中国市场数据，建议投资者:",
            "1. 密切关注官方财经媒体报道",
            "2. 重视基本面分析和财务数据",
            "3. 参考股吧投资者讨论（需结合基本面）",
            "4. 考虑政策环境对股价的影响",
            "",
            f"生成时间: {sentiment_data.get('timestamp', datetime.now().isoformat())}",
        ])
        
        return "\n".join(report_lines)
        
    except Exception as e:
        return f"""
中国市场情绪分析 - {ticker}
分析日期: {curr_date}

❌ 分析失败: {str(e)}

💡 替代建议:
1. 查看财经新闻网站的相关报道
2. 关注雪球、东方财富等投资社区讨论
3. 参考专业机构的研究报告
4. 重点分析基本面和技术面数据

注: 中国社交媒体数据获取存在技术限制，建议以基本面分析为主。
"""
