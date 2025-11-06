"""
高性能数据库写入工具（支持MySQL和SQLite）
使用文件缓存 + 异步批量写入，大幅提升写入性能
"""
import pandas as pd
import sqlite3
from pathlib import Path
import os
import time
import threading
from typing import Optional
from queue import Queue
from sqlalchemy import create_engine, text
import logging

logger = logging.getLogger(__name__)


class AsyncDBWriter:
    """异步高性能数据库写入器（支持MySQL和SQLite）"""
    
    def __init__(self, engine, table: str, cache_dir: Optional[str] = None, 
                 cache_batch_size: int = 10000, flush_interval: int = 30):
        """
        初始化异步写入器
        
        Args:
            engine: SQLAlchemy engine
            table: 表名
            cache_dir: 缓存目录
            cache_batch_size: 缓存批量大小（条数）
            flush_interval: 自动刷新间隔（秒）
        """
        self.engine = engine
        self.table = table
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data_cache") / "db_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / f"{table}_cache.parquet"
        self.cache_batch_size = cache_batch_size
        self.flush_interval = flush_interval
        
        # 写入队列
        self.write_queue = Queue()
        self.is_running = False
        self.write_thread = None
        self.last_flush_time = time.time()
        
        # 确定唯一键
        if table == 'stock_market_daily':
            self.unique_cols = ['ts_code', 'trade_date']
        elif table in ['stock_financials', 'stock_technical_indicators']:
            self.unique_cols = ['ts_code', 'trade_date']
        elif table == 'stock_basic_info':
            self.unique_cols = ['ts_code']
        else:
            self.unique_cols = []
        
        # 启动异步写入线程
        self.start()
    
    def start(self):
        """启动异步写入线程"""
        if not self.is_running:
            self.is_running = True
            self.write_thread = threading.Thread(target=self._write_worker, daemon=True)
            self.write_thread.start()
            logger.debug(f"启动异步写入线程: {self.table}")
    
    def stop(self):
        """停止异步写入线程"""
        self.is_running = False
        if self.write_thread:
            self.write_thread.join(timeout=10)
    
    def append(self, df: pd.DataFrame):
        """追加数据到缓存（非阻塞）"""
        if df is None or df.empty:
            return
        
        # 追加到Parquet缓存文件
        if self.cache_file.exists():
            try:
                existing_df = pd.read_parquet(self.cache_file)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                # 去重
                if self.unique_cols and all(col in combined_df.columns for col in self.unique_cols):
                    combined_df = combined_df.drop_duplicates(subset=self.unique_cols, keep='last')
            except Exception as e:
                logger.warning(f"读取缓存文件失败，使用新数据: {e}")
                combined_df = df
        else:
            combined_df = df
        
        # 保存到缓存
        try:
            combined_df.to_parquet(self.cache_file, index=False)
        except Exception as e:
            logger.error(f"保存缓存文件失败: {e}")
            return
        
        # 如果缓存达到阈值，立即刷新
        if len(combined_df) >= self.cache_batch_size:
            self.flush()
        # 如果超过刷新间隔，也刷新
        elif time.time() - self.last_flush_time > self.flush_interval:
            self.flush()
    
    def flush(self):
        """将缓存数据写入队列（非阻塞）"""
        if not self.cache_file.exists():
            return
        
        try:
            df = pd.read_parquet(self.cache_file)
            if df.empty:
                return
            
            # 将数据放入写入队列
            self.write_queue.put(df.copy())
            
            # 清空缓存文件
            if self.cache_file.exists():
                self.cache_file.unlink()
            
            self.last_flush_time = time.time()
        except Exception as e:
            logger.error(f"刷新缓存失败: {e}")
    
    def _write_worker(self):
        """异步写入工作线程"""
        while self.is_running:
            try:
                # 从队列获取数据（带超时）
                try:
                    df = self.write_queue.get(timeout=1)
                except:
                    continue
                
                # 批量写入数据库
                self._batch_write(df)
                self.write_queue.task_done()
                
            except Exception as e:
                logger.error(f"异步写入失败: {e}")
                time.sleep(1)
    
    def _batch_write(self, df: pd.DataFrame):
        """批量写入数据库"""
        if df.empty:
            return
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                if self.engine.url.drivername.startswith('mysql'):
                    # MySQL: 使用REPLACE INTO（最快）
                    self._batch_write_mysql(df)
                else:
                    # SQLite: 使用优化的批量写入
                    self._batch_write_sqlite(df)
                return
            except Exception as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"批量写入失败: {e}")
                    raise
    
    def _batch_write_mysql(self, df: pd.DataFrame):
        """MySQL批量写入"""
        temp_table = f"temp_{self.table}_{int(time.time())}"
        
        try:
            # 写入临时表
            df.to_sql(temp_table, con=self.engine, if_exists="replace", index=False, chunksize=5000)
            
            # 获取列名
            columns = df.columns.tolist()
            cols_str = ', '.join([f'`{col}`' for col in columns])
            
            # 使用REPLACE INTO实现upsert
            with self.engine.begin() as conn:
                conn.execute(text(f"REPLACE INTO `{self.table}` ({cols_str}) SELECT {cols_str} FROM `{temp_table}`"))
                conn.execute(text(f"DROP TABLE IF EXISTS `{temp_table}`"))
            
            logger.debug(f"MySQL批量写入完成: {self.table}, {len(df)}条记录")
        except Exception as e:
            # 清理临时表
            try:
                with self.engine.begin() as conn:
                    conn.execute(text(f"DROP TABLE IF EXISTS `{temp_table}`"))
            except:
                pass
            raise
    
    def _batch_write_sqlite(self, df: pd.DataFrame):
        """SQLite批量写入"""
        db_url = str(self.engine.url)
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                db_path = os.path.abspath(db_path)
        else:
            raise ValueError(f"不支持的数据库类型: {db_url}")
        
        conn = sqlite3.connect(db_path, timeout=60.0)
        cursor = conn.cursor()
        
        try:
            # 优化SQLite设置
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            
            # 如果有唯一键，先批量删除
            if self.unique_cols and all(col in df.columns for col in self.unique_cols):
                unique_values = df[self.unique_cols].drop_duplicates()
                if len(unique_values) > 0:
                    # 分批删除
                    batch_size = 500
                    for i in range(0, len(unique_values), batch_size):
                        batch = unique_values.iloc[i:i+batch_size]
                        conditions = []
                        for _, row in batch.iterrows():
                            cond = ' AND '.join([f"{col} = '{row[col]}'" for col in self.unique_cols])
                            conditions.append(f"({cond})")
                        where_clause = ' OR '.join(conditions)
                        cursor.execute(f"DELETE FROM {self.table} WHERE {where_clause}")
            
            # 批量插入
            columns = df.columns.tolist()
            placeholders = ','.join(['?' for _ in columns])
            insert_sql = f"INSERT INTO {self.table} ({','.join(columns)}) VALUES ({placeholders})"
            
            # 分批插入
            chunk_size = 1000
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i+chunk_size]
                values = [tuple(row) for row in chunk.values]
                cursor.executemany(insert_sql, values)
            
            conn.commit()
            logger.debug(f"SQLite批量写入完成: {self.table}, {len(df)}条记录")
        finally:
            conn.close()


