#!/usr/bin/env python3
"""Incremental synchronizer for financial datasets (growth, profit, cashflow, balance)."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / ".."))

from config import DB_URL  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402
from fetch_extended_data import (  # noqa: E402
    fetch_growth_data,
    fetch_profit_data,
    fetch_cashflow_data,
    fetch_balance_data,
)

ENGINE = get_engine(DB_URL)

STATUS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS data_sync_status (
    dataset VARCHAR(32) PRIMARY KEY,
    last_run_at DATETIME NULL,
    last_success_at DATETIME NULL,
    last_status VARCHAR(20) DEFAULT NULL,
    last_message TEXT,
    last_duration_sec DOUBLE,
    pending_before INT,
    pending_after INT,
    last_batch_count INT,
    success_count BIGINT DEFAULT 0,
    failure_count BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

@dataclass
class DatasetConfig:
    name: str
    table: str
    func: Callable[[pd.Series], int]
    years_arg: bool = True
    quarters_arg: bool = True
    default_freshness_years: int = 1


DATASETS: Dict[str, DatasetConfig] = {
    "growth": DatasetConfig("成长能力", "stock_financials_growth", fetch_growth_data),
    "profit": DatasetConfig("利润表", "stock_financials_profit", fetch_profit_data),
    "cashflow": DatasetConfig("现金流量表", "stock_financials_cashflow", fetch_cashflow_data),
    "balance": DatasetConfig("资产负债表", "stock_financials_balance", fetch_balance_data),
}


def ensure_status_table():
    with ENGINE.begin() as conn:
        conn.execute(text(STATUS_TABLE_SQL))


def current_year() -> int:
    return datetime.now().year


def compute_min_year(freshness_years: int) -> int:
    return max(2005, current_year() - max(freshness_years - 1, 0))


def count_pending(dataset: DatasetConfig, min_year: int) -> int:
    query = text(
        f"""
        WITH latest AS (
            SELECT ts_code, MAX(year) AS max_year
            FROM {dataset.table}
            GROUP BY ts_code
        )
        SELECT COUNT(*)
        FROM vw_stock_basic_info_unique b
        LEFT JOIN latest lg ON b.ts_code = lg.ts_code
        WHERE lg.max_year IS NULL OR lg.max_year < :min_year
        """
    )
    with ENGINE.connect() as conn:
        value = conn.execute(query, {"min_year": min_year}).scalar()
    return int(value or 0)


def fetch_pending_codes(dataset: DatasetConfig, min_year: int, limit: int, offset: int) -> List[str]:
    query = text(
        f"""
        WITH latest AS (
            SELECT ts_code, MAX(year) AS max_year
            FROM {dataset.table}
            GROUP BY ts_code
        )
        SELECT b.ts_code
        FROM vw_stock_basic_info_unique b
        LEFT JOIN latest lg ON b.ts_code = lg.ts_code
        WHERE lg.max_year IS NULL OR lg.max_year < :min_year
        ORDER BY b.ts_code
        LIMIT :limit OFFSET :offset
        """
    )
    with ENGINE.connect() as conn:
        rows = conn.execute(query, {"min_year": min_year, "limit": limit, "offset": offset}).fetchall()
    return [row[0] for row in rows]


def run_dataset_batch(dataset: DatasetConfig, codes: Iterable[str], min_year: int) -> None:
    codes_list = list(dict.fromkeys(code.strip().upper() for code in codes if code))
    if not codes_list:
        return

    years = list(range(min_year, current_year() + 1)) or [current_year()]
    kwargs: Dict[str, Optional[List[int]]] = {}
    if dataset.years_arg:
        kwargs["years"] = years
    if dataset.quarters_arg:
        kwargs["quarters"] = [1, 2, 3, 4]

    series = pd.Series(codes_list, name="ts_code")
    dataset.func(series, **kwargs)


def update_status(
    dataset_key: str,
    status: str,
    message: str,
    duration: float,
    pending_before: int,
    pending_after: int,
    batch_count: int,
) -> None:
    last_run = datetime.now(timezone.utc)
    success_inc = 1 if status == "success" else 0
    failure_inc = 1 if status != "success" else 0
    last_success_at = last_run if status == "success" else None

    sql = text(
        """
        INSERT INTO data_sync_status (
            dataset, last_run_at, last_success_at, last_status, last_message,
            last_duration_sec, pending_before, pending_after, last_batch_count,
            success_count, failure_count
        ) VALUES (
            :dataset, :last_run_at, :last_success_at, :last_status, :last_message,
            :duration, :pending_before, :pending_after, :batch_count,
            :success_inc, :failure_inc
        )
        ON DUPLICATE KEY UPDATE
            last_run_at = VALUES(last_run_at),
            last_status = VALUES(last_status),
            last_message = VALUES(last_message),
            last_duration_sec = VALUES(last_duration_sec),
            pending_before = VALUES(pending_before),
            pending_after = VALUES(pending_after),
            last_batch_count = VALUES(last_batch_count),
            updated_at = CURRENT_TIMESTAMP,
            success_count = success_count + VALUES(success_count),
            failure_count = failure_count + VALUES(failure_count),
            last_success_at = CASE
                WHEN VALUES(last_status) = 'success' THEN VALUES(last_run_at)
                ELSE last_success_at END
        """
    )
    with ENGINE.begin() as conn:
        conn.execute(
            sql,
            {
                "dataset": dataset_key,
                "last_run_at": last_run,
                "last_success_at": last_success_at,
                "last_status": status,
                "last_message": message[:5000],
                "duration": duration,
                "pending_before": pending_before,
                "pending_after": pending_after,
                "batch_count": batch_count,
                "success_inc": success_inc,
                "failure_inc": failure_inc,
            },
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Financial data incremental synchronizer")
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=["growth", "profit", "cashflow"],
        choices=list(DATASETS.keys()),
        help="Datasets to sync",
    )
    parser.add_argument("--limit", type=int, default=50, help="Stocks per batch")
    parser.add_argument("--offset", type=int, default=0, help="Offset within pending list")
    parser.add_argument("--freshness-years", type=int, default=None, help="Minimum year requirement")
    parser.add_argument("--loop", action="store_true", help="Process batches continuously")
    parser.add_argument("--sleep", type=int, default=300, help="Delay between loop iterations (seconds)")
    parser.add_argument("--codes", nargs="*", help="Explicit ts_code list to sync")
    parser.add_argument("--codes-file", type=Path, help="Path to file containing ts_codes")
    return parser.parse_args()


def load_codes_from_file(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def sync_specific_codes(dataset_keys: List[str], codes: List[str], min_year: int) -> None:
    for key in dataset_keys:
        dataset = DATASETS[key]
        print(f"🚀 针对性同步 [{dataset.name}] {len(codes)} 支股票")
        start = time.time()
        try:
            run_dataset_batch(dataset, codes, min_year)
            update_status(
                dataset_key=key,
                status="success",
                message="manual-sync",
                duration=time.time() - start,
                pending_before=0,
                pending_after=0,
                batch_count=len(set(codes)),
            )
            print("✅ 完成")
        except Exception as exc:  # pragma: no cover
            print(f"❌ 同步失败: {exc}")
            update_status(
                dataset_key=key,
                status="failed",
                message=str(exc),
                duration=time.time() - start,
                pending_before=0,
                pending_after=0,
                batch_count=len(set(codes)),
            )


def main():
    args = parse_args()
    ensure_status_table()

    dataset_keys = args.datasets

    codes: List[str] = []
    if args.codes:
        codes.extend(args.codes)
    if args.codes_file:
        codes.extend(load_codes_from_file(args.codes_file))
    codes = list(dict.fromkeys(code.strip().upper() for code in codes if code))

    if codes:
        min_year = compute_min_year(args.freshness_years or 1)
        sync_specific_codes(dataset_keys, codes, min_year)
        print("🏁 同步流程结束")
        return

    loop = args.loop
    min_year_overrides: Dict[str, int] = {}

    while True:
        all_completed = True
        for key in dataset_keys:
            dataset = DATASETS[key]
            min_year = min_year_overrides.get(key) or compute_min_year(
                args.freshness_years or dataset.default_freshness_years
            )
            pending_before = count_pending(dataset, min_year)
            if pending_before == 0:
                update_status(
                    dataset_key=key,
                    status="success",
                    message="no-pending",
                    duration=0.0,
                    pending_before=0,
                    pending_after=0,
                    batch_count=0,
                )
                print(f"🎉 [{dataset.name}] 已满足最新年份要求，无需同步")
                continue

            all_completed = False
            print(f"📝 [{dataset.name}] 待同步 {pending_before} 支，要求年份 ≥ {min_year}")
            codes_batch = fetch_pending_codes(dataset, min_year, args.limit, args.offset)
            if not codes_batch:
                print(f"✅ [{dataset.name}] 当前批次没有可同步的股票")
                continue

            start = time.time()
            status = "success"
            message = "ok"
            try:
                run_dataset_batch(dataset, codes_batch, min_year)
            except Exception as exc:  # pragma: no cover
                status = "failed"
                message = str(exc)
                print(f"❌ [{dataset.name}] 批次失败: {exc}")
            pending_after = count_pending(dataset, min_year)
            duration = time.time() - start

            update_status(
                dataset_key=key,
                status=status,
                message=message,
                duration=duration,
                pending_before=pending_before,
                pending_after=pending_after,
                batch_count=len(codes_batch),
            )

            print(
                f"[{dataset.name}] 批次完成，用时 {duration:.1f}s，待同步 {pending_after} 支"
            )

        if not loop or all_completed:
            break
        sleep_seconds = max(args.sleep, 30)
        print(f"⏱️ {sleep_seconds} 秒后继续下一轮...\n")
        time.sleep(sleep_seconds)

    print("🏁 同步流程结束")


if __name__ == "__main__":
    main()
