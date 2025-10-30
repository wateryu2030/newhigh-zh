import pandas as pd
from .base import BaseFactor


class MomentumFactor(BaseFactor):
    def __init__(self, window: int = 20):
        self.window = window

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")
        return data['close'].pct_change(self.window)


class VolumeFactor(BaseFactor):
    def __init__(self, window: int = 20):
        self.window = window

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        if 'volume' not in data.columns:
            raise ValueError("Data must contain 'volume' column")
        return data['volume'].pct_change(self.window)
