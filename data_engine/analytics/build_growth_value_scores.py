#!/usr/bin/env python3
"""Compute growth/value composite scores and store them in MySQL."""
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import DB_URL  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402

CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS analysis_stock_scores (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        ts_code VARCHAR(20) NOT NULL,
        stock_name VARCHAR(100),
        trade_date DATE,
        growth_period VARCHAR(8),
        pe DOUBLE,
        pb DOUBLE,
        net_profit_yoy DOUBLE,
        eps_yoy DOUBLE,
        value_score DOUBLE,
        growth_score DOUBLE,
        composite_score DOUBLE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_ts_trade (ts_code, trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
)


def percentile_rank(series: pd.Series) -> pd.Series:
    if series.isna().all():
        return pd.Series(0.5, index=series.index)
    return series.rank(pct=True, method="max")


def clip_and_fill(series: pd.Series, lower: float, upper: float, fill: float = None) -> pd.Series:
    clipped = series.astype(float)
    clipped = clipped.replace([np.inf, -np.inf], np.nan)
    clipped = clipped.clip(lower=lower, upper=upper)
    if fill is not None:
        clipped = clipped.fillna(fill)
    return clipped


def fetch_latest_market(conn) -> pd.DataFrame:
    latest_trade_date = conn.execute(text("SELECT MAX(trade_date) FROM stock_market_daily")).scalar()
    if latest_trade_date is None:
        return pd.DataFrame()
    df = pd.read_sql(
        text(
            """
            SELECT ts_code, trade_date, close, peTTM, pbMRQ, pct_chg, turnover_rate
            FROM stock_market_daily
            WHERE trade_date = :trade_date
            """
        ),
        conn,
        params={"trade_date": latest_trade_date},
    )
    return df


def fetch_latest_growth(conn) -> pd.DataFrame:
    df = pd.read_sql(
        text(
            """
            SELECT g.ts_code,
                   g.year,
                   g.quarter,
                   g.trade_date,
                   g.net_profit_yoy,
                   g.eps_yoy,
                   g.shareholders_equity_yoy,
                   g.total_assets_yoy,
                   g.profit_yoy
            FROM stock_financials_growth g
            JOIN (
                SELECT ts_code, MAX(year * 10 + quarter) AS latest_yq
                FROM stock_financials_growth
                GROUP BY ts_code
            ) latest ON g.ts_code = latest.ts_code
                     AND (g.year * 10 + g.quarter) = latest.latest_yq
        """
        ),
        conn,
    )
    return df


def build_scores():
    engine = get_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(CREATE_TABLE_SQL)

    with engine.connect() as conn:
        df_basic = pd.read_sql(
            text("SELECT ts_code, COALESCE(code_name, ts_code) AS stock_name FROM vw_stock_basic_info_unique"),
            conn,
        )
        df_market = fetch_latest_market(conn)
        df_growth = fetch_latest_growth(conn)

    if df_market.empty:
        print("⚠️ 无最新市场数据，停止计算")
        return None

    merged = df_basic.merge(df_market, on="ts_code", how="left")
    merged = merged.merge(df_growth, on="ts_code", how="left", suffixes=("", "_growth"))

    merged["peTTM"] = clip_and_fill(merged["peTTM"], 0, 200)
    merged["pbMRQ"] = clip_and_fill(merged["pbMRQ"], 0, 20)

    growth_metrics = [
        "net_profit_yoy",
        "eps_yoy",
        "shareholders_equity_yoy",
        "total_assets_yoy",
        "profit_yoy",
    ]
    for col in growth_metrics:
        if col in merged.columns:
            merged[col] = clip_and_fill(merged[col], -100, 200)

    merged["growth_score"] = 0.5
    valid_growth_cols = [col for col in ["net_profit_yoy", "eps_yoy", "profit_yoy"] if col in merged.columns]
    if valid_growth_cols:
        growth_scores = [percentile_rank(merged[col].fillna(merged[col].median())) for col in valid_growth_cols]
        merged["growth_score"] = pd.concat(growth_scores, axis=1).mean(axis=1)

    value_components = []
    if "peTTM" in merged.columns:
        value_components.append(1 - percentile_rank(merged["peTTM"].fillna(merged["peTTM"].median())))
    if "pbMRQ" in merged.columns:
        value_components.append(1 - percentile_rank(merged["pbMRQ"].fillna(merged["pbMRQ"].median())))
    merged["value_score"] = pd.concat(value_components, axis=1).mean(axis=1) if value_components else 0.5

    merged["composite_score"] = (merged["growth_score"] * 0.6 + merged["value_score"] * 0.4).round(4)
    merged["growth_score"] = merged["growth_score"].round(4)
    merged["value_score"] = merged["value_score"].round(4)

    merged["growth_period"] = merged.apply(
        lambda row: f"{int(row['year'])}Q{int(row['quarter'])}" if pd.notna(row.get("year")) and pd.notna(row.get("quarter")) else None,
        axis=1,
    )

    result_cols = [
        "ts_code",
        "stock_name",
        "trade_date",
        "growth_period",
        "peTTM",
        "pbMRQ",
        "net_profit_yoy",
        "eps_yoy",
        "value_score",
        "growth_score",
        "composite_score",
    ]
    result = merged[result_cols].copy()
    result.rename(
        columns={
            "peTTM": "pe",
            "pbMRQ": "pb",
        },
        inplace=True,
    )
    result["trade_date"] = pd.to_datetime(result["trade_date"]).dt.date
    result["updated_at"] = datetime.utcnow()

    engine = get_engine(DB_URL)
    result.to_sql("analysis_stock_scores", engine, if_exists="replace", index=False)

    latest_trade_date = result["trade_date"].dropna().max()
    print(f"✅ 评分完成，共 {len(result)} 条，trade_date={latest_trade_date}")
    return result


if __name__ == "__main__":
    build_scores()
