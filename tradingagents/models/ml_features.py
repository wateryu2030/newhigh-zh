#!/usr/bin/env python3
"""
机器学习特征工程模块
自动提取技术指标和基本面特征
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from tradingagents.utils.logging_init import get_logger

logger = get_logger('models.ml_features')


def extract_features(df: pd.DataFrame, lookback_days: int = 20) -> pd.DataFrame:
    """
    提取技术指标和基本面特征
    
    Args:
        df: 股票价格数据（需包含 open, high, low, close, volume 列）
        lookback_days: 回看天数
    
    Returns:
        包含特征的DataFrame
    """
    if df.empty or 'close' not in df.columns:
        logger.warning("⚠️ 数据为空或缺少close列")
        return df
    
    result = df.copy()
    
    # 确保数据按日期排序
    if 'trade_date' in result.columns:
        result = result.sort_values('trade_date')
    elif result.index.name == 'trade_date' or 'date' in result.index.names:
        result = result.sort_index()
    
    close = result['close'].values
    
    # === 技术指标特征 ===
    
    # 1. 移动平均线
    result['ma5'] = pd.Series(close).rolling(5).mean().values
    result['ma10'] = pd.Series(close).rolling(10).mean().values
    result['ma20'] = pd.Series(close).rolling(20).mean().values
    result['ma60'] = pd.Series(close).rolling(60).mean().values
    
    # 2. 动量指标
    result['momentum_5'] = pd.Series(close).pct_change(5).values
    result['momentum_10'] = pd.Series(close).pct_change(10).values
    result['momentum_20'] = pd.Series(close).pct_change(20).values
    
    # 3. 波动率
    if len(close) >= 10:
        result['volatility_10'] = pd.Series(close).rolling(10).std().values
        result['volatility_20'] = pd.Series(close).rolling(20).std().values
    else:
        result['volatility_10'] = 0.0
        result['volatility_20'] = 0.0
    
    # 4. RSI相对强弱指标
    result['rsi_14'] = _calculate_rsi(close, period=14)
    
    # 5. MACD指标
    macd_result = _calculate_macd(close)
    result['macd'] = macd_result['macd']
    result['macd_signal'] = macd_result['signal']
    result['macd_hist'] = macd_result['hist']
    
    # 6. 成交量特征
    if 'volume' in result.columns:
        vol = result['volume'].values
        result['volume_ma5'] = pd.Series(vol).rolling(5).mean().values
        result['volume_ratio'] = vol / (pd.Series(vol).rolling(20).mean().values + 1e-6)
        result['volume_change'] = pd.Series(vol).pct_change().values
    else:
        result['volume_ma5'] = 0.0
        result['volume_ratio'] = 1.0
        result['volume_change'] = 0.0
    
    # 7. 价格位置（当前价格在N日内的相对位置）
    if len(close) >= lookback_days:
        high_n = pd.Series(close).rolling(lookback_days).max().values
        low_n = pd.Series(close).rolling(lookback_days).min().values
        result['price_position'] = (close - low_n) / (high_n - low_n + 1e-6)
    else:
        result['price_position'] = 0.5
    
    # 8. 涨跌停特征（如果有数据）
    if 'up_limit' in result.columns and 'down_limit' in result.columns:
        result['is_up_limit'] = (result['close'] >= result['up_limit']).astype(int)
        result['is_down_limit'] = (result['close'] <= result['down_limit']).astype(int)
        result['limit_distance'] = (result['close'] - result['down_limit']) / (
            result['up_limit'] - result['down_limit'] + 1e-6
        )
    else:
        # 简化计算：假设10%涨跌停
        prev_close = pd.Series(close).shift(1).values
        result['is_up_limit'] = ((close - prev_close) / (prev_close + 1e-6) >= 0.095).astype(int)
        result['is_down_limit'] = ((close - prev_close) / (prev_close + 1e-6) <= -0.095).astype(int)
    
    # === 未来收益标签（用于训练）===
    # 计算未来N日收益率（作为预测目标）
    future_returns = pd.Series(close).shift(-lookback_days) / close - 1
    result['future_return'] = future_returns.values
    
    # 二分类标签：是否超过阈值（如5%）
    result['future_return_binary'] = (future_returns > 0.05).astype(int)
    
    # 填充NaN值
    result = result.fillna(method='bfill').fillna(method='ffill').fillna(0)
    
    logger.info(f"✅ 特征提取完成: {len(result.columns)} 个特征")
    return result


def _calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """计算RSI指标"""
    if len(prices) < period + 1:
        return np.zeros(len(prices))
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = pd.Series(gains).rolling(period).mean().values
    avg_loss = pd.Series(losses).rolling(period).mean().values
    avg_loss = np.where(avg_loss == 0, 1e-6, avg_loss)
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # 前面period个值设为NaN，用0填充
    rsi = np.concatenate([[0] * period, rsi[period:]])
    
    return np.nan_to_num(rsi, nan=50.0)


def _calculate_macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
    """计算MACD指标"""
    if len(prices) < slow:
        return {
            'macd': np.zeros(len(prices)),
            'signal': np.zeros(len(prices)),
            'hist': np.zeros(len(prices))
        }
    
    ema_fast = pd.Series(prices).ewm(span=fast).mean().values
    ema_slow = pd.Series(prices).ewm(span=slow).mean().values
    
    macd = ema_fast - ema_slow
    signal_line = pd.Series(macd).ewm(span=signal).mean().values
    hist = macd - signal_line
    
    return {
        'macd': np.nan_to_num(macd, nan=0.0),
        'signal': np.nan_to_num(signal_line, nan=0.0),
        'hist': np.nan_to_num(hist, nan=0.0)
    }


def select_features(df: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """
    选择用于模型训练的特征列
    
    Args:
        df: 包含特征的DataFrame
        feature_cols: 指定特征列，None表示使用默认特征集
    
    Returns:
        只包含特征列的DataFrame
    """
    if feature_cols is None:
        # 默认特征集（排除目标列和ID列）
        exclude_cols = ['ts_code', 'trade_date', 'date', 'future_return', 'future_return_binary']
        feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    available_cols = [col for col in feature_cols if col in df.columns]
    
    if not available_cols:
        logger.warning("⚠️ 没有可用的特征列")
        return pd.DataFrame()
    
    return df[available_cols]


def normalize_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    特征归一化（Z-score标准化）
    
    Args:
        df: 特征DataFrame
    
    Returns:
        归一化后的DataFrame
    """
    result = df.copy()
    
    for col in result.columns:
        if result[col].dtype in [np.float64, np.int64]:
            mean = result[col].mean()
            std = result[col].std()
            if std > 1e-6:
                result[col] = (result[col] - mean) / std
            else:
                result[col] = 0
    
    return result

