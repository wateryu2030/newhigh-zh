#!/usr/bin/env python3
"""
量化交易组件
"""

import streamlit as st
import sys
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from tradingagents.models import (
        QuantitativeTrader,
        SignalType,
        StrategyType
    )
    MODELS_AVAILABLE = True
except ImportError as e:
    MODELS_AVAILABLE = False
    st.error(f"量化交易模型模块不可用: {e}")

from tradingagents.dataflows.interface import (
    get_china_stock_data_unified,
    get_YFin_data_online
)
from tradingagents.utils.stock_utils import StockUtils
from tradingagents.utils.report_parser import ReportParser
import pandas as pd
import re
from typing import Optional

logger = None
try:
    from tradingagents.utils.logging_init import get_logger
    logger = get_logger('web.quantitative_trading')
except:
    import logging
    logger = logging.getLogger('quantitative_trading')


def parse_market_data_string(data_str: str, ticker: str) -> Optional[pd.DataFrame]:
    """
    解析市场数据字符串为DataFrame
    支持多种数据格式：表格格式、行格式、CSV格式
    """
    if not data_str or len(data_str.strip()) == 0:
        return None
    
    # 检查是否包含错误信息
    if "❌" in data_str or "错误" in data_str or "失败" in data_str:
        logger.warning(f"数据字符串包含错误信息: {data_str[:200]}")
        return None
    
    try:
        # 方法1: 尝试解析为表格格式（包含列名和数据行）
        lines = [line.strip() for line in data_str.split('\n') if line.strip()]
        
        # 查找可能的表头行（包含 Date, Close, 日期, 收盘等关键词）
        header_idx = None
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['date', 'close', '收盘', '日期', 'date', '时间']):
                header_idx = i
                break
        
        data_rows = []
        
        if header_idx is not None:
            # 找到表头，解析后续数据行
            headers = [col.strip() for col in lines[header_idx].split() if col.strip()]
            
            # 尝试确定列的位置
            date_col_idx = None
            close_col_idx = None
            
            for i, header in enumerate(headers):
                header_lower = header.lower()
                if 'date' in header_lower or '日期' in header_lower or '时间' in header_lower:
                    date_col_idx = i
                if 'close' in header_lower or '收盘' in header_lower or 'close' in header_lower:
                    close_col_idx = i
            
            # 解析数据行
            for line in lines[header_idx + 1:]:
                if not line or line.startswith('-') or '|' not in line and '\t' not in line and ',' not in line:
                    continue
                
                # 尝试分割行（支持多种分隔符）
                parts = re.split(r'[\s|,\t]+', line.strip())
                parts = [p.strip() for p in parts if p.strip()]
                
                if len(parts) < 2:
                    continue
                
                try:
                    # 查找日期
                    date_val = None
                    for part in parts:
                        date_match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', part)
                        if date_match:
                            date_val = pd.to_datetime(f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}")
                            break
                    
                    if date_val is None:
                        continue
                    
                    # 查找价格（数字，可能有小数点）
                    price_val = None
                    for part in parts:
                        # 移除可能的货币符号和逗号
                        clean_part = part.replace('¥', '').replace('$', '').replace(',', '').replace('，', '')
                        try:
                            price_candidate = float(clean_part)
                            if 0.01 < price_candidate < 10000:  # 合理价格范围
                                price_val = price_candidate
                                break
                        except:
                            continue
                    
                    if price_val is None:
                        continue
                    
                    data_rows.append({
                        'date': date_val,
                        'close': price_val,
                        'open': price_val,  # 简化：使用收盘价
                        'high': price_val,
                        'low': price_val,
                        'volume': 0
                    })
                    
                except Exception as e:
                    logger.debug(f"解析行失败: {line}, 错误: {e}")
                    continue
        
        # 方法2: 如果没有找到表头，尝试直接解析包含日期的行
        if len(data_rows) < 10:
            for line in lines:
                # 匹配日期+价格模式：2024-01-01 10.50 或 2024/01/01 10.50
                date_price_match = re.search(
                    r'(\d{4})[-/](\d{1,2})[-/](\d{1,2}).*?([\d.]+)',
                    line
                )
                if date_price_match:
                    try:
                        date_val = pd.to_datetime(
                            f"{date_price_match.group(1)}-{date_price_match.group(2).zfill(2)}-{date_price_match.group(3).zfill(2)}"
                        )
                        price_val = float(date_price_match.group(4))
                        if 0.01 < price_val < 10000:
                            # 检查是否已存在相同日期
                            if not any(row['date'] == date_val for row in data_rows):
                                data_rows.append({
                                    'date': date_val,
                                    'close': price_val,
                                    'open': price_val,
                                    'high': price_val,
                                    'low': price_val,
                                    'volume': 0
                                })
                    except:
                        continue
        
        # 去重并排序
        if len(data_rows) >= 10:
            df = pd.DataFrame(data_rows)
            df = df.drop_duplicates(subset=['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            
            if len(df) >= 10:
                logger.info(f"✅ 成功解析 {len(df)} 条数据")
                return df
        
        # 数据不足
        logger.warning(f"解析到的数据不足（{len(data_rows)}条），无法生成有效信号")
        logger.debug(f"数据字符串前500字符: {data_str[:500]}")
        return None
            
    except Exception as e:
        logger.warning(f"解析市场数据失败: {e}", exc_info=True)
        logger.debug(f"失败的数据字符串前500字符: {data_str[:500]}")
        return None


def render_quantitative_trading():
    """渲染量化交易页面"""
    
    if not MODELS_AVAILABLE:
        st.error("❌ 量化交易模型模块不可用，请检查依赖安装")
        st.info("""
        请确保已安装所有依赖：
        ```bash
        pip install -r requirements.txt
        ```
        """)
        return
    
    st.title("💹 量化交易")
    st.markdown("基于技术指标和策略的自动化交易系统，支持多种交易策略和风险管理")
    
    # 初始化session state
    if 'trader' not in st.session_state:
        st.session_state.trader = None
    if 'trade_history' not in st.session_state:
        st.session_state.trade_history = []
    if 'positions' not in st.session_state:
        st.session_state.positions = {}
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 交易配置")
        
        # 初始资金
        initial_capital = st.number_input(
            "💰 初始资金",
            min_value=10000.0,
            max_value=10000000.0,
            value=100000.0,
            step=10000.0,
            help="模拟交易的初始资金"
        )
        
        # 策略选择
        strategy_type = st.selectbox(
            "📊 交易策略",
            [StrategyType.TREND_FOLLOWING, StrategyType.MEAN_REVERSION, 
             StrategyType.MOMENTUM, StrategyType.MULTI_FACTOR],
            format_func=lambda x: {
                StrategyType.TREND_FOLLOWING: "趋势跟踪",
                StrategyType.MEAN_REVERSION: "均值回归",
                StrategyType.MOMENTUM: "动量策略",
                StrategyType.MULTI_FACTOR: "多因子策略"
            }.get(x, x.value),
            help="选择适合市场环境的交易策略"
        )
        
        # 最大持仓数
        max_positions = st.slider(
            "📈 最大持仓数",
            min_value=1,
            max_value=20,
            value=5,
            help="同时持有的最大股票数量"
        )
        
        # 单笔风险
        risk_per_trade = st.slider(
            "⚠️ 单笔风险 (%)",
            min_value=0.5,
            max_value=5.0,
            value=2.0,
            step=0.5,
            help="每笔交易的最大风险比例"
        ) / 100.0
        
        st.markdown("---")
        
        # 初始化/重置交易器
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 初始化交易器", use_container_width=True):
                st.session_state.trader = QuantitativeTrader(
                    initial_capital=initial_capital,
                    strategy_type=strategy_type,
                    max_positions=max_positions,
                    risk_per_trade=risk_per_trade
                )
                st.success("✅ 交易器初始化成功")
        
        with col2:
            if st.button("🔄 重置", use_container_width=True):
                st.session_state.trader = None
                st.session_state.trade_history = []
                st.session_state.positions = {}
                st.success("✅ 已重置")
    
    # 主内容区
    if st.session_state.trader is None:
        st.info("💡 请在侧边栏配置交易参数并初始化交易器")
        return
    
    trader = st.session_state.trader
    
    # 投资组合状态
    st.markdown("### 📊 投资组合状态")
    status = trader.get_portfolio_status()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("总资产", f"¥{status['total_value']:,.2f}")
    with col2:
        st.metric("可用资金", f"¥{status['current_capital']:,.2f}")
    with col3:
        st.metric("持仓市值", f"¥{status['positions_value']:,.2f}")
    with col4:
        total_return = status['total_return_percent']
        st.metric("总收益率", f"{total_return:.2f}%", 
                 delta=f"¥{status['total_pnl']:,.2f}")
    with col5:
        st.metric("持仓数量", status['positions_count'])
    
    # 持仓明细
    if status['positions']:
        st.markdown("### 📋 当前持仓")
        positions_df = pd.DataFrame(status['positions'])
        st.dataframe(positions_df, use_container_width=True)
        
        # 持仓盈亏图表
        if len(status['positions']) > 0:
            fig = px.bar(
                positions_df,
                x='ticker',
                y='pnl_percent',
                title="持仓盈亏分布",
                color='pnl_percent',
                color_continuous_scale=['red', 'yellow', 'green']
            )
            fig.update_layout(yaxis_title="盈亏 (%)")
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # 交易执行
    st.markdown("### 💹 交易执行")
    
    tab1, tab2, tab3 = st.tabs(["📡 信号生成", "📊 历史交易", "📈 回测分析"])
    
    with tab1:
        render_signal_generation(trader)
    
    with tab2:
        render_trade_history(trader)
    
    with tab3:
        render_backtest(trader)


def render_signal_generation(trader: QuantitativeTrader):
    """渲染信号生成界面"""
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        ticker_input = st.text_input(
            "股票代码",
            placeholder="例如: 002701 或 002701,601360",
            help="输入股票代码，多个代码用逗号分隔（将处理第一个）"
        )
        
        # 处理多个股票代码（取第一个）
        ticker = None
        if ticker_input:
            tickers = [t.strip() for t in ticker_input.split(',') if t.strip()]
            if tickers:
                ticker = tickers[0]  # 只处理第一个
                if len(tickers) > 1:
                    st.info(f"💡 检测到多个股票代码，将分析第一个: {ticker}（共{len(tickers)}个）")
        
        if ticker:
            # 先获取当前价格
            current_price = st.number_input(
                "💰 当前价格",
                min_value=0.01,
                value=7.85,
                help="请输入股票的当前价格",
                key=f"price_{ticker}"
            )
            
            if st.button("🔍 生成交易信号", type="primary", use_container_width=True):
                with st.spinner("正在分析市场数据并生成信号..."):
                    try:
                        # 获取市场数据（根据股票类型选择接口）
                        market_info = StockUtils.get_market_info(ticker)
                        
                        end_date = datetime.now()
                        start_date = end_date - timedelta(days=60)
                        
                        data_str = ""
                        market_df = None
                        
                        try:
                            import time
                            
                            # 添加重试机制（最多3次）
                            max_retries = 3
                            retry_delay = 2  # 等待时间（秒）
                            data_str = ""
                            
                            for attempt in range(max_retries):
                                try:
                                    if market_info['is_china']:
                                        data_str = get_china_stock_data_unified(
                                            ticker,
                                            start_date.strftime('%Y-%m-%d'),
                                            end_date.strftime('%Y-%m-%d')
                                        )
                                    else:
                                        data_str = get_YFin_data_online(
                                            ticker,
                                            start_date.strftime('%Y-%m-%d'),
                                            end_date.strftime('%Y-%m-%d')
                                        )
                                    
                                    # 检查是否包含频率限制错误
                                    if "Too Many Requests" in data_str or "Rate limited" in data_str or "频率限制" in data_str:
                                        if attempt < max_retries - 1:
                                            wait_time = retry_delay * (attempt + 1)
                                            st.warning(f"⚠️ API请求频率限制，等待 {wait_time} 秒后重试... ({attempt + 1}/{max_retries})")
                                            time.sleep(wait_time)
                                            continue
                                        else:
                                            raise Exception("API请求频率限制，已重试3次仍失败")
                                    
                                    # 检查是否包含其他错误
                                    if "❌" in data_str or "错误" in data_str or "失败" in data_str:
                                        if "Too Many Requests" in data_str or "Rate limited" in data_str:
                                            raise Exception("API请求频率限制")
                                        break
                                    
                                    # 数据获取成功，跳出重试循环
                                    break
                                    
                                except Exception as retry_error:
                                    if "Too Many Requests" in str(retry_error) or "Rate limited" in str(retry_error) or "频率限制" in str(retry_error):
                                        if attempt < max_retries - 1:
                                            wait_time = retry_delay * (attempt + 1)
                                            st.warning(f"⚠️ API请求频率限制，等待 {wait_time} 秒后重试... ({attempt + 1}/{max_retries})")
                                            time.sleep(wait_time)
                                            continue
                                        else:
                                            raise
                                    else:
                                        raise
                            
                            # 尝试解析数据字符串为DataFrame
                            market_df = parse_market_data_string(data_str, ticker) if data_str else None
                            
                        except Exception as e:
                            error_msg = str(e)
                            logger.warning(f"获取市场数据失败: {e}")
                            
                            # 根据错误类型显示不同的提示
                            if "Too Many Requests" in error_msg or "Rate limited" in error_msg or "频率限制" in error_msg:
                                st.error("❌ API请求频率限制")
                                st.warning("""
                                **API请求过于频繁，请稍后重试**
                                
                                **解决方案：**
                                1. **等待一段时间**（建议等待30秒-1分钟后重试）
                                2. **减少请求频率**（避免连续多次点击）
                                3. **检查API配额**
                                   - Tushare免费账户有每日/每分钟请求限制
                                   - 考虑升级到付费账户获取更高配额
                                4. **使用缓存数据**
                                   - 系统会自动缓存数据，避免重复请求
                                   - 可以尝试刷新页面使用缓存
                                
                                **临时解决方案：**
                                - 等待1-2分钟后重试
                                - 或使用"多因子策略"，结合已有的分析报告
                                """)
                            else:
                                st.warning(f"⚠️ 市场数据获取失败: {error_msg[:100]}")
                                
                                # 显示数据获取失败的详细提示
                                with st.expander("💡 如何解决数据获取问题？", expanded=False):
                                    st.markdown("""
                                    可能的原因和解决方案：
                                    
                                    1. **API配置问题**
                                       - 检查 Tushare API 密钥是否正确配置在 `.env` 文件中
                                       - 确认 Tushare 账户有足够的积分
                                       
                                    2. **网络连接问题**
                                       - 检查网络连接是否正常
                                       - 尝试刷新页面重试
                                       
                                    3. **数据源服务问题**
                                       - 确认 MongoDB 是否正在运行
                                       - 检查数据缓存是否过期
                                       
                                    4. **股票代码格式问题**
                                       - 确认股票代码格式正确（A股：6位数字，如 002701）
                                       - 避免使用特殊字符
                                       
                                    5. **日期范围问题**
                                       - 当前查询60天历史数据
                                       - 如果是新股或停牌股票，可能没有足够数据
                                       
                                    **临时解决方案**：
                                    - 可以尝试使用"多因子策略"，它不依赖历史价格数据
                                    - 或者先在其他页面（股票分析）生成分析报告，然后使用报告数据
                                    """)
                            
                            market_df = None
                        
                        # 生成信号
                        try:
                            # 如果有market_df，生成信号
                            if market_df is not None:
                                signal, strength, details = trader.generate_signal(
                                    ticker=ticker,
                                    current_price=current_price,
                                    market_data=market_df,
                                    analysis_reports=None
                                )
                            else:
                                # 如果没有市场数据，尝试使用简化信号生成
                                st.info("💡 由于无法获取历史价格数据，将使用简化信号生成（基于当前价格）")
                                signal = SignalType.HOLD
                                strength = 0.0
                                details = {
                                    'reason': '无法获取历史数据，建议持有或使用多因子策略',
                                    'suggestion': '可以尝试：1)等待API频率限制解除后重试，2)使用多因子策略结合分析报告'
                                }
                        except Exception as e:
                            # 如果生成信号失败，返回持有信号
                            error_msg = str(e)
                            logger.error(f"信号生成失败: {e}", exc_info=True)
                            
                            signal = SignalType.HOLD
                            strength = 0.0
                            
                            # 根据错误类型提供不同的提示
                            if "Too Many Requests" in error_msg or "Rate limited" in error_msg:
                                details = {
                                    'error': error_msg,
                                    'reason': 'API请求频率限制，信号生成失败',
                                    'suggestion': '请等待30秒-1分钟后重试，或使用多因子策略'
                                }
                            else:
                                details = {
                                    'error': error_msg,
                                    'reason': '信号生成失败，建议持有',
                                    'suggestion': '可以尝试使用其他策略或检查数据源配置'
                                }
                        
                        # 显示信号
                        st.markdown("### 📡 交易信号")
                        
                        signal_colors = {
                            SignalType.BUY: "🟢",
                            SignalType.SELL: "🔴",
                            SignalType.HOLD: "🟡",
                            SignalType.CLOSE: "⚫"
                        }
                        
                        # 根据不同的错误类型显示不同的提示
                        reason = details.get('reason', '')
                        suggestion = details.get('suggestion', '')
                        
                        if 'API请求频率限制' in reason or 'Rate limited' in reason or 'Too Many Requests' in reason:
                            st.error("❌ API请求频率限制")
                            st.warning(f"""
                            **原因：** {reason}
                            
                            **解决建议：**
                            1. **等待后重试**：等待30秒-1分钟后再次点击"生成交易信号"
                            2. **减少请求频率**：避免连续多次请求
                            3. **检查API配额**：
                               - Tushare免费账户有请求频率限制
                               - 考虑升级账户或使用其他数据源
                            4. **使用替代方案**：
                               - 切换到"多因子策略"
                               - 先在"股票分析"页面生成分析报告
                               - 然后使用报告数据生成信号
                            """)
                            if suggestion:
                                st.info(f"💡 {suggestion}")
                                
                        elif '数据不足' in reason or '数据量不足' in reason:
                            st.error("❌ 数据不足，无法生成有效信号")
                            st.info("""
                            **可能的原因：**
                            - 获取的历史数据少于20条（需要至少20-26条数据）
                            - 数据解析失败（数据格式不支持）
                            - API或数据源配置问题
                            
                            **建议：**
                            1. 检查数据源配置（Tushare API密钥）
                            2. 确认股票代码正确
                            3. 如果是新股，等待有更多交易数据
                            4. 或使用"多因子策略"，结合分析报告生成信号
                            """)
                        else:
                            signal_display = f"""
                            <div style="padding: 20px; border-radius: 10px; background: {'#d4edda' if signal == SignalType.BUY else '#f8d7da' if signal == SignalType.SELL else '#fff3cd'}; margin: 10px 0;">
                                <h2>{signal_colors.get(signal, '⚪')} {signal.value}</h2>
                                <p><strong>信号强度:</strong> {strength:.2f}/10.0</p>
                                <p><strong>信号详情:</strong> {reason}</p>
                            </div>
                            """
                            st.markdown(signal_display, unsafe_allow_html=True)
                        
                        # 执行交易选项
                        if signal in [SignalType.BUY, SignalType.SELL, SignalType.CLOSE]:
                            st.markdown("### ⚡ 执行交易")
                            
                            quantity = st.number_input(
                                "交易数量（留空自动计算）",
                                min_value=0,
                                value=0,
                                help="留空或0表示根据风险管理自动计算仓位"
                            )
                            
                            col_exec1, col_exec2 = st.columns(2)
                            with col_exec1:
                                if st.button(f"✅ 执行 {signal.value}", type="primary", use_container_width=True):
                                    try:
                                        success = trader.execute_trade(
                                            ticker=ticker,
                                            signal=signal,
                                            price=current_price,
                                            quantity=quantity if quantity > 0 else None
                                        )
                                        if success:
                                            st.success(f"✅ {signal.value} 执行成功")
                                            st.rerun()
                                        else:
                                            st.warning("⚠️ 交易执行失败，请查看日志")
                                    except Exception as e:
                                        st.error(f"❌ 交易执行错误: {e}")
                            
                            with col_exec2:
                                if st.button("📊 查看持仓建议", use_container_width=True):
                                    # 计算建议仓位
                                    if signal == SignalType.BUY:
                                        stop_loss = current_price * (1 - 0.05)  # 假设5%止损
                                        suggested_qty = trader.calculate_position_size(
                                            ticker, current_price, stop_loss
                                        )
                                        st.info(f"💡 建议仓位: {suggested_qty} 股\n"
                                               f"预计成本: ¥{current_price * suggested_qty:,.2f}")
                    
                    except Exception as e:
                        st.error(f"❌ 生成信号失败: {e}")
                        if logger:
                            logger.error(f"信号生成失败: {e}", exc_info=True)
    
    with col2:
        st.markdown("### 📊 策略说明")
        
        strategy_descriptions = {
            StrategyType.TREND_FOLLOWING: """
            **趋势跟踪策略**
            - 跟随价格趋势
            - 金叉买入，死叉卖出
            - 适合趋势明显市场
            """,
            StrategyType.MEAN_REVERSION: """
            **均值回归策略**
            - 价格偏离均值时交易
            - 触及上下轨操作
            - 适合震荡市场
            """,
            StrategyType.MOMENTUM: """
            **动量策略**
            - 追逐强势股票
            - 基于RSI和MACD
            - 适合强势市场
            """,
            StrategyType.MULTI_FACTOR: """
            **多因子策略**
            - 综合多个维度
            - 技术+基本面+情绪
            - 适合所有市场
            """
        }
        
        st.markdown(strategy_descriptions.get(trader.strategy_type, ""))


def render_trade_history(trader: QuantitativeTrader):
    """渲染交易历史"""
    
    trade_history = trader.trade_history
    
    if not trade_history:
        st.info("📝 暂无交易记录")
        return
    
    # 转换为DataFrame
    history_df = pd.DataFrame(trade_history)
    
    st.markdown(f"### 📋 交易历史（共 {len(trade_history)} 笔）")
    
    # 交易统计
    if 'pnl' in history_df.columns:
        total_pnl = history_df['pnl'].sum()
        winning_trades = len(history_df[history_df['pnl'] > 0])
        losing_trades = len(history_df[history_df['pnl'] < 0])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总盈亏", f"¥{total_pnl:,.2f}")
        with col2:
            st.metric("盈利交易", winning_trades)
        with col3:
            st.metric("亏损交易", losing_trades)
        with col4:
            win_rate = winning_trades / len(trade_history) * 100 if trade_history else 0
            st.metric("胜率", f"{win_rate:.1f}%")
    
    # 交易列表
    st.dataframe(history_df, use_container_width=True)
    
    # 盈亏曲线图
    if 'date' in history_df.columns and 'pnl' in history_df.columns:
        history_df['cumulative_pnl'] = history_df['pnl'].cumsum()
        fig = px.line(
            history_df,
            x='date',
            y='cumulative_pnl',
            title="累计盈亏曲线",
            labels={'cumulative_pnl': '累计盈亏 (¥)', 'date': '日期'}
        )
        st.plotly_chart(fig, use_container_width=True)


def render_backtest(trader: QuantitativeTrader):
    """渲染回测分析"""
    
    st.info("📊 回测分析功能开发中，将支持历史数据回测和策略性能评估")
    
    # TODO: 实现回测功能
    st.markdown("""
    ### 计划功能
    
    1. **历史回测**
       - 选择回测时间段
       - 选择回测股票池
       - 执行策略回测
    
    2. **性能指标**
       - 总收益率
       - 年化收益率
       - 夏普比率
       - 最大回撤
       - 胜率
    
    3. **对比分析**
       - 多个策略对比
       - 参数优化建议
    """)
