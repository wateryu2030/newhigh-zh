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
        """
        备用下载方法（使用AKShare等）
        优化：批量获取，减少API调用
        """
        try:
            import akshare as ak
            logger.info("📥 使用AKShare作为备用数据源...")
            
            # 方法1：尝试使用 spot_em 接口（更快，一次性获取所有A股实时数据）
            try:
                logger.info("📊 尝试使用 ak.stock_zh_a_spot_em() 批量获取...")
                # 添加重试机制
                max_retries = 3
                delay = 2
                stock_spot = None
                for attempt in range(max_retries):
                    try:
                        stock_spot = ak.stock_zh_a_spot_em()
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"⚠️ 第 {attempt + 1} 次尝试失败: {e}, {delay}秒后重试...")
                            time.sleep(delay)
                            delay *= 2
                        else:
                            raise
                
                if not stock_spot.empty:
                    logger.info(f"✅ 通过spot接口获取到 {len(stock_spot)} 只股票")
                    
                    # 映射列名
                    column_mapping = {
                        '代码': 'symbol',
                        '名称': 'name',
                        '最新价': 'close',
                        '涨跌幅': 'pct_chg',
                        '涨跌额': 'change',
                        '成交量': 'volume',
                        '成交额': 'amount',
                        '市盈率-动态': 'pe',
                        '市净率': 'pb',
                        '总市值': 'total_mv',
                        '流通市值': 'circ_mv'
                    }
                    
                    result = pd.DataFrame()
                    for old_col, new_col in column_mapping.items():
                        if old_col in stock_spot.columns:
                            result[new_col] = stock_spot[old_col]
                    
                    # 如果没有从spot获取到行业，尝试从其他接口
                    if 'industry' not in result.columns:
                        # 获取行业信息（可选，较慢）
                        logger.info("📊 获取行业信息...")
                        try:
                            # 使用股票信息接口批量获取行业
                            stock_info_all = ak.stock_info_a_code_name()
                            # 合并行业信息（如果有）
                            # 注意：这个接口可能不包含行业，需要逐个查询
                            # 为了速度，我们跳过详细行业获取，使用空值
                            result['industry'] = ''
                        except:
                            result['industry'] = ''
                    
                    # 补齐标准列
                    if 'ts_code' not in result.columns:
                        result['ts_code'] = result['symbol'].apply(lambda x: f"{x}.SH" if x.startswith('6') else f"{x}.SZ")
                    if 'area' not in result.columns:
                        result['area'] = ''
                    if 'market' not in result.columns:
                        result['market'] = result['symbol'].apply(lambda x: 'SH' if x.startswith('6') else 'SZ')
                    if 'list_date' not in result.columns:
                        result['list_date'] = ''
                    if 'pe' not in result.columns:
                        result['pe'] = None
                    if 'pb' not in result.columns:
                        result['pb'] = None
                    if 'total_mv' not in result.columns:
                        result['total_mv'] = None
                    if 'circ_mv' not in result.columns:
                        result['circ_mv'] = None
                    
                    result['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 保存到数据库
                    self.save_to_db(result)
                    logger.info(f"✅ 使用AKShare spot接口下载了 {len(result)} 只股票数据")
                    return result[['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 
                                  'list_date', 'pe', 'pb', 'total_mv', 'circ_mv', 'update_time']]
            
            except Exception as e:
                logger.warning(f"⚠️ spot接口失败，尝试基础接口: {e}")
            
            # 方法2：降级到基础接口
            logger.info("📊 使用基础接口 ak.stock_info_a_code_name()...")
            # 添加重试机制
            max_retries = 3
            delay = 2
            stock_info = None
            for attempt in range(max_retries):
                try:
                    stock_info = ak.stock_info_a_code_name()
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ 第 {attempt + 1} 次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        raise
            
            if stock_info.empty:
                logger.error("❌ AKShare基础接口也返回空数据")
                return pd.DataFrame()
            
            logger.info(f"✅ 获取到 {len(stock_info)} 只股票基本信息")
            
            # 重命名列以匹配标准格式
            result = pd.DataFrame({
                'ts_code': '',
                'symbol': stock_info['code'] if 'code' in stock_info.columns else stock_info.iloc[:, 0],
                'name': stock_info['name'] if 'name' in stock_info.columns else stock_info.iloc[:, 1],
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
            
            # 填充ts_code和market
            result['ts_code'] = result['symbol'].apply(
                lambda x: f"{x}.SH" if str(x).startswith('6') else f"{x}.SZ"
            )
            result['market'] = result['symbol'].apply(
                lambda x: 'SH' if str(x).startswith('6') else 'SZ'
            )
            
            # 注意：为了速度，跳过逐个查询行业信息（5000+股票会非常慢）
            # 如果需要行业信息，可以后续单独批量更新
            logger.info("💡 提示：行业信息未获取（避免5000+次API调用），可使用后续接口补充")
            
            # 保存到数据库
            self.save_to_db(result)
            
            logger.info(f"✅ 使用AKShare基础接口下载了 {len(result)} 只股票数据")
            return result
            
        except ImportError:
            logger.error("❌ AKShare未安装，请运行: pip install akshare")
            return pd.DataFrame()
        except ConnectionError as e:
            logger.error(f"❌ 网络连接错误: {e}")
            logger.info("💡 建议: 检查网络连接，或稍后重试")
            return pd.DataFrame()
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                logger.error(f"❌ 网络连接错误: {e}")
                logger.info("💡 建议: 检查网络连接是否稳定，或稍后重试")
            elif "rate limit" in error_msg.lower() or "频率" in error_msg:
                logger.error(f"❌ 请求频率过高: {e}")
                logger.info("💡 建议: 等待一段时间后重试")
            else:
                logger.error(f"❌ 备用下载方法失败: {e}", exc_info=True)
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

