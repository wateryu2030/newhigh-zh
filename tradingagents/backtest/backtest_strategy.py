#!/usr/bin/env python3
"""
回测策略接口
定义策略信号生成方法
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from tradingagents.utils.logging_init import get_logger

logger = get_logger('backtest.strategy')


class BaseStrategy(ABC):
    """策略基类"""
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            data: 股票价格数据（包含 open, high, low, close, volume）
        
        Returns:
            包含信号的DataFrame（signal列：1=买入，-1=卖出，0=持有）
        """
        pass


class MAStrategy(BaseStrategy):
    """移动平均策略（金叉死叉）"""
    
    def __init__(self, fast_period: int = 5, slow_period: int = 20):
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成MA交叉信号"""
        if data.empty or 'close' not in data.columns:
            return pd.DataFrame()
        
        result = data.copy()
        
        # 计算移动平均线
        result['ma_fast'] = result['close'].rolling(self.fast_period).mean()
        result['ma_slow'] = result['close'].rolling(self.slow_period).mean()
        
        # 生成信号：金叉买入，死叉卖出
        result['signal'] = 0
        
        # 金叉：快线上穿慢线
        golden_cross = (
            (result['ma_fast'] > result['ma_slow']) &
            (result['ma_fast'].shift(1) <= result['ma_slow'].shift(1))
        )
        result.loc[golden_cross, 'signal'] = 1
        
        # 死叉：快线下穿慢线
        death_cross = (
            (result['ma_fast'] < result['ma_slow']) &
            (result['ma_fast'].shift(1) >= result['ma_slow'].shift(1))
        )
        result.loc[death_cross, 'signal'] = -1
        
        return result[['signal', 'ma_fast', 'ma_slow']]


class MomentumStrategy(BaseStrategy):
    """动量策略"""
    
    def __init__(self, period: int = 20, threshold: float = 0.05):
        self.period = period
        self.threshold = threshold
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成动量信号"""
        if data.empty or 'close' not in data.columns:
            return pd.DataFrame()
        
        result = data.copy()
        
        # 计算动量
        result['momentum'] = result['close'].pct_change(self.period)
        
        # 生成信号
        result['signal'] = 0
        result.loc[result['momentum'] > self.threshold, 'signal'] = 1  # 买入
        result.loc[result['momentum'] < -self.threshold, 'signal'] = -1  # 卖出
        
        return result[['signal', 'momentum']]


class MLStrategy(BaseStrategy):
    """机器学习策略（使用模型预测）"""
    
    def __init__(self, model, threshold: float = 0.5):
        self.model = model
        self.threshold = threshold
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """使用模型预测生成信号"""
        if data.empty:
            return pd.DataFrame()
        
        try:
            from tradingagents.models.ml_features import extract_features, select_features
            
            # 提取特征
            features_df = extract_features(data)
            
            if features_df.empty:
                return pd.DataFrame({'signal': [0] * len(data)})
            
            # 选择特征列
            feature_cols = select_features(features_df)
            
            if feature_cols.empty:
                return pd.DataFrame({'signal': [0] * len(data)})
            
            # 预测
            if hasattr(self.model, 'predict_proba'):
                predictions = self.model.predict_proba(feature_cols.values)[:, 1]
            else:
                predictions = self.model.predict(feature_cols.values)
            
            # 生成信号：预测概率>阈值买入，否则卖出
            result = pd.DataFrame({
                'signal': (predictions > self.threshold).astype(int) * 2 - 1,  # 1或-1
                'prediction': predictions
            }, index=data.index)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ ML策略生成信号失败: {e}")
            return pd.DataFrame({'signal': [0] * len(data)})


def create_strategy(strategy_type: str, **kwargs) -> BaseStrategy:
    """
    创建策略实例
    
    Args:
        strategy_type: 策略类型（ma/momentum/ml）
        **kwargs: 策略参数
    
    Returns:
        策略实例
    """
    if strategy_type == "ma":
        return MAStrategy(
            fast_period=kwargs.get('fast_period', 5),
            slow_period=kwargs.get('slow_period', 20)
        )
    elif strategy_type == "momentum":
        return MomentumStrategy(
            period=kwargs.get('period', 20),
            threshold=kwargs.get('threshold', 0.05)
        )
    elif strategy_type == "ml":
        model = kwargs.get('model')
        if model is None:
            raise ValueError("ML策略需要提供model参数")
        return MLStrategy(model=model, threshold=kwargs.get('threshold', 0.5))
    else:
        raise ValueError(f"未知策略类型: {strategy_type}")

