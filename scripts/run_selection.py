import pandas as pd
from pathlib import Path
from tradingagents.factors.price_volume import MomentumFactor, VolumeFactor
from tradingagents.llm_alpha.scorer import LLMScorer
from tradingagents.selection.scorer import calculate_alpha


def run_selection(date: str) -> None:
    base = Path(__file__).resolve().parents[1]
    data_file = base / f"data/{date}.csv"
    llm_file = base / f"data/llm/{date}.csv"

    data = pd.read_csv(data_file) if data_file.exists() else pd.DataFrame()
    if data.empty:
        print(f"No data found: {data_file}")
        return

    momentum = MomentumFactor().calculate(data).rename('score')
    volume = VolumeFactor().calculate(data).rename('score')

    if llm_file.exists():
        llm_df = pd.read_csv(llm_file)
        llm_scores = LLMScorer(llm_df).score()[['score']]
    else:
        llm_scores = pd.DataFrame({'score': pd.Series(0.0, index=momentum.index)})

    factors_df = pd.DataFrame({'score': momentum.fillna(0.0)})
    sector_df = pd.DataFrame({'score': volume.fillna(0.0)})

    alpha = calculate_alpha(factors_df, llm_scores, sector_df)
    print(alpha.tail())


if __name__ == "__main__":
    run_selection('2025-10-29')
