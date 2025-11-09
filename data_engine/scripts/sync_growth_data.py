#!/usr/bin/env python3
"""Incremental sync tool for stock_financials_growth data."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / ".."))

from config import DB_URL  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402
from fetch_extended_data import fetch_growth_data  # noqa: E402

DEFAULT_LIMIT = 50


def current_year() -> int:
    return datetime.now().year


def compute_min_year(freshness_years: int) -> int:
    year = current_year() - max(freshness_years - 1, 0)
    return max(2005, year)  # BaoStock earliest year


def fetch_missing_codes(engine, min_year: int, limit: int, offset: int = 0) -> List[str]:
    query = f"""
        WITH latest AS (
            SELECT ts_code, MAX(year) AS max_year
            FROM stock_financials_growth
            GROUP BY ts_code
        )
        SELECT b.ts_code
        FROM vw_stock_basic_info_unique b
        LEFT JOIN latest lg ON b.ts_code = lg.ts_code
        WHERE lg.max_year IS NULL OR lg.max_year < :min_year
        ORDER BY b.ts_code
        LIMIT {limit} OFFSET {offset}
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), {"min_year": min_year}).fetchall()
    return [row[0] for row in rows]


def count_pending(engine, min_year: int) -> int:
    with engine.connect() as conn:
        total = conn.execute(
            text(
                """
                WITH latest AS (
                    SELECT ts_code, MAX(year) AS max_year
                    FROM stock_financials_growth
                    GROUP BY ts_code
                )
                SELECT COUNT(*)
                FROM vw_stock_basic_info_unique b
                LEFT JOIN latest lg ON b.ts_code = lg.ts_code
                WHERE lg.max_year IS NULL OR lg.max_year < :min_year
                """
            ),
            {"min_year": min_year},
        ).scalar()
    return int(total or 0)


def run_batch(engine, codes: Iterable[str]) -> int:
    codes = list(dict.fromkeys(codes))
    if not codes:
        return 0
    series = pd.Series(codes, name="ts_code")
    fetch_growth_data(series)
    return len(codes)


def parse_args():
    parser = argparse.ArgumentParser(description="Incremental growth-data synchronizer")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Max stocks per batch")
    parser.add_argument("--offset", type=int, default=0, help="Offset inside pending list")
    parser.add_argument(
        "--freshness-years",
        type=int,
        default=1,
        help="Require latest growth data to be within this number of years",
    )
    parser.add_argument("--loop", action="store_true", help="Process continuously until queue exhausted")
    parser.add_argument("--sleep", type=int, default=60, help="Delay between loop iterations (seconds)")
    parser.add_argument(
        "--codes",
        nargs="*",
        help="Optional explicit ts_code list (skip DB scan)",
    )
    parser.add_argument(
        "--codes-file",
        type=Path,
        help="Path to text file containing ts_codes (one per line) to process",
    )
    return parser.parse_args()


def load_codes_from_file(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def main():
    args = parse_args()
    engine = get_engine(DB_URL)

    if args.codes or args.codes_file:
        codes: List[str] = []
        if args.codes:
            codes.extend(args.codes)
        if args.codes_file:
            codes.extend(load_codes_from_file(args.codes_file))
        codes = list(dict.fromkeys([code.strip().upper() for code in codes if code.strip()]))
        if not codes:
            print("✅ 没有有效的股票代码可处理")
            return
        print(f"🚀 手动同步 {len(codes)} 支股票：{codes[:5]}{'...' if len(codes) > 5 else ''}")
        run_batch(engine, codes)
        print("✅ 手动同步完成")
        return

    min_year = compute_min_year(args.freshness_years)
    loop = args.loop
    iteration = 0

    while True:
        pending_total = count_pending(engine, min_year)
        if pending_total == 0:
            print("🎉 成长数据已满足指定的时间范围，无需同步")
            break

        print(
            f"📝 待同步股票：{pending_total} 支（需要至少 {min_year} 年的数据）"
        )
        codes = fetch_missing_codes(engine, min_year, args.limit, args.offset)
        if not codes:
            print("✅ 当前批次没有可同步的股票")
            break

        iteration += 1
        print(
            f"🚀 第 {iteration} 批（{len(codes)} 支）："
            f"{', '.join(codes[:min(5, len(codes))])}{'...' if len(codes) > 5 else ''}"
        )
        start = time.time()
        try:
            run_batch(engine, codes)
        except Exception as exc:
            print(f"❌ 同步失败: {exc}")
        else:
            elapsed = time.time() - start
            print(f"✅ 批次完成，用时 {elapsed:.1f} 秒")

        if not loop:
            break

        print(f"⏱️ {args.sleep} 秒后处理下一批...")
        time.sleep(max(args.sleep, 1))

    print("🏁 同步流程结束")


if __name__ == "__main__":
    main()
