#!/usr/bin/env python3
"""
增强版数据下载器
支持Parquet缓存、增量更新、数据验证
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import time

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

from tradingagents.utils.logging_init import get_logger
from tradingagents.dataflows.a_share_downloader import AShareDownloader

logger = get_logger('dataflows.data_downloader')


class DataDownloader:
    """
    增强版数据下载器
    支持本地缓存（Parquet）、增量更新、数据验证
    """
    
    def __init__(
        self,
        save_path: str = "data/stock_daily.parquet",
        cache_dir: str = "data/cache",
        provider: str = "tushare"
    ):
        """
        初始化数据下载器
        
        Args:
            save_path: 主数据文件路径（Parquet格式）
            cache_dir: 缓存目录
            provider: 数据提供商（tushare/akshare）
        """
        self.save_path = Path(save_path)
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.provider = provider
        
        # 初始化数据提供商
        if provider == "tushare":
            try:
                from tradingagents.dataflows.tushare_adapter import get_tushare_adapter
                adapter = get_tushare_adapter()
                if adapter.provider and adapter.provider.connected:
                    self.pro = adapter.provider.pro_api
                    self.provider_available = True
                else:
                    self.pro = None
                    self.provider_available = False
            except Exception as e:
                logger.warning(f"⚠️ Tushare初始化失败: {e}")
                self.pro = None
                self.provider_available = False
        else:
            self.pro = None
            self.provider_available = False
        
        # A股基础数据下载器（用于获取股票列表）
        self.basic_downloader = AShareDownloader()
        
        logger.info(f"✅ DataDownloader初始化完成 (provider={provider}, parquet={PARQUET_AVAILABLE})")
    
    def _load_existing_data(self) -> pd.DataFrame:
        """加载现有数据"""
        if not PARQUET_AVAILABLE:
            # 降级到CSV
            csv_path = str(self.save_path).replace('.parquet', '.csv')
            if os.path.exists(csv_path):
                return pd.read_csv(csv_path, parse_dates=['trade_date'])
            return pd.DataFrame()
        
        if not self.save_path.exists():
            return pd.DataFrame()
        
        try:
            return pq.read_table(self.save_path).to_pandas()
        except Exception as e:
            logger.warning(f"⚠️ 读取Parquet失败，尝试CSV: {e}")
            csv_path = str(self.save_path).replace('.parquet', '.csv')
            if os.path.exists(csv_path):
                return pd.read_csv(csv_path, parse_dates=['trade_date'])
            return pd.DataFrame()
    
    def _save_data(self, df: pd.DataFrame, mode: str = "overwrite"):
        """保存数据到Parquet或CSV"""
        if df.empty:
            return
        
        if PARQUET_AVAILABLE:
            try:
                if mode == "append" and self.save_path.exists():
                    # 读取现有数据并合并
                    existing = self._load_existing_data()
                    if not existing.empty:
                        # 合并并去重
                        combined = pd.concat([existing, df], ignore_index=True)
                        combined = combined.drop_duplicates(
                            subset=['ts_code', 'trade_date'],
                            keep='last'
                        ).sort_values(['ts_code', 'trade_date'])
                        df = combined
                
                table = pa.Table.from_pandas(df)
                pq.write_table(table, self.save_path)
                logger.info(f"✅ 数据已保存到Parquet: {len(df)} 条记录")
                return
            except Exception as e:
                logger.warning(f"⚠️ Parquet保存失败，降级到CSV: {e}")
        
        # 降级到CSV
        csv_path = str(self.save_path).replace('.parquet', '.csv')
        if mode == "append" and os.path.exists(csv_path):
            existing = pd.read_csv(csv_path, parse_dates=['trade_date'])
            df = pd.concat([existing, df], ignore_index=True)
            df = df.drop_duplicates(
                subset=['ts_code', 'trade_date'],
                keep='last'
            ).sort_values(['ts_code', 'trade_date'])
        
        df.to_csv(csv_path, index=False)
        logger.info(f"✅ 数据已保存到CSV: {len(df)} 条记录")
    
    def update_daily(
        self,
        code_list: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        更新每日数据
        
        Args:
            code_list: 股票代码列表，None表示更新所有
            start_date: 开始日期（YYYYMMDD），None表示从最新数据继续
            end_date: 结束日期（YYYYMMDD），None表示今天
            force_refresh: 是否强制刷新（忽略缓存）
        
        Returns:
            更新的数据DataFrame
        """
        if not self.provider_available:
            logger.error("❌ 数据提供商未就绪，请检查配置")
            return pd.DataFrame()
        
        # 加载现有数据
        existing_data = self._load_existing_data() if not force_refresh else pd.DataFrame()
        
        # 确定更新的股票列表
        if code_list is None:
            # 获取所有A股代码
            basic_info = self.basic_downloader.download_all_stocks(use_cache=True)
            if basic_info.empty:
                logger.error("❌ 无法获取股票列表")
                return pd.DataFrame()
            code_list = basic_info['ts_code'].tolist()
            logger.info(f"📋 获取到 {len(code_list)} 只股票")
        
        # 确定日期范围
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        if start_date is None:
            if not existing_data.empty:
                # 从最新数据继续
                latest_date = existing_data['trade_date'].max()
                if isinstance(latest_date, pd.Timestamp):
                    start_date = (latest_date + timedelta(days=1)).strftime('%Y%m%d')
                else:
                    start_date = (pd.to_datetime(latest_date) + timedelta(days=1)).strftime('%Y%m%d')
            else:
                # 默认下载最近一年
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        logger.info(f"📥 开始更新数据: {len(code_list)} 只股票, {start_date} 到 {end_date}")
        
        # 分批下载
        all_data = []
        batch_size = 500
        total_batches = (len(code_list) + batch_size - 1) // batch_size
        
        for i in range(0, len(code_list), batch_size):
            batch = code_list[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"⏳ 批次 {batch_num}/{total_batches}: 处理 {len(batch)} 只股票")
            
            for code in batch:
                try:
                    # 检查缓存
                    cache_file = self.cache_dir / f"{code}_{start_date}_{end_date}.parquet"
                    if not force_refresh and cache_file.exists():
                        try:
                            cached_df = pq.read_table(cache_file).to_pandas()
                            if not cached_df.empty:
                                all_data.append(cached_df)
                                continue
                        except:
                            pass
                    
                    # 从API获取（带重试）
                    max_retries = 3
                    df = None
                    
                    for attempt in range(max_retries):
                        try:
                            df = self.pro.daily(
                                ts_code=code,
                                start_date=start_date,
                                end_date=end_date
                            )
                            
                            # 成功获取数据，退出重试循环
                            break
                            
                        except Exception as api_error:
                            error_msg = str(api_error)
                            
                            # 检查是否是频率限制错误
                            if "Too Many Requests" in error_msg or "Rate limited" in error_msg or "频率限制" in error_msg:
                                if attempt < max_retries - 1:
                                    # 指数退避：2秒、4秒、6秒
                                    wait_time = 2 * (attempt + 1)
                                    logger.warning(f"⏳ {code} 频率限制，等待{wait_time}秒后重试...")
                                    time.sleep(wait_time)
                                    continue
                                else:
                                    logger.error(f"❌ {code} 达到最大重试次数，跳过")
                                    df = None
                                    break
                            else:
                                # 其他错误，直接退出
                                logger.error(f"❌ {code} API错误: {error_msg}")
                                df = None
                                break
                    
                    if df is not None and not df.empty:
                        # 标准化列名
                        df['ts_code'] = code
                        df['trade_date'] = pd.to_datetime(df['trade_date'])
                        
                        # 缓存到本地
                        if PARQUET_AVAILABLE:
                            try:
                                table = pa.Table.from_pandas(df)
                                pq.write_table(table, cache_file)
                            except:
                                pass
                        
                        all_data.append(df)
                    
                    # 控制请求频率（Tushare要求间隔0.2秒以上）
                    time.sleep(0.3)
                    
                except Exception as e:
                    logger.warning(f"⚠️ {code} 下载失败: {e}")
                    continue
        
        if not all_data:
            logger.warning("⚠️ 未获取到任何数据")
            return pd.DataFrame()
        
        # 合并所有数据
        result = pd.concat(all_data, ignore_index=True)
        result = result.drop_duplicates(subset=['ts_code', 'trade_date'], keep='last')
        
        # 数据验证
        result = self._validate_data(result)
        
        # 保存到主文件
        self._save_data(result, mode="append")
        
        logger.info(f"✅ 数据更新完成: {len(result)} 条新记录")
        return result
    
    def _validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证数据完整性"""
        if df.empty:
            return df
        
        # 检查必需列
        required_cols = ['ts_code', 'trade_date', 'close']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"⚠️ 数据缺少列: {missing_cols}")
            return pd.DataFrame()
        
        # 删除异常数据
        original_len = len(df)
        
        # 删除价格为0或负数的记录
        if 'close' in df.columns:
            df = df[df['close'] > 0]
        
        # 删除交易量为负数的记录
        if 'vol' in df.columns:
            df = df[df['vol'] >= 0]
        
        # 删除重复记录
        df = df.drop_duplicates(subset=['ts_code', 'trade_date'], keep='last')
        
        removed = original_len - len(df)
        if removed > 0:
            logger.info(f"🧹 数据验证: 删除了 {removed} 条异常记录")
        
        return df
    
    def get_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取单只股票的数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
        
        Returns:
            股票数据DataFrame
        """
        # 先从主文件加载
        existing = self._load_existing_data()
        
        if not existing.empty:
            # 过滤指定股票
            stock_data = existing[existing['ts_code'] == symbol].copy()
            
            # 按日期过滤
            if start_date:
                start = pd.to_datetime(start_date)
                stock_data = stock_data[stock_data['trade_date'] >= start]
            
            if end_date:
                end = pd.to_datetime(end_date)
                stock_data = stock_data[stock_data['trade_date'] <= end]
            
            if not stock_data.empty:
                logger.info(f"✅ 从缓存加载 {symbol}: {len(stock_data)} 条记录")
                return stock_data.sort_values('trade_date')
        
        # 缓存未命中，从API获取
        logger.info(f"📥 从API获取 {symbol} 数据...")
        return self.update_daily([symbol], start_date, end_date, force_refresh=False)
    
    def check_data_completeness(
        self,
        code_list: Optional[List[str]] = None,
        target_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        检查数据完整性
        
        Args:
            code_list: 股票代码列表
            target_date: 目标日期（YYYYMMDD），None表示最新日期
        
        Returns:
            数据完整性报告
        """
        if code_list is None:
            basic_info = self.basic_downloader.download_all_stocks(use_cache=True)
            code_list = basic_info['ts_code'].tolist()
        
        existing = self._load_existing_data()
        
        if existing.empty:
            return pd.DataFrame({
                'ts_code': code_list,
                'has_data': False,
                'latest_date': None,
                'record_count': 0
            })
        
        if target_date:
            target = pd.to_datetime(target_date)
        else:
            target = existing['trade_date'].max()
        
        report = []
        for code in code_list:
            stock_data = existing[existing['ts_code'] == code]
            has_data = not stock_data.empty
            latest_date = stock_data['trade_date'].max() if has_data else None
            record_count = len(stock_data)
            
            report.append({
                'ts_code': code,
                'has_data': has_data,
                'latest_date': latest_date,
                'record_count': record_count,
                'is_up_to_date': latest_date >= target if latest_date else False
            })
        
        return pd.DataFrame(report)


def get_data_downloader(
    save_path: str = "data/stock_daily.parquet",
    provider: str = "tushare"
) -> DataDownloader:
    """获取数据下载器实例"""
    return DataDownloader(save_path=save_path, provider=provider)

