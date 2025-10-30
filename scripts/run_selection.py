import pandas as pd
from pathlib import Path
from tradingagents.factors.price_volume import MomentumFactor, VolumeFactor
from tradingagents.llm_alpha.scorer import LLMScorer
from tradingagents.selection.scorer import calculate_alpha
from tradingagents.dataflows.data_loader import get_price_df
from datetime import datetime, timedelta


def run_selection(date: str) -> None:
    base = Path(__file__).resolve().parents[1]
    data_file = base / f"data/{date}.csv"
    llm_file = base / f"data/llm/{date}.csv"

    if data_file.exists():
        data = pd.read_csv(data_file)
    else:
        # 若无本地csv，尝试拉取示例：按固定股票池获取60日数据
        tickers = ['000001', '600519', '002701']
        end = datetime.strptime(date, "%Y-%m-%d")
        start = (end - timedelta(days=60)).strftime("%Y-%m-%d")
        dfs = []
        for t in tickers:
            df = get_price_df(t, start, date)
            if not df.empty:
                d2 = df.copy()
                d2['ticker'] = t
                d2.reset_index(inplace=True)
                d2.rename(columns={'date': 'date'}, inplace=True)
                dfs.append(d2)
        data = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    if data.empty:
        print("No data available for selection.")
        return

    # 逐ticker计算因子（示例：使用最后一日）
    out_rows = []
    for tkr, g in data.groupby('ticker'):
        g = g.sort_values('date')
        mom = MomentumFactor().calculate(g.rename(columns={'Close': 'close', 'Volume': 'volume'}) if 'Close' in g.columns else g)
        volf = VolumeFactor().calculate(g)
        out_rows.append({'ticker': tkr, 'momentum': mom.iloc[-1] if len(mom) else 0.0, 'volume_chg': volf.iloc[-1] if len(volf) else 0.0})

    factors_df = pd.DataFrame(out_rows).set_index('ticker')
    factors_df['score'] = factors_df['momentum'].fillna(0.0)

    if llm_file.exists():
        llm_df = pd.read_csv(llm_file)
        llm_scores = LLMScorer(llm_df).score().set_index(llm_df.get('ticker', pd.Series(llm_df.index)))
    else:
        llm_scores = pd.DataFrame({'score': 0.0}, index=factors_df.index)

    sector_df = pd.DataFrame({'score': factors_df['volume_chg'].fillna(0.0)}, index=factors_df.index)

    alpha = calculate_alpha(factors_df[['score']], llm_scores[['score']], sector_df[['score']])
    print(alpha.sort_values(ascending=False).head())


if __name__ == "__main__":
    run_selection('2025-10-29')
