#!/usr/bin/env python3
"""
Mark invalid (inactive) stock codes based on missing or stale market data.

Usage:
    python3 data_engine/scripts/mark_invalid_codes.py [--stale-days 365]

This script will:
  1. Ensure helper table `stock_invalid_codes` exists.
  2. Identify stocks that have never had market data or whose latest trade_date is older
     than the configured staleness threshold.
  3. Update `stock_basic_info.status` to "0" (inactive) for invalid codes.
  4. Remove codes from `stock_invalid_codes` and reset their status when they recover.
  5. Persist diagnostic details for future inspection.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import bindparam, text

# Ensure project modules are importable
CURRENT_DIR = Path(__file__).resolve().parent
DATA_ENGINE_DIR = CURRENT_DIR.parent
if str(DATA_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_ENGINE_DIR))

from config import DB_URL  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402


def create_helper_table(conn) -> None:
    """Create helper table to store invalid code metadata."""
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS stock_invalid_codes (
                ts_code VARCHAR(20) NOT NULL PRIMARY KEY,
                reason VARCHAR(255) NOT NULL,
                last_trade_date DATE NULL,
                rows_count BIGINT NOT NULL DEFAULT 0,
                stale_days INT NULL,
                detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )


def fetch_market_snapshot(conn) -> pd.DataFrame:
    """Load aggregated market availability for each stock."""
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
    return pd.read_sql_query(query, conn)


def determine_invalid_codes(
    snapshot: pd.DataFrame, stale_days: Optional[int]
) -> pd.DataFrame:
    """Return dataframe of invalid codes with reason."""
    if snapshot.empty:
        return snapshot

    invalid_mask = snapshot["rows_count"] == 0
    reasons: List[str] = []

    snapshot["last_trade_date"] = pd.to_datetime(
        snapshot["last_trade_date"], errors="coerce"
    )

    if stale_days is not None and stale_days > 0:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=stale_days)
        stale_mask = snapshot["last_trade_date"].notna() & (
            snapshot["last_trade_date"] < cutoff
        )
        snapshot.loc[stale_mask, "invalid_reason"] = (
            f"行情数据超过{stale_days}天未更新"
        )
        invalid_mask = invalid_mask | stale_mask
    snapshot.loc[snapshot["rows_count"] == 0, "invalid_reason"] = "无历史行情记录"

    invalid_df = snapshot.loc[invalid_mask].copy()
    invalid_df = invalid_df[
        ["ts_code", "code_name", "status", "rows_count", "last_trade_date", "invalid_reason"]
    ].rename(columns={"invalid_reason": "reason"})
    return invalid_df


def load_existing_invalid(conn) -> Dict[str, Dict]:
    query = text("SELECT ts_code, reason FROM stock_invalid_codes")
    rows = conn.execute(query).fetchall()
    return {row.ts_code: {"reason": row.reason} for row in rows}


def update_invalid_table(conn, invalid_df: pd.DataFrame, stale_days: Optional[int]) -> None:
    if invalid_df.empty:
        return

    insert_stmt = text(
        """
        INSERT INTO stock_invalid_codes (ts_code, reason, last_trade_date, rows_count, stale_days, detected_at)
        VALUES (:ts_code, :reason, :last_trade_date, :rows_count, :stale_days, NOW())
        ON DUPLICATE KEY UPDATE
            reason = VALUES(reason),
            last_trade_date = VALUES(last_trade_date),
            rows_count = VALUES(rows_count),
            stale_days = VALUES(stale_days),
            updated_at = NOW()
        """
    )
    records = [
        {
            "ts_code": row.ts_code,
            "reason": row.reason,
            "last_trade_date": row.last_trade_date.date()
            if pd.notna(row.last_trade_date)
            else None,
            "rows_count": int(row.rows_count),
            "stale_days": stale_days if row.reason.startswith("行情数据超过") else None,
        }
        for row in invalid_df.itertuples()
    ]
    conn.execute(insert_stmt, records)


def purge_recovered_codes(conn, codes_to_keep: List[str]) -> List[str]:
    query = text("SELECT ts_code FROM stock_invalid_codes")
    existing = {row.ts_code for row in conn.execute(query).fetchall()}
    leftover = list(existing - set(codes_to_keep))
    if leftover:
        delete_stmt = text(
            "DELETE FROM stock_invalid_codes WHERE ts_code IN :codes"
        ).bindparams(bindparam("codes", expanding=True))
        conn.execute(delete_stmt, {"codes": leftover})
    return leftover


def update_stock_status(
    conn, invalid_codes: List[str], recovered_codes: List[str]
) -> None:
    if invalid_codes:
        update_inactive = (
            text(
                "UPDATE stock_basic_info SET status = '0' WHERE ts_code IN :codes"
            ).bindparams(bindparam("codes", expanding=True))
        )
        conn.execute(update_inactive, {"codes": invalid_codes})

    if recovered_codes:
        update_active = (
            text(
                "UPDATE stock_basic_info SET status = '1' WHERE ts_code IN :codes"
            ).bindparams(bindparam("codes", expanding=True))
        )
        conn.execute(update_active, {"codes": recovered_codes})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mark invalid stock codes based on missing or stale market data."
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=None,
        help="Mark stocks as invalid if最后交易日距离今天超过该天数（默认仅标记无行情数据）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = get_engine(DB_URL)
    with engine.begin() as conn:
        create_helper_table(conn)
        snapshot = fetch_market_snapshot(conn)
        invalid_df = determine_invalid_codes(snapshot, args.stale_days)

        invalid_codes = invalid_df["ts_code"].tolist() if not invalid_df.empty else []
        update_invalid_table(conn, invalid_df, args.stale_days)
        recovered_codes = purge_recovered_codes(conn, invalid_codes)
        update_stock_status(conn, invalid_codes, recovered_codes)

    print("=== Invalid Code Summary ===")
    print(f"Total stocks analysed: {len(snapshot)}")
    print(f"Marked invalid: {len(invalid_codes)}")
    if invalid_codes:
        print("Sample invalid codes:")
        print(invalid_df.head(10).to_string(index=False))
    if recovered_codes:
        print(f"Recovered codes: {len(recovered_codes)}")
        print(", ".join(sorted(recovered_codes)[:10]))


if __name__ == "__main__":
    main()

