import os
import time
from datetime import datetime, timedelta
import pandas as pd

from utils.logger import setup_logger
from utils.retry import retry
from utils.db_utils import get_engine, upsert_df

from config import (
    DB_URL, START_DATE, END_DATE,
    USE_BAOSTOCK, USE_AKSHARE, USE_TUSHARE,
    TUSHARE_TOKEN, SLEEP_SEC_TUSHARE, SLEEP_SEC_WEB
)

logger = setup_logger(log_file=os.path.join(os.path.dirname(__file__), "data_cache/update.log"))
engine = get_engine(DB_URL)

# 全局engine，供其他函数使用

# ---------- 可选：Baostock ----------
if USE_BAOSTOCK:
    import baostock as bs

# ---------- 可选：AkShare ----------
if USE_AKSHARE:
    import akshare as ak

# ---------- 可选：TuShare ----------
if USE_TUSHARE:
    import tushare as ts
    if TUSHARE_TOKEN and TUSHARE_TOKEN != "PUT_YOUR_TUSHARE_TOKEN_HERE":
        ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api() if TUSHARE_TOKEN else None
else:
    pro = None


# ------------------ 基础信息（优先 baostock，回退 tushare） ------------------
@retry(tries=5, delay=1.0)
def fetch_stock_basic_info():
    df = None
    if USE_BAOSTOCK:
        lg = bs.login()
        if lg.error_code != '0':
            logger.warning(f"baostock 登录失败: {lg.error_msg}")
        else:
            rs = bs.query_stock_basic()
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            df = pd.DataFrame(rows, columns=rs.fields)
            bs.logout()
    if (df is None or df.empty) and pro is not None:
        # tushare 回退
        df = pro.stock_basic(exchange='', list_status='L',
                             fields='ts_code,symbol,name,area,industry,market,list_date,is_hs')
    if df is None or df.empty:
        raise RuntimeError("获取基础信息失败（baostock/tushare均不可用）。")
    # 规范列/类型
    if 'code' in df.columns and 'ts_code' not in df.columns:
        # baostock 的 code 形如 "sh.600000"，转 ts_code 风格
        def to_ts(code):
            p = str(code).split('.')
            return (p[1] + ('.SH' if p[0]=='sh' else '.SZ')) if len(p)==2 else code
        df['ts_code'] = df['code'].map(to_ts)
    df = df.drop_duplicates(subset=['ts_code'])
    upsert_df(df, "stock_basic_info", engine, if_exists="replace")
    logger.info(f"stock_basic_info 写入 {len(df)} 条")
    return df[['ts_code']].dropna()


# ------------------ 日行情（优先 baostock） ------------------
@retry(tries=5, delay=1.0)
def fetch_market_daily(ts_codes: pd.Series):
    if not USE_BAOSTOCK:
        logger.warning("未启用 Baostock，跳过日行情获取。")
        return 0

    import baostock as bs
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")

    total = 0
    for i, row in ts_codes.reset_index(drop=True).iterrows():
        ts_code = row['ts_code']
        # 转 baostock 代码风格
        if ts_code.endswith(".SH"):
            code = "sh." + ts_code.split('.')[0]
        else:
            code = "sz." + ts_code.split('.')[0]
        # 获取K线数据和财务指标
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,preclose,pctChg,volume,amount,turn,peTTM,pbMRQ,psTTM",
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
            # 标准列名
            df.rename(columns={"date":"trade_date","pctChg":"pct_chg","turn":"turnover_rate"}, inplace=True)
            df["ts_code"] = ts_code
            # 删除code列（baostock返回，但表结构不需要）
            if 'code' in df.columns:
                df = df.drop(columns=['code'])
            # 修正列名：preclose -> preclose（保持一致）
            if 'pre_close' in df.columns and 'preclose' not in df.columns:
                df = df.rename(columns={'pre_close': 'preclose'})
            # 修正列名：vol -> volume
            if 'vol' in df.columns and 'volume' not in df.columns:
                df = df.rename(columns={'vol': 'volume'})
            upsert_df(df, "stock_market_daily", engine, if_exists="append")
            total += len(df)
            
            # 同时将PE/PB/PS数据写入财务表
            if 'peTTM' in df.columns or 'pbMRQ' in df.columns:
                df_fin = df[['ts_code', 'trade_date']].copy()
                if 'peTTM' in df.columns:
                    df_fin['pe'] = pd.to_numeric(df['peTTM'], errors='coerce')
                if 'pbMRQ' in df.columns:
                    df_fin['pb'] = pd.to_numeric(df['pbMRQ'], errors='coerce')
                if 'psTTM' in df.columns:
                    df_fin['ps'] = pd.to_numeric(df['psTTM'], errors='coerce')
                # 补充其他字段
                for col in ['pcf','roe','roa','eps','bps','total_mv','circ_mv','revenue_yoy','net_profit_yoy','gross_profit_margin']:
                    df_fin[col] = None
                df_fin = df_fin.dropna(subset=['pe', 'pb'], how='all')  # 保留至少有一个财务指标的记录
                if not df_fin.empty:
                    upsert_df(df_fin, "stock_financials", engine, if_exists="append")
        if (i+1) % 20 == 0:
            logger.info(f"日K进度 {i+1}/{len(ts_codes)}")
        time.sleep(SLEEP_SEC_WEB)
    bs.logout()
    logger.info(f"stock_market_daily 共写入 {total} 行")
    return total


