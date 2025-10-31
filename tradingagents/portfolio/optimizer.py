import numpy as np
import pandas as pd
from typing import Optional


class PortfolioOptimizer:
    def __init__(self, max_weight: float = 0.1, risk_free_rate: float = 0.03,
                 industry_cap: float = 0.3, turnover_cap: float = 0.3):
        self.max_weight = float(max_weight)
        self.risk_free_rate = float(risk_free_rate)
        self.industry_cap = float(industry_cap)
        self.turnover_cap = float(turnover_cap)

    def optimize(self, alpha: pd.Series, vol: pd.Series,
                 correlation_matrix: Optional[pd.DataFrame] = None,
                 industry: Optional[pd.Series] = None,
                 prev_weights: Optional[pd.Series] = None) -> pd.Series:
        alpha = alpha.fillna(0.0)
        vol = vol.replace(0, np.nan).fillna(vol[vol > 0].min() or 1.0)
        raw = alpha / vol
        w = np.clip(raw, 0, self.max_weight)
        if w.sum() > 1.0:
            w = w / w.sum()
        w = pd.Series(w, index=alpha.index)

        # 行业暴露约束：每个行业不超过 industry_cap
        if industry is not None and len(industry) == len(w):
            df = pd.DataFrame({'w': w, 'ind': industry})
            for ind_val, grp in df.groupby('ind'):
                total = grp['w'].sum()
                if total > self.industry_cap:
                    scale = self.industry_cap / total
                    df.loc[grp.index, 'w'] *= scale
            w = df['w']

        # 换手控制：限制 sum(|w - w_prev|) <= turnover_cap
        if prev_weights is not None and len(prev_weights) == len(w):
            prev = prev_weights.reindex(w.index).fillna(0.0)
            diff = (w - prev).abs().sum()
            if diff > self.turnover_cap and diff > 0:
                # 通过线性插值缩放到预算内
                lam = self.turnover_cap / diff
                w = prev + lam * (w - prev)
                w = w.clip(lower=0)
                if w.sum() > 1.0:
                    w = w / w.sum()

        return w
