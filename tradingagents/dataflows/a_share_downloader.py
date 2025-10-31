#!/usr/bin/env python3
"""
A股基础数据下载器
批量下载并存储A股基本信息（代码、名称、市盈率、市值等）
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import time

from tradingagents.utils.logging_init import get_logger

logger = get_logger('dataflows.a_share_downloader')


class AShareDownloader:
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化A股数据下载器
        
        Args:
            db_path: SQLite数据库路径，默认在项目data目录
        """
        if db_path is None:
            base = Path(__file__).resolve().parents[2]
            db_path = base / "data" / "a_share_basic.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 股票基本信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_basic (
                ts_code TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                area TEXT,
                industry TEXT,
                market TEXT,
                list_date TEXT,
                pe REAL,
                pb REAL,
                total_mv REAL,
                circ_mv REAL,
                update_time TEXT NOT NULL
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON stock_basic(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON stock_basic(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_industry ON stock_basic(industry)")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ 数据库初始化完成: {self.db_path}")

    def download_all_stocks(self, use_cache: bool = True) -> pd.DataFrame:
        """
        下载所有A股基本信息
        
        Args:
            use_cache: 是否使用缓存（检查更新时间）
        
        Returns:
            包含所有股票信息的DataFrame
        """
        try:
            # 尝试使用Tushare
            from tradingagents.dataflows.tushare_adapter import get_tushare_adapter
            adapter = get_tushare_adapter()
            
            if not adapter.provider or not adapter.provider.connected:
                logger.warning("⚠️ Tushare未连接，尝试使用备用数据源")
                return self._download_fallback()
            
            # 获取股票基本信息
            logger.info("📥 开始下载A股基本信息...")
            pro = adapter.provider.pro_api
            
            # 获取股票列表
            stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,market,list_date')
            
            if stock_list.empty:
                logger.warning("⚠️ 未获取到股票列表")
                return pd.DataFrame()
            
            logger.info(f"✅ 获取到 {len(stock_list)} 只股票基本信息")
            
            # 获取每日指标（包含PE、PB、市值）
            logger.info("📥 获取每日指标数据（PE、PB、市值）...")
            
            # 分批获取，避免API限制
            all_data = []
            batch_size = 500
            today = datetime.now().strftime('%Y%m%d')
            
            for i in range(0, len(stock_list), batch_size):
                batch = stock_list.iloc[i:i+batch_size]
                ts_codes = ','.join(batch['ts_code'].tolist())
                
                try:
                    # 获取每日指标
                    daily_basic = pro.daily_basic(
                        trade_date=today,
                        ts_code=ts_codes,
                        fields='ts_code,pe,pb,total_mv,circ_mv'
                    )
                    
                    # 合并数据
                    merged = batch.merge(daily_basic, on='ts_code', how='left')
                    all_data.append(merged)
                    
                    time.sleep(0.2)  # 控制请求频率
                    
                    if (i + batch_size) % 1000 == 0:
                        logger.info(f"⏳ 已处理 {i + batch_size}/{len(stock_list)} 只股票")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 批次 {i//batch_size + 1} 获取失败: {e}")
                    # 即使失败也保存基本信息
                    all_data.append(batch)
            
            # 合并所有数据
            if all_data:
                result = pd.concat(all_data, ignore_index=True)
                result['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 填充缺失值
                result['pe'] = pd.to_numeric(result['pe'], errors='coerce')
                result['pb'] = pd.to_numeric(result['pb'], errors='coerce')
                result['total_mv'] = pd.to_numeric(result['total_mv'], errors='coerce')
                result['circ_mv'] = pd.to_numeric(result['circ_mv'], errors='coerce')
                
                # 保存到数据库
                self.save_to_db(result)
                
                logger.info(f"✅ 成功下载并保存 {len(result)} 只股票数据")
                return result
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}", exc_info=True)
            return self._download_fallback()

    def _download_fallback(self) -> pd.DataFrame:
        """备用下载方法（使用AKShare等）"""
        try:
            import akshare as ak
            logger.info("📥 使用AKShare作为备用数据源...")
            
            # 获取A股股票列表
            stock_info = ak.stock_info_a_code_name()
            
            if stock_info.empty:
                return pd.DataFrame()
            
            # 重命名列以匹配标准格式
            result = pd.DataFrame({
                'ts_code': '',
                'symbol': stock_info['code'],
                'name': stock_info['name'],
                'area': '',
                'industry': '',
                'market': '',
                'list_date': '',
                'pe': None,
                'pb': None,
                'total_mv': None,
                'circ_mv': None,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            # 尝试获取行业信息
            try:
                for idx, row in result.iterrows():
                    code = row['symbol']
                    try:
                        # 获取个股基本信息
                        info = ak.stock_individual_info_em(symbol=code)
                        if not info.empty:
                            industry = info[info['item'] == '行业']['value'].values
                            if len(industry) > 0:
                                result.loc[idx, 'industry'] = industry[0]
                        time.sleep(0.1)  # 控制频率
                    except:
                        continue
            except Exception as e:
                logger.warning(f"⚠️ 获取行业信息失败: {e}")
            
            # 保存到数据库
            self.save_to_db(result)
            
            logger.info(f"✅ 使用AKShare下载了 {len(result)} 只股票数据")
            return result
            
        except Exception as e:
            logger.error(f"❌ 备用下载方法也失败: {e}")
            return pd.DataFrame()

    def save_to_db(self, data: pd.DataFrame):
        """保存数据到SQLite数据库"""
        if data.empty:
            return
        
        conn = sqlite3.connect(str(self.db_path))
        
        # 先删除旧数据（可选：改为更新模式）
        # conn.execute("DELETE FROM stock_basic")
        
        # 插入或更新数据
        data.to_sql('stock_basic', conn, if_exists='replace', index=False)
        
        conn.commit()
        conn.close()
        logger.info(f"✅ 数据已保存到数据库: {len(data)} 条记录")

    def search_stocks(self, 
                     keyword: Optional[str] = None,
                     industry: Optional[str] = None,
                     min_market_cap: Optional[float] = None,
                     max_pe: Optional[float] = None,
                     max_pb: Optional[float] = None,
                     limit: int = 100) -> pd.DataFrame:
        """
        搜索股票
        
        Args:
            keyword: 关键字（代码或名称）
            industry: 行业筛选
            min_market_cap: 最小市值（亿元）
            max_pe: 最大市盈率
            max_pb: 最大市净率
            limit: 返回数量限制
        
        Returns:
            符合条件的股票DataFrame
        """
        conn = sqlite3.connect(str(self.db_path))
        
        query = "SELECT * FROM stock_basic WHERE 1=1"
        params = []
        
        if keyword:
            query += " AND (symbol LIKE ? OR name LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        
        if industry:
            query += " AND industry LIKE ?"
            params.append(f"%{industry}%")
        
        if min_market_cap:
            query += " AND (total_mv >= ? OR total_mv IS NULL)"
            params.append(min_market_cap * 1e8)  # 转换为元
        
        if max_pe:
            query += " AND (pe <= ? OR pe IS NULL)"
            params.append(max_pe)
        
        if max_pb:
            query += " AND (pb <= ? OR pb IS NULL)"
            params.append(max_pb)
        
        query += f" ORDER BY update_time DESC LIMIT {limit}"
        
        result = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return result

    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """获取单只股票的详细信息"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM stock_basic WHERE symbol = ?",
            (symbol,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = ['ts_code', 'symbol', 'name', 'area', 'industry', 'market',
                      'list_date', 'pe', 'pb', 'total_mv', 'circ_mv', 'update_time']
            return dict(zip(columns, row))
        
        return None

    def update_stock_data(self, symbols: List[str]) -> pd.DataFrame:
        """更新指定股票的最新数据"""
        # 实现增量更新逻辑
        # 可以调用download_all_stocks或只更新特定股票
        pass


def get_downloader(db_path: Optional[str] = None) -> AShareDownloader:
    """获取下载器实例"""
    return AShareDownloader(db_path)