# ------------------ 财务/估值（日频快照，优先baostock获取，回退akshare） ------------------
@retry(tries=5, delay=1.0)
def fetch_financials_daily_basic():
    # 直接返回0，财务数据在日行情中已经包含
    logger.info("财务估值数据从日行情中获取")
    return 0
    
    # 以下为原有逻辑（tushare/akshare回退）
    total = 0
    if pro is not None and USE_TUSHARE:
        # 用 tushare 的 daily_basic 批量拉取
        trade_dates = pd.date_range(START_DATE, END_DATE, freq="B").strftime("%Y%m%d").tolist()
        for i, td in enumerate(trade_dates):
            try:
                df = pro.daily_basic(trade_date=td,
                                     fields="ts_code,trade_date,pe,pb,ps,ps_ttm,total_mv,circ_mv")
                if df is not None and not df.empty:
                    # align schema
                    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
                    df['pcf'] = None
                    df['roe'] = None
                    df['roa'] = None
                    df['eps'] = None
                    df['bps'] = None
                    df['revenue_yoy'] = None
                    df['net_profit_yoy'] = None
                    df['gross_profit_margin'] = None
                    upsert_df(df, "stock_financials", engine, if_exists="append")
                    total += len(df)
            except Exception as e:
                logger.warning(f"daily_basic {td} 异常: {e}")
            time.sleep(SLEEP_SEC_TUSHARE)
        logger.info(f"stock_financials 写入 {total} 行（tushare daily_basic）")
        return total

    # 回退到 akshare（实时/当日快照）
    if USE_AKSHARE:
        try:
            df = ak.stock_zh_a_spot_em()
            # 映射到目标字段
            m = {
                "代码":"ts_code", "日期":"trade_date",
                "市盈率-动态":"pe", "市净率":"pb", "市销率":"ps",
                "总市值":"total_mv", "流通市值":"circ_mv"
            }
            df = df.rename(columns=m)
            if "ts_code" not in df.columns and "代码" in df.columns:
                # akshare 返回 600000.SH 风格
                pass
            df["trade_date"] = pd.to_datetime(datetime.now().date())
            needed = ["ts_code","trade_date","pe","pb","ps","pcf",
                      "roe","roa","eps","bps","total_mv","circ_mv",
                      "revenue_yoy","net_profit_yoy","gross_profit_margin"]
            for c in needed:
                if c not in df.columns:
                    df[c] = None
            upsert_df(df[needed], "stock_financials", engine, if_exists="append")
            logger.info(f"stock_financials 写入 {len(df)} 行（akshare spot 回退）")
            return len(df)
        except Exception as e:
            raise RuntimeError(f"akshare 财务快照失败: {e}")
    raise RuntimeError("未能获取财务/估值数据。")


