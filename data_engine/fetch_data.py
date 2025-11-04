"""
BaoStock数据下载模块
只使用BaoStock作为唯一数据源，确保数据完整性
"""
import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

# Add data_engine directory to path for imports
data_engine_dir = Path(__file__).parent
sys.path.insert(0, str(data_engine_dir))

from utils.logger import setup_logger
from utils.retry import retry
from utils.db_utils import get_engine, upsert_df

from config import DB_URL, START_DATE, END_DATE, SLEEP_SEC_WEB

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
    
    # 字段映射
    column_mapping = {
        'code_name': 'name',
        'ipoDate': 'list_date',
        'outDate': 'delist_date'
    }
    df = df.rename(columns=column_mapping)
    
    # 删除不需要的列
    for col in ['code', 'type', 'status']:
        if col in df.columns:
            df = df.drop(columns=[col])
    
    # 添加缺失列
    for col in ['symbol', 'area', 'industry', 'market', 'is_hs']:
        if col not in df.columns:
            df[col] = None
    
    # 确保列顺序
    expected_fields = ['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 'list_date', 'delist_date', 'is_hs']
    for field in expected_fields:
        if field not in df.columns:
            df[field] = None
    df = df[expected_fields]
    
    df = df.drop_duplicates(subset=['ts_code'])
    # 使用upsert逻辑，支持增量更新
    upsert_df(df, "stock_basic_info", engine, if_exists="append")
    logger.info(f"stock_basic_info 写入 {len(df)} 条")
    return df[['ts_code']].dropna()


# ------------------ 日行情（K线+财务指标） ------------------
@retry(tries=5, delay=1.0)
def fetch_market_daily(ts_codes: pd.Series):
    """获取日K线数据，包含PE/PB/PS等财务指标"""
    logger.info(f"开始下载日K行情数据，共{len(ts_codes)}只股票")
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    # BaoStock标准字段列表
    fields = "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM"
    
    total = 0
    success_count = 0
    failed_count = 0
    failed_codes = []
    
    for i, row in ts_codes.reset_index(drop=True).iterrows():
        ts_code = row['ts_code']
        # 转baostock代码风格
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        try:
            # 获取K线数据和财务指标
            rs = bs.query_history_k_data_plus(
                code,
                fields,
                start_date=START_DATE,
                end_date=END_DATE,
                frequency="d",
                adjustflag="3"
            )
            
            # 检查是否有错误
            if rs.error_code != '0':
                logger.warning(f"  ⚠️ {ts_code} ({code}) 查询失败: {rs.error_msg}")
                failed_count += 1
                failed_codes.append(ts_code)
                time.sleep(SLEEP_SEC_WEB)
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
                
                upsert_df(df, "stock_market_daily", engine, if_exists="append")
                total += len(df)
                
                # 同时将PE/PB/PS数据写入财务表
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
                        upsert_df(df_fin, "stock_financials", engine, if_exists="append")
                success_count += 1
            else:
                logger.warning(f"  ⚠️ {ts_code} ({code}) 无数据返回")
                failed_count += 1
                failed_codes.append(ts_code)
        except Exception as e:
            logger.error(f"  ❌ {ts_code} ({code}) 下载出错: {e}")
            failed_count += 1
            failed_codes.append(ts_code)
        
        if (i+1) % 50 == 0:
            logger.info(f"日K进度 {i+1}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
        
        time.sleep(SLEEP_SEC_WEB)
    
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
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).parent.parent / "data" / "stock_database.db"
        if db_path.exists():
            # 使用超时连接，避免数据库锁定
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            cursor = conn.cursor()
            # 获取已有最新日期的股票列表
            cursor.execute("""
                SELECT DISTINCT ts_code 
                FROM stock_market_daily 
                WHERE trade_date = (SELECT MAX(trade_date) FROM stock_market_daily)
            """)
            existing_codes = set([row[0] for row in cursor.fetchall()])
            conn.close()
            
            # 找出缺失的股票
            all_codes = set(codes_df['ts_code'].tolist())
            missing_codes = all_codes - existing_codes
            
            # 检查BATCH_SIZE设置
            batch_size = os.getenv("BATCH_SIZE", "full")
            
            if missing_codes:
                logger.info(f"发现 {len(missing_codes)} 只股票缺少市场数据，将优先下载")
                missing_df = codes_df[codes_df['ts_code'].isin(missing_codes)]
                fetch_market_daily(missing_df)
            
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
                            fetch_market_daily(existing_update_codes)
                    logger.info(f"批量更新完成（共更新 {min(limit, len(codes_df))} 只股票）")
                except ValueError:
                    logger.warning(f"BATCH_SIZE值无效: {batch_size}，跳过已有股票更新")
        else:
            # 数据库不存在，全量下载
            logger.info(f"数据库不存在，全量下载所有股票日K数据（共{len(codes_df)}只）")
            fetch_market_daily(codes_df)
    except Exception as e:
        logger.warning(f"检查已有数据时出错: {e}，将全量下载")
        batch_size = os.getenv("BATCH_SIZE", "full")
        if batch_size.lower() in ["none", "null", "full"]:
            fetch_market_daily(codes_df)
        else:
            try:
                limit = int(batch_size)
                fetch_market_daily(codes_df.head(limit))
            except ValueError:
                fetch_market_daily(codes_df)
    
    logger.info("✅ 全部完成")


if __name__ == "__main__":
    main()
