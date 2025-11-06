"""
BaoStock数据下载模块
只使用BaoStock作为唯一数据源，确保数据完整性
"""
import os
import sys
import time
import signal
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

# Add data_engine directory to path for imports
data_engine_dir = Path(__file__).parent
sys.path.insert(0, str(data_engine_dir))

from utils.logger import setup_logger
from utils.retry import retry
from utils.db_utils import get_engine, upsert_df
from utils.fast_db_writer import fast_upsert_df, AsyncDBWriter

from config import DB_URL, START_DATE, END_DATE, SLEEP_SEC_WEB, DB_WRITE_BATCH_SIZE, CACHE_BATCH_SIZE

import baostock as bs

logger = setup_logger(log_file=os.path.join(os.path.dirname(__file__), "data_cache/update.log"))
engine = get_engine(DB_URL)


# ------------------ 基础信息 ------------------
@retry(tries=5, delay=1.0)
def fetch_stock_basic_info():
    """获取股票基础信息，只保留type=1的股票，排除指数"""
    logger.info("开始获取股票基础信息...")
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    rs = bs.query_stock_basic()
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    
    if not rows:
        bs.logout()
        raise RuntimeError("未获取到股票基础信息")
    
    df = pd.DataFrame(rows, columns=rs.fields)
    bs.logout()
    
    # 过滤：只保留股票（type=1），排除指数（type=2）
    if 'type' in df.columns:
        df = df[df['type'] == '1']
        logger.info(f"过滤后剩余股票: {len(df)} 只（排除了指数）")
    
    # baostock的code转ts_code风格
    def to_ts(code):
        p = str(code).split('.')
        return (p[1] + ('.SH' if p[0]=='sh' else '.SZ')) if len(p)==2 else code
    
    df['ts_code'] = df['code'].map(to_ts)
    
    # 根据实际表结构调整字段（适配现有表结构）
    # 实际表有: code, code_name, ipoDate, outDate, type, status, ts_code
    # 保留原始字段，只添加ts_code
    df = df.drop_duplicates(subset=['ts_code'])
    
    # 使用upsert逻辑，支持增量更新（直接使用原始字段）
    upsert_df(df[['ts_code', 'code', 'code_name', 'ipoDate', 'outDate', 'type', 'status']], 
              "stock_basic_info", engine, if_exists="append")
    logger.info(f"stock_basic_info 写入 {len(df)} 条")
    return df[['ts_code']].dropna()


