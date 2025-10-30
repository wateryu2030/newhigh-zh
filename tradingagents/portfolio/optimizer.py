import numpy as np
import pandas as pd


class PortfolioOptimizer:
    def __init__(self, max_weight: float = 0.1, risk_free_rate: float = 0.03):
        self.max_weight = float(max_weight)
        self.risk_free_rate = float(risk_free_rate)

    def optimize(self, alpha: pd.Series, vol: pd.Series, correlation_matrix: pd.DataFrame | None = None) -> pd.Series:
        """Simple risk-parity-ish sizing using alpha/vol with max cap.
        correlation_matrix reserved for future constraints.
        """
        alpha = alpha.fillna(0.0)
        vol = vol.replace(0, np.nan).fillna(vol[vol > 0].min() or 1.0)
        raw = alpha / vol
        pos = np.clip(raw, 0, self.max_weight)
        if pos.sum() > 1.0:
            pos = pos / pos.sum()  # normalize to 100% total capital
        return pos
