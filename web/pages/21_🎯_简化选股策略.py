"""
简化版选股策略页面
基于现有数据实现多维度条件选股，类似专业选股工具
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime, timedelta
import numpy as np

# 添加项目路径
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
data_engine_path = project_root / "data_engine"
if str(data_engine_path) not in sys.path:
    sys.path.insert(0, str(data_engine_path))

from data_engine.config import DB_URL
from data_engine.utils.db_utils import get_engine
from sqlalchemy import text, inspect
from web.utils.data_cleaner import clean_duplicate_columns

st.set_page_config(
    page_title="简化选股策略",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 简化版选股策略")
st.markdown("基于现有数据实现多维度条件选股，支持技术面、基本面、行情面、财务面筛选")

# 初始化数据库连接
@st.cache_resource
def get_db_engine():
    return get_engine(DB_URL)

engine = get_db_engine()
inspector = inspect(engine)
tables = inspector.get_table_names()

# 检查数据可用性
has_market = 'stock_market_daily' in tables
has_financials = 'stock_financials' in tables
has_technical = 'stock_technical_indicators' in tables
has_moneyflow = 'stock_moneyflow' in tables

if not has_market:
    st.error("❌ 缺少市场数据表 stock_market_daily，请先下载数据")
    st.stop()

# 获取最新交易日期
@st.cache_data(ttl=300)
def get_latest_date():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(trade_date) FROM stock_market_daily"))
        return result.scalar()

latest_date = get_latest_date()
if not latest_date:
    st.error("❌ 没有找到市场数据，请先下载数据")
    st.stop()

st.info(f"📅 当前数据日期: {latest_date}")

# ========== 加载数据 ==========
@st.cache_data(ttl=300)
def load_stock_data():
    """加载股票数据"""
    with engine.connect() as conn:
        # 基础信息
        df_basic = pd.read_sql_query("SELECT * FROM stock_basic_info", engine)
        df_basic = df_basic.drop_duplicates(subset=['ts_code'], keep='first')
        
        # 市场数据（最新日期）
        query_market = f"""
            SELECT 
                ts_code,
                close as price,
                volume,
                amount,
                pct_chg as change_pct,
                turnover_rate,
                amplitude,
                peTTM as pe,
                pbMRQ as pb,
                psTTM as ps
            FROM stock_market_daily
            WHERE trade_date = '{latest_date}'
        """
        df_market = pd.read_sql_query(query_market, engine)
        
        # 财务数据（最新日期，为每个股票获取最新数据）
        df_fin = None
        if has_financials:
            query_fin = f"""
                SELECT 
                    f1.ts_code,
                    f1.pe,
                    f1.pb,
                    f1.ps,
                    f1.roe,
                    f1.roa,
                    f1.eps,
                    f1.total_mv,
                    f1.circ_mv,
                    f1.revenue_yoy,
                    f1.net_profit_yoy,
                    f1.gross_profit_margin
                FROM stock_financials f1
                INNER JOIN (
                    SELECT ts_code, MAX(trade_date) as max_date
                    FROM stock_financials
                    GROUP BY ts_code
                ) f2 ON f1.ts_code = f2.ts_code AND f1.trade_date = f2.max_date
            """
            df_fin = pd.read_sql_query(query_fin, engine)
        
        # 技术指标（最新日期）
        df_tech = None
        if has_technical:
            query_tech = f"""
                SELECT 
                    ts_code,
                    ma5,
                    ma20,
                    ma60,
                    rsi,
                    macd,
                    kdj_k,
                    kdj_d
                FROM stock_technical_indicators
                WHERE trade_date = (
                    SELECT MAX(trade_date) FROM stock_technical_indicators
                )
            """
            df_tech = pd.read_sql_query(query_tech, engine)
        
        # 资金流向（最新日期）
        df_mf = None
        if has_moneyflow:
            query_mf = f"""
                SELECT 
                    ts_code,
                    net_mf_amount,
                    net_mf_ratio,
                    super_large,
                    large
                FROM stock_moneyflow
                WHERE trade_date = (
                    SELECT MAX(trade_date) FROM stock_moneyflow
                )
            """
            df_mf = pd.read_sql_query(query_mf, engine)
        
        # 合并数据
        df = df_basic.merge(df_market, on='ts_code', how='inner')
        if df_fin is not None:
            df = df.merge(df_fin, on='ts_code', how='left', suffixes=('', '_fin'))
            # 合并重复字段（优先使用财务表的）
            if 'pe_fin' in df.columns:
                df['pe'] = df['pe_fin'].fillna(df['pe'])
            if 'pb_fin' in df.columns:
                df['pb'] = df['pb_fin'].fillna(df['pb'])
            if 'ps_fin' in df.columns:
                df['ps'] = df['ps_fin'].fillna(df['ps'])
            df = df.drop(columns=[col for col in df.columns if col.endswith('_fin')], errors='ignore')
        
        if df_tech is not None:
            df = df.merge(df_tech, on='ts_code', how='left')
        
        if df_mf is not None:
            df = df.merge(df_mf, on='ts_code', how='left')
        
        # 字段重命名
        if 'code_name' in df.columns:
            df = df.rename(columns={'code_name': 'stock_name', 'ts_code': 'stock_code'})
        elif 'name' in df.columns:
            df = df.rename(columns={'name': 'stock_name', 'ts_code': 'stock_code'})
        else:
            df = df.rename(columns={'ts_code': 'stock_code'})
        
        return df

df = load_stock_data()

if df.empty:
    st.error("❌ 没有找到股票数据")
    st.stop()

st.success(f"✅ 加载 {len(df):,} 只股票数据")

# ========== 选股条件设置 ==========
st.markdown("---")
st.subheader("📋 选股条件设置")

# 使用tabs组织不同类型的筛选条件
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 技术面", 
    "💰 基本面", 
    "📈 行情面", 
    "💼 财务面",
    "🎯 综合条件"
])

filter_conditions = {}

# ========== 技术面筛选 ==========
with tab1:
    st.markdown("#### 📊 技术指标筛选")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**均线系统**")
        ma_enabled = st.checkbox("启用均线筛选", key="ma_enabled")
        if ma_enabled:
            ma_type = st.selectbox("均线类型", ["MA5", "MA20", "MA60"], key="ma_type")
            ma_condition = st.selectbox("条件", ["上穿", "下穿", "上方", "下方", "金叉", "死叉"], key="ma_condition")
            if ma_type and ma_condition:
                filter_conditions['ma'] = {'type': ma_type, 'condition': ma_condition}
        
        st.markdown("**MACD**")
        macd_enabled = st.checkbox("启用MACD筛选", key="macd_enabled")
        if macd_enabled:
            macd_condition = st.selectbox("MACD条件", ["金叉", "死叉", "正值", "负值"], key="macd_condition")
            if macd_condition:
                filter_conditions['macd'] = {'condition': macd_condition}
        
        st.markdown("**RSI**")
        rsi_enabled = st.checkbox("启用RSI筛选", key="rsi_enabled")
        if rsi_enabled:
            rsi_range = st.slider("RSI范围", 0.0, 100.0, (30.0, 70.0), key="rsi_range")
            filter_conditions['rsi'] = {'range': rsi_range}
    
    with col2:
        st.markdown("**KDJ**")
        kdj_enabled = st.checkbox("启用KDJ筛选", key="kdj_enabled")
        if kdj_enabled:
            kdj_condition = st.selectbox("KDJ条件", ["金叉", "死叉", "超买(>80)", "超卖(<20)"], key="kdj_condition")
            if kdj_condition:
                filter_conditions['kdj'] = {'condition': kdj_condition}
        
        st.markdown("**形态**")
        form_enabled = st.checkbox("启用形态筛选", key="form_enabled")
        if form_enabled:
            form_type = st.selectbox("形态类型", ["突破", "整理", "回调"], key="form_type")
            if form_type:
                filter_conditions['form'] = {'type': form_type}

# ========== 基本面筛选 ==========
with tab2:
    st.markdown("#### 💰 基本面指标筛选")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**估值指标**")
        pe_enabled = st.checkbox("启用PE筛选", key="pe_enabled")
        if pe_enabled:
            pe_range = st.slider("PE范围", 0.0, 100.0, (0.0, 30.0), key="pe_range")
            filter_conditions['pe'] = {'range': pe_range}
        
        pb_enabled = st.checkbox("启用PB筛选", key="pb_enabled")
        if pb_enabled:
            pb_range = st.slider("PB范围", 0.0, 10.0, (0.0, 3.0), key="pb_range")
            filter_conditions['pb'] = {'range': pb_range}
        
        ps_enabled = st.checkbox("启用PS筛选", key="ps_enabled")
        if ps_enabled:
            ps_range = st.slider("PS范围", 0.0, 20.0, (0.0, 5.0), key="ps_range")
            filter_conditions['ps'] = {'range': ps_range}
    
    with col2:
        st.markdown("**市值指标**")
        mv_enabled = st.checkbox("启用总市值筛选", key="mv_enabled")
        if mv_enabled:
            mv_range = st.slider("总市值范围（亿元）", 0.0, 10000.0, (0.0, 1000.0), key="mv_range")
            filter_conditions['total_mv'] = {'range': (mv_range[0] * 1e8, mv_range[1] * 1e8)}
        
        st.markdown("**股本指标**")
        circ_mv_enabled = st.checkbox("启用流通市值筛选", key="circ_mv_enabled")
        if circ_mv_enabled:
            circ_mv_range = st.slider("流通市值范围（亿元）", 0.0, 5000.0, (0.0, 500.0), key="circ_mv_range")
            filter_conditions['circ_mv'] = {'range': (circ_mv_range[0] * 1e8, circ_mv_range[1] * 1e8)}

# ========== 行情面筛选 ==========
with tab3:
    st.markdown("#### 📈 行情指标筛选")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**价格表现**")
        price_enabled = st.checkbox("启用价格筛选", key="price_enabled")
        if price_enabled:
            price_range = st.slider("价格范围（元）", 0.0, 500.0, (0.0, 100.0), key="price_range")
            filter_conditions['price'] = {'range': price_range}
        
        change_enabled = st.checkbox("启用涨跌幅筛选", key="change_enabled")
        if change_enabled:
            change_range = st.slider("涨跌幅范围（%）", -10.0, 10.0, (-5.0, 5.0), key="change_range")
            filter_conditions['change_pct'] = {'range': change_range}
        
        amplitude_enabled = st.checkbox("启用振幅筛选", key="amplitude_enabled")
        if amplitude_enabled:
            amplitude_range = st.slider("振幅范围（%）", 0.0, 20.0, (0.0, 10.0), key="amplitude_range")
            filter_conditions['amplitude'] = {'range': amplitude_range}
    
    with col2:
        st.markdown("**成交量指标**")
        volume_enabled = st.checkbox("启用成交量筛选", key="volume_enabled")
        if volume_enabled:
            volume_type = st.selectbox("成交量条件", ["放量", "缩量", "正常"], key="volume_type")
            if volume_type:
                filter_conditions['volume'] = {'type': volume_type}
        
        turnover_enabled = st.checkbox("启用换手率筛选", key="turnover_enabled")
        if turnover_enabled:
            turnover_range = st.slider("换手率范围（%）", 0.0, 50.0, (0.0, 10.0), key="turnover_range")
            filter_conditions['turnover_rate'] = {'range': turnover_range}
        
        amount_enabled = st.checkbox("启用成交额筛选", key="amount_enabled")
        if amount_enabled:
            amount_range = st.slider("成交额范围（亿元）", 0.0, 1000.0, (0.0, 100.0), key="amount_range")
            filter_conditions['amount'] = {'range': (amount_range[0] * 1e8, amount_range[1] * 1e8)}

# ========== 财务面筛选 ==========
with tab4:
    st.markdown("#### 💼 财务指标筛选")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**盈利能力**")
        roe_enabled = st.checkbox("启用ROE筛选", key="roe_enabled")
        if roe_enabled:
            roe_range = st.slider("ROE范围（%）", -50.0, 50.0, (0.0, 30.0), key="roe_range")
            filter_conditions['roe'] = {'range': roe_range}
        
        roa_enabled = st.checkbox("启用ROA筛选", key="roa_enabled")
        if roa_enabled:
            roa_range = st.slider("ROA范围（%）", -20.0, 20.0, (0.0, 15.0), key="roa_range")
            if roa_range:
                filter_conditions['roa'] = {'range': roa_range}
        
        margin_enabled = st.checkbox("启用毛利率筛选", key="margin_enabled")
        if margin_enabled:
            margin_range = st.slider("毛利率范围（%）", 0.0, 100.0, (20.0, 80.0), key="margin_range")
            if margin_range:
                filter_conditions['gross_profit_margin'] = {'range': margin_range}
    
    with col2:
        st.markdown("**成长性**")
        revenue_yoy_enabled = st.checkbox("启用营收增长率筛选", key="revenue_yoy_enabled")
        if revenue_yoy_enabled:
            revenue_yoy_range = st.slider("营收增长率范围（%）", -100.0, 500.0, (0.0, 100.0), key="revenue_yoy_range")
            filter_conditions['revenue_yoy'] = {'range': revenue_yoy_range}
        
        profit_yoy_enabled = st.checkbox("启用净利润增长率筛选", key="profit_yoy_enabled")
        if profit_yoy_enabled:
            profit_yoy_range = st.slider("净利润增长率范围（%）", -200.0, 1000.0, (0.0, 100.0), key="profit_yoy_range")
            if profit_yoy_range:
                filter_conditions['net_profit_yoy'] = {'range': profit_yoy_range}
        
        eps_enabled = st.checkbox("启用每股收益筛选", key="eps_enabled")
        if eps_enabled:
            eps_range = st.slider("每股收益范围（元）", -5.0, 10.0, (0.0, 2.0), key="eps_range")
            filter_conditions['eps'] = {'range': eps_range}

# ========== 综合条件 ==========
with tab5:
    st.markdown("#### 🎯 综合条件设置")
    
    # 排除ST股票
    exclude_st = st.checkbox("排除ST股票", value=True, key="exclude_st")
    
    # 排除新股
    exclude_new = st.checkbox("排除新股（上市不足1年）", value=False, key="exclude_new")
    
    # 行业筛选
    if 'industry' in df.columns or 'code_name' in df.columns:
        industries = ['全部']
        if 'industry' in df.columns:
            industries.extend(sorted([str(x) for x in df['industry'].dropna().unique() if pd.notna(x)]))
        industry_filter = st.selectbox("行业筛选", industries, key="industry_filter")
        if industry_filter != '全部':
            filter_conditions['industry'] = {'value': industry_filter}
    
    # 自定义SQL条件
    st.markdown("**自定义SQL条件（高级）**")
    custom_sql = st.text_area(
        "输入SQL WHERE条件（例如: pe < 20 AND pb < 2）",
        key="custom_sql",
        height=100
    )
    if custom_sql:
        filter_conditions['custom_sql'] = {'condition': custom_sql}

# ========== 执行选股 ==========
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    if st.button("🚀 执行选股", type="primary", use_container_width=True):
        st.session_state.run_selection = True

with col2:
    if st.button("🔄 重置条件", use_container_width=True):
        st.session_state.run_selection = False
        st.rerun()

with col3:
    st.caption(f"💡 当前已设置 {len(filter_conditions)} 个筛选条件")

# ========== 应用筛选条件 ==========
if st.session_state.get("run_selection", False):
    display_df = df.copy()
    display_df = clean_duplicate_columns(display_df, keep_first=False)
    
    original_count = len(display_df)
    filter_log = []  # 记录每个筛选条件的过滤效果
    
    # 调试信息：显示设置的筛选条件
    if len(filter_conditions) > 0:
        st.info(f"🔍 已设置 {len(filter_conditions)} 个筛选条件: {list(filter_conditions.keys())}")
        # 显示每个条件的详细值
        with st.expander("📋 筛选条件详情", expanded=False):
            for key, condition in filter_conditions.items():
                st.text(f"  {key}: {condition}")
    else:
        st.warning("⚠️ 未设置任何筛选条件，将显示所有股票")
    
    # 显示数据字段可用性
    with st.expander("📊 数据字段可用性检查", expanded=False):
        st.text(f"总记录数: {len(display_df)}")
        for key in filter_conditions.keys():
            if key in display_df.columns:
                non_null = display_df[key].notna().sum()
                st.text(f"  ✅ {key}: {non_null}/{len(display_df)} 非空 ({non_null/len(display_df)*100:.1f}%)")
            else:
                st.text(f"  ❌ {key}: 字段不存在")
    
    # 应用各个筛选条件（只筛选非空值，空值视为不符合条件）
    for key, condition in filter_conditions.items():
        before_count = len(display_df)
        
        if key == 'pe' and 'pe' in display_df.columns:
            pe_range = condition['range']
            # 只筛选非空值，空值排除
            mask = (display_df['pe'].notna()) & (display_df['pe'] >= pe_range[0]) & (display_df['pe'] <= pe_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"PE筛选 ({pe_range[0]}-{pe_range[1]}): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'pb' and 'pb' in display_df.columns:
            pb_range = condition['range']
            mask = (display_df['pb'].notna()) & (display_df['pb'] >= pb_range[0]) & (display_df['pb'] <= pb_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"PB筛选 ({pb_range[0]}-{pb_range[1]}): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'ps' and 'ps' in display_df.columns:
            ps_range = condition['range']
            mask = (display_df['ps'].notna()) & (display_df['ps'] >= ps_range[0]) & (display_df['ps'] <= ps_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"PS筛选 ({ps_range[0]}-{ps_range[1]}): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'total_mv' and 'total_mv' in display_df.columns:
            mv_range = condition['range']
            mask = (display_df['total_mv'].notna()) & (display_df['total_mv'] >= mv_range[0]) & (display_df['total_mv'] <= mv_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"总市值筛选 ({mv_range[0]/1e8:.0f}-{mv_range[1]/1e8:.0f}亿): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'circ_mv' and 'circ_mv' in display_df.columns:
            circ_mv_range = condition['range']
            mask = (display_df['circ_mv'].notna()) & (display_df['circ_mv'] >= circ_mv_range[0]) & (display_df['circ_mv'] <= circ_mv_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"流通市值筛选 ({circ_mv_range[0]/1e8:.0f}-{circ_mv_range[1]/1e8:.0f}亿): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'price' and 'price' in display_df.columns:
            price_range = condition['range']
            mask = (display_df['price'].notna()) & (display_df['price'] >= price_range[0]) & (display_df['price'] <= price_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"价格筛选 ({price_range[0]}-{price_range[1]}元): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'change_pct' and 'change_pct' in display_df.columns:
            change_range = condition['range']
            mask = (display_df['change_pct'].notna()) & (display_df['change_pct'] >= change_range[0]) & (display_df['change_pct'] <= change_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"涨跌幅筛选 ({change_range[0]}-{change_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'amplitude' and 'amplitude' in display_df.columns:
            amplitude_range = condition['range']
            mask = (display_df['amplitude'].notna()) & (display_df['amplitude'] >= amplitude_range[0]) & (display_df['amplitude'] <= amplitude_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"振幅筛选 ({amplitude_range[0]}-{amplitude_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'turnover_rate' and 'turnover_rate' in display_df.columns:
            turnover_range = condition['range']
            mask = (display_df['turnover_rate'].notna()) & (display_df['turnover_rate'] >= turnover_range[0]) & (display_df['turnover_rate'] <= turnover_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"换手率筛选 ({turnover_range[0]}-{turnover_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'amount' and 'amount' in display_df.columns:
            amount_range = condition['range']
            mask = (display_df['amount'].notna()) & (display_df['amount'] >= amount_range[0]) & (display_df['amount'] <= amount_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"成交额筛选 ({amount_range[0]/1e8:.0f}-{amount_range[1]/1e8:.0f}亿): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'rsi' and 'rsi' in display_df.columns:
            rsi_range = condition['range']
            mask = (display_df['rsi'].notna()) & (display_df['rsi'] >= rsi_range[0]) & (display_df['rsi'] <= rsi_range[1])
            display_df = display_df[mask]
            after_count = len(display_df)
            filter_log.append(f"RSI筛选 ({rsi_range[0]}-{rsi_range[1]}): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'roe' and 'roe' in display_df.columns:
            roe_range = condition['range']
            # 检查数据可用性
            non_null_count = display_df['roe'].notna().sum()
            if non_null_count == 0:
                filter_log.append(f"ROE筛选 ({roe_range[0]}-{roe_range[1]}%): ⚠️ 数据全为空，无法筛选")
                # 如果数据全为空，排除所有记录
                display_df = display_df[display_df['roe'].isna()]  # 这会排除所有记录
                after_count = len(display_df)
            else:
                mask = (display_df['roe'].notna()) & (display_df['roe'] >= roe_range[0]) & (display_df['roe'] <= roe_range[1])
                display_df = display_df[mask]
                after_count = len(display_df)
                filter_log.append(f"ROE筛选 ({roe_range[0]}-{roe_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条，可用数据: {non_null_count} 条)")
        
        elif key == 'roa' and 'roa' in display_df.columns:
            roa_range = condition['range']
            # 检查数据可用性
            non_null_count = display_df['roa'].notna().sum()
            if non_null_count == 0:
                filter_log.append(f"ROA筛选 ({roa_range[0]}-{roa_range[1]}%): ⚠️ 数据全为空，无法筛选")
                # 如果数据全为空，排除所有记录
                display_df = display_df[display_df['roa'].isna()]  # 这会排除所有记录
                after_count = len(display_df)
            else:
                mask = (display_df['roa'].notna()) & (display_df['roa'] >= roa_range[0]) & (display_df['roa'] <= roa_range[1])
                display_df = display_df[mask]
                after_count = len(display_df)
                filter_log.append(f"ROA筛选 ({roa_range[0]}-{roa_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条，可用数据: {non_null_count} 条)")
        
        elif key == 'gross_profit_margin' and 'gross_profit_margin' in display_df.columns:
            margin_range = condition['range']
            # 检查数据可用性
            non_null_count = display_df['gross_profit_margin'].notna().sum()
            if non_null_count == 0:
                filter_log.append(f"毛利率筛选 ({margin_range[0]}-{margin_range[1]}%): ⚠️ 数据全为空，无法筛选")
                # 如果数据全为空，排除所有记录
                display_df = display_df[display_df['gross_profit_margin'].isna()]  # 这会排除所有记录
                after_count = len(display_df)
            else:
                mask = (display_df['gross_profit_margin'].notna()) & (display_df['gross_profit_margin'] >= margin_range[0]) & (display_df['gross_profit_margin'] <= margin_range[1])
                display_df = display_df[mask]
                after_count = len(display_df)
                filter_log.append(f"毛利率筛选 ({margin_range[0]}-{margin_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条，可用数据: {non_null_count} 条)")
        
        elif key == 'revenue_yoy' and 'revenue_yoy' in display_df.columns:
            revenue_yoy_range = condition['range']
            # 检查数据可用性
            non_null_count = display_df['revenue_yoy'].notna().sum()
            if non_null_count == 0:
                filter_log.append(f"营收增长率筛选 ({revenue_yoy_range[0]}-{revenue_yoy_range[1]}%): ⚠️ 数据全为空，无法筛选")
                # 如果数据全为空，排除所有记录
                display_df = display_df[display_df['revenue_yoy'].isna()]  # 这会排除所有记录
                after_count = len(display_df)
            else:
                mask = (display_df['revenue_yoy'].notna()) & (display_df['revenue_yoy'] >= revenue_yoy_range[0]) & (display_df['revenue_yoy'] <= revenue_yoy_range[1])
                display_df = display_df[mask]
                after_count = len(display_df)
                filter_log.append(f"营收增长率筛选 ({revenue_yoy_range[0]}-{revenue_yoy_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条，可用数据: {non_null_count} 条)")
        
        elif key == 'net_profit_yoy' and 'net_profit_yoy' in display_df.columns:
            profit_yoy_range = condition['range']
            # 检查数据可用性
            non_null_count = display_df['net_profit_yoy'].notna().sum()
            if non_null_count == 0:
                filter_log.append(f"净利润增长率筛选 ({profit_yoy_range[0]}-{profit_yoy_range[1]}%): ⚠️ 数据全为空，无法筛选")
                # 如果数据全为空，排除所有记录
                display_df = display_df[display_df['net_profit_yoy'].isna()]  # 这会排除所有记录
                after_count = len(display_df)
            else:
                mask = (display_df['net_profit_yoy'].notna()) & (display_df['net_profit_yoy'] >= profit_yoy_range[0]) & (display_df['net_profit_yoy'] <= profit_yoy_range[1])
                display_df = display_df[mask]
                after_count = len(display_df)
                filter_log.append(f"净利润增长率筛选 ({profit_yoy_range[0]}-{profit_yoy_range[1]}%): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条，可用数据: {non_null_count} 条)")
        
        elif key == 'eps' and 'eps' in display_df.columns:
            eps_range = condition['range']
            # 检查数据可用性
            non_null_count = display_df['eps'].notna().sum()
            if non_null_count == 0:
                filter_log.append(f"每股收益筛选 ({eps_range[0]}-{eps_range[1]}元): ⚠️ 数据全为空，无法筛选")
                # 如果数据全为空，排除所有记录
                display_df = display_df[display_df['eps'].isna()]  # 这会排除所有记录
                after_count = len(display_df)
            else:
                mask = (display_df['eps'].notna()) & (display_df['eps'] >= eps_range[0]) & (display_df['eps'] <= eps_range[1])
                display_df = display_df[mask]
                after_count = len(display_df)
                filter_log.append(f"每股收益筛选 ({eps_range[0]}-{eps_range[1]}元): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条，可用数据: {non_null_count} 条)")
        
        elif key == 'industry' and 'industry' in display_df.columns:
            industry_value = condition['value']
            before_count = len(display_df)
            display_df = display_df[display_df['industry'] == industry_value]
            after_count = len(display_df)
            filter_log.append(f"行业筛选 ({industry_value}): {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
        
        elif key == 'custom_sql':
            try:
                custom_condition = condition['condition']
                before_count = len(display_df)
                display_df = display_df.query(custom_condition)
                after_count = len(display_df)
                filter_log.append(f"自定义SQL筛选: {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
            except Exception as e:
                st.warning(f"⚠️ 自定义SQL条件错误: {e}")
    
    # 排除ST股票
    if exclude_st:
        before_count = len(display_df)
        if 'stock_name' in display_df.columns:
            display_df = display_df[~display_df['stock_name'].astype(str).str.contains('ST', case=False, na=False)]
        elif 'code_name' in display_df.columns:
            display_df = display_df[~display_df['code_name'].astype(str).str.contains('ST', case=False, na=False)]
        after_count = len(display_df)
        filter_log.append(f"排除ST股票: {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
    
    # 排除新股
    if exclude_new:
        before_count = len(display_df)
        if 'ipoDate' in display_df.columns:
            cutoff_date = datetime.now() - timedelta(days=365)
            display_df = display_df[
                pd.to_datetime(display_df['ipoDate'], errors='coerce') < cutoff_date
            ]
        after_count = len(display_df)
        filter_log.append(f"排除新股: {before_count} → {after_count} (过滤掉 {before_count - after_count} 条)")
    
    # 显示结果
    st.markdown("---")
    st.subheader("📊 选股结果")
    
    result_count = len(display_df)
    st.success(f"✅ 筛选完成: 从 {original_count:,} 只股票中筛选出 {result_count:,} 只符合条件的股票")
    
    # 显示筛选日志
    if filter_log:
        with st.expander("🔍 筛选过程详情", expanded=False):
            for log in filter_log:
                st.text(log)
    
    if result_count > 0:
        # 显示统计信息
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("筛选结果", f"{result_count:,} 只")
        with col2:
            if 'pe' in display_df.columns:
                avg_pe = display_df['pe'].mean()
                st.metric("平均PE", f"{avg_pe:.2f}" if not pd.isna(avg_pe) else "N/A")
        with col3:
            if 'pb' in display_df.columns:
                avg_pb = display_df['pb'].mean()
                st.metric("平均PB", f"{avg_pb:.2f}" if not pd.isna(avg_pb) else "N/A")
        with col4:
            if 'total_mv' in display_df.columns:
                total_mcap = display_df['total_mv'].sum() / 1e12
                st.metric("总市值", f"{total_mcap:.2f}万亿" if total_mcap > 0 else "N/A")
        
        # 选择要显示的列
        display_cols = ['stock_code', 'stock_name']
        for col in ['price', 'change_pct', 'pe', 'pb', 'ps', 'roe', 'total_mv', 'turnover_rate', 'rsi', 'macd']:
            if col in display_df.columns:
                display_cols.append(col)
        
        display_cols = [col for col in display_cols if col in display_df.columns]
        
        # 显示数据表格
        st.dataframe(
            display_df[display_cols],
            use_container_width=True,
            height=600,
            hide_index=True
        )
        
        # 导出功能
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            csv_data = display_df[display_cols].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 导出为CSV",
                csv_data.encode("utf-8-sig"),
                file_name=f"stock_selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.warning("⚠️ 没有找到符合条件的股票，请调整筛选条件")

