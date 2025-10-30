import pandas as pd
from abc import ABC, abstractmethod


class BaseFactor(ABC):
    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """Calculate factor series given OHLCV DataFrame."""
        pass

    @staticmethod
    def normalize(factor: pd.Series) -> pd.Series:
        """Z-score normalization with sample std (ddof=1)."""
        if factor is None or len(factor) == 0:
            return factor
        std = factor.std(ddof=1)
        if std == 0 or pd.isna(std):
            return pd.Series([0.0] * len(factor), index=factor.index)
        return (factor - factor.mean()) / std
