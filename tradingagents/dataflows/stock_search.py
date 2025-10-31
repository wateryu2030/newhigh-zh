#!/usr/bin/env python3
"""
股票搜索接口
提供便捷的股票搜索和查询功能
"""

from typing import Optional, List, Dict
import pandas as pd
from pathlib import Path

from tradingagents.dataflows.a_share_downloader import AShareDownloader, get_downloader


class StockSearcher:
    """股票搜索器"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.downloader = get_downloader(db_path)
    
    def search(self, 
              keyword: Optional[str] = None,
              industry: Optional[str] = None,
              min_market_cap: Optional[float] = None,
              max_pe: Optional[float] = None,
              max_pb: Optional[float] = None,
              limit: int = 100) -> pd.DataFrame:
        """
        搜索股票
        
        Args:
            keyword: 关键字（代码或名称，如"平安"、"000001"）
            industry: 行业（如"银行"、"科技"）
            min_market_cap: 最小市值（亿元）
            max_pe: 最大市盈率
            max_pb: 最大市净率
            limit: 返回数量限制
        
        Returns:
            符合条件的股票DataFrame
        """
        return self.downloader.search_stocks(
            keyword=keyword,
            industry=industry,
            min_market_cap=min_market_cap,
            max_pe=max_pe,
            max_pb=max_pb,
            limit=limit
        )
    
    def get_info(self, symbol: str) -> Optional[Dict]:
        """
        获取单只股票的详细信息
        
        Args:
            symbol: 股票代码（如"000001"）
        
        Returns:
            股票信息字典，包含所有字段
        """
        return self.downloader.get_stock_info(symbol)
    
    def get_stock_list(self, 
                      filters: Optional[Dict] = None,
                      limit: int = 1000) -> List[str]:
        """
        获取股票代码列表
        
        Args:
            filters: 筛选条件字典
            limit: 返回数量限制
        
        Returns:
            股票代码列表
        """
        df = self.search(
            keyword=filters.get('keyword') if filters else None,
            industry=filters.get('industry') if filters else None,
            min_market_cap=filters.get('min_market_cap') if filters else None,
            max_pe=filters.get('max_pe') if filters else None,
            max_pb=filters.get('max_pb') if filters else None,
            limit=limit
        )
        
        return df['symbol'].tolist() if not df.empty else []
    
    def get_industry_list(self) -> List[str]:
        """获取所有行业列表"""
        df = self.downloader.search_stocks(limit=100000)
        if df.empty:
            return []
        
        industries = df['industry'].dropna().unique().tolist()
        return sorted([i for i in industries if i])


def get_searcher(db_path: Optional[str] = None) -> StockSearcher:
    """获取搜索器实例"""
    return StockSearcher(db_path)

