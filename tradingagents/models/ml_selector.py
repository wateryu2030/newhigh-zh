#!/usr/bin/env python3
"""
机器学习选股器
基于RandomForest等模型进行智能选股
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from pathlib import Path
import pickle
import joblib

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from tradingagents.utils.logging_init import get_logger
from tradingagents.models.ml_features import extract_features, select_features, normalize_features

logger = get_logger('models.ml_selector')


class SmartSelector:
    """
    智能选股器（基于机器学习）
    """
    
    def __init__(
        self,
        model_type: str = "classifier",
        n_estimators: int = 100,
        max_depth: int = 10,
        model_path: Optional[str] = None
    ):
        """
        初始化智能选股器
        
        Args:
            model_type: 模型类型（classifier/regressor）
            n_estimators: 树的数量
            max_depth: 树的最大深度
            model_path: 保存/加载模型的路径
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("需要安装 scikit-learn: pip install scikit-learn")
        
        self.model_type = model_type
        self.model_path = Path(model_path) if model_path else None
        
        if model_type == "classifier":
            self.model = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42,
                n_jobs=-1
            )
        else:
            self.model = RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42,
                n_jobs=-1
            )
        
        self.feature_cols = None
        self.is_trained = False
        
        # 尝试加载已有模型
        if self.model_path and self.model_path.exists():
            self.load_model(self.model_path)
        
        logger.info(f"✅ SmartSelector初始化完成 (model_type={model_type})")
    
    def train(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        test_size: float = 0.2,
        normalize: bool = True
    ) -> Dict[str, float]:
        """
        训练模型
        
        Args:
            features: 特征DataFrame
            labels: 标签Series（分类：0/1，回归：收益率）
            test_size: 测试集比例
            normalize: 是否归一化特征
        
        Returns:
            训练指标字典
        """
        if features.empty or labels.empty:
            logger.error("❌ 训练数据为空")
            return {}
        
        # 特征归一化
        if normalize:
            features = normalize_features(features)
        
        # 保存特征列名
        self.feature_cols = features.columns.tolist()
        
        # 处理缺失值和无穷值
        features = features.replace([np.inf, -np.inf], np.nan).fillna(0)
        labels = labels.replace([np.inf, -np.inf], np.nan).fillna(0 if self.model_type == "classifier" else 0.0)
        
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            features.values,
            labels.values,
            test_size=test_size,
            random_state=42,
            stratify=labels if self.model_type == "classifier" else None
        )
        
        logger.info(f"📊 训练数据: {len(X_train)} 条，测试数据: {len(X_test)} 条")
        
        # 训练模型
        logger.info("🔧 开始训练模型...")
        self.model.fit(X_train, y_train)
        self.is_trained = True
        
        # 评估模型
        train_pred = self.model.predict(X_train)
        test_pred = self.model.predict(X_test)
        
        metrics = {}
        
        if self.model_type == "classifier":
            # 分类指标
            metrics['train_accuracy'] = accuracy_score(y_train, train_pred)
            metrics['test_accuracy'] = accuracy_score(y_test, test_pred)
            metrics['test_precision'] = precision_score(y_test, test_pred, zero_division=0)
            metrics['test_recall'] = recall_score(y_test, test_pred, zero_division=0)
            metrics['test_f1'] = f1_score(y_test, test_pred, zero_division=0)
            
            # ROC-AUC（需要概率）
            try:
                test_proba = self.model.predict_proba(X_test)[:, 1]
                metrics['test_roc_auc'] = roc_auc_score(y_test, test_proba)
            except:
                metrics['test_roc_auc'] = 0.0
        else:
            # 回归指标
            from sklearn.metrics import mean_squared_error, r2_score
            metrics['train_rmse'] = np.sqrt(mean_squared_error(y_train, train_pred))
            metrics['test_rmse'] = np.sqrt(mean_squared_error(y_test, test_pred))
            metrics['test_r2'] = r2_score(y_test, test_pred)
        
        logger.info(f"✅ 模型训练完成，测试集指标: {metrics}")
        
        # 保存模型
        if self.model_path:
            self.save_model(self.model_path)
        
        return metrics
    
    def predict_stocks(
        self,
        features: pd.DataFrame,
        return_proba: bool = False,
        normalize: bool = True
    ) -> pd.DataFrame:
        """
        预测股票收益概率
        
        Args:
            features: 特征DataFrame
            return_proba: 是否返回概率（仅分类器）
            normalize: 是否归一化特征
        
        Returns:
            包含预测结果的DataFrame
        """
        if not self.is_trained:
            logger.error("❌ 模型未训练，无法预测")
            return pd.DataFrame()
        
        if features.empty:
            logger.error("❌ 特征数据为空")
            return pd.DataFrame()
        
        # 确保特征列一致
        if self.feature_cols:
            missing_cols = [col for col in self.feature_cols if col not in features.columns]
            if missing_cols:
                logger.warning(f"⚠️ 缺少特征列: {missing_cols}，将用0填充")
                for col in missing_cols:
                    features[col] = 0
            features = features[self.feature_cols]
        
        # 特征归一化
        if normalize:
            features = normalize_features(features)
        
        # 处理缺失值和无穷值
        features = features.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # 预测
        if self.model_type == "classifier" and return_proba:
            predictions = self.model.predict_proba(features.values)[:, 1]
        else:
            predictions = self.model.predict(features.values)
        
        result = features.copy()
        result['prediction'] = predictions
        
        if self.model_type == "classifier" and return_proba:
            result['probability'] = predictions
            result['prediction_binary'] = (predictions > 0.5).astype(int)
        
        logger.info(f"✅ 预测完成: {len(result)} 只股票")
        return result
    
    def save_model(self, path: str):
        """保存模型"""
        if not self.is_trained:
            logger.warning("⚠️ 模型未训练，跳过保存")
            return
        
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            'model': self.model,
            'feature_cols': self.feature_cols,
            'model_type': self.model_type,
            'is_trained': self.is_trained
        }
        
        joblib.dump(model_data, save_path)
        logger.info(f"✅ 模型已保存: {save_path}")
    
    def load_model(self, path: str):
        """加载模型"""
        try:
            model_data = joblib.load(path)
            self.model = model_data['model']
            self.feature_cols = model_data.get('feature_cols')
            self.model_type = model_data.get('model_type', 'classifier')
            self.is_trained = model_data.get('is_trained', False)
            
            logger.info(f"✅ 模型已加载: {path}")
        except Exception as e:
            logger.error(f"❌ 加载模型失败: {e}")
            self.is_trained = False
    
    def get_feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        """
        获取特征重要性
        
        Args:
            top_n: 返回前N个重要特征
        
        Returns:
            特征重要性DataFrame
        """
        if not self.is_trained or self.feature_cols is None:
            logger.error("❌ 模型未训练，无法获取特征重要性")
            return pd.DataFrame()
        
        importances = self.model.feature_importances_
        
        result = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': importances
        }).sort_values('importance', ascending=False).head(top_n)
        
        return result

