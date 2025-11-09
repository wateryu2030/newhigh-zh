#!/usr/bin/env python3
"""补充成长能力数据，仅处理数据库中缺失的股票。"""

import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DB_URL, SLEEP_SEC_WEB  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402
from fetch_extended_data import fetch_growth_data  # noqa: E402

BATCH_SIZE = 200  # 每批处理股票数
PAUSE_BETWEEN_BATCHES = 3  # 批次间隔（秒），缓解接口压力


def load_missing_ts_codes(engine):
    query = text(
        """
        SELECT DISTINCT b.ts_code
        FROM stock_basic_info b
        LEFT JOIN (
            SELECT DISTINCT ts_code FROM stock_financials_growth
        ) g ON b.ts_code = g.ts_code
        WHERE g.ts_code IS NULL
        ORDER BY b.ts_code
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df['ts_code'] if not df.empty else pd.Series(dtype=str)


def main():
    engine = get_engine(DB_URL)
    missing_ts_codes = load_missing_ts_codes(engine)
    total_missing = len(missing_ts_codes)
    if total_missing == 0:
        print("✅ 成长能力数据已经完整，无需补充。")
        return

    print(f"🔄 需要补充成长能力数据的股票数: {total_missing}")

    for start in range(0, total_missing, BATCH_SIZE):
        batch_codes = missing_ts_codes.iloc[start:start + BATCH_SIZE]
        print(
            f"➡️  处理第 {start + 1}~{start + len(batch_codes)} 支股票, "
            f"批次大小 {len(batch_codes)}"
        )
        fetch_growth_data(batch_codes)
        time.sleep(PAUSE_BETWEEN_BATCHES)

    print("✅ 成长能力数据补充任务完成")


if __name__ == "__main__":
    main()
