from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any


class BacktestEngine:
    def __init__(self, data: pd.DataFrame, strategies: List[str]):
        self.data = data
        self.strategies = strategies
        self.orders: List[Dict[str, Any]] = []

    def execute(self) -> None:
        signals = self.calculate_signals(self.data)
        for signal in signals:
            if self.can_fill(signal):
                self.place_order(signal)

    def can_fill(self, signal: Dict[str, Any]) -> bool:
        row = signal.get('row', {})
        up = row.get('up_limit')
        down = row.get('down_limit')
        price = signal.get('price')
        side = signal.get('side')
        if side == 'BUY' and up is not None and price >= up:
            return False
        if side == 'SELL' and down is not None and price <= down:
            return False
        return True

    def calculate_signals(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        # placeholder: generate one mock signal
        if len(data) == 0:
            return []
        last = data.iloc[-1].to_dict()
        price = float(last.get('close', 10))
        return [{'side': 'BUY', 'price': price, 'row': last}]

    def place_order(self, signal: Dict[str, Any]) -> None:
        self.orders.append(signal)
