#!/usr/bin/env python3
"""
智能选股组件
"""

import streamlit as st
import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from tradingagents.models import StockScreener, create_screener_config
    MODELS_AVAILABLE = True
except ImportError as e:
    MODELS_AVAILABLE = False
    st.error(f"选股模型模块不可用: {e}")

from tradingagents.utils.stock_utils import StockUtils

logger = None
try:
    from tradingagents.utils.logging_init import get_logger
    logger = get_logger('web.stock_screening')
except:
    import logging
    logger = logging.getLogger('stock_screening')


def render_stock_screening():
    """渲染智能选股页面"""
    
    if not MODELS_AVAILABLE:
        st.error("❌ 选股模型模块不可用，请检查依赖安装")
        st.info("""
        请确保已安装所有依赖：
        ```bash
        pip install -r requirements.txt
        ```
        """)
        return
    
    st.title("🔍 智能选股")
    st.markdown("基于多维度分析的智能选股系统，帮助您从海量股票中筛选出最具投资价值的标的")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 选股配置")
        
        # 策略选择
        strategy_type = st.selectbox(
            "📊 选股策略",
            ["balanced", "conservative", "aggressive", "value", "growth"],
            format_func=lambda x: {
                "balanced": "平衡型（推荐）",
                "conservative": "保守型（稳健投资）",
                "aggressive": "激进型（追求收益）",
                "value": "价值型（长期持有）",
                "growth": "成长型（高速增长）"
            }.get(x, x),
            help="选择适合您风险偏好的选股策略"
        )
        
        config_params = create_screener_config(strategy_type)
        
        st.markdown("### 📊 评分权重")
        st.json(config_params['weights'])
        
        st.markdown("### 📋 筛选条件")
        st.json(config_params['score_conditions'])
        
        st.markdown("---")
        
        # 市场筛选
        market_types = st.multiselect(
            "🌐 市场类型",
            ["A股", "港股", "美股"],
            default=["A股"],
            help="选择要筛选的市场"
        )
        
        # 行业筛选（可选）
        include_industry_filter = st.checkbox("启用行业筛选")
        industry = None
        if include_industry_filter:
            industry = st.text_input("行业关键词（如：科技、金融）", placeholder="留空则显示所有行业")
    
    # 主内容区
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 股票输入方式
        input_method = st.radio(
            "📝 股票输入方式",
            ["手动输入", "文件上传", "自动获取（A股全市场）"],
            horizontal=True
        )
        
        if input_method == "手动输入":
            stock_input = st.text_area(
                "输入股票代码（每行一个，或用逗号分隔）",
                placeholder="例如：\n000001\n600519\n002701",
                height=150
            )
            
            if stock_input:
                # 解析股票代码
                stock_list = []
                for line in stock_input.split('\n'):
                    line = line.strip()
                    if line:
                        # 支持逗号分隔
                        for code in line.split(','):
                            code = code.strip()
                            if code and len(code) >= 4:
                                stock_list.append(code)
                
                if stock_list:
                    st.info(f"✅ 已识别 {len(stock_list)} 只股票")
        
        elif input_method == "文件上传":
            uploaded_file = st.file_uploader("上传CSV文件（包含股票代码列）", type=['csv'])
            stock_list = []
            if uploaded_file:
                try:
                    df = pd.read_csv(uploaded_file)
                    # 尝试找到股票代码列
                    code_columns = [col for col in df.columns if 'code' in col.lower() or '代码' in col or 'ticker' in col.lower()]
                    if code_columns:
                        stock_list = df[code_columns[0]].dropna().astype(str).tolist()
                        st.success(f"✅ 成功读取 {len(stock_list)} 只股票")
                    else:
                        st.warning("⚠️ 未找到股票代码列，请确保CSV文件包含'code'、'代码'或'ticker'列")
                except Exception as e:
                    st.error(f"❌ 文件读取失败: {e}")
        
        else:
            # 自动获取A股列表（示例：使用常见股票代码）
            st.info("💡 自动获取功能需要配置Tushare等数据源，当前显示示例股票")
            default_stocks = ['000001', '000002', '600000', '600519', '000858', '002701', '300750', '600036']
            stock_list = st.multiselect(
                "选择示例股票（实际使用中会获取全市场数据）",
                default_stocks,
                default=default_stocks[:5]
            )
    
    with col2:
        st.markdown("### 📊 快速统计")
        if 'stock_list' in locals() and stock_list:
            st.metric("候选股票", len(stock_list))
            
            # 分析市场分布
            market_dist = {}
            for ticker in stock_list:
                try:
                    market_info = StockUtils.get_market_info(ticker)
                    market_name = market_info['market_name']
                    market_dist[market_name] = market_dist.get(market_name, 0) + 1
                except:
                    pass
            
            if market_dist:
                st.markdown("**市场分布**")
                for market, count in market_dist.items():
                    st.write(f"- {market}: {count}只")
    
    # 执行筛选按钮
    if 'stock_list' in locals() and stock_list and st.button("🚀 开始智能筛选", type="primary", use_container_width=True):
        
        with st.spinner("🔍 正在筛选股票，请稍候..."):
            try:
                # 使用工具函数运行筛选
                from web.utils.model_runner import run_stock_screening
                
                result = run_stock_screening(
                    stock_list=stock_list,
                    strategy_type=strategy_type,
                    screening_conditions={
                        'market': market_types if market_types else ['A股', '港股', '美股']
                    }
                )
                
                # 保存结果到session state
                st.session_state['screening_result'] = result
                st.success(f"✅ 筛选完成！找到 {result['recommended_count']} 只推荐股票")
                
            except Exception as e:
                st.error(f"❌ 筛选失败: {e}")
                import traceback
                st.exception(e)
                if logger:
                    logger.error(f"选股失败: {e}", exc_info=True)
    
    # 显示筛选结果
    if 'screening_result' in st.session_state:
        display_screening_results(st.session_state['screening_result'])


