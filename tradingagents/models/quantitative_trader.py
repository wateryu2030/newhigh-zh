#!/usr/bin/env python3
"""
量化交易模型核心实现
基于信号生成和风险管理的自动化交易系统
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np

from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.stock_utils import StockUtils
from tradingagents.dataflows.interface import (
    get_china_stock_data_unified,
    get_YFin_data_online
)

logger = get_logger('models.quantitative_trader')


class SignalType(Enum):
    """交易信号类型"""
    BUY = "买入"
    SELL = "卖出"
    HOLD = "持有"
    CLOSE = "平仓"


class StrategyType(Enum):
    """策略类型"""
    TREND_FOLLOWING = "趋势跟踪"
    MEAN_REVERSION = "均值回归"
    MOMENTUM = "动量策略"
    MULTI_FACTOR = "多因子策略"


class Position:
    """持仓类"""
    
    def __init__(
        self,
        ticker: str,
        entry_price: float,
        quantity: int,
        entry_date: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ):
        self.ticker = ticker
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_date = entry_date
        self.stop_loss = stop_loss
        self.take_profit = take_profit
    
    def update_stop_loss(self, price: float, trailing_stop_percent: float):
        """更新移动止损"""
        if price > self.entry_price:  # 只有盈利时才移动止损
            new_stop_loss = price * (1 - trailing_stop_percent)
            if new_stop_loss > (self.stop_loss or 0):
                self.stop_loss = new_stop_loss
    
    def get_pnl(self, current_price: float) -> float:
        """计算盈亏"""
        return (current_price - self.entry_price) * self.quantity
    
    def get_pnl_percent(self, current_price: float) -> float:
        """计算盈亏百分比"""
        return (current_price - self.entry_price) / self.entry_price * 100


class QuantitativeTrader:
    """量化交易模型"""
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        strategy_type: StrategyType = StrategyType.MULTI_FACTOR,
        max_positions: int = 10,
        risk_per_trade: float = 0.02  # 单笔交易风险2%
    ):
        """
        初始化量化交易器
        
        Args:
            initial_capital: 初始资金
            strategy_type: 策略类型
            max_positions: 最大持仓数量
            risk_per_trade: 单笔交易风险比例
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.strategy_type = strategy_type
        self.max_positions = max_positions
        self.risk_per_trade = risk_per_trade
        
        # 持仓管理
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Dict] = []
        
        # 策略参数
        self.strategy_params = self._get_strategy_params(strategy_type)
        
        logger.info(f"✅ 量化交易器初始化完成")
        logger.info(f"   初始资金: ¥{initial_capital:,.2f}")
        logger.info(f"   策略类型: {strategy_type.value}")
        logger.info(f"   最大持仓: {max_positions}")
    
    def _get_strategy_params(self, strategy_type: StrategyType) -> Dict:
        """获取策略参数"""
        params = {
            StrategyType.TREND_FOLLOWING: {
                'ma_short': 5,
                'ma_long': 20,
                'stop_loss': -0.05,      # -5%
                'take_profit': 0.15,     # +15%
                'trend_confirmation_days': 3
            },
            StrategyType.MEAN_REVERSION: {
                'bollinger_period': 20,
                'bollinger_std': 2.0,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'stop_loss': -0.03,      # -3%
                'take_profit': 0.05      # +5%
            },
            StrategyType.MOMENTUM: {
                'rsi_threshold': 60,
                'macd_threshold': 0,
                'volume_surge_threshold': 1.2,  # 成交量增长20%
                'stop_loss': -0.05,
                'take_profit': 0.20      # +20%
            },
            StrategyType.MULTI_FACTOR: {
                'min_composite_score': 70,
                'stop_loss': -0.05,
                'take_profit': 0.15,
                'weights': {
                    'technical': 0.35,
                    'fundamental': 0.35,
                    'sentiment': 0.15,
                    'news': 0.15
                }
            }
        }
        return params.get(strategy_type, params[StrategyType.MULTI_FACTOR])
    
    def generate_signal(
        self,
        ticker: str,
        current_price: float,
        market_data: Optional[pd.DataFrame] = None,
        analysis_reports: Optional[Dict[str, str]] = None
    ) -> Tuple[SignalType, float, Dict]:
        """
        生成交易信号
        
        Args:
            ticker: 股票代码
            current_price: 当前价格
            market_data: 市场数据（DataFrame）
            analysis_reports: 分析报告字典（包含各分析师的报告）
        
        Returns:
            (信号类型, 信号强度, 信号详情)
        """
        try:
            if self.strategy_type == StrategyType.TREND_FOLLOWING:
                return self._trend_following_signal(ticker, current_price, market_data)
            elif self.strategy_type == StrategyType.MEAN_REVERSION:
                return self._mean_reversion_signal(ticker, current_price, market_data)
            elif self.strategy_type == StrategyType.MOMENTUM:
                return self._momentum_signal(ticker, current_price, market_data)
            elif self.strategy_type == StrategyType.MULTI_FACTOR:
                return self._multi_factor_signal(ticker, current_price, analysis_reports)
            else:
                return SignalType.HOLD, 0.0, {}
        except Exception as e:
            logger.error(f"❌ 生成信号失败 {ticker}: {e}")
            return SignalType.HOLD, 0.0, {'error': str(e)}
    
    def _trend_following_signal(
        self,
        ticker: str,
        current_price: float,
        market_data: Optional[pd.DataFrame]
    ) -> Tuple[SignalType, float, Dict]:
        """趋势跟踪信号"""
        if market_data is None or len(market_data) < 20:
            return SignalType.HOLD, 0.0, {'reason': '数据不足，无法计算趋势信号'}
        
        try:
            params = self.strategy_params
            
            # 检查必要的列
            if 'close' not in market_data.columns:
                return SignalType.HOLD, 0.0, {'reason': '缺少收盘价数据'}
            
            if len(market_data) < params['ma_long']:
                return SignalType.HOLD, 0.0, {'reason': f'数据量不足（需要至少{params["ma_long"]}条）'}
            
            close = market_data['close']
            ma_short = close.rolling(params['ma_short']).mean().iloc[-1]
            ma_long = close.rolling(params['ma_long']).mean().iloc[-1]
            
            if len(market_data) < params['ma_short'] + 1:
                ma_short_prev = ma_short
                ma_long_prev = ma_long
            else:
                ma_short_prev = close.rolling(params['ma_short']).mean().iloc[-2]
                ma_long_prev = close.rolling(params['ma_long']).mean().iloc[-2]
        
            # 检查是否有NaN值
            if pd.isna(ma_short) or pd.isna(ma_long) or pd.isna(ma_short_prev) or pd.isna(ma_long_prev):
                return SignalType.HOLD, 0.0, {'reason': '移动平均线计算异常'}
            
            # 金叉买入
            if ma_short > ma_long and ma_short_prev <= ma_long_prev:
                strength = min((ma_short - ma_long) / ma_long * 100, 10.0)
                return SignalType.BUY, strength, {
                    'reason': f'MA{params["ma_short"]}上穿MA{params["ma_long"]}',
                    'ma_short': float(ma_short),
                    'ma_long': float(ma_long)
                }
            
            # 死叉卖出
            elif ma_short < ma_long and ma_short_prev >= ma_long_prev:
                strength = min((ma_long - ma_short) / ma_long * 100, 10.0)
                return SignalType.SELL, strength, {
                    'reason': f'MA{params["ma_short"]}下穿MA{params["ma_long"]}',
                    'ma_short': float(ma_short),
                    'ma_long': float(ma_long)
                }
            
            return SignalType.HOLD, 0.0, {'reason': '无明确趋势信号'}
            
        except Exception as e:
            logger.error(f"趋势跟踪信号计算失败: {e}", exc_info=True)
            return SignalType.HOLD, 0.0, {'reason': f'信号计算错误: {str(e)}'}
    
    def _mean_reversion_signal(
        self,
        ticker: str,
        current_price: float,
        market_data: Optional[pd.DataFrame]
    ) -> Tuple[SignalType, float, Dict]:
        """均值回归信号"""
        if market_data is None or len(market_data) < 20:
            return SignalType.HOLD, 0.0, {'reason': '数据不足，无法计算均值回归信号'}
        
        try:
            params = self.strategy_params
            if 'close' not in market_data.columns:
                return SignalType.HOLD, 0.0, {'reason': '缺少收盘价数据'}
            
            if len(market_data) < max(params['bollinger_period'], 14):
                return SignalType.HOLD, 0.0, {'reason': f'数据量不足（需要至少{max(params["bollinger_period"], 14)}条）'}
            
            close = market_data['close']
        
            # 计算布林带
            ma = close.rolling(params['bollinger_period']).mean().iloc[-1]
            std = close.rolling(params['bollinger_period']).std().iloc[-1]
            
            # 检查NaN值
            if pd.isna(ma) or pd.isna(std):
                return SignalType.HOLD, 0.0, {'reason': '布林带计算异常'}
            
            upper = ma + params['bollinger_std'] * std
            lower = ma - params['bollinger_std'] * std
            
            # 计算RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            
            # 避免除以零
            rs = gain / loss.replace(0, 1e-10)
            rsi = 100 - (100 / (1 + rs))
            rsi_current = rsi.iloc[-1]
            
            # 检查RSI是否为NaN
            if pd.isna(rsi_current):
                return SignalType.HOLD, 0.0, {'reason': 'RSI计算异常'}
            
            # 触及下轨且超卖 -> 买入
            if current_price < lower and rsi_current < params['rsi_oversold']:
                strength = min((lower - current_price) / lower * 100, 10.0)
                return SignalType.BUY, strength, {
                    'reason': '价格触及布林带下轨且RSI超卖',
                    'bollinger_lower': float(lower),
                    'rsi': float(rsi_current)
                }
            
            # 触及上轨且超买 -> 卖出
            elif current_price > upper and rsi_current > params['rsi_overbought']:
                strength = min((current_price - upper) / upper * 100, 10.0)
                return SignalType.SELL, strength, {
                    'reason': '价格触及布林带上轨且RSI超买',
                    'bollinger_upper': float(upper),
                    'rsi': float(rsi_current)
                }
            
            return SignalType.HOLD, 0.0, {'reason': '无均值回归信号'}
            
        except Exception as e:
            logger.error(f"均值回归信号计算失败: {e}", exc_info=True)
            return SignalType.HOLD, 0.0, {'reason': f'信号计算错误: {str(e)}'}
    
    def _momentum_signal(
        self,
        ticker: str,
        current_price: float,
        market_data: Optional[pd.DataFrame]
    ) -> Tuple[SignalType, float, Dict]:
        """动量策略信号"""
        if market_data is None or len(market_data) < 20:
            return SignalType.HOLD, 0.0, {'reason': '数据不足，无法计算动量信号'}
        
        try:
            params = self.strategy_params
            
            if 'close' not in market_data.columns:
                return SignalType.HOLD, 0.0, {'reason': '缺少收盘价数据'}
            
            if len(market_data) < 26:
                return SignalType.HOLD, 0.0, {'reason': '数据量不足（需要至少26条）'}
            
            close = market_data['close']
            volume = market_data['volume'] if 'volume' in market_data.columns else None
            
            # 计算RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            
            # 避免除以零
            rs = gain / loss.replace(0, 1e-10)
            rsi = 100 - (100 / (1 + rs))
            rsi_current = rsi.iloc[-1]
            
            # 检查RSI是否为NaN
            if pd.isna(rsi_current):
                return SignalType.HOLD, 0.0, {'reason': 'RSI计算异常'}
            
            # 计算MACD（简化版）
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd = ema12 - ema26
            macd_current = macd.iloc[-1]
            
            if pd.isna(macd_current):
                macd_current = 0.0
            
            # 计算成交量增长率
            volume_surge = False
            if volume is not None and len(volume) >= 20:
                try:
                    avg_volume = volume.rolling(20).mean().iloc[-1]
                    current_volume = volume.iloc[-1]
                    if not pd.isna(avg_volume) and not pd.isna(current_volume) and avg_volume > 0:
                        volume_surge = current_volume / avg_volume >= params['volume_surge_threshold']
                except:
                    volume_surge = False
            
            # 强动量买入信号
            if rsi_current > params['rsi_threshold'] and macd_current > params['macd_threshold'] and volume_surge:
                strength = min((rsi_current - params['rsi_threshold']) / 30 * 10, 10.0)
                return SignalType.BUY, strength, {
                    'reason': '强动量信号',
                    'rsi': float(rsi_current),
                    'macd': float(macd_current),
                    'volume_surge': volume_surge
                }
            
            # 动量衰竭卖出
            elif rsi_current < 50 or macd_current < 0:
                return SignalType.SELL, 5.0, {
                    'reason': '动量衰竭',
                    'rsi': float(rsi_current),
                    'macd': float(macd_current)
                }
            
            return SignalType.HOLD, 0.0, {'reason': '无动量信号'}
            
        except Exception as e:
            logger.error(f"动量信号计算失败: {e}", exc_info=True)
            return SignalType.HOLD, 0.0, {'reason': f'信号计算错误: {str(e)}'}
    
    def _multi_factor_signal(
        self,
        ticker: str,
        current_price: float,
        analysis_reports: Dict[str, str]
    ) -> Tuple[SignalType, float, Dict]:
        """多因子策略信号"""
        # 使用现有的分析报告生成信号
        # 这里需要结合stock_screener的评分逻辑
        
        # TODO: 实际实现应该：
        # 1. 解析各分析师报告
        # 2. 计算综合评分
        # 3. 根据评分生成信号
        
        # 简化实现
        return SignalType.HOLD, 0.0, {'reason': '多因子信号（待实现）'}
    
    def calculate_position_size(
        self,
        ticker: str,
        entry_price: float,
        stop_loss_price: float
    ) -> int:
        """
        计算仓位大小（基于风险）
        
        Args:
            ticker: 股票代码
            entry_price: 入场价格
            stop_loss_price: 止损价格
        
        Returns:
            建议仓位（股数）
        """
        # 单笔交易风险金额
        risk_amount = self.current_capital * self.risk_per_trade
        
        # 每股风险
        risk_per_share = abs(entry_price - stop_loss_price)
        
        if risk_per_share <= 0:
            return 0
        
        # 计算股数
        quantity = int(risk_amount / risk_per_share)
        
        # 限制最大仓位（不超过可用资金的30%）
        max_position_value = self.current_capital * 0.30
        max_quantity = int(max_position_value / entry_price)
        quantity = min(quantity, max_quantity)
        
        return quantity
    
    def execute_trade(
        self,
        ticker: str,
        signal: SignalType,
        price: float,
        quantity: Optional[int] = None,
        date: Optional[datetime] = None
    ) -> bool:
        """
        执行交易
        
        Args:
            ticker: 股票代码
            signal: 交易信号
            price: 交易价格
            quantity: 交易数量（None时自动计算）
            date: 交易日期
        
        Returns:
            是否执行成功
        """
        date = date or datetime.now()
        
        try:
            if signal == SignalType.BUY:
                # 检查是否已有持仓
                if ticker in self.positions:
                    logger.warning(f"⚠️ {ticker} 已有持仓，跳过买入")
                    return False
                
                # 检查持仓数量限制
                if len(self.positions) >= self.max_positions:
                    logger.warning(f"⚠️ 已达到最大持仓数 {self.max_positions}")
                    return False
                
                # 计算仓位
                if quantity is None:
                    stop_loss = price * (1 + self.strategy_params['stop_loss'])
                    quantity = self.calculate_position_size(ticker, price, stop_loss)
                
                if quantity <= 0:
                    logger.warning(f"⚠️ {ticker} 计算仓位为0，跳过交易")
                    return False
                
                # 检查资金
                cost = price * quantity
                if cost > self.current_capital:
                    logger.warning(f"⚠️ 资金不足，需要 ¥{cost:,.2f}，可用 ¥{self.current_capital:,.2f}")
                    return False
                
                # 创建持仓
                stop_loss = price * (1 + self.strategy_params['stop_loss'])
                take_profit = price * (1 + self.strategy_params['take_profit'])
                
                position = Position(
                    ticker=ticker,
                    entry_price=price,
                    quantity=quantity,
                    entry_date=date,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                
                self.positions[ticker] = position
                self.current_capital -= cost
                
                # 记录交易
                self.trade_history.append({
                    'date': date,
                    'ticker': ticker,
                    'action': '买入',
                    'price': price,
                    'quantity': quantity,
                    'cost': cost
                })
                
                logger.info(f"✅ 买入 {ticker}: {quantity}股 @ ¥{price:.2f}, 成本: ¥{cost:,.2f}")
                return True
            
            elif signal == SignalType.SELL or signal == SignalType.CLOSE:
                # 平仓
                if ticker not in self.positions:
                    logger.warning(f"⚠️ {ticker} 无持仓，无法卖出")
                    return False
                
                position = self.positions[ticker]
                if quantity is None:
                    quantity = position.quantity
                
                # 计算收益
                revenue = price * quantity
                pnl = (price - position.entry_price) * quantity
                pnl_percent = (price - position.entry_price) / position.entry_price * 100
                
                # 更新持仓
                position.quantity -= quantity
                if position.quantity <= 0:
                    del self.positions[ticker]
                else:
                    # 部分平仓，按比例调整成本
                    position.entry_price = (position.entry_price * position.quantity + price * quantity) / position.quantity
                
                self.current_capital += revenue
                
                # 记录交易
                self.trade_history.append({
                    'date': date,
                    'ticker': ticker,
                    'action': '卖出',
                    'price': price,
                    'quantity': quantity,
                    'revenue': revenue,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent
                })
                
                logger.info(f"✅ 卖出 {ticker}: {quantity}股 @ ¥{price:.2f}, 收益: ¥{pnl:,.2f} ({pnl_percent:.2f}%)")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 执行交易失败 {ticker}: {e}")
            return False
    
    def check_risk_management(self, ticker: str, current_price: float, date: datetime):
        """检查风险管理条件（止损、止盈）"""
        if ticker not in self.positions:
            return
        
        position = self.positions[ticker]
        
        # 检查止损
        if position.stop_loss and current_price <= position.stop_loss:
            logger.warning(f"⚠️ {ticker} 触发止损，当前价格: ¥{current_price:.2f}, 止损价: ¥{position.stop_loss:.2f}")
            self.execute_trade(ticker, SignalType.CLOSE, current_price, None, date)
            return
        
        # 检查止盈
        if position.take_profit and current_price >= position.take_profit:
            logger.info(f"🎯 {ticker} 达到止盈，当前价格: ¥{current_price:.2f}, 止盈价: ¥{position.take_profit:.2f}")
            # 可以选择全部平仓或分批止盈
            self.execute_trade(ticker, SignalType.CLOSE, current_price, None, date)
            return
        
        # 更新移动止损（如果启用）
        if hasattr(self.strategy_params, 'trailing_stop'):
            trailing_stop_percent = self.strategy_params.get('trailing_stop', 0.03)
            position.update_stop_loss(current_price, trailing_stop_percent)
    
    def get_portfolio_status(self) -> Dict[str, Any]:
        """获取投资组合状态"""
        total_value = self.current_capital
        total_cost = 0
        total_pnl = 0
        
        positions_detail = []
        for ticker, position in self.positions.items():
            # TODO: 获取当前价格
            current_price = position.entry_price  # 简化，实际需要实时价格
            pnl = position.get_pnl(current_price)
            pnl_percent = position.get_pnl_percent(current_price)
            
            position_value = current_price * position.quantity
            total_value += position_value
            total_cost += position.entry_price * position.quantity
            total_pnl += pnl
            
            positions_detail.append({
                'ticker': ticker,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'current_price': current_price,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'value': position_value
            })
        
        total_return = (total_value - self.initial_capital) / self.initial_capital * 100
        
        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'positions_value': total_value - self.current_capital,
            'total_value': total_value,
            'total_pnl': total_pnl,
            'total_return_percent': total_return,
            'positions_count': len(self.positions),
            'positions': positions_detail,
            'trade_count': len(self.trade_history)
        }
