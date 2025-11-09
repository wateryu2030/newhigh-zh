#!/usr/bin/env python3
"""
Generate diagnostic report for market data coverage.

Usage:
    python3 data_engine/scripts/market_data_diagnostics.py [--stale-days 365]

Outputs summary statistics including:
  - Total stocks and coverage ratio.
  - List of stocks missing market data.
  - Stocks with stale data beyond the threshold.
  - Status distribution and discrepancy checks.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text

CURRENT_DIR = Path(__file__).resolve().parent
DATA_ENGINE_DIR = CURRENT_DIR.parent
if str(DATA_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_ENGINE_DIR))

from config import DB_URL  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="诊断行情数据覆盖情况并输出摘要报表"
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=365,
        help="若行情最新日期早于该天数，则视为过期（默认365天）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="每类样例展示数量（默认20条）",
    )
    return parser.parse_args()


def load_snapshot(engine) -> pd.DataFrame:
    query = text(
        """
        SELECT
            bi.ts_code,
            bi.code_name,
            bi.status,
            COUNT(md.trade_date) AS rows_count,
            MAX(md.trade_date) AS last_trade_date
        FROM stock_basic_info bi
        LEFT JOIN stock_market_daily md
            ON bi.ts_code = md.ts_code
        GROUP BY bi.ts_code, bi.code_name, bi.status
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df


def human_readable(df: pd.DataFrame, limit: int) -> str:
    if df.empty:
        return "  (无)"
    trimmed = df.head(limit).copy()
    trimmed["last_trade_date"] = trimmed["last_trade_date"].astype(str)
    return trimmed[["ts_code", "code_name", "status", "rows_count", "last_trade_date"]].to_string(
        index=False
    )


def main() -> None:
    args = parse_args()
    engine = get_engine(DB_URL)
    snapshot = load_snapshot(engine)
    if snapshot.empty:
        print("未查询到任何股票基础信息，请确认数据库配置。")
        return

    snapshot["last_trade_date"] = pd.to_datetime(
        snapshot["last_trade_date"], errors="coerce"
    )

    total = len(snapshot)
    with_data = snapshot[snapshot["rows_count"] > 0]
    without_data = snapshot[snapshot["rows_count"] == 0]

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=args.stale_days)
    stale = with_data[
        with_data["last_trade_date"].notna()
        & (with_data["last_trade_date"] < cutoff)
    ]

    status_counts = snapshot["status"].value_counts(dropna=False).sort_index()

    print("=== 行情数据诊断报表 ===")
    print(f"总股票数: {total}")
    print(f"拥有行情数据: {len(with_data)} ({len(with_data) / total:.2%})")
    print(f"缺失行情数据: {len(without_data)} ({len(without_data) / total:.2%})")
    print(
        f"行情超过 {args.stale_days} 天未更新: {len(stale)} ({len(stale) / total:.2%})"
    )
    print("\n按 status 字段统计：")
    for status, count in status_counts.items():
        ratio = count / total
        print(f"  status={status}: {count} ({ratio:.2%})")

    print("\n缺失行情数据样例：")
    print(human_readable(without_data.sort_values("ts_code"), args.limit))

    print(f"\n最新行情早于 {args.stale_days} 天样例：")
    print(
        human_readable(
            stale.sort_values("last_trade_date").reset_index(drop=True), args.limit
        )
    )

    # Status mismatch diagnostics
    active_without_data = without_data[without_data["status"] == "1"]
    inactive_with_data = with_data[with_data["status"] == "0"]

    if not active_without_data.empty:
        print("\n⚠️  标记为在市(status=1)但无行情数据的股票：")
        print(human_readable(active_without_data, args.limit))
    if not inactive_with_data.empty:
        print("\n⚠️  标记为退市(status=0)但仍有行情数据的股票：")
        print(human_readable(inactive_with_data, args.limit))


if __name__ == "__main__":
    main()

