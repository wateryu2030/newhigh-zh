import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from tradingagents.dataflows.data_loader import get_price_df
from tradingagents.factors.price_volume import MomentumFactor, VolumeFactor
from tradingagents.llm_alpha.scorer import LLMScorer
from tradingagents.selection.scorer import calculate_alpha
from tradingagents.portfolio.optimizer import PortfolioOptimizer
from tradingagents.dataflows.stock_search import get_searcher

st.set_page_config(page_title="智能选股_量化版", page_icon="🧠")
st.title("🧠 智能选股系统（量化分析版）")

# 参数
colA, colB, colC = st.columns(3)
with colA:
    tickers_input = st.text_input("股票列表（逗号分隔）", "000001,600519,002701")
with colB:
    days = st.number_input("回看天数", min_value=20, max_value=240, value=60)
with colC:
    start_compute = st.button("生成Alpha与权重", type="primary")

llm_uploader = st.file_uploader("上传LLM事件CSV（列：ticker,event_text）", type=['csv'])
industry_uploader = st.file_uploader("上传行业映射CSV（列：ticker,industry）", type=['csv'])
prevw_uploader = st.file_uploader("上传上一期权重CSV（列：ticker,weight）", type=['csv'])
turnover_cap = st.slider("换手上限（总换手比例）", min_value=0.0, max_value=1.0, value=0.3, step=0.05)
industry_cap = st.slider("行业上限（组合占比）", min_value=0.1, max_value=1.0, value=0.3, step=0.05)
max_weight = st.slider("单票上限（组合占比）", min_value=0.05, max_value=0.5, value=0.2, step=0.05)

st.markdown("---")

if start_compute:
    end = datetime.now()
    start = (end - timedelta(days=int(days))).strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")
    tickers = [t.strip() for t in tickers_input.split(',') if t.strip()]

    rows = []
    prices_latest = {}

    for t in tickers:
        df = get_price_df(t, start, end_s)
        if df.empty:
            continue
        g = df.reset_index().rename(columns={'date': 'date'})
        mom = MomentumFactor().calculate(g)
        volf = VolumeFactor().calculate(g)
        rows.append({'ticker': t,
                     'momentum': mom.iloc[-1] if len(mom) else 0.0,
                     'volume_chg': volf.iloc[-1] if len(volf) else 0.0})
        prices_latest[t] = float(g['close'].iloc[-1]) if 'close' in g.columns else float(df['close'].iloc[-1])

    if not rows:
        st.error("未获取到任何标的数据，请检查代码或数据源配置")
    else:
        factors_df = pd.DataFrame(rows).set_index('ticker')
        factors_df['score'] = factors_df['momentum'].fillna(0.0)

        # 处理LLM事件
        if llm_uploader is not None:
            llm_df = pd.read_csv(llm_uploader)
            if {'ticker', 'event_text'}.issubset(llm_df.columns):
                scored = LLMScorer(llm_df).score()
                st.subheader("LLM 事件打分（含rationale/event_type）")
                st.dataframe(scored[['ticker', 'event_text', 'score', 'rationale', 'event_type']], use_container_width=True)
                llm_scores = scored.groupby('ticker')['score'].mean().reindex(factors_df.index).fillna(0.0).to_frame('score')
            else:
                st.warning("LLM CSV 需包含列：ticker,event_text；已忽略LLM打分。")
                llm_scores = pd.DataFrame({'score': 0.0}, index=factors_df.index)
        else:
            llm_scores = pd.DataFrame({'score': 0.0}, index=factors_df.index)

        sector_df = pd.DataFrame({'score': factors_df['volume_chg'].fillna(0.0)}, index=factors_df.index)

        alpha = calculate_alpha(factors_df[['score']], llm_scores[['score']], sector_df[['score']])
        st.subheader("Alpha")
        st.dataframe(alpha.sort_values(ascending=False).to_frame('alpha'))

        # 行业映射
        industry_series = None
        if industry_uploader is not None:
            idf = pd.read_csv(industry_uploader)
            if {'ticker', 'industry'}.issubset(idf.columns):
                industry_series = idf.set_index('ticker')['industry'].reindex(factors_df.index)
            else:
                st.warning("行业CSV需包含列：ticker,industry；尝试从数据库自动获取...")
        
        # 如果未上传行业文件，尝试从数据库自动获取
        if industry_series is None or (industry_series.isna().all() if industry_series is not None else True):
            try:
                searcher = get_searcher()
                industry_dict = {}
                for ticker in factors_df.index:
                    info = searcher.get_info(ticker)
                    if info and info.get('industry'):
                        industry_dict[ticker] = info['industry']
                if industry_dict:
                    industry_series = pd.Series(industry_dict, index=factors_df.index)
                    st.info(f"✅ 自动获取到 {len(industry_dict)} 只股票的行业信息")
            except Exception as e:
                st.debug(f"自动获取行业信息失败: {e}")

        # 上一期权重
        prev_weights = None
        if prevw_uploader is not None:
            pw = pd.read_csv(prevw_uploader)
            if {'ticker', 'weight'}.issubset(pw.columns):
                prev_weights = pw.set_index('ticker')['weight'].reindex(factors_df.index).fillna(0.0)
            else:
                st.warning("上一期权重CSV需包含列：ticker,weight；将忽略换手约束。")

        # 计算权重
        vol_proxy = (factors_df['volume_chg'].abs() + 1e-6).rename('vol')
        opt = PortfolioOptimizer(max_weight=max_weight, industry_cap=industry_cap, turnover_cap=turnover_cap)
        weights = opt.optimize(alpha, vol_proxy, correlation_matrix=None, industry=industry_series, prev_weights=prev_weights)
        weights_df = weights.sort_values(ascending=False).to_frame('weight')
        st.subheader("目标权重（含行业/换手约束）")
        st.dataframe(weights_df)

        # 预估持仓成本
        total_capital = st.number_input("模拟资金(¥)", min_value=10000.0, value=100000.0, step=10000.0)
        if prices_latest:
            pos = []
            for t, w in weights.items():
                if w <= 0:
                    continue
                price = prices_latest.get(t, 0.0)
                qty = int((total_capital * float(w)) / price) if price > 0 else 0
                ind = industry_series[t] if industry_series is not None and t in industry_series.index and pd.notna(industry_series[t]) else ''
                pos.append({'ticker': t, 'weight': float(w), 'price': price, 'qty': qty, 'industry': ind})
            st.subheader("拟建仓明细")
            st.dataframe(pd.DataFrame(pos))

# 因子图表已在主流程中展示
