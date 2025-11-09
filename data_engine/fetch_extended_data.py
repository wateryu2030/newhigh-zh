"""
BaoStock扩展数据下载模块
下载行业分类、指数、财务数据等扩展数据
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
from utils.fast_db_writer import fast_upsert_df, AsyncDBWriter

from config import DB_URL, START_DATE, END_DATE, SLEEP_SEC_WEB

import baostock as bs

logger = setup_logger(log_file=os.path.join(os.path.dirname(__file__), "data_cache/update_extended.log"))
engine = get_engine(DB_URL)
NETWORK_ERROR_KEYWORDS = ("网络接收错误", "网络连接失败", "Connection aborted", "Connection reset")
MAX_NETWORK_RETRY = 3
NETWORK_FAIL_STREAK_LIMIT = 6

# ==================== 登录管理 ====================
def ensure_logged_in():
    """确保BaoStock已登录，如果未登录则自动登录"""
    try:
        # 尝试一个简单的查询来检查登录状态
        test_rs = bs.query_all_stock("2024-01-01")
        if test_rs.error_code == '10001004' or (test_rs.error_msg and '用户未登录' in test_rs.error_msg):
            logger.warning("检测到未登录，重新登录...")
            bs.logout()  # 先登出
            time.sleep(0.5)
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"baostock 重新登录失败: {lg.error_msg}")
            logger.info("重新登录成功")
            return True
        return True
    except Exception as e:
        # 如果查询失败，尝试重新登录
        logger.warning(f"登录状态检查失败，尝试重新登录: {e}")
        try:
            bs.logout()
        except:
            pass
        time.sleep(0.5)
        lg = bs.login()
        if lg.error_code != '0':
            raise RuntimeError(f"baostock 重新登录失败: {lg.error_msg}")
        logger.info("重新登录成功")
        return True


def check_and_relogin_on_error(error_msg):
    """检查错误信息，如果是登录相关错误，则重新登录"""
    if error_msg and ('用户未登录' in error_msg or '10001004' in error_msg or '未登录' in error_msg):
        logger.warning("检测到登录过期，重新登录...")
        try:
            bs.logout()
        except:
            pass
        time.sleep(0.5)
        lg = bs.login()
        if lg.error_code != '0':
            raise RuntimeError(f"baostock 重新登录失败: {lg.error_msg}")
        logger.info("重新登录成功")
        return True
    return False


# ==================== 行业分类数据 ====================
@retry(tries=5, delay=1.0)
def fetch_stock_industry():
    """获取股票行业分类数据"""
    logger.info("开始获取股票行业分类数据...")
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    rs = bs.query_stock_industry()
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    
    if not rows:
        bs.logout()
        logger.warning("未获取到行业分类数据")
        return pd.DataFrame()
    
    df = pd.DataFrame(rows, columns=rs.fields)
    bs.logout()
    
    # 转换代码格式
    def to_ts(code):
        if pd.isna(code):
            return None
        code_str = str(code)
        if '.' in code_str:
            p = code_str.split('.')
            return (p[1] + ('.SH' if p[0]=='sh' else '.SZ')) if len(p)==2 else code_str
        return code_str
    
    if 'code' in df.columns:
        df['ts_code'] = df['code'].map(to_ts)
    
    # 映射到现有表结构
    rename_map = {}
    if 'industry' in df.columns:
        rename_map['industry'] = 'industry_sw'  # 申万行业
    if 'industryClassification' in df.columns:
        rename_map['industryClassification'] = 'industry_csrc'  # 证监会行业
    
    if rename_map:
        df = df.rename(columns=rename_map)
    
    # 写入数据库
    if 'ts_code' in df.columns and len(df) > 0:
        # 只保留需要的列
        cols_to_keep = ['ts_code']
        if 'industry_sw' in df.columns:
            cols_to_keep.append('industry_sw')
        if 'industry_csrc' in df.columns:
            cols_to_keep.append('industry_csrc')
        if 'concept' in df.columns:
            cols_to_keep.append('concept')
        
        df_to_write = df[cols_to_keep].copy()
        
        # 如果有concept列，需要展开（一个股票可能有多个概念）
        if 'concept' in df_to_write.columns:
            # 处理概念数据（可能需要拆分）
            pass
        
        # 使用upsert逻辑
        upsert_df(df_to_write, "stock_concept_industry", engine, if_exists="append")
        logger.info(f"stock_concept_industry 写入 {len(df_to_write)} 条")
    
    return df


# ==================== 指数数据 ====================
@retry(tries=5, delay=1.0)
def fetch_index_daily(index_codes=None):
    """获取指数日K数据
    
    Args:
        index_codes: 指数代码列表，默认获取主要指数
    """
    if index_codes is None:
        index_codes = [
            ('sh.000001', '上证指数'),
            ('sz.399001', '深证成指'),
            ('sz.399006', '创业板指'),
            ('sh.000300', '沪深300'),
            ('sh.000905', '中证500'),
            ('sh.000016', '上证50'),
        ]
    
    logger.info(f"开始下载指数数据，共{len(index_codes)}个指数")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    fields = "date,code,open,high,low,close,preclose,volume,amount,pctChg"
    all_data = []
    
    for index_code, index_name in index_codes:
        try:
            rs = bs.query_history_k_data_plus(
                index_code,
                fields,
                start_date=START_DATE,
                end_date=END_DATE,
                frequency="d",
                adjustflag="3"
            )
            
            if rs.error_code != '0':
                logger.warning(f"  ⚠️ {index_name} ({index_code}) 查询失败: {rs.error_msg}")
                continue
            
            rows = []
            while rs.error_code == '0' and rs.next():
                row = rs.get_row_data()
                rows.append(row)
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                df['index_code'] = index_code
                df['name'] = index_name
                all_data.append(df)
                logger.info(f"  ✅ {index_name} ({index_code}) 下载成功，共 {len(df)} 天数据")
            
            time.sleep(SLEEP_SEC_WEB)
            
        except Exception as e:
            logger.error(f"  ❌ {index_name} ({index_code}) 下载失败: {e}")
            continue
    
    bs.logout()
    
    if not all_data:
        logger.warning("未获取到任何指数数据")
        return pd.DataFrame()
    
    # 合并所有指数数据
    df_all = pd.concat(all_data, ignore_index=True)
    
    # 字段映射
    rename_map = {
        'date': 'trade_date',
        'code': 'index_code_orig',
        'pctChg': 'pct_chg',
    }
    df_all = df_all.rename(columns=rename_map)
    
    # 转换日期格式
    if 'trade_date' in df_all.columns:
        df_all['trade_date'] = pd.to_datetime(df_all['trade_date']).dt.date
    
    # 写入数据库（只写入表结构中存在的字段）
    # 先检查表结构，只选择存在的字段
    from sqlalchemy import inspect as sql_inspect
    inspector = sql_inspect(engine)
    table_columns = [col['name'] for col in inspector.get_columns('market_index_daily')]
    
    # 可用的字段列表
    available_cols = ['index_code', 'name', 'trade_date', 'close', 'pct_chg']
    # 如果表中有这些字段，也添加
    for col in ['open', 'high', 'low', 'preclose', 'volume', 'amount']:
        if col in table_columns:
            available_cols.append(col)
    
    cols_to_write = [col for col in available_cols if col in df_all.columns]
    
    if cols_to_write:
        df_to_write = df_all[cols_to_write].copy()
        upsert_df(df_to_write, "market_index_daily", engine, if_exists="append")
        logger.info(f"market_index_daily 写入 {len(df_to_write)} 条")
    
    return df_all


# ==================== 财务数据（利润表） ====================
@retry(tries=5, delay=1.0)
def fetch_profit_data(ts_codes: pd.Series, years=None, quarters=None):
    """获取利润表数据（季频）
    
    Args:
        ts_codes: 股票代码Series
        years: 年份列表，默认最近3年
        quarters: 季度列表，默认[1,2,3,4]
    """
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year - 2, current_year + 1))
    
    if quarters is None:
        quarters = [1, 2, 3, 4]
    
    logger.info(f"开始下载利润表数据，共{len(ts_codes)}只股票，{len(years)}年，{len(quarters)}个季度")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    network_retry_candidates = set()
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        network_failure_streak = 0
        skip_remaining_for_stock = False
        
        for year in years:
            for quarter in quarters:
                try:
                    rs = bs.query_profit_data(code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        if '数据不存在' not in rs.error_msg:
                            logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                        failed_count += 1
                        time.sleep(SLEEP_SEC_WEB)
                        continue
                    
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    
                    if rows:
                        df = pd.DataFrame(rows, columns=rs.fields)
                        df['ts_code'] = ts_code
                        df['year'] = year
                        df['quarter'] = quarter
                        df['trade_date'] = pd.to_datetime(f"{year}-{quarter*3:02d}-01").date()
                        
                        # 写入数据库
                        try:
                            # 映射字段名（根据BaoStock返回的实际字段调整）
                            field_mapping = {}
                            if 'statDate' in df.columns:
                                df = df.drop(columns=['statDate'])
                            
                            # 选择要写入的列（只保留存在的列）
                            cols_to_write = ['ts_code', 'year', 'quarter', 'trade_date']
                            # 添加财务字段（如果存在）
                            financial_cols = ['revenue', 'operatingProfit', 'totalProfit', 'netProfit', 
                                            'eps', 'roe', 'grossProfitRate', 'netProfitRate']
                            for col in financial_cols:
                                if col in df.columns:
                                    cols_to_write.append(col)
                            
                            if len(cols_to_write) > 4:  # 至少有财务数据
                                df_to_write = df[cols_to_write].copy()
                                # 重命名字段（BaoStock字段名转数据库字段名）
                                rename_map = {
                                    'operatingProfit': 'operating_profit',
                                    'totalProfit': 'total_profit',
                                    'netProfit': 'net_profit',
                                    'grossProfitRate': 'gross_profit_margin',
                                    'netProfitRate': 'net_profit_margin'
                                }
                                df_to_write = df_to_write.rename(columns=rename_map)
                                
                                # 处理空值：将空字符串转换为None，并转换数值字段
                                numeric_cols = ['operating_profit', 'total_profit', 'net_profit', 'eps', 'roe', 
                                              'gross_profit_margin', 'net_profit_margin', 'revenue']
                                for col in numeric_cols:
                                    if col in df_to_write.columns:
                                        # 将空字符串、'nan'等转换为None
                                        df_to_write[col] = df_to_write[col].replace(['', ' ', 'nan', 'NaN', 'NULL', None], None)
                                        # 尝试转换为数值类型，无法转换的设为None
                                        df_to_write[col] = pd.to_numeric(df_to_write[col], errors='coerce')
                                
                                upsert_df(df_to_write, "stock_financials_profit", engine, if_exists="append")
                                total += len(df_to_write)
                                success_count += 1
                        except Exception as e:
                            logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 写入失败: {e}")
                            failed_count += 1
                    
                    time.sleep(SLEEP_SEC_WEB)
                    
                except Exception as e:
                    logger.error(f"  ❌ {ts_code} {year}Q{quarter} 下载失败: {e}")
                    failed_count += 1
                    continue
        
        if i % 50 == 0:
            logger.info(f"利润表进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"利润表数据下载完成，共 {total} 条记录")
    
    return total


# ==================== 业绩预告/快报 ====================
@retry(tries=5, delay=1.0)
def fetch_performance_forecast(ts_codes: pd.Series, start_date=None, end_date=None):
    """获取业绩预告数据"""
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"开始下载业绩预告数据，共{len(ts_codes)}只股票")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        try:
            # 每100个股票检查一次登录状态
            if i % 100 == 0:
                ensure_logged_in()
            
            rs = bs.query_forecast_report(code, start_date=start_date, end_date=end_date)
            
            if rs.error_code != '0':
                # 检查是否是登录错误，如果是则重新登录并重试一次
                if check_and_relogin_on_error(rs.error_msg):
                    # 重新登录后重试一次
                    rs = bs.query_forecast_report(code, start_date=start_date, end_date=end_date)
                    if rs.error_code != '0':
                        if '数据不存在' not in rs.error_msg:
                            logger.warning(f"  ⚠️ {ts_code} 查询失败: {rs.error_msg}")
                        failed_count += 1
                        time.sleep(SLEEP_SEC_WEB)
                        continue
                else:
                    if '数据不存在' not in rs.error_msg:
                        logger.warning(f"  ⚠️ {ts_code} 查询失败: {rs.error_msg}")
                    failed_count += 1
                    time.sleep(SLEEP_SEC_WEB)
                    continue
            
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                df['ts_code'] = ts_code
                
                # 写入数据库
                try:
                    # 映射字段名
                    field_mapping = {
                        'reportDate': 'report_date',
                        'publishDate': 'publish_date',
                        'type': 'forecast_type',
                        'profit': 'forecast_net_profit',
                        'profitRatio': 'forecast_profit_change_pct',
                        'revenue': 'forecast_revenue',
                        'revenueRatio': 'forecast_revenue_change_pct',
                        'content': 'content'
                    }
                    
                    # 重命名字段
                    df_to_write = df.rename(columns=field_mapping)
                    
                    # 转换日期格式
                    if 'report_date' in df_to_write.columns:
                        df_to_write['report_date'] = pd.to_datetime(df_to_write['report_date'], errors='coerce').dt.date
                    if 'publish_date' in df_to_write.columns:
                        df_to_write['publish_date'] = pd.to_datetime(df_to_write['publish_date'], errors='coerce').dt.date
                    
                    # 选择要写入的列
                    cols_to_write = ['ts_code']
                    for col in ['report_date', 'publish_date', 'forecast_type', 'forecast_net_profit', 
                               'forecast_profit_change_pct', 'forecast_revenue', 'forecast_revenue_change_pct', 'content']:
                        if col in df_to_write.columns:
                            cols_to_write.append(col)
                    
                    if len(cols_to_write) > 1:  # 至少有ts_code和其他字段
                        df_final = df_to_write[cols_to_write].copy()
                        upsert_df(df_final, "stock_performance_forecast", engine, if_exists="append")
                        total += len(df_final)
                        success_count += 1
                        logger.info(f"  ✅ {ts_code} 下载成功，共 {len(df_final)} 条预告")
                    else:
                        logger.warning(f"  ⚠️ {ts_code} 数据字段不完整")
                except Exception as e:
                    logger.warning(f"  ⚠️ {ts_code} 写入失败: {e}")
                    failed_count += 1
            
            time.sleep(SLEEP_SEC_WEB)
            
        except Exception as e:
            logger.error(f"  ❌ {ts_code} 下载失败: {e}")
            failed_count += 1
            continue
        
        if i % 50 == 0:
            logger.info(f"业绩预告进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"业绩预告数据下载完成，共 {total} 条记录")
    
    return total


# ==================== 成分股数据 ====================
@retry(tries=5, delay=1.0)
def fetch_index_stocks():
    """获取主要指数成分股"""
    logger.info("开始下载指数成分股数据...")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    index_functions = [
        ('hs300', bs.query_hs300_stocks, '沪深300'),
        ('sz50', bs.query_sz50_stocks, '上证50'),
        ('zz500', bs.query_zz500_stocks, '中证500'),
    ]
    
    all_data = []
    
    for index_key, query_func, index_name in index_functions:
        try:
            rs = query_func()
            
            if rs.error_code != '0':
                logger.warning(f"  ⚠️ {index_name} 查询失败: {rs.error_msg}")
                continue
            
            rows = []
            while rs.error_code == '0' and rs.next():
                row = rs.get_row_data()
                rows.append(row)
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                df['index_name'] = index_name
                df['index_key'] = index_key
                
                # 转换代码格式
                def to_ts(code):
                    if pd.isna(code):
                        return None
                    code_str = str(code)
                    if '.' in code_str:
                        p = code_str.split('.')
                        return (p[1] + ('.SH' if p[0]=='sh' else '.SZ')) if len(p)==2 else code_str
                    return code_str
                
                if 'code' in df.columns:
                    df['ts_code'] = df['code'].map(to_ts)
                
                # 写入数据库
                try:
                    cols_to_write = ['index_key', 'index_name']
                    
                    if 'ts_code' in df.columns:
                        cols_to_write.append('ts_code')
                    if 'code' in df.columns:
                        cols_to_write.append('code')
                    if 'code_name' in df.columns:
                        cols_to_write.append('code_name')
                    if 'updateDate' in df.columns:
                        df['date'] = pd.to_datetime(df['updateDate'], errors='coerce').dt.date
                        cols_to_write.append('date')
                    
                    if len(cols_to_write) >= 3:  # 至少要有index_key, index_name, ts_code
                        df_to_write = df[cols_to_write].copy()
                        upsert_df(df_to_write, "index_constituents", engine, if_exists="append")
                        logger.info(f"  ✅ {index_name} 下载成功，共 {len(df)} 只成分股，已写入数据库")
                    else:
                        logger.warning(f"  ⚠️ {index_name} 字段不完整，可用字段: {list(df.columns)}")
                except Exception as e:
                    logger.warning(f"  ⚠️ {index_name} 写入失败: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                
                all_data.append(df)
            
            time.sleep(SLEEP_SEC_WEB)
            
        except Exception as e:
            logger.error(f"  ❌ {index_name} 下载失败: {e}")
            continue
    
    bs.logout()
    
    if not all_data:
        logger.warning("未获取到任何成分股数据")
        return pd.DataFrame()
    
    # 合并数据
    df_all = pd.concat(all_data, ignore_index=True)
    logger.info(f"成分股数据下载完成，共 {len(df_all)} 条记录")
    
    return df_all


# ==================== 资产负债表数据 ====================
@retry(tries=5, delay=1.0)
def fetch_balance_data(ts_codes: pd.Series, years=None, quarters=None):
    """获取资产负债表数据（季频）"""
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year - 2, current_year + 1))
    
    if quarters is None:
        quarters = [1, 2, 3, 4]
    
    logger.info(f"开始下载资产负债表数据，共{len(ts_codes)}只股票，{len(years)}年，{len(quarters)}个季度")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        for year in years:
            for quarter in quarters:
                try:
                    # 每100个股票检查一次登录状态
                    if i % 100 == 0:
                        ensure_logged_in()
                    
                    rs = bs.query_balance_data(code, year=year, quarter=quarter)
                    
                    if rs.error_code != '0':
                        # 检查是否是登录错误，如果是则重新登录并重试一次
                        if check_and_relogin_on_error(rs.error_msg):
                            # 重新登录后重试一次
                            rs = bs.query_balance_data(code, year=year, quarter=quarter)
                            if rs.error_code != '0':
                                if '数据不存在' not in rs.error_msg:
                                    logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                                failed_count += 1
                                time.sleep(SLEEP_SEC_WEB)
                                continue
                        else:
                            if '数据不存在' not in rs.error_msg:
                                logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                            failed_count += 1
                            time.sleep(SLEEP_SEC_WEB)
                            continue
                    
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    
                    if rows:
                        df = pd.DataFrame(rows, columns=rs.fields)
                        df['ts_code'] = ts_code
                        df['year'] = year
                        df['quarter'] = quarter
                        
                        # 处理日期字段
                        if 'statDate' in df.columns:
                            df['trade_date'] = pd.to_datetime(df['statDate']).dt.date
                            df['stat_date'] = pd.to_datetime(df['statDate']).dt.date
                        else:
                            df['trade_date'] = pd.to_datetime(f"{year}-{quarter*3:02d}-01").date()
                            df['stat_date'] = None
                        
                        if 'pubDate' in df.columns:
                            df['pub_date'] = pd.to_datetime(df['pubDate']).dt.date
                        else:
                            df['pub_date'] = None
                        
                        try:
                            # 删除不需要的字段
                            cols_to_drop = ['code', 'statDate', 'pubDate']
                            for col in cols_to_drop:
                                if col in df.columns:
                                    df = df.drop(columns=[col])
                            
                            # 根据实际返回字段写入（BaoStock返回的是比率数据）
                            cols_to_write = ['ts_code', 'year', 'quarter', 'trade_date']
                            
                            # 添加实际存在的字段
                            balance_cols = ['currentRatio', 'quickRatio', 'cashRatio', 'YOYLiability', 
                                          'liabilityToAsset', 'assetToEquity']
                            for col in balance_cols:
                                if col in df.columns:
                                    cols_to_write.append(col)
                            
                            # 添加日期字段
                            if 'pub_date' in df.columns:
                                cols_to_write.append('pub_date')
                            if 'stat_date' in df.columns:
                                cols_to_write.append('stat_date')
                            
                            if len(cols_to_write) > 4:
                                df_to_write = df[cols_to_write].copy()
                                rename_map = {
                                    'currentRatio': 'current_ratio',
                                    'quickRatio': 'quick_ratio',
                                    'cashRatio': 'cash_ratio',
                                    'YOYLiability': 'yoy_liability',
                                    'liabilityToAsset': 'liability_to_asset',
                                    'assetToEquity': 'asset_to_equity'
                                }
                                df_to_write = df_to_write.rename(columns=rename_map)
                                
                                # 处理空值：将空字符串转换为None
                                for col in df_to_write.columns:
                                    if df_to_write[col].dtype == 'object':
                                        df_to_write[col] = df_to_write[col].replace(['', ' '], None)
                                
                                upsert_df(df_to_write, "stock_financials_balance", engine, if_exists="append")
                                total += len(df_to_write)
                                success_count += 1
                            else:
                                logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 数据字段不足，跳过")
                                failed_count += 1
                        except Exception as e:
                            logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 写入失败: {e}")
                            failed_count += 1
                    
                    time.sleep(SLEEP_SEC_WEB)
                    
                except Exception as e:
                    logger.error(f"  ❌ {ts_code} {year}Q{quarter} 下载失败: {e}")
                    failed_count += 1
                    continue
        
        if i % 50 == 0:
            logger.info(f"资产负债表进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"资产负债表数据下载完成，共 {total} 条记录")
    return total


# ==================== 现金流量表数据 ====================
@retry(tries=5, delay=1.0)
def fetch_cashflow_data(ts_codes: pd.Series, years=None, quarters=None):
    """获取现金流量表数据（季频）"""
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year - 2, current_year + 1))
    
    if quarters is None:
        quarters = [1, 2, 3, 4]
    
    logger.info(f"开始下载现金流量表数据，共{len(ts_codes)}只股票，{len(years)}年，{len(quarters)}个季度")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        for year in years:
            for quarter in quarters:
                try:
                    rs = bs.query_cash_flow_data(code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        # 检查是否是登录错误，如果是则重新登录并重试一次
                        if check_and_relogin_on_error(rs.error_msg):
                            # 重新登录后重试一次
                            rs = bs.query_cash_flow_data(code, year=year, quarter=quarter)
                            if rs.error_code != '0':
                                if '数据不存在' not in rs.error_msg:
                                    logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                                failed_count += 1
                                time.sleep(SLEEP_SEC_WEB)
                                continue
                        else:
                            if '数据不存在' not in rs.error_msg:
                                logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                            failed_count += 1
                            time.sleep(SLEEP_SEC_WEB)
                            continue
                    
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    
                    if rows:
                        df = pd.DataFrame(rows, columns=rs.fields)
                        df['ts_code'] = ts_code
                        df['year'] = year
                        df['quarter'] = quarter
                        df['trade_date'] = pd.to_datetime(f"{year}-{quarter*3:02d}-01").date()
                        
                        try:
                            if 'statDate' in df.columns:
                                df = df.drop(columns=['statDate'])
                            
                            cols_to_write = ['ts_code', 'year', 'quarter', 'trade_date']
                            
                            # 根据实际返回字段
                            cashflow_cols = ['CAToAsset', 'NCAToAsset', 'tangibleAssetToAsset', 
                                           'ebitToInterest', 'CFOToOR', 'CFOToNP', 'CFOToGr']
                            for col in cashflow_cols:
                                if col in df.columns:
                                    cols_to_write.append(col)
                            
                            if len(cols_to_write) > 4:
                                df_to_write = df[cols_to_write].copy()
                                rename_map = {
                                    'CAToAsset': 'ca_to_asset',
                                    'NCAToAsset': 'nca_to_asset',
                                    'tangibleAssetToAsset': 'tangible_asset_to_asset',
                                    'ebitToInterest': 'ebit_to_interest',
                                    'CFOToOR': 'cfo_to_or',
                                    'CFOToNP': 'cfo_to_np',
                                    'CFOToGr': 'cfo_to_gr'
                                }
                                df_to_write = df_to_write.rename(columns=rename_map)
                                # 清洗空白值并转换数值类型
                                for col in df_to_write.columns:
                                    if df_to_write[col].dtype == 'object':
                                        df_to_write[col] = df_to_write[col].replace(['', ' ', 'nan', 'NaN'], None)
                                for col in ['ca_to_asset', 'nca_to_asset', 'tangible_asset_to_asset',
                                            'ebit_to_interest', 'cfo_to_or', 'cfo_to_np', 'cfo_to_gr']:
                                    if col in df_to_write.columns:
                                        df_to_write[col] = pd.to_numeric(df_to_write[col], errors='coerce')
                                upsert_df(df_to_write, "stock_financials_cashflow", engine, if_exists="append")
                                total += len(df_to_write)
                                success_count += 1
                        except Exception as e:
                            logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 写入失败: {e}")
                            failed_count += 1
                    
                    time.sleep(SLEEP_SEC_WEB)
                    
                except Exception as e:
                    logger.error(f"  ❌ {ts_code} {year}Q{quarter} 下载失败: {e}")
                    failed_count += 1
                    continue
        
        if i % 50 == 0:
            logger.info(f"现金流量表进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"现金流量表数据下载完成，共 {total} 条记录")
    return total


# ==================== 业绩快报数据 ====================
@retry(tries=5, delay=1.0)
def fetch_performance_express(ts_codes: pd.Series, start_date=None, end_date=None):
    """获取业绩快报数据"""
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"开始下载业绩快报数据，共{len(ts_codes)}只股票")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        try:
            rs = bs.query_performance_express_report(code, start_date=start_date, end_date=end_date)
            if rs.error_code != '0':
                # 检查是否是登录错误，如果是则重新登录并重试一次
                if check_and_relogin_on_error(rs.error_msg):
                    # 重新登录后重试一次
                    rs = bs.query_performance_express_report(code, start_date=start_date, end_date=end_date)
                    if rs.error_code != '0':
                        if '数据不存在' not in rs.error_msg:
                            logger.warning(f"  ⚠️ {ts_code} 查询失败: {rs.error_msg}")
                        failed_count += 1
                        time.sleep(SLEEP_SEC_WEB)
                        continue
                else:
                    if '数据不存在' not in rs.error_msg:
                        logger.warning(f"  ⚠️ {ts_code} 查询失败: {rs.error_msg}")
                    failed_count += 1
                    time.sleep(SLEEP_SEC_WEB)
                    continue
            
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                df['ts_code'] = ts_code
                
                try:
                    # 映射字段名
                    field_mapping = {
                        'performanceExpStatDate': 'report_date',
                        'performanceExpPubDate': 'publish_date',
                        'performanceExpressTotalAsset': 'total_assets',
                        'performanceExpressNetAsset': 'shareholders_equity',
                        'performanceExpressEPSDiluted': 'eps',
                        'performanceExpressROEWa': 'roe',
                        'performanceExpressGRYOY': 'revenue_yoy',
                        'performanceExpressOPYOY': 'operating_profit_yoy'
                    }
                    
                    df_to_write = df.rename(columns=field_mapping)
                    
                    # 转换日期格式
                    if 'report_date' in df_to_write.columns:
                        df_to_write['report_date'] = pd.to_datetime(df_to_write['report_date'], errors='coerce').dt.date
                    if 'publish_date' in df_to_write.columns:
                        df_to_write['publish_date'] = pd.to_datetime(df_to_write['publish_date'], errors='coerce').dt.date
                    
                    # 选择要写入的列
                    cols_to_write = ['ts_code']
                    optional_cols = ['report_date', 'publish_date', 'total_assets', 'shareholders_equity', 
                                   'eps', 'roe', 'revenue_yoy', 'operating_profit_yoy']
                    
                    for col in optional_cols:
                        if col in df_to_write.columns:
                            cols_to_write.append(col)
                    
                    if len(cols_to_write) > 1:
                        df_final = df_to_write[cols_to_write].copy()
                        upsert_df(df_final, "stock_performance_express", engine, if_exists="append")
                        total += len(df_final)
                        success_count += 1
                except Exception as e:
                    logger.warning(f"  ⚠️ {ts_code} 写入失败: {e}")
                    failed_count += 1
            
            time.sleep(SLEEP_SEC_WEB)
            
        except Exception as e:
            logger.error(f"  ❌ {ts_code} 下载失败: {e}")
            failed_count += 1
            continue
        
        if i % 50 == 0:
            logger.info(f"业绩快报进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"业绩快报数据下载完成，共 {total} 条记录")
    return total


# ==================== 成长能力数据 ====================
@retry(tries=5, delay=1.0)
def fetch_growth_data(ts_codes: pd.Series, years=None, quarters=None):
    """获取成长能力数据（季频）"""
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year - 2, current_year + 1))
    
    if quarters is None:
        quarters = [1, 2, 3, 4]
    
    logger.info(f"开始下载成长能力数据，共{len(ts_codes)}只股票，{len(years)}年，{len(quarters)}个季度")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    network_retry_candidates = set()
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        network_failure_streak = 0
        skip_remaining_for_stock = False
        
        for year in years:
            for quarter in quarters:
                try:
                    attempt = 0
                    rs = None
                    while True:
                        rs = bs.query_growth_data(code, year=year, quarter=quarter)
                        if rs.error_code == '0':
                            break
                        error_msg = rs.error_msg or ''
                        if check_and_relogin_on_error(error_msg):
                            continue
                        normalized_msg = error_msg.lower()
                        is_network_issue = (
                            any(keyword in error_msg for keyword in NETWORK_ERROR_KEYWORDS)
                            or "network" in normalized_msg
                            or "网络" in error_msg
                        )
                        if is_network_issue and attempt < MAX_NETWORK_RETRY:
                            attempt += 1
                            wait_seconds = min(2 ** attempt, 10)
                            logger.warning(
                                f"  ⚠️ {ts_code} {year}Q{quarter} 网络波动，{wait_seconds}s 后重试 ({attempt}/{MAX_NETWORK_RETRY})"
                            )
                            time.sleep(wait_seconds)
                            continue
                        if is_network_issue:
                            network_failure_streak += 1
                        else:
                            network_failure_streak = 0
                        logger.warning(
                            f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {error_msg} (network_issue={is_network_issue}, attempt={attempt})"
                        )
                        failed_count += 1
                        rs = None
                        if is_network_issue and network_failure_streak >= NETWORK_FAIL_STREAK_LIMIT:
                            skip_remaining_for_stock = True
                            network_retry_candidates.add(ts_code)
                            logger.warning(
                                f"  ⚠️ {ts_code} 网络连续失败 {network_failure_streak} 次，跳过剩余季度，稍后重试"
                            )
                        break
                    if skip_remaining_for_stock:
                        break
                    if rs is None or rs.error_code != '0':
                        continue
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    if not rows:
                        continue
                    df = pd.DataFrame(rows, columns=rs.fields)
                    df['ts_code'] = ts_code
                    df['year'] = year
                    df['quarter'] = quarter
                    df['trade_date'] = pd.to_datetime(f"{year}-{quarter*3:02d}-01").date()
                    try:
                        if 'statDate' in df.columns:
                            df = df.drop(columns=['statDate'])
                        cols_to_write = ['ts_code', 'year', 'quarter', 'trade_date']
                        growth_cols = ['YOYEquity', 'YOYAsset', 'YOYNI', 'YOYEPSBasic', 'YOYPNI']
                        for col in growth_cols:
                            if col in df.columns:
                                cols_to_write.append(col)
                        if len(cols_to_write) > 4:
                            df_to_write = df[cols_to_write].copy()
                            rename_map = {
                                'YOYEquity': 'shareholders_equity_yoy',
                                'YOYAsset': 'total_assets_yoy',
                                'YOYNI': 'net_profit_yoy',
                                'YOYEPSBasic': 'eps_yoy',
                                'YOYPNI': 'profit_yoy'
                            }
                            df_to_write = df_to_write.rename(columns=rename_map)
                            for col in df_to_write.columns:
                                if df_to_write[col].dtype == 'object':
                                    df_to_write[col] = df_to_write[col].replace(['', ' ', 'nan', 'NaN'], None)
                            for col in ['shareholders_equity_yoy', 'total_assets_yoy', 'net_profit_yoy', 'eps_yoy', 'profit_yoy']:
                                if col in df_to_write.columns:
                                    df_to_write[col] = pd.to_numeric(df_to_write[col], errors='coerce')
                            upsert_df(df_to_write, "stock_financials_growth", engine, if_exists="append")
                            total += len(df_to_write)
                            success_count += 1
                            network_failure_streak = 0
                    except Exception as e:
                        logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 写入失败: {e}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"  ❌ {ts_code} {year}Q{quarter} 下载失败: {e}")
                    failed_count += 1
                    continue
                finally:
                    time.sleep(SLEEP_SEC_WEB)
            if skip_remaining_for_stock:
                logger.info(f"  ⏸️  {ts_code} 已暂存，稍后重试剩余年度")
                break

        if i % 50 == 0:
            logger.info(f"成长能力进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")

    if network_retry_candidates:
        preview = list(sorted(network_retry_candidates))[:10]
        logger.warning(
            f"成长能力数据存在网络待重试股票 {len(network_retry_candidates)} 支，示例: {preview}"
        )

    bs.logout()
    logger.info(f"成长能力数据下载完成，共 {total} 条记录")
    return total


# ==================== 营运能力数据 ====================
@retry(tries=5, delay=1.0)
def fetch_operation_data(ts_codes: pd.Series, years=None, quarters=None):
    """获取营运能力数据（季频）"""
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year - 2, current_year + 1))
    
    if quarters is None:
        quarters = [1, 2, 3, 4]
    
    logger.info(f"开始下载营运能力数据，共{len(ts_codes)}只股票，{len(years)}年，{len(quarters)}个季度")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        for year in years:
            for quarter in quarters:
                try:
                    rs = bs.query_operation_data(code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        # 检查是否是登录错误，如果是则重新登录并重试一次
                        if check_and_relogin_on_error(rs.error_msg):
                            # 重新登录后重试一次
                            rs = bs.query_operation_data(code, year=year, quarter=quarter)
                            if rs.error_code != '0':
                                if '数据不存在' not in rs.error_msg:
                                    logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                                failed_count += 1
                                time.sleep(SLEEP_SEC_WEB)
                                continue
                        else:
                            if '数据不存在' not in rs.error_msg:
                                logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                            failed_count += 1
                            time.sleep(SLEEP_SEC_WEB)
                            continue
                    
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    
                    if rows:
                        df = pd.DataFrame(rows, columns=rs.fields)
                        df['ts_code'] = ts_code
                        df['year'] = year
                        df['quarter'] = quarter
                        df['trade_date'] = pd.to_datetime(f"{year}-{quarter*3:02d}-01").date()
                        
                        try:
                            if 'statDate' in df.columns:
                                df = df.drop(columns=['statDate'])
                            
                            cols_to_write = ['ts_code', 'year', 'quarter', 'trade_date']
                            
                            operation_cols = ['NRTurnRatio', 'NRTurnDays', 'INVTurnRatio', 
                                            'INVTurnDays', 'CATurnRatio', 'AssetTurnRatio']
                            for col in operation_cols:
                                if col in df.columns:
                                    cols_to_write.append(col)
                            
                            if len(cols_to_write) > 4:
                                df_to_write = df[cols_to_write].copy()
                                rename_map = {
                                    'NRTurnRatio': 'receivables_turnover',
                                    'NRTurnDays': 'receivables_turnover_days',
                                    'INVTurnRatio': 'inventory_turnover',
                                    'INVTurnDays': 'inventory_turnover_days',
                                    'CATurnRatio': 'current_assets_turnover',
                                    'AssetTurnRatio': 'total_assets_turnover'
                                }
                                df_to_write = df_to_write.rename(columns=rename_map)
                                
                                upsert_df(df_to_write, "stock_financials_operation", engine, if_exists="append")
                                total += len(df_to_write)
                                success_count += 1
                        except Exception as e:
                            logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 写入失败: {e}")
                            failed_count += 1
                    
                    time.sleep(SLEEP_SEC_WEB)
                    
                except Exception as e:
                    logger.error(f"  ❌ {ts_code} {year}Q{quarter} 下载失败: {e}")
                    failed_count += 1
                    continue
        
        if i % 50 == 0:
            logger.info(f"营运能力进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"营运能力数据下载完成，共 {total} 条记录")
    return total


# ==================== 杜邦指数数据 ====================
@retry(tries=5, delay=1.0)
def fetch_dupont_data(ts_codes: pd.Series, years=None, quarters=None):
    """获取杜邦指数数据（季频）"""
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year - 2, current_year + 1))
    
    if quarters is None:
        quarters = [1, 2, 3, 4]
    
    logger.info(f"开始下载杜邦指数数据，共{len(ts_codes)}只股票，{len(years)}年，{len(quarters)}个季度")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        for year in years:
            for quarter in quarters:
                try:
                    rs = bs.query_dupont_data(code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        # 检查是否是登录错误，如果是则重新登录并重试一次
                        if check_and_relogin_on_error(rs.error_msg):
                            # 重新登录后重试一次
                            rs = bs.query_dupont_data(code, year=year, quarter=quarter)
                            if rs.error_code != '0':
                                if '数据不存在' not in rs.error_msg:
                                    logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                                failed_count += 1
                                time.sleep(SLEEP_SEC_WEB)
                                continue
                        else:
                            if '数据不存在' not in rs.error_msg:
                                logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 查询失败: {rs.error_msg}")
                            failed_count += 1
                            time.sleep(SLEEP_SEC_WEB)
                            continue
                    
                    rows = []
                    while rs.error_code == '0' and rs.next():
                        rows.append(rs.get_row_data())
                    
                    if rows:
                        df = pd.DataFrame(rows, columns=rs.fields)
                        df['ts_code'] = ts_code
                        df['year'] = year
                        df['quarter'] = quarter
                        df['trade_date'] = pd.to_datetime(f"{year}-{quarter*3:02d}-01").date()
                        
                        try:
                            if 'statDate' in df.columns:
                                df = df.drop(columns=['statDate'])
                            
                            cols_to_write = ['ts_code', 'year', 'quarter', 'trade_date']
                            
                            dupont_cols = ['dupontROE', 'dupontAssetStoEquity', 'dupontAssetTurn', 
                                         'dupontPnitoni', 'dupontNitogr', 'dupontTaxBurden', 
                                         'dupontIntburden', 'dupontEbittogr']
                            for col in dupont_cols:
                                if col in df.columns:
                                    cols_to_write.append(col)
                            
                            if len(cols_to_write) > 4:
                                df_to_write = df[cols_to_write].copy()
                                rename_map = {
                                    'dupontROE': 'roe',
                                    'dupontAssetStoEquity': 'equity_multiplier',
                                    'dupontAssetTurn': 'total_assets_turnover',
                                    'dupontPnitoni': 'net_profit_to_ni',
                                    'dupontNitogr': 'ni_to_gr',
                                    'dupontTaxBurden': 'tax_burden',
                                    'dupontIntburden': 'int_burden',
                                    'dupontEbittogr': 'ebit_to_gr'
                                }
                                df_to_write = df_to_write.rename(columns=rename_map)
                                
                                upsert_df(df_to_write, "stock_financials_dupont", engine, if_exists="append")
                                total += len(df_to_write)
                                success_count += 1
                        except Exception as e:
                            logger.warning(f"  ⚠️ {ts_code} {year}Q{quarter} 写入失败: {e}")
                            failed_count += 1
                    
                    time.sleep(SLEEP_SEC_WEB)
                    
                except Exception as e:
                    logger.error(f"  ❌ {ts_code} {year}Q{quarter} 下载失败: {e}")
                    failed_count += 1
                    continue
        
        if i % 50 == 0:
            logger.info(f"杜邦指数进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"杜邦指数数据下载完成，共 {total} 条记录")
    return total


# ==================== 股息分红数据 ====================
@retry(tries=5, delay=1.0)
def fetch_dividend_data(ts_codes: pd.Series, years=None):
    """获取股息分红数据"""
    if years is None:
        current_year = datetime.now().year
        years = list(range(current_year - 2, current_year + 1))
    
    logger.info(f"开始下载股息分红数据，共{len(ts_codes)}只股票，{len(years)}年")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        for year in years:
            try:
                rs = bs.query_dividend_data(code, year=year, yearType='report')
                if rs.error_code != '0':
                    # 检查是否是登录错误，如果是则重新登录并重试一次
                    if check_and_relogin_on_error(rs.error_msg):
                        # 重新登录后重试一次
                        rs = bs.query_dividend_data(code, year=year, yearType='report')
                        if rs.error_code != '0':
                            if '数据不存在' not in rs.error_msg:
                                logger.warning(f"  ⚠️ {ts_code} {year} 查询失败: {rs.error_msg}")
                            failed_count += 1
                            time.sleep(SLEEP_SEC_WEB)
                            continue
                    else:
                        if '数据不存在' not in rs.error_msg:
                            logger.warning(f"  ⚠️ {ts_code} {year} 查询失败: {rs.error_msg}")
                        failed_count += 1
                        time.sleep(SLEEP_SEC_WEB)
                        continue
                
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                
                if rows:
                    df = pd.DataFrame(rows, columns=rs.fields)
                    df['ts_code'] = ts_code
                    df['year'] = year
                    df['year_type'] = 'report'
                    
                    try:
                        cols_to_write = ['ts_code', 'year', 'year_type']
                        
                        # 只使用数据库表中存在的字段
                        dividend_cols = ['dividPlanDate', 'dividRegistDate', 'dividOperateDate', 
                                        'dividCashPsBeforeTax']
                        for col in dividend_cols:
                            if col in df.columns:
                                cols_to_write.append(col)
                        
                        if len(cols_to_write) > 3:
                            df_to_write = df[cols_to_write].copy()
                            # 只映射数据库中存在的字段
                            rename_map = {
                                'dividPlanDate': 'dividend_date',
                                'dividRegistDate': 'record_date',
                                'dividOperateDate': 'ex_dividend_date',
                                'dividCashPsBeforeTax': 'dividend_ratio'
                            }
                            df_to_write = df_to_write.rename(columns=rename_map)
                            
                            # 转换日期格式（只转换存在的字段）
                            for date_col in ['dividend_date', 'ex_dividend_date', 'record_date']:
                                if date_col in df_to_write.columns:
                                    df_to_write[date_col] = pd.to_datetime(df_to_write[date_col], errors='coerce').dt.date
                            
                            # 确保只写入数据库表中存在的列
                            valid_cols = ['ts_code', 'year', 'year_type', 'dividend_date', 
                                         'record_date', 'ex_dividend_date', 'dividend_ratio']
                            df_final = df_to_write[[col for col in valid_cols if col in df_to_write.columns]].copy()
                            
                            upsert_df(df_final, "stock_dividend", engine, if_exists="append")
                            total += len(df_final)
                            success_count += 1
                    except Exception as e:
                        logger.warning(f"  ⚠️ {ts_code} {year} 写入失败: {e}")
                        failed_count += 1
                
                time.sleep(SLEEP_SEC_WEB)
                
            except Exception as e:
                logger.error(f"  ❌ {ts_code} {year} 下载失败: {e}")
                failed_count += 1
                continue
        
        if i % 50 == 0:
            logger.info(f"股息分红进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"股息分红数据下载完成，共 {total} 条记录")
    return total


# ==================== 复权因子数据 ====================
@retry(tries=5, delay=1.0)
def fetch_adjust_factor(ts_codes: pd.Series, start_date=None, end_date=None):
    """获取复权因子数据"""
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"开始下载复权因子数据，共{len(ts_codes)}只股票")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    total = 0
    success_count = 0
    failed_count = 0
    
    for i, ts_code in enumerate(ts_codes, 1):
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        
        try:
            rs = bs.query_adjust_factor(code, start_date=start_date, end_date=end_date)
            if rs.error_code != '0':
                # 检查是否是登录错误，如果是则重新登录并重试一次
                if check_and_relogin_on_error(rs.error_msg):
                    # 重新登录后重试一次
                    rs = bs.query_adjust_factor(code, start_date=start_date, end_date=end_date)
                    if rs.error_code != '0':
                        if '数据不存在' not in rs.error_msg:
                            logger.warning(f"  ⚠️ {ts_code} 查询失败: {rs.error_msg}")
                        failed_count += 1
                        time.sleep(SLEEP_SEC_WEB)
                        continue
                else:
                    if '数据不存在' not in rs.error_msg:
                        logger.warning(f"  ⚠️ {ts_code} 查询失败: {rs.error_msg}")
                    failed_count += 1
                    time.sleep(SLEEP_SEC_WEB)
                    continue
            
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                df['ts_code'] = ts_code
                
                try:
                    cols_to_write = ['ts_code']
                    
                    factor_cols = ['dividOperateDate', 'foreAdjustFactor', 'backAdjustFactor']
                    for col in factor_cols:
                        if col in df.columns:
                            cols_to_write.append(col)
                    
                    if len(cols_to_write) > 1:
                        df_to_write = df[cols_to_write].copy()
                        rename_map = {
                            'dividOperateDate': 'adjust_date',
                            'foreAdjustFactor': 'forward_factor',
                            'backAdjustFactor': 'backward_factor'
                        }
                        df_to_write = df_to_write.rename(columns=rename_map)
                        
                        # 转换日期格式
                        if 'adjust_date' in df_to_write.columns:
                            df_to_write['adjust_date'] = pd.to_datetime(df_to_write['adjust_date'], errors='coerce').dt.date
                        
                        upsert_df(df_to_write, "stock_adjust_factor", engine, if_exists="append")
                        total += len(df_to_write)
                        success_count += 1
                except Exception as e:
                    logger.warning(f"  ⚠️ {ts_code} 写入失败: {e}")
                    failed_count += 1
            
            time.sleep(SLEEP_SEC_WEB)
            
        except Exception as e:
            logger.error(f"  ❌ {ts_code} 下载失败: {e}")
            failed_count += 1
            continue
        
        if i % 50 == 0:
            logger.info(f"复权因子进度 {i}/{len(ts_codes)} | 成功: {success_count} | 失败: {failed_count}")
    
    bs.logout()
    logger.info(f"复权因子数据下载完成，共 {total} 条记录")
    return total


# ==================== 交易日历数据 ====================
@retry(tries=5, delay=1.0)
def fetch_trade_dates(start_date=None, end_date=None):
    """获取交易日历数据"""
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"开始下载交易日历数据，日期范围: {start_date} ~ {end_date}")
    
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    
    rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
    if rs.error_code != '0':
        bs.logout()
        logger.warning(f"查询交易日历失败: {rs.error_msg}")
        return 0
    
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    
    bs.logout()
    
    if not rows:
        logger.warning("未获取到交易日历数据")
        return 0
    
    df = pd.DataFrame(rows, columns=rs.fields)
    
    # 写入数据库
    try:
        field_mapping = {
            'calendar_date': 'trade_date',
            'is_trading_day': 'is_trade_day'
        }
        
        df_to_write = df.rename(columns=field_mapping)
        
        # 转换日期格式
        if 'trade_date' in df_to_write.columns:
            df_to_write['trade_date'] = pd.to_datetime(df_to_write['trade_date'], errors='coerce').dt.date
        
        # 转换is_trade_day为整数
        if 'is_trade_day' in df_to_write.columns:
            df_to_write['is_trade_day'] = df_to_write['is_trade_day'].astype(int)
        
        cols_to_write = ['trade_date', 'is_trade_day']
        cols_to_write = [col for col in cols_to_write if col in df_to_write.columns]
        
        if cols_to_write:
            df_final = df_to_write[cols_to_write].copy()
            upsert_df(df_final, "trade_calendar", engine, if_exists="append")
            logger.info(f"交易日历数据下载完成，共 {len(df_final)} 条记录")
            return len(df_final)
        else:
            logger.warning(f"交易日历字段不完整，字段: {list(df.columns)}")
            return 0
    except Exception as e:
        logger.error(f"交易日历写入失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


# ==================== 主函数 ====================
def main():
    """主函数：下载所有扩展数据"""
    logger.info("="*70)
    logger.info("🚀 开始下载BaoStock扩展数据")
    logger.info("="*70)
    
    try:
        # 1. 下载行业分类数据
        logger.info("\n1️⃣ 下载行业分类数据...")
        fetch_stock_industry()
        
        # 2. 下载指数数据
        logger.info("\n2️⃣ 下载指数数据...")
        fetch_index_daily()
        
        # 3. 下载成分股数据（不需要股票列表）
        logger.info("\n3️⃣ 下载指数成分股数据...")
        fetch_index_stocks()
        
        # 4. 下载交易日历（不需要股票列表，最近1个月）
        logger.info("\n4️⃣ 下载交易日历数据（最近1个月）...")
        today = datetime.now()
        one_month_ago = today - timedelta(days=30)
        start_date = one_month_ago.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        fetch_trade_dates(start_date=start_date, end_date=end_date)
        
        # 5. 获取股票列表（用于财务数据下载）
        logger.info("\n5️⃣ 获取股票列表...")
        from fetch_data import fetch_stock_basic_info
        codes_df = fetch_stock_basic_info()
        
        if codes_df is not None and len(codes_df) > 0:
            ts_codes = codes_df['ts_code']
            
            # 下载最近2年的财务数据（确保有已发布的数据）
            # 财务数据通常有延迟，所以下载最近2年所有季度的数据
            today = datetime.now()
            current_year = today.year
            current_month = today.month
            
            # 下载最近2年的数据（从当前年份往前推2年）
            years = list(range(current_year - 1, current_year + 1))
            # 下载所有4个季度
            quarters = [1, 2, 3, 4]
            
            # 计算日期范围（用于日志显示）
            start_date = (datetime(current_year - 1, 1, 1) - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            
            logger.info(f"📅 数据下载时间范围: {start_date} ~ {end_date}")
            logger.info(f"📅 涉及年份: {years}, 季度: {quarters}")
            logger.info(f"📊 总共需要下载 {len(ts_codes)} 只股票的数据")
            
            # 高优先级数据（全量下载）
            logger.info("\n6️⃣ 下载高优先级财务数据（全量下载）...")
            
            # 6.1 利润表数据
            logger.info("  6.1 利润表数据...")
            fetch_profit_data(ts_codes, years=years, quarters=quarters)
            
            # 6.2 资产负债表数据
            logger.info("  6.2 资产负债表数据...")
            fetch_balance_data(ts_codes, years=years, quarters=quarters)
            
            # 6.3 现金流量表数据
            logger.info("  6.3 现金流量表数据...")
            fetch_cashflow_data(ts_codes, years=years, quarters=quarters)
            
            # 6.4 业绩快报数据
            logger.info("  6.4 业绩快报数据...")
            fetch_performance_express(ts_codes, start_date=start_date, end_date=end_date)
            
            # 中优先级数据（全量下载）
            logger.info("\n7️⃣ 下载中优先级财务数据（全量下载）...")
            
            # 7.1 成长能力数据
            logger.info("  7.1 成长能力数据...")
            growth_data, network_retry_candidates = fetch_growth_data(ts_codes, years=years, quarters=quarters)
            
            # 7.2 营运能力数据
            logger.info("  7.2 营运能力数据...")
            fetch_operation_data(ts_codes, years=years, quarters=quarters)
            
            # 7.3 杜邦指数数据
            logger.info("  7.3 杜邦指数数据...")
            fetch_dupont_data(ts_codes, years=years, quarters=quarters)
            
            # 7.4 股息分红数据（按年份下载，最近1个月可能跨年）
            logger.info("  7.4 股息分红数据...")
            fetch_dividend_data(ts_codes, years=years)
            
            # 低优先级数据（全量下载）
            logger.info("\n8️⃣ 下载低优先级数据（全量下载）...")
            
            # 8.1 复权因子数据
            logger.info("  8.1 复权因子数据...")
            fetch_adjust_factor(ts_codes, start_date=start_date, end_date=end_date)
            
            # 8.2 业绩预告
            logger.info("  8.2 业绩预告数据...")
            fetch_performance_forecast(ts_codes, start_date=start_date, end_date=end_date)
        
        logger.info("\n" + "="*70)
        logger.info("✅ 扩展数据下载完成")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"❌ 扩展数据下载失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()

