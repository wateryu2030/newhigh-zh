#!/usr/bin/env python3
"""
Backfill market capitalization for `stock_financials` using existing market data.

We approximate total market cap (total_mv) from the latest daily trading data:
    float_shares ≈ (turnover_amount / close_price) / (turnover_rate / 100)
    total_mv ≈ close_price * float_shares

`turnover_amount` is stored in `stock_market_daily.amount` (单位: 万元) and
`turnover_rate` in `stock_market_daily.turnover_rate`.

This script writes the estimated `total_mv` back into `stock_financials`.
Optionally, `circ_mv` can be populated later when reliable free-float shares
data becomes available.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text

# Ensure data_engine package is importable
DATA_ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(DATA_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_ENGINE_DIR))

from config import DB_URL  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402
from utils.fast_db_writer import fast_upsert_df  # noqa: E402


def load_targets(engine, limit: Optional[int], force: bool) -> pd.DataFrame:
    """Identify stocks and dates needing market cap backfill."""
    with engine.connect() as conn:
        if force:
            query = text(
                """
                WITH latest AS (
                    SELECT ts_code, MAX(trade_date) AS trade_date
                    FROM stock_market_daily
                    GROUP BY ts_code
                )
                SELECT l.ts_code, l.trade_date
                FROM latest l
                ORDER BY l.trade_date DESC
                """
            )
            df = pd.read_sql_query(query, conn)
        else:
            query = text(
                """
                WITH latest AS (
                    SELECT ts_code, MAX(trade_date) AS trade_date
                    FROM stock_market_daily
                    GROUP BY ts_code
                )
                SELECT l.ts_code, l.trade_date
                FROM latest l
                LEFT JOIN stock_financials f
                    ON l.ts_code = f.ts_code AND l.trade_date = f.trade_date
                WHERE f.total_mv IS NULL OR f.total_mv <= 0
                ORDER BY l.trade_date DESC
                """
            )
            df = pd.read_sql_query(query, conn)
    if df.empty:
        return df
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if limit:
        return df.head(limit)
    return df


def load_market_snapshot(engine, ts_code: str, trade_date: str) -> Optional[pd.Series]:
    """Fetch the relevant market row for computation."""
    with engine.connect() as conn:
        query = text(
            """
            SELECT ts_code, trade_date, close, amount, turnover_rate
            FROM stock_market_daily
            WHERE ts_code = :ts_code AND trade_date = :trade_date
            LIMIT 1
            """
        )
        df = pd.read_sql_query(query, conn, params={"ts_code": ts_code, "trade_date": trade_date})
    if df.empty:
        return None
    return df.iloc[0]


def compute_market_cap(snapshot: pd.Series) -> Optional[float]:
    close = pd.to_numeric(snapshot.get("close"), errors="coerce")
    amount = pd.to_numeric(snapshot.get("amount"), errors="coerce")
    turnover_rate = pd.to_numeric(snapshot.get("turnover_rate"), errors="coerce")

    if pd.isna(close) or close <= 0:
        return None
    if pd.isna(amount) or amount <= 0:
        return None
    if pd.isna(turnover_rate) or turnover_rate <= 0:
        return None

    # BaoStock amount unit is 10,000 RMB
    turnover_amount_yuan = amount * 10_000
    try:
        approx_volume = turnover_amount_yuan / close
        float_shares = approx_volume / (turnover_rate / 100)
        total_mv = close * float_shares
        if total_mv is None or not pd.notna(total_mv) or total_mv <= 0:
            return None
        return float(total_mv)
    except ZeroDivisionError:
        return None


def backfill(engine, limit: Optional[int], force: bool, dry_run: bool) -> None:
    targets = load_targets(engine, limit, force)
    print(f"待处理股票: {len(targets)}")

    if targets.empty:
        print("没有需要回填的股票。")
        return

    updates = []
    success = 0
    fail = 0

    for idx, row in targets.iterrows():
        ts_code = row["ts_code"]
        trade_date = row["trade_date"]
        snapshot = load_market_snapshot(engine, ts_code, trade_date)
        if snapshot is None:
            print(f"[WARN] {ts_code} {trade_date} 未找到行情数据")
            fail += 1
            continue

        total_mv = compute_market_cap(snapshot)
        if total_mv is None:
            print(f"[WARN] {ts_code} {trade_date} 无法计算市值（缺少成交额/换手率/价格）")
            fail += 1
            continue

        df_row = pd.DataFrame(
            [
                {
                    "ts_code": ts_code,
                    "trade_date": trade_date,
                    "total_mv": total_mv,
                    "circ_mv": None,
                    "update_time": datetime.now(timezone.utc),
                }
            ]
        )
        updates.append(df_row)
        success += 1

        if (idx + 1) % 100 == 0:
            print(f"[INFO] 进度 {idx + 1}/{len(targets)}，成功 {success}，失败 {fail}")

    if not updates:
        print("没有可写入的数据")
        return

    result_df = pd.concat(updates, ignore_index=True)
    if dry_run:
        print("Dry run 模式，预览前5行：")
        print(result_df.head())
    else:
        fast_upsert_df(result_df, "stock_financials", engine, if_exists="append")
        print(f"写入完成: {len(result_df)} 行（成功 {success}，失败 {fail}）")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="回填 stock_financials 市值字段")
    parser.add_argument("--limit", type=int, default=None, help="限制处理股票数量")
    parser.add_argument("--force", action="store_true", help="即使已有市值也重新计算")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写入数据库")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = get_engine(DB_URL)
    backfill(engine, args.limit, args.force, args.dry_run)


if __name__ == "__main__":
    main()

