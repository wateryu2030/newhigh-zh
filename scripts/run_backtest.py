import pandas as pd
from pathlib import Path
from tradingagents.backtest.engine import BacktestEngine
from tradingagents.dataflows.data_loader import get_price_df
from datetime import datetime, timedelta


def run_backtest() -> None:
    base = Path(__file__).resolve().parents[1]
    data_file = base / "data/backtest_data.csv"
    if data_file.exists():
        data = pd.read_csv(data_file)
    else:
        # 拉取演示数据：近60日的一个标的
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        df = get_price_df('000001', start, end)
        data = df.reset_index().rename(columns={'date': 'date'}) if not df.empty else pd.DataFrame()

    if data.empty:
        print("No backtest data available.")
        return

    strategies = ['momentum', 'mean_reversion']
    engine = BacktestEngine(data, strategies, cost_bps=5, slippage_bps=5, init_capital=100000.0)
    engine.execute()
    print(f"Orders: {engine.orders}")
    print("Metrics:", engine.metrics())


if __name__ == "__main__":
    run_backtest()
