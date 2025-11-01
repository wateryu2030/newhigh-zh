#!/usr/bin/env python3
"""
一体化智能交易脚本
完成：数据下载/缓存 → 特征工程 → 智能选股（ML） → 策略回测 → 报告生成
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.data_downloader import DataDownloader
from tradingagents.models.ml_features import extract_features, select_features
from tradingagents.models.ml_selector import SmartSelector
from tradingagents.backtest.backtest_strategy import create_strategy, MAStrategy
from tradingagents.backtest.engine import BacktestEngine
from tradingagents.backtest.backtest_report import BacktestReport
from tradingagents.utils.logging_init import get_logger

logger = get_logger('scripts.smart_trading')


def run_smart_trading(
    symbols: list,
    start_date: str,
    end_date: str,
    provider: str = "tushare",
    data_dir: str = "data",
    run_dir: str = "runs",
    train_ml: bool = True,
    strategy_type: str = "ma"
):
    """
    运行一体化智能交易流程
    
    Args:
        symbols: 股票代码列表（如 ["600519.SH", "000001.SZ"]）
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        provider: 数据提供商
        data_dir: 数据目录
        run_dir: 运行结果目录
        train_ml: 是否训练ML模型
        strategy_type: 回测策略类型（ma/momentum/ml）
    """
    # 创建运行目录
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_path = Path(run_dir) / run_id
    run_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"🚀 开始智能交易流程 (run_id={run_id})")
    
    # === 步骤1: 数据下载 ===
    logger.info("📥 步骤1: 下载股票数据...")
    downloader = DataDownloader(
        save_path=f"{data_dir}/stock_daily.parquet",
        provider=provider
    )
    
    all_data = {}
    for symbol in symbols:
        try:
            # 转换日期格式
            start_ts = pd.to_datetime(start_date).strftime('%Y%m%d')
            end_ts = pd.to_datetime(end_date).strftime('%Y%m%d')
            
            df = downloader.get_stock_data(symbol, start_ts, end_ts)
            if not df.empty:
                all_data[symbol] = df
                logger.info(f"✅ {symbol}: {len(df)} 条记录")
            else:
                logger.warning(f"⚠️ {symbol}: 未获取到数据")
        except Exception as e:
            logger.error(f"❌ {symbol} 下载失败: {e}")
    
    if not all_data:
        logger.error("❌ 未获取到任何数据，退出")
        return
    
    # === 步骤2: 特征工程 ===
    logger.info("🔧 步骤2: 特征工程...")
    all_features = {}
    
    for symbol, df in all_data.items():
        try:
            # 确保列名正确
            if 'trade_date' in df.columns:
                df = df.set_index('trade_date')
            
            features_df = extract_features(df)
            if not features_df.empty:
                all_features[symbol] = features_df
                
                # 保存特征
                feature_file = run_path / f"{symbol.replace('.', '_')}_features.parquet"
                try:
                    features_df.to_parquet(feature_file)
                except:
                    features_df.to_csv(str(feature_file).replace('.parquet', '.csv'), index=False)
                
                logger.info(f"✅ {symbol}: {len(features_df.columns)} 个特征")
        except Exception as e:
            logger.error(f"❌ {symbol} 特征提取失败: {e}")
    
    if not all_features:
        logger.error("❌ 未提取到任何特征，退出")
        return
    
    # === 步骤3: 智能选股（ML）===
    ml_scores = {}
    ml_model = None
    
    if train_ml:
        logger.info("🧠 步骤3: 训练ML模型并进行选股...")
        
        # 合并所有股票的特征用于训练
        train_features_list = []
        train_labels_list = []
        
        for symbol, features_df in all_features.items():
            # 选择特征列（排除目标列）
            feature_cols = select_features(features_df)
            
            if not feature_cols.empty and 'future_return_binary' in features_df.columns:
                # 移除NaN行
                valid_mask = ~(feature_cols.isna().any(axis=1) | features_df['future_return_binary'].isna())
                
                train_features_list.append(feature_cols[valid_mask])
                train_labels_list.append(features_df.loc[valid_mask, 'future_return_binary'])
        
        if train_features_list:
            combined_features = pd.concat(train_features_list, ignore_index=True)
            combined_labels = pd.concat(train_labels_list, ignore_index=True)
            
            # 训练模型
            model_path = run_path / "ml_model.pkl"
            ml_model = SmartSelector(model_type="classifier", model_path=str(model_path))
            
            metrics = ml_model.train(combined_features, combined_labels)
            logger.info(f"✅ ML模型训练完成: {metrics}")
            
            # 对每只股票进行预测
            for symbol, features_df in all_features.items():
                feature_cols = select_features(features_df)
                if not feature_cols.empty:
                    predictions = ml_model.predict_stocks(feature_cols, return_proba=True)
                    if 'probability' in predictions.columns:
                        ml_scores[symbol] = predictions['probability'].iloc[-1]  # 最新预测
                        logger.info(f"✅ {symbol}: ML评分 = {ml_scores[symbol]:.4f}")
    else:
        logger.info("⏭️ 步骤3: 跳过ML训练，使用简单评分...")
        # 简单评分：使用动量
        for symbol, features_df in all_features.items():
            if 'momentum_20' in features_df.columns:
                ml_scores[symbol] = features_df['momentum_20'].iloc[-1]
    
    # 保存选股结果
    if ml_scores:
        scores_df = pd.DataFrame([
            {'symbol': k, 'ml_score': v}
            for k, v in ml_scores.items()
        ]).sort_values('ml_score', ascending=False)
        
        scores_file = run_path / "scores_today.csv"
        scores_df.to_csv(scores_file, index=False)
        logger.info(f"✅ 选股结果已保存: {scores_file}")
    
    # === 步骤4: 策略回测 ===
    logger.info("📊 步骤4: 运行回测...")
    
    backtest_results = {}
    
    for symbol, df in all_data.items():
        try:
            # 创建策略
            if strategy_type == "ma":
                strategy = MAStrategy(fast_period=5, slow_period=20)
            elif strategy_type == "ml" and ml_model:
                strategy = create_strategy("ml", model=ml_model, threshold=0.5)
            else:
                strategy = MAStrategy()  # 默认
            
            # 生成信号
            signals_df = strategy.generate_signals(df)
            
            if signals_df.empty or 'signal' not in signals_df.columns:
                logger.warning(f"⚠️ {symbol}: 未生成信号")
                continue
            
            # 合并数据和信号
            df_with_signals = df.copy()
            if 'trade_date' in df_with_signals.columns:
                df_with_signals = df_with_signals.set_index('trade_date')
            
            df_with_signals['signal'] = signals_df['signal'].reindex(df_with_signals.index, fill_value=0)
            
            # 运行回测
            engine = BacktestEngine(
                data=df_with_signals,
                strategies=[strategy_type],
                initial_capital=100000.0,
                commission_rate=0.0003,
                slippage_rate=0.0001
            )
            
            # 覆盖信号生成方法
            def _calculate_signals(data):
                signals = []
                for idx, row in data.iterrows():
                    signal_val = row.get('signal', 0)
                    if signal_val == 1:
                        signals.append({
                            'side': 'BUY',
                            'price': float(row.get('close', 0)),
                            'qty': 100,
                            'row': row.to_dict()
                        })
                    elif signal_val == -1:
                        signals.append({
                            'side': 'SELL',
                            'price': float(row.get('close', 0)),
                            'qty': 100,
                            'row': row.to_dict()
                        })
                return signals
            
            engine.calculate_signals = _calculate_signals
            engine.execute()
            
            # 生成报告
            report = BacktestReport(engine)
            backtest_results[symbol] = report.generate_report()
            
            logger.info(f"✅ {symbol}: 回测完成")
            
        except Exception as e:
            logger.error(f"❌ {symbol} 回测失败: {e}")
    
    # 保存所有回测结果
    if backtest_results:
        all_scores = []
        for symbol, result in backtest_results.items():
            summary = result.get('summary', {})
            metrics = result.get('metrics', {})
            all_scores.append({
                'symbol': symbol,
                'total_return': summary.get('total_return', 0),
                'annualized_return': metrics.get('annualized_return', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'ml_score': ml_scores.get(symbol, 0)
            })
        
        all_scores_df = pd.DataFrame(all_scores)
        all_scores_file = run_path / "scores_all.parquet"
        try:
            all_scores_df.to_parquet(all_scores_file)
        except:
            all_scores_df.to_csv(str(all_scores_file).replace('.parquet', '.csv'), index=False)
        
        logger.info(f"✅ 所有回测结果已保存: {all_scores_file}")
    
    # === 保存元数据 ===
    meta = {
        'run_id': run_id,
        'symbols': symbols,
        'start_date': start_date,
        'end_date': end_date,
        'provider': provider,
        'strategy_type': strategy_type,
        'train_ml': train_ml,
        'created_at': datetime.now().isoformat()
    }
    
    meta_file = run_path / "meta.json"
    import json
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ 流程完成！结果保存在: {run_path}")
    print(f"\n📁 运行结果: {run_path}")
    print(f"   - 特征文件: features.parquet")
    print(f"   - 选股结果: scores_today.csv")
    print(f"   - 回测结果: scores_all.csv")
    print(f"   - 元数据: meta.json\n")


def main():
    parser = argparse.ArgumentParser(description='一体化智能交易脚本')
    parser.add_argument('--symbols', nargs='+', required=True, help='股票代码列表')
    parser.add_argument('--start', required=True, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--provider', default='tushare', choices=['tushare', 'akshare'], help='数据提供商')
    parser.add_argument('--data-dir', default='data', help='数据目录')
    parser.add_argument('--run-dir', default='runs', help='运行结果目录')
    parser.add_argument('--no-train-ml', action='store_true', help='不训练ML模型')
    parser.add_argument('--strategy', default='ma', choices=['ma', 'momentum', 'ml'], help='回测策略类型')
    
    args = parser.parse_args()
    
    run_smart_trading(
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end,
        provider=args.provider,
        data_dir=args.data_dir,
        run_dir=args.run_dir,
        train_ml=not args.no_train_ml,
        strategy_type=args.strategy
    )


if __name__ == "__main__":
    main()

