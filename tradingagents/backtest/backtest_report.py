#!/usr/bin/env python3
"""
回测报告生成模块
生成详细的回测绩效报告
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

from tradingagents.utils.logging_init import get_logger

logger = get_logger('backtest.report')


class BacktestReport:
    """回测报告生成器"""
    
    def __init__(self, engine):
        """
        初始化报告生成器
        
        Args:
            engine: BacktestEngine实例
        """
        self.engine = engine
        self.metrics = self.engine.metrics() if hasattr(self.engine, 'metrics') else {}
    
    def generate_report(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        生成完整回测报告
        
        Args:
            save_path: 保存路径（JSON格式）
        
        Returns:
            报告字典
        """
        report = {
            'summary': self._generate_summary(),
            'metrics': self._calculate_metrics(),
            'trades': self._analyze_trades(),
            'equity_curve': self._get_equity_curve()
        }
        
        if save_path:
            self._save_report(report, save_path)
        
        return report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成摘要信息"""
        if hasattr(self.engine, 'init_capital'):
            init_capital = self.engine.init_capital
        else:
            init_capital = 100000.0
        
        final_equity = self.metrics.get('final_equity', init_capital)
        total_return = self.metrics.get('total_return', 0.0)
        
        return {
            'initial_capital': init_capital,
            'final_equity': final_equity,
            'total_return': total_return,
            'total_return_pct': f"{total_return * 100:.2f}%",
            'strategy': getattr(self.engine, 'strategies', ['unknown']),
            'commission_rate': getattr(self.engine, 'cost_bps', 5.0) / 10000,
            'slippage_rate': getattr(self.engine, 'slippage_bps', 5.0) / 10000
        }
    
    def _calculate_metrics(self) -> Dict[str, Any]:
        """计算绩效指标"""
        metrics = {}
        
        # 基础指标
        if 'annualized_return' in self.metrics:
            metrics['annualized_return'] = self.metrics['annualized_return']
            metrics['annualized_return_pct'] = f"{self.metrics['annualized_return'] * 100:.2f}%"
        
        if 'max_drawdown' in self.metrics:
            metrics['max_drawdown'] = self.metrics['max_drawdown']
            metrics['max_drawdown_pct'] = f"{self.metrics['max_drawdown'] * 100:.2f}%"
        
        if 'sharpe_ratio' in self.metrics:
            metrics['sharpe_ratio'] = self.metrics['sharpe_ratio']
        
        # 计算额外指标
        if hasattr(self.engine, 'equity') and self.engine.equity:
            equity_df = pd.DataFrame(self.engine.equity)
            if 'equity' in equity_df.columns:
                equity_series = equity_df['equity']
                
                # 日收益率
                daily_returns = equity_series.pct_change().dropna()
                
                # 胜率（盈利交易占比）
                if hasattr(self.engine, 'orders') and self.engine.orders:
                    trades_df = pd.DataFrame(self.engine.orders)
                    if len(trades_df) > 0:
                        # 简化：假设订单有盈亏信息
                        # 实际需要根据买入卖出配对计算
                        pass
                
                # 波动率
                metrics['volatility'] = daily_returns.std() * np.sqrt(252)
                metrics['volatility_pct'] = f"{metrics['volatility'] * 100:.2f}%"
                
                # Calmar比率
                if metrics.get('annualized_return', 0) != 0 and abs(metrics.get('max_drawdown', 1)) > 1e-6:
                    metrics['calmar_ratio'] = metrics['annualized_return'] / abs(metrics['max_drawdown'])
        
        return metrics
    
    def _analyze_trades(self) -> Dict[str, Any]:
        """分析交易记录"""
        if not hasattr(self.engine, 'orders') or not self.engine.orders:
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'total_commission': 0.0
            }
        
        trades_df = pd.DataFrame(self.engine.orders)
        
        buy_trades = trades_df[trades_df['side'] == 'BUY']
        sell_trades = trades_df[trades_df['side'] == 'SELL']
        
        total_commission = trades_df['fee'].sum() if 'fee' in trades_df.columns else 0.0
        
        return {
            'total_trades': len(trades_df),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_commission': total_commission,
            'avg_trade_size': trades_df['qty'].mean() if 'qty' in trades_df.columns else 0
        }
    
    def _get_equity_curve(self) -> pd.DataFrame:
        """获取资金曲线数据"""
        if hasattr(self.engine, 'equity') and self.engine.equity:
            return pd.DataFrame(self.engine.equity)
        return pd.DataFrame()
    
    def _save_report(self, report: Dict[str, Any], save_path: str):
        """保存报告到文件"""
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 转换DataFrame为字典
        report_dict = report.copy()
        
        if isinstance(report_dict.get('equity_curve'), pd.DataFrame):
            eq_df = report_dict['equity_curve']
            if not eq_df.empty:
                report_dict['equity_curve'] = eq_df.to_dict('records')
            else:
                report_dict['equity_curve'] = []
        
        # 保存JSON
        json_path = save_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False, default=str)
        
        # 保存资金曲线CSV
        if isinstance(report.get('equity_curve'), pd.DataFrame) and not report['equity_curve'].empty:
            csv_path = save_path.with_suffix('').with_name(f"{save_path.stem}_equity_curve.csv")
            report['equity_curve'].to_csv(csv_path, index=False)
        
        logger.info(f"✅ 回测报告已保存: {json_path}")
    
    def print_report(self):
        """打印报告到控制台"""
        print("\n" + "="*60)
        print("📊 回测绩效报告")
        print("="*60)
        
        # 摘要
        summary = self._generate_summary()
        print(f"\n💰 资金状况:")
        print(f"  初始资金: {summary['initial_capital']:,.2f}")
        print(f"  最终资金: {summary['final_equity']:,.2f}")
        print(f"  总收益率: {summary['total_return_pct']}")
        
        # 绩效指标
        metrics = self._calculate_metrics()
        print(f"\n📈 绩效指标:")
        if 'annualized_return_pct' in metrics:
            print(f"  年化收益: {metrics['annualized_return_pct']}")
        if 'sharpe_ratio' in metrics:
            print(f"  夏普比率: {metrics['sharpe_ratio']:.2f}")
        if 'max_drawdown_pct' in metrics:
            print(f"  最大回撤: {metrics['max_drawdown_pct']}")
        if 'volatility_pct' in metrics:
            print(f"  波动率: {metrics['volatility_pct']}")
        
        # 交易统计
        trades = self._analyze_trades()
        print(f"\n📋 交易统计:")
        print(f"  总交易次数: {trades['total_trades']}")
        print(f"  买入次数: {trades['buy_trades']}")
        print(f"  卖出次数: {trades['sell_trades']}")
        print(f"  总手续费: {trades['total_commission']:,.2f}")
        
        print("\n" + "="*60 + "\n")

