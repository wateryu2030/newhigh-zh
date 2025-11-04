import os
import sys
import pandas as pd
import pandas_ta as ta
from pathlib import Path

# Add data_engine directory to path for imports
data_engine_dir = Path(__file__).parent
sys.path.insert(0, str(data_engine_dir))

from utils.logger import setup_logger
from utils.db_utils import get_engine, read_sql, upsert_df
from config import DB_URL

logger = setup_logger(log_file=os.path.join(os.path.dirname(__file__), "data_cache/update.log"))
engine = get_engine(DB_URL)

def compute_for_stock(ts_code: str):
    sql = f"SELECT ts_code, trade_date, open, high, low, close, volume FROM stock_market_daily WHERE ts_code='{ts_code}' ORDER BY trade_date"
    df = read_sql(sql, engine)
    if df.empty: 
        return 0
    # 确保数值列为数值类型
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    # RSI / MACD / KDJ / ATR / VOLATILITY
    df['rsi'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    if macd is not None and not macd.empty:
        macd_col = [c for c in macd.columns if 'MACD' in c and not 'SIGNAL' in c]
        if macd_col:
            df['macd'] = macd[macd_col[0]]
    kdj = ta.kdj(high=df['high'], low=df['low'], close=df['close'])
    if kdj is not None and not kdj.empty:
        # pandas_ta返回的列名可能不同，动态获取
        k_col = [c for c in kdj.columns if c.startswith('K_')]
        d_col = [c for c in kdj.columns if c.startswith('D_')]
        if k_col and d_col:
            df['kdj_k'] = kdj[k_col[0]]
            df['kdj_d'] = kdj[d_col[0]]
    atr_result = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=14)
    if atr_result is not None and not atr_result.empty:
        if isinstance(atr_result, pd.Series):
            df['atr'] = atr_result
        elif isinstance(atr_result, pd.DataFrame):
            atr_col = [c for c in atr_result.columns if 'ATR' in c]
            if atr_col:
                df['atr'] = atr_result[atr_col[0]]
    df['volatility'] = df['close'].pct_change().rolling(20).std() * (252 ** 0.5)

    # 只保留存在的列
    keep = ['ts_code','trade_date','ma5','ma20','ma60','rsi','macd','kdj_k','kdj_d','atr','volatility']
    available_cols = [c for c in keep if c in df.columns]
    upsert_df(df[available_cols].dropna(subset=['trade_date']), "stock_technical_indicators", engine, if_exists="append")
    return len(df)

def main(limit=400):
    codes = read_sql("SELECT ts_code FROM stock_basic_info LIMIT {}".format(limit), engine)
    total = 0
    for ts_code in codes['ts_code']:
        total += compute_for_stock(ts_code)
    logger.info(f"技术指标写入/更新完成, 共 {total} 行")

if __name__ == "__main__":
    main()