def display_screening_results(result: Dict[str, Any]):
    """显示筛选结果"""
    
    st.markdown("---")
    st.header("📊 筛选结果")
    
    # 结果统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("候选总数", result['total_candidates'])
    with col2:
        st.metric("基础筛选后", result['filtered_count'])
    with col3:
        st.metric("推荐股票", result['recommended_count'])
    with col4:
        st.metric("筛选日期", result['screening_date'])
    
    recommended_stocks = result.get('recommended_stocks', [])
    
    if not recommended_stocks:
        st.warning("⚠️ 未找到符合条件的推荐股票，请尝试调整筛选条件")
        return
    
    # 评分分布图表
    if len(recommended_stocks) > 0:
        st.markdown("### 📈 评分分布")
        
        scores_df = pd.DataFrame([
            {
                '股票代码': stock['ticker'],
                '综合评分': stock['scores']['composite'],
                '技术面': stock['scores']['technical'],
                '基本面': stock['scores']['fundamental'],
                '情绪': stock['scores']['sentiment'],
                '新闻': stock['scores']['news']
            }
            for stock in recommended_stocks
        ])
        
        # 雷达图（前5只）
        fig_radar = go.Figure()
        
        for i, stock in enumerate(recommended_stocks[:5]):
            scores = stock['scores']
            fig_radar.add_trace(go.Scatterpolar(
                r=[
                    scores['technical'],
                    scores['fundamental'],
                    scores['sentiment'],
                    scores['news'],
                    scores['composite']
                ],
                theta=['技术面', '基本面', '情绪', '新闻', '综合'],
                fill='toself',
                name=stock['ticker']
            ))
        
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )),
            showlegend=True,
            title="前5只股票评分对比（雷达图）"
        )
        st.plotly_chart(fig_radar, use_container_width=True)
        
        # 柱状图
        fig_bar = px.bar(
            scores_df.head(20),
            x='股票代码',
            y=['综合评分', '技术面', '基本面', '情绪', '新闻'],
            barmode='group',
            title="前20只股票评分对比"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # 详细列表
    st.markdown("### 📋 推荐股票详情")
    
    # 排序选项
    sort_by = st.selectbox(
        "排序方式",
        ["综合评分", "技术面评分", "基本面评分", "情绪评分"],
        key="sort_option"
    )
    
    sort_key_map = {
        "综合评分": "composite",
        "技术面评分": "technical",
        "基本面评分": "fundamental",
        "情绪评分": "sentiment"
    }
    
    sorted_stocks = sorted(
        recommended_stocks,
        key=lambda x: x['scores'].get(sort_key_map[sort_by], 0),
        reverse=True
    )
    
    # 显示前50只
    display_count = st.slider("显示数量", 10, min(50, len(sorted_stocks)), 20)
    
    # 创建详细表格
    for i, stock in enumerate(sorted_stocks[:display_count], 1):
        with st.expander(f"#{i} {stock['ticker']} - 综合评分: {stock['scores']['composite']:.2f}", expanded=(i <= 3)):
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("综合评分", f"{stock['scores']['composite']:.1f}")
            with col2:
                st.metric("技术面", f"{stock['scores']['technical']:.1f}")
            with col3:
                st.metric("基本面", f"{stock['scores']['fundamental']:.1f}")
            with col4:
                st.metric("情绪", f"{stock['scores']['sentiment']:.1f}")
            with col5:
                st.metric("新闻", f"{stock['scores']['news']:.1f}")
            
            # 评分条形图
            score_data = pd.DataFrame({
                '维度': ['技术面', '基本面', '情绪', '新闻'],
                '评分': [
                    stock['scores']['technical'],
                    stock['scores']['fundamental'],
                    stock['scores']['sentiment'],
                    stock['scores']['news']
                ]
            })
            fig = px.bar(score_data, x='维度', y='评分', title=f"{stock['ticker']} 各维度评分")
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
            
            # 操作按钮
            btn1, btn2 = st.columns(2)
            with btn1:
                if st.button(f"🔍 查看详细分析", key=f"analyze_{stock['ticker']}"):
                    st.session_state['selected_ticker'] = stock['ticker']
                    st.info(f"将在股票分析页面分析 {stock['ticker']}")
            with btn2:
                if st.button(f"📊 加入观察", key=f"watch_{stock['ticker']}"):
                    if 'watchlist' not in st.session_state:
                        st.session_state['watchlist'] = []
                    if stock['ticker'] not in st.session_state['watchlist']:
                        st.session_state['watchlist'].append(stock['ticker'])
                        st.success(f"✅ {stock['ticker']} 已加入观察列表")
    
    # 导出结果
    st.markdown("---")
    st.markdown("### 💾 导出结果")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 导出CSV", use_container_width=True):
            export_df = pd.DataFrame([
                {
                    '股票代码': stock['ticker'],
                    '综合评分': stock['scores']['composite'],
                    '技术面': stock['scores']['technical'],
                    '基本面': stock['scores']['fundamental'],
                    '情绪': stock['scores']['sentiment'],
                    '新闻': stock['scores']['news']
                }
                for stock in sorted_stocks
            ])
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="下载CSV文件",
                data=csv,
                file_name=f"选股结果_{result['screening_date']}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("📥 导出JSON", use_container_width=True):
            import json
            json_data = json.dumps(result, ensure_ascii=False, indent=2, default=str)
            st.download_button(
                label="下载JSON文件",
                data=json_data,
                file_name=f"选股结果_{result['screening_date']}.json",
                mime="application/json"
            )
