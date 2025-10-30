#!/usr/bin/env python3
"""
量化交易模型使用示例
演示如何使用量化交易模型进行交易
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.models import (
    QuantitativeTrader,
    SignalType,
    StrategyType
)
from tradingagents.dataflows.interface import get_stock_market_data_unified


def example_quantitative_trading():
    """量化交易模型使用示例"""
    
    print("=" * 60)
    print("💹 量化交易模型使用示例")
    print("=" * 60)
    
    # 1. 初始化交易器
    trader = QuantitativeTrader(
        initial_capital=100000.0,  # 初始资金10万
        strategy_type=StrategyType.TREND_FOLLOWING,  # 使用趋势跟踪策略
        max_positions=5,  # 最多5只股票
        risk_per_trade=0.02  # 单笔风险2%
    )
    
    print(f"\n💰 初始资金: ¥{trader.initial_capital:,.2f}")
    print(f"📈 策略类型: {trader.strategy_type.value}")
    
    # 2. 模拟交易流程（示例股票）
    ticker = '002701'
    print(f"\n📊 分析股票: {ticker}")
    
    # 3. 获取市场数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    print(f"📅 获取市场数据: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
    
    try:
        # 获取市场数据（实际使用中需要解析返回的数据）
        data_str = get_stock_market_data_unified(
            ticker,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        # 注意：实际使用中需要将返回的字符串转换为DataFrame
        # 这里只是演示流程
        
        print("✅ 数据获取成功")
        
        # 4. 生成交易信号（示例）
        current_price = 7.85  # 假设当前价格
        
        # 实际使用中需要将数据转换为DataFrame
        # import pandas as pd
        # market_data = parse_market_data(data_str)  # 需要实现解析函数
        
        signal, strength, details = trader.generate_signal(
            ticker=ticker,
            current_price=current_price,
            market_data=None  # 实际使用中传入解析后的DataFrame
        )
        
        print(f"\n📡 交易信号: {signal.value}")
        print(f"   信号强度: {strength:.2f}")
        print(f"   信号详情: {details}")
        
        # 5. 执行交易
        if signal == SignalType.BUY:
            print(f"\n💵 执行买入...")
            success = trader.execute_trade(
                ticker=ticker,
                signal=signal,
                price=current_price
            )
            
            if success:
                print("✅ 买入成功")
            else:
                print("❌ 买入失败")
        
        # 6. 查看投资组合状态
        print("\n" + "=" * 60)
        print("📊 投资组合状态")
        print("=" * 60)
        
        status = trader.get_portfolio_status()
        print(f"初始资金: ¥{status['initial_capital']:,.2f}")
        print(f"当前现金: ¥{status['current_capital']:,.2f}")
        print(f"持仓市值: ¥{status['positions_value']:,.2f}")
        print(f"总资产: ¥{status['total_value']:,.2f}")
        print(f"总盈亏: ¥{status['total_pnl']:,.2f}")
        print(f"总收益率: {status['total_return_percent']:.2f}%")
        print(f"持仓数量: {status['positions_count']}")
        print(f"交易次数: {status['trade_count']}")
        
        if status['positions']:
            print("\n📋 持仓明细:")
            for pos in status['positions']:
                print(f"  {pos['ticker']}: {pos['quantity']}股 @ ¥{pos['entry_price']:.2f}")
                print(f"    当前价格: ¥{pos['current_price']:.2f}")
                print(f"    盈亏: ¥{pos['pnl']:,.2f} ({pos['pnl_percent']:.2f}%)")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✨ 示例完成")
    print("=" * 60)


if __name__ == '__main__':
    example_quantitative_trading()
