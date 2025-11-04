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
    for i, row in ts_codes.reset_index(drop=True).iterrows():
        ts_code = row['ts_code']
        # 转baostock代码风格
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        # 获取K线数据和财务指标
        rs = bs.query_history_k_data_plus(
            code,
            fields,
            start_date=START_DATE,
            end_date=END_DATE,
            frequency="d",
            adjustflag="3"
        )
        
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
        else:
            logger.warning(f"  ⚠️ {ts_code} 无数据")
        
        if (i+1) % 20 == 0:
            logger.info(f"日K进度 {i+1}/{len(ts_codes)}")
        
        time.sleep(SLEEP_SEC_WEB)
    
    bs.logout()
    logger.info(f"stock_market_daily 共写入 {total} 行")
    return total


def main():
    """主函数：下载所有数据"""
    logger.info("🚀 开始更新 A股智能选股基础数据库")
    logger.info(f"抓取窗口: {START_DATE} ~ {END_DATE}")
    
    # 1. 获取基础信息（静态数据，全量更新）
    codes_df = fetch_stock_basic_info()
    
    # 2. 下载日K行情（增量更新，支持多次运行）
    # BATCH_SIZE=400表示限制400只，设置为none/full表示全量
    batch_size = os.getenv("BATCH_SIZE", "400")
    if batch_size and batch_size.lower() not in ["none", "null", "full"]:
        try:
            limit = int(batch_size)
            head_codes = codes_df.head(limit)
            logger.info(f"限制批量大小: {limit}只股票")
        except ValueError:
            logger.warning(f"BATCH_SIZE值无效: {batch_size}，使用默认400")
            head_codes = codes_df.head(400)
    else:
        head_codes = codes_df
        logger.info(f"全量下载所有股票日K数据（共{len(codes_df)}只）")
    
    fetch_market_daily(head_codes)
    
    logger.info("✅ 全部完成")


if __name__ == "__main__":
    main()
