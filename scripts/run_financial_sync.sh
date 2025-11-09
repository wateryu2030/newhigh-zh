#!/bin/bash
# Run nightly financial data sync.
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$BASE_DIR"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="$LOG_DIR/financial_sync_$TIMESTAMP.log"
{
  echo "==== Financial Sync Started at $(date '+%Y-%m-%d %H:%M:%S') ===="
  python3 data_engine/scripts/sync_financial_data.py --loop --sleep 600 --limit 100
  echo "==== Financial Sync Finished at $(date '+%Y-%m-%d %H:%M:%S') ===="
} >> "$LOG_FILE" 2>&1
