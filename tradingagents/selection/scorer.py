import pandas as pd


def rank_score(df: pd.DataFrame, by: str = 'factor', group: str = 'industry') -> pd.Series:
    """Cross-sectional z-score by date and group, then convert to [-1, 1]."""
    if 'date' not in df.columns:
        raise ValueError("df must contain 'date' column")
    if by not in df.columns:
        raise ValueError(f"df must contain '{by}' column")

    z = df.groupby(['date', group])[by].transform(lambda s: (s - s.mean()) / s.std(ddof=1)) if group in df.columns else \
        df.groupby(['date'])[by].transform(lambda s: (s - s.mean()) / s.std(ddof=1))

    pct = df.groupby('date')[z.name if hasattr(z, 'name') and z.name else by].rank(pct=True)
    return 2 * pct - 1  # map to [-1, 1]


def calculate_alpha(factors: pd.DataFrame,
                    llm_scores: pd.DataFrame,
                    sector_scores: pd.DataFrame,
                    w_factor: float = 0.5,
                    w_event: float = 0.3,
                    w_sector: float = 0.2) -> pd.Series:
    """Weighted alpha from factor/LLM/sector scores. Inputs must align by index."""
    s1 = factors['score'] if 'score' in factors else factors.squeeze()
    s2 = llm_scores['score'] if 'score' in llm_scores else llm_scores.squeeze()
    s3 = sector_scores['score'] if 'score' in sector_scores else sector_scores.squeeze()
    alpha = (w_factor * s1.fillna(0) + w_event * s2.fillna(0) + w_sector * s3.fillna(0))
    return alpha