# ------------------ 资金流向（tushare） ------------------
@retry(tries=5, delay=1.0)
def fetch_moneyflow():
    if pro is None:
        logger.warning("未配置 TUSHARE_TOKEN，跳过资金流向。")
        return 0
    dates = pd.date_range(START_DATE, END_DATE, freq="B").strftime("%Y%m%d").tolist()
    total = 0
    for i, td in enumerate(dates):
        try:
            df = pro.moneyflow(trade_date=td)
            if df is not None and not df.empty:
                df.rename(columns={
                    "buy_sm_vol":"super_large","buy_lg_vol":"large",
                    "buy_md_vol":"medium","buy_sm_vol.1":"small"  # 防止重名，这里仅示例，实际以tushare字段为准
                }, inplace=True, errors="ignore")
                # 统一列
                for col in ["net_mf_amount","net_mf_ratio","super_large","large","medium","small"]:
                    if col not in df.columns:
                        df[col] = None
                df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
                keep = ["ts_code","trade_date","net_mf_amount","net_mf_ratio","super_large","large","medium","small"]
                upsert_df(df[keep], "stock_moneyflow", engine, if_exists="append")
                total += len(df)
        except Exception as e:
            logger.warning(f"moneyflow {td} 异常: {e}")
        time.sleep(SLEEP_SEC_TUSHARE)
    logger.info(f"stock_moneyflow 写入 {total} 行")
    return total


# ------------------ 行业/概念（tushare & akshare 组合） ------------------
@retry(tries=5, delay=1.0)
def fetch_concept_industry():
    total = 0
    # tushare 概念
    if pro is not None:
        try:
            concepts = pro.concept()
            for _, c in concepts.iterrows():
                cid = c['code']
                detail = pro.concept_detail(id=cid, fields="id,ts_code,name")
                if detail is not None and not detail.empty:
                    detail['concept'] = c['name']
                    detail = detail[['ts_code','concept']]
                    upsert_df(detail, "stock_concept_industry", engine, if_exists="append")
                    total += len(detail)
                time.sleep(SLEEP_SEC_TUSHARE)
        except Exception as e:
            logger.warning(f"概念抓取异常: {e}")

    # akshare 行业（申万/证监会）可按需补充
    # 这里先略，避免不同来源口径冲突

    logger.info(f"stock_concept_industry 写入 {total} 行")
    return total


# ------------------ 市场指数（日线） ------------------
@retry(tries=5, delay=1.0)
def fetch_market_index_daily():
    total = 0
    if pro is None:
        logger.warning("未配置 TUSHARE_TOKEN，跳过指数。")
        return 0
    # 例：沪深300
    index_list = [("000300.SH", "沪深300")]
    for code, name in index_list:
        try:
            df = pro.index_daily(ts_code=code, start_date=START_DATE.replace("-",""), end_date=END_DATE.replace("-",""))
            if df is not None and not df.empty:
                df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
                df['index_code'] = code
                df['name'] = name
                df['pe'] = None
                df['pb'] = None
                keep = ["index_code","name","trade_date","close","pct_chg","pe","pb"]
                upsert_df(df[keep], "market_index_daily", engine, if_exists="append")
                total += len(df)
        except Exception as e:
            logger.warning(f"指数 {code} 异常: {e}")
        time.sleep(SLEEP_SEC_TUSHARE)
    logger.info(f"market_index_daily 写入 {total} 行")
    return total


def main():
    logger.info(f"抓取窗口: {START_DATE} ~ {END_DATE}")
    codes_df = fetch_stock_basic_info()
    fetch_financials_daily_basic()
    # Tushare禁用时跳过
    if USE_TUSHARE:
        fetch_market_index_daily()
        fetch_concept_industry()
    # 限制规模：仅对前若干只股票拉日K（避免初次运行过慢，可在生产中放开）
    head_codes = codes_df.head(400)
    fetch_market_daily(head_codes)

if __name__ == "__main__":
    main()
