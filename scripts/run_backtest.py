import pandas as pd
from pathlib import Path
from tradingagents.backtest.engine import BacktestEngine


def run_backtest() -> None:
    base = Path(__file__).resolve().parents[1]
    data_file = base / "data/backtest_data.csv"
    data = pd.read_csv(data_file) if data_file.exists() else pd.DataFrame()
    if data.empty:
        print(f"No backtest data found: {data_file}")
        return

    strategies = ['momentum', 'mean_reversion']
    engine = BacktestEngine(data, strategies)
    engine.execute()
    print(f"Orders: {engine.orders}")


if __name__ == "__main__":
    run_backtest()
