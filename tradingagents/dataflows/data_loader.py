from __future__ import annotations
import os
import re
import pandas as pd
from datetime import datetime

try:
    import yfinance as yf
except Exception:
    yf = None  # type: ignore

from tradingagents.utils.stock_utils import StockUtils
from tradingagents.dataflows.interface import (
    get_china_stock_data_unified,
    get_YFin_data_online,
)


def _parse_date_price_lines(text: str) -> pd.DataFrame:
    rows = []
    for line in (text or "").splitlines():
        m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2}).*?([\d.]+)", line)
        if m:
            ds = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
            try:
                rows.append({
                    'date': pd.to_datetime(ds),
                    'close': float(m.group(4)),
                })
            except Exception:
                continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates(subset=['date']).set_index('date').sort_index()
    return df


def get_price_df(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Return OHLCV-like DataFrame indexed by date. Prefers real DataFrame sources."""
    mi = StockUtils.get_market_info(ticker)
    # Non-China → yfinance
    if not mi.get('is_china') and yf is not None:
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if not df.empty:
                out = df.rename(columns=str.lower)[['open', 'high', 'low', 'close', 'volume']]
                return out
        except Exception:
            pass
    # China → unified string, parse
    try:
        s = get_china_stock_data_unified(ticker, start_date, end_date)
        df = _parse_date_price_lines(s)
        if not df.empty:
            df['open'] = df['close']
            df['high'] = df['close']
            df['low'] = df['close']
            df['volume'] = 0
            return df[['open', 'high', 'low', 'close', 'volume']]
    except Exception:
        pass
    # Fallback → try YF online string and parse
    try:
        s2 = get_YFin_data_online(ticker, start_date, end_date)
        df2 = _parse_date_price_lines(s2)
        if not df2.empty:
            df2['open'] = df2['close']
            df2['high'] = df2['close']
            df2['low'] = df2['close']
            df2['volume'] = 0
            return df2[['open', 'high', 'low', 'close', 'volume']]
    except Exception:
        pass
    return pd.DataFrame()