# ------------------ 日行情（K线+财务指标） ------------------
@retry(tries=5, delay=1.0)
def fetch_market_daily(ts_codes: pd.Series):
    """获取日K线数据，包含PE/PB/PS等财务指标"""
    logger.info(f"开始下载日K行情数据，共{len(ts_codes)}只股票")
    
    # BaoStock标准字段列表
    fields = "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM"
    
    total = 0
    success_count = 0
    failed_count = 0
    failed_codes = []
    processed_count = 0  # 已处理的股票总数（包括成功和失败）
    
    # 使用异步写入器（文件缓存 + 异步批量写入）
    cache_dir = os.path.join(os.path.dirname(__file__), "data_cache", "db_cache")
    market_daily_writer = AsyncDBWriter(
        engine, 
        "stock_market_daily", 
        cache_dir=cache_dir,
        cache_batch_size=CACHE_BATCH_SIZE,
        flush_interval=60  # 60秒自动刷新
    )
    financials_writer = AsyncDBWriter(
        engine,
        "stock_financials",
        cache_dir=cache_dir,
        cache_batch_size=CACHE_BATCH_SIZE,
        flush_interval=60
    )
    
    # 不再需要内存批次，直接使用异步写入器
    
    # 登录状态检查和重新登录
    login_retry_count = 0
    max_login_retries = 3
    
    def ensure_login():
        """确保BaoStock已登录，如果未登录则重新登录"""
        nonlocal login_retry_count
        bs.logout()  # 先登出
        time.sleep(0.5)
        lg = bs.login()
        if lg.error_code != '0':
            login_retry_count += 1
            if login_retry_count >= max_login_retries:
                raise RuntimeError(f"BaoStock登录失败（重试{max_login_retries}次）: {lg.error_msg}")
            logger.warning(f"重新登录失败，{login_retry_count}/{max_login_retries}次重试")
            time.sleep(1)
            return ensure_login()  # 递归重试
        else:
            login_retry_count = 0
            logger.info("✅ 重新登录成功")
    
    # 初始登录
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    # 确保ts_codes是Series格式
    if isinstance(ts_codes, pd.DataFrame):
        ts_codes = ts_codes['ts_code'] if 'ts_code' in ts_codes.columns else ts_codes.iloc[:, 0]
    
    for i, ts_code in enumerate(ts_codes, 0):
        # 转baostock代码风格
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        processed_count += 1  # 每处理一只股票就递增
        
        try:
            # 获取K线数据和财务指标（添加超时保护）
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"查询超时: {ts_code}")
            
            # 设置5秒超时（单只股票查询）
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)  # 5秒超时
            
            try:
                rs = bs.query_history_k_data_plus(
                    code,
                    fields,
                    start_date=START_DATE,
                    end_date=END_DATE,
                    frequency="d",
                    adjustflag="3"
                )
                signal.alarm(0)  # 取消超时
            except TimeoutError:
                logger.warning(f"  ⚠️ {ts_code} ({code}) 查询超时")
                failed_count += 1
                failed_codes.append(ts_code)
                time.sleep(SLEEP_SEC_WEB)
                continue
            except Exception as e:
                signal.alarm(0)  # 取消超时
                raise e
            
            # 检查是否有错误
            if rs.error_code != '0':
                # 如果是"用户未登录"错误，尝试重新登录
                if '未登录' in rs.error_msg or '用户未登录' in rs.error_msg:
                    logger.warning(f"  ⚠️ {ts_code} ({code}) 登录失效，尝试重新登录...")
                    try:
                        ensure_login()
                        # 重新尝试查询
                        rs = bs.query_history_k_data_plus(
                            code,
                            fields,
                            start_date=START_DATE,
                            end_date=END_DATE,
                            frequency="d",
                            adjustflag="3"
                        )
                        if rs.error_code == '0':
                            # 重新登录成功，继续处理
                            pass
                        else:
                            logger.warning(f"  ⚠️ {ts_code} ({code}) 重新登录后查询仍失败: {rs.error_msg}")
                            failed_count += 1
                            failed_codes.append(ts_code)
                            time.sleep(SLEEP_SEC_WEB * 2)
                            continue
                    except Exception as e:
                        logger.error(f"  ❌ {ts_code} ({code}) 重新登录失败: {e}")
                        failed_count += 1
                        failed_codes.append(ts_code)
                        time.sleep(SLEEP_SEC_WEB * 2)
                        continue
                # 如果是网络错误，增加等待时间后重试
                elif '网络接收错误' in rs.error_msg or '接收数据异常' in rs.error_msg:
                    logger.warning(f"  ⚠️ {ts_code} ({code}) 网络错误，等待后重试...")
                    time.sleep(SLEEP_SEC_WEB * 5)  # 网络错误时等待更长时间
                    # 尝试重新登录
                    try:
                        ensure_login()
                        # 重新尝试查询
                        rs = bs.query_history_k_data_plus(
                            code,
                            fields,
                            start_date=START_DATE,
                            end_date=END_DATE,
                            frequency="d",
                            adjustflag="3"
                        )
                        if rs.error_code == '0':
                            # 重试成功，继续处理
                            pass
                        else:
                            logger.warning(f"  ⚠️ {ts_code} ({code}) 重试后仍失败: {rs.error_msg}")
                            failed_count += 1
                            failed_codes.append(ts_code)
                            time.sleep(SLEEP_SEC_WEB * 2)
                            continue
                    except Exception as e:
                        logger.error(f"  ❌ {ts_code} ({code}) 重试失败: {e}")
                        failed_count += 1
                        failed_codes.append(ts_code)
                        time.sleep(SLEEP_SEC_WEB * 2)
                        continue
                else:
                    logger.warning(f"  ⚠️ {ts_code} ({code}) 查询失败: {rs.error_msg}")
                    failed_count += 1
                    failed_codes.append(ts_code)
                    # 优化：失败时短暂休息，避免连续失败
                    time.sleep(SLEEP_SEC_WEB * 2)
                    continue
            
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                # 标准列名映射
                df.rename(columns={
                    "date": "trade_date",
                    "pctChg": "pct_chg",
                    "turn": "turnover_rate"
                }, inplace=True)
                df["ts_code"] = ts_code
                
                # 删除code列
                if 'code' in df.columns:
                    df = df.drop(columns=['code'])
                
                # 确保所有数值列为数值类型
                numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'pct_chg', 'volume', 
                              'amount', 'turnover_rate', 'peTTM', 'pbMRQ', 'psTTM']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # 计算振幅
                df['amplitude'] = ((df['high'] - df['low']) / df['preclose'] * 100).round(2)
                
                # 确保列顺序（匹配数据库）
                expected_fields = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'preclose',
                                 'pct_chg', 'volume', 'amount', 'turnover_rate', 'amplitude', 
                                 'peTTM', 'pbMRQ', 'psTTM']
                for field in expected_fields:
                    if field not in df.columns:
                        df[field] = None
                df = df[expected_fields]
                
                # 直接使用异步写入器（非阻塞）
                market_daily_writer.append(df)
                
                # 同时准备财务数据
                if 'peTTM' in df.columns or 'pbMRQ' in df.columns:
                    df_fin = df[['ts_code', 'trade_date']].copy()
                    if 'peTTM' in df.columns:
                        df_fin['pe'] = df['peTTM']
                    if 'pbMRQ' in df.columns:
                        df_fin['pb'] = df['pbMRQ']
                    if 'psTTM' in df.columns:
                        df_fin['ps'] = df['psTTM']
                    
                    # 补充其他字段
                    for col in ['pcf', 'roe', 'roa', 'eps', 'bps', 'total_mv', 'circ_mv', 
                              'revenue_yoy', 'net_profit_yoy', 'gross_profit_margin']:
                        df_fin[col] = None
                    
                    df_fin = df_fin.dropna(subset=['pe', 'pb'], how='all')
                    if not df_fin.empty:
                        financials_writer.append(df_fin)
                
                total += len(df)
                
                # 添加成功日志（每10只股票记录一次，避免日志过多）
                if success_count % 10 == 0:
                    logger.info(f"  ✅ {ts_code} ({code}) 下载成功，共 {len(df)} 天数据")
                success_count += 1
            else:
                logger.warning(f"  ⚠️ {ts_code} ({code}) 无数据返回")
                failed_count += 1
                failed_codes.append(ts_code)
        except Exception as e:
            logger.error(f"  ❌ {ts_code} ({code}) 下载出错: {e}")
            failed_count += 1
            failed_codes.append(ts_code)
        
        # 每50只股票显示进度，并触发刷新（确保数据及时写入）
        if (i+1) % 50 == 0:
            logger.info(f"日K进度 {i+1}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
            # 触发刷新，确保数据及时写入
            market_daily_writer.flush()
            financials_writer.flush()
        
        # 优化：减少休息时间，只在每200只股票时短暂休息，避免被限流
        if (i+1) % 200 == 0:
            time.sleep(SLEEP_SEC_WEB * 3)  # 每200只休息0.15秒
        else:
            time.sleep(SLEEP_SEC_WEB)  # 正常间隔0.05秒
    
    # 最后刷新所有缓存数据
    logger.info("刷新所有缓存数据...")
    market_daily_writer.flush()
    financials_writer.flush()
    
    # 等待所有异步写入完成
    logger.info("等待异步写入完成...")
    
    # 等待队列清空
    timeout = 300  # 最多等待5分钟
    start_time = time.time()
    while not market_daily_writer.write_queue.empty() or not financials_writer.write_queue.empty():
        if time.time() - start_time > timeout:
            logger.warning("异步写入超时，部分数据可能仍在写入队列中")
            break
        time.sleep(1)
    
    # 停止写入器
    market_daily_writer.stop()
    financials_writer.stop()
    logger.info("异步写入器已停止")
    
    bs.logout()
    logger.info(f"stock_market_daily 共写入 {total} 行")
    logger.info(f"✅ 下载完成: 成功 {success_count} 只，失败 {failed_count} 只")
    if failed_codes:
        logger.warning(f"失败的股票代码（前20个）: {failed_codes[:20]}")
    return total


def main():
    """主函数：下载所有数据"""
    logger.info("🚀 开始更新 A股智能选股基础数据库")
    logger.info(f"抓取窗口: {START_DATE} ~ {END_DATE}")
    
    # 1. 获取基础信息（静态数据，全量更新）
    codes_df = fetch_stock_basic_info()
    
    # 2. 下载日K行情（智能增量更新：优先下载缺失的数据）
    # 检查数据库中已有的股票，只下载缺失的数据
    try:
        from sqlalchemy import text
        # 使用MySQL检查已有数据
        with engine.connect() as conn:
            # 获取已有最新日期的股票列表
            result = conn.execute(text("""
                SELECT DISTINCT ts_code 
                FROM stock_market_daily 
                WHERE trade_date = (SELECT MAX(trade_date) FROM stock_market_daily)
            """))
            existing_codes = set([row[0] for row in result.fetchall()])
            
            # 找出缺失的股票
            all_codes = set(codes_df['ts_code'].tolist())
            missing_codes = all_codes - existing_codes
            
            # 检查BATCH_SIZE设置
            batch_size = os.getenv("BATCH_SIZE", "full")
            
            if missing_codes:
                logger.info(f"发现 {len(missing_codes)} 只股票缺少市场数据，将优先下载")
                missing_df = codes_df[codes_df['ts_code'].isin(missing_codes)]
                fetch_market_daily(missing_df['ts_code'])
            
            # 根据BATCH_SIZE决定是否更新已有股票
            # 如果已经下载了缺失的股票，且BATCH_SIZE=full，则不再重复下载
            # 只有在增量更新模式下才更新已有股票
            if batch_size.lower() in ["none", "null", "full"]:
                # 全量更新模式：如果还有缺失的股票，继续下载；否则只更新已有股票的最新数据（最近30天）
                if missing_codes:
                    logger.info(f"继续下载缺失的股票数据（共{len(missing_codes)}只）")
                else:
                    logger.info(f"所有股票数据已完整，跳过全量更新")
                    # 可以选择性地更新最近几天的数据，但这里先跳过，避免重复下载
            else:
                # 批量更新：只更新指定数量的股票
                try:
                    limit = int(batch_size)
                    # 优先更新缺失的股票，如果还有剩余，再更新已有股票
                    if len(missing_codes) < limit:
                        remaining = limit - len(missing_codes)
                        existing_update_codes = codes_df[~codes_df['ts_code'].isin(missing_codes)].head(remaining)
                        if len(existing_update_codes) > 0:
                            logger.info(f"更新 {remaining} 只已有股票的最新数据")
                            fetch_market_daily(existing_update_codes['ts_code'])
                    logger.info(f"批量更新完成（共更新 {min(limit, len(codes_df))} 只股票）")
                except ValueError:
                    logger.warning(f"BATCH_SIZE值无效: {batch_size}，跳过已有股票更新")
    except Exception as e:
        logger.warning(f"检查已有数据时出错: {e}，将全量下载")
        batch_size = os.getenv("BATCH_SIZE", "full")
        if batch_size.lower() in ["none", "null", "full"]:
            fetch_market_daily(codes_df['ts_code'])
        else:
            try:
                limit = int(batch_size)
                fetch_market_daily(codes_df.head(limit)['ts_code'])
            except ValueError:
                fetch_market_daily(codes_df['ts_code'])
    
    logger.info("✅ 全部完成")


if __name__ == "__main__":
    main()
