#!/usr/bin/env python3
"""Create or refresh database views that expose deduplicated stock basics."""
from pathlib import Path
import sys

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import DB_URL  # noqa: E402
from utils.db_utils import get_engine  # noqa: E402

VIEW_SQL = text(
    """
    CREATE OR REPLACE VIEW vw_stock_basic_info_unique AS
    SELECT
        ts_code,
        MAX(NULLIF(code, '')) AS code,
        MAX(NULLIF(code_name, '')) AS code_name,
        MAX(NULLIF(ipoDate, '')) AS ipoDate,
        MAX(NULLIF(outDate, '')) AS outDate,
        MAX(NULLIF(type, '')) AS type,
        MAX(NULLIF(status, '')) AS status
    FROM stock_basic_info
    WHERE ts_code IS NOT NULL AND ts_code <> ''
    GROUP BY ts_code
    """
)


def main():
    engine = get_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(VIEW_SQL)
    print("✅ View vw_stock_basic_info_unique 已刷新")


if __name__ == "__main__":
    main()