def fast_upsert_df(df: pd.DataFrame, table: str, engine, if_exists="append", chunksize=5000):
    """
    快速upsert函数，使用优化的批量写入方式
    支持MySQL和SQLite
    """
    if df is None or df.empty:
        return 0
    
    # MySQL: 使用REPLACE INTO（最快）
    if engine.url.drivername.startswith('mysql'):
        temp_table = f"temp_{table}_{id(df)}"
        df.to_sql(temp_table, con=engine, if_exists="replace", index=False, chunksize=chunksize)
        columns = df.columns.tolist()
        cols_str = ', '.join([f'`{col}`' for col in columns])
        with engine.begin() as conn:
            conn.execute(text(f"REPLACE INTO `{table}` ({cols_str}) SELECT {cols_str} FROM `{temp_table}`"))
            conn.execute(text(f"DROP TABLE IF EXISTS `{temp_table}`"))
        return len(df)
    
    # SQLite: 使用优化的批量写入
    db_url = str(engine.url)
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
    else:
        raise ValueError(f"不支持的数据库类型: {db_url}")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=60.0)
            cursor = conn.cursor()
            
            # 优化SQLite设置
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            
            # 确定唯一键
            if table == 'stock_market_daily':
                unique_cols = ['ts_code', 'trade_date']
            elif table in ['stock_financials', 'stock_technical_indicators']:
                unique_cols = ['ts_code', 'trade_date']
            elif table == 'stock_basic_info':
                unique_cols = ['ts_code']
            else:
                unique_cols = []
            
            # 如果有唯一键，先批量删除
            if unique_cols and all(col in df.columns for col in unique_cols):
                unique_values = df[unique_cols].drop_duplicates()
                if len(unique_values) > 0:
                    # 分批删除
                    batch_size = 500
                    for i in range(0, len(unique_values), batch_size):
                        batch = unique_values.iloc[i:i+batch_size]
                        conditions = []
                        for _, row in batch.iterrows():
                            cond = ' AND '.join([f"{col} = '{row[col]}'" for col in unique_cols])
                            conditions.append(f"({cond})")
                        where_clause = ' OR '.join(conditions)
                        cursor.execute(f"DELETE FROM {table} WHERE {where_clause}")
            
            # 批量插入
            columns = df.columns.tolist()
            placeholders = ','.join(['?' for _ in columns])
            insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
            
            # 分批插入
            chunk_size = 1000
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i+chunk_size]
                values = [tuple(row) for row in chunk.values]
                cursor.executemany(insert_sql, values)
            
            conn.commit()
            conn.close()
            return len(df)
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            else:
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            else:
                raise
        finally:
            try:
                conn.close()
            except:
                pass
