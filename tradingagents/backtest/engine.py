from __future__ import annotations
import math
import pandas as pd
import numpy as np
from typing import List, Dict, Any


class BacktestEngine:
    def __init__(self, data: pd.DataFrame, strategies: List[str],
                 cost_bps: float = 5.0, slippage_bps: float = 5.0, init_capital: float = 100000.0,
                 t_plus_one: bool = True):
        self.data = data.copy()
        self.strategies = strategies
        self.cost_bps = float(cost_bps)
        self.slippage_bps = float(slippage_bps)
        self.init_capital = float(init_capital)
        self.t_plus_one = bool(t_plus_one)
        self.orders: List[Dict[str, Any]] = []
        self.equity = []
        self.position = 0
        self.cash = self.init_capital
        self.last_buy_date = None

    def _limit_bands(self, row: pd.Series) -> Dict[str, float]:
        # 若无明确涨跌停列，按10%简化计算
        close_y = float(row.get('prev_close', row.get('close', np.nan)))
        if not math.isnan(close_y) and close_y > 0:
            up = row.get('up_limit', close_y * 1.1)
            down = row.get('down_limit', close_y * 0.9)
        else:
            px = float(row.get('close', 0))
            up, down = (px * 1.1, px * 0.9) if px > 0 else (np.inf, -np.inf)
        return {'up': float(up), 'down': float(down)}

    def execute(self) -> None:
        if 'date' in self.data.columns:
            self.data = self.data.sort_values('date')
        signals = self.calculate_signals(self.data)
        for signal in signals:
            if self.can_fill(signal):
                self.place_order(signal)
        for idx, row in self.data.iterrows():
            price = float(row.get('close', np.nan))
            if math.isnan(price):
                continue
            equity = self.cash + self.position * price
            dt = row.get('date', idx)
            self.equity.append({'date': dt, 'equity': equity})

    def can_fill(self, signal: Dict[str, Any]) -> bool:
        row = signal.get('row', {})
        bands = self._limit_bands(pd.Series(row))
        price = signal.get('price')
        side = signal.get('side')
        dt = row.get('date')

        if side == 'SELL' and self.t_plus_one and self.last_buy_date is not None:
            if dt == self.last_buy_date:
                return False
        if side == 'BUY' and price >= bands['up']:
            return False
        if side == 'SELL' and price <= bands['down']:
            return False
        return True

    def calculate_signals(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        if len(data) < 2:
            return []
        last = data.iloc[-1].to_dict()
        price = float(last.get('close', 10))
        return [{'side': 'BUY', 'price': price, 'qty': 100, 'row': last}]

    def place_order(self, signal: Dict[str, Any]) -> None:
        side = signal.get('side')
        price = float(signal.get('price', 0))
        qty = int(signal.get('qty', 0))
        row = signal.get('row', {})
        dt = row.get('date')
        if qty <= 0 or price <= 0:
            return
        fill_price = price * (1 + self.slippage_bps / 1e4) if side == 'BUY' else price * (1 - self.slippage_bps / 1e4)
        fee = fill_price * qty * (self.cost_bps / 1e4)
        if side == 'BUY':
            cost = fill_price * qty + fee
            if self.cash >= cost:
                self.cash -= cost
                self.position += qty
                self.last_buy_date = dt
                self.orders.append({'side': side, 'price': fill_price, 'qty': qty, 'fee': fee, 'date': dt})
        elif side == 'SELL' and self.position >= qty:
            proceeds = fill_price * qty - fee
            self.cash += proceeds
            self.position -= qty
            self.orders.append({'side': side, 'price': fill_price, 'qty': qty, 'fee': fee, 'date': dt})

    def metrics(self) -> Dict[str, Any]:
        if not self.equity:
            return {}
        eq = pd.DataFrame(self.equity)
        eq['ret'] = eq['equity'].pct_change().fillna(0.0)
        total_return = eq['equity'].iloc[-1] / eq['equity'].iloc[0] - 1.0
        # 年化假设252交易日
        ann_return = (1 + total_return) ** (252 / max(1, len(eq))) - 1
        # 夏普（无风险0）
        sharpe = (eq['ret'].mean() * 252) / (eq['ret'].std(ddof=1) * np.sqrt(252) + 1e-12)
        # 最大回撤
        cum = eq['equity'].cummax()
        drawdown = (eq['equity'] / cum - 1.0).min()
        return {
            'total_return': float(total_return),
            'annualized_return': float(ann_return),
            'sharpe': float(sharpe),
            'max_drawdown': float(drawdown),
            'final_equity': float(eq['equity'].iloc[-1]),
        }
