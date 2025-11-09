"""
智能选股（简化版）
基于data_engine数据库 + LLM的智能选股系统
"""

import os
import streamlit as st
import pandas as pd
from pathlib import Path
import sys
from typing import List, Dict
from tradingagents.utils.logging_init import get_logger

logger = get_logger('web.smart_selection')

# 添加项目根目录及 data_engine 到路径
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
data_engine_root = project_root / "data_engine"
if str(data_engine_root) not in sys.path:
    sys.path.insert(0, str(data_engine_root))

from data_engine.config import DB_URL
from data_engine.utils.db_utils import get_engine
from sqlalchemy import text, inspect

st.set_page_config(
    page_title="智能选股_简化版",
    page_icon="🧠",
    layout="wide"
)

st.markdown(
    """
    <style>
    .hero-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 28px 32px;
        border-radius: 18px;
        display: flex;
        align-items: center;
        gap: 24px;
        box-shadow: 0 18px 36px rgba(102, 126, 234, 0.25);
        margin-bottom: 24px;
    }
    .hero-card .hero-icon {
        font-size: 42px;
        background: rgba(255, 255, 255, 0.2);
        width: 72px;
        height: 72px;
        border-radius: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .hero-card h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
    }
    .hero-card p {
        margin: 4px 0 0 0;
        font-size: 15px;
        opacity: 0.92;
    }
    </style>
    <div class="hero-card">
        <div class="hero-icon">🚀</div>
        <div>
            <h1>智能选股（基于本地基础资料 + LLM）</h1>
            <p>结合本地行情与财报数据，快速筛选并调用 LLM 生成候选组合建议。</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 从数据库加载数据（使用MySQL或SQLite，根据配置）
df = None
try:
    engine = get_engine(DB_URL)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    with engine.connect() as conn:
        view_exists = 'vw_stock_basic_info_unique' in tables
        columns = "ts_code, code_name"
        has_industry_table = 'stock_basic_info_extra' in tables
        query_parts = ["SELECT", columns]
        query_parts.append("FROM vw_stock_basic_info_unique" if view_exists else "FROM stock_basic_info")
        basic_query = " ".join(query_parts)
        df_basic = pd.read_sql_query(basic_query, conn)
        df_basic = df_basic.rename(columns={"code_name": "name"})
        if 'ts_code' not in df_basic.columns:
            st.error("stock_basic_info 缺少 ts_code 字段，无法继续")
            st.stop()
        before_dedup = len(df_basic)
        df_basic = df_basic.drop_duplicates(subset=["ts_code"], keep="first")
        if len(df_basic) < before_dedup:
            logger.info(
                "基础信息去重: %s -> %s", before_dedup, len(df_basic)
            )
        # 获取行业数据（如果存在）
        df_industry = None
        if 'stock_industry_classified' in tables:
            industry_query = text(
                """
                SELECT ts_code, industry
                FROM stock_industry_classified
                WHERE industry IS NOT NULL
                """
            )
            df_industry = pd.read_sql_query(industry_query, conn)
        elif 'stock_basic_info_extra' in tables:
            df_industry = pd.read_sql_query("SELECT ts_code, industry FROM stock_basic_info_extra", conn)
        if df_industry is not None:
            df_industry = df_industry.drop_duplicates(subset=['ts_code'], keep='first')
            df_basic = df_basic.merge(df_industry, on='ts_code', how='left')
        latest_date = conn.execute(text("SELECT MAX(trade_date) FROM stock_market_daily")).scalar()
        if latest_date:
            query_market = text(
                """
                    SELECT 
                        m.ts_code,
                        m.close AS price,
                        m.volume,
                        m.amount AS turnover,
                        m.turnover_rate,
                        m.pct_chg AS change_pct,
                        m.peTTM AS pe,
                        m.pbMRQ AS pb,
                        m.psTTM AS ps
                    FROM stock_market_daily m
                    WHERE m.trade_date = :latest_date
                """
            )
            df_market = pd.read_sql_query(query_market, conn, params={"latest_date": latest_date})
            if 'ts_code' in df_market.columns:
                df_market = df_market.drop_duplicates(subset=["ts_code"], keep="first")
            if 'stock_financials' in tables:
                query_fin = text(
                    """
                        SELECT 
                            f.ts_code,
                            f.total_mv,
                            f.circ_mv
                        FROM stock_financials f
                        WHERE f.trade_date = (
                            SELECT MAX(trade_date) FROM stock_financials
                        )
                    """
                )
                df_fin = pd.read_sql_query(query_fin, conn)
                if 'ts_code' in df_fin.columns:
                    df_fin = df_fin.drop_duplicates(subset=["ts_code"], keep="first")
            else:
                df_fin = None
        else:
            latest_date = None
            df_market = None
            df_fin = None
        if df_basic is not None and latest_date:
            df = df_basic.merge(df_market, on='ts_code', how='left')
            if df_fin is not None:
                df = df.merge(df_fin, on='ts_code', how='left')
            rename_map = {
                'ts_code': 'code',
                'name': 'name',
                'price': 'price',
                'total_mv': 'market_cap',
                'circ_mv': 'float_cap',
                'volume': 'volume',
                'turnover': 'turnover',
                'turnover_rate': 'turnover_rate',
                'change_pct': 'change_pct',
                'peTTM': 'pe',
                'pbMRQ': 'pb',
                'psTTM': 'ps',
            }
            df = df.rename(columns=rename_map)
            if 'market_cap' not in df.columns:
                df['market_cap'] = None
            if 'turnover_rate' not in df.columns:
                df['turnover_rate'] = None
            if 'pe' not in df.columns:
                df['pe'] = None
            if 'pb' not in df.columns:
                df['pb'] = None
            numeric_cols = [
                "market_cap",
                "float_cap",
                "price",
                "turnover",
                "turnover_rate",
                "pe",
                "pb",
                "volume",
                "ps",
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if {"market_cap", "turnover", "turnover_rate"}.issubset(df.columns):
                fallback_mask = (
                    (df["market_cap"].isna() | (df["market_cap"] <= 0))
                    & df["turnover"].notna()
                    & (df["turnover"] > 0)
                    & df["turnover_rate"].notna()
                    & (df["turnover_rate"] > 0)
                )
                if fallback_mask.any():
                    df.loc[fallback_mask, "market_cap"] = (
                        df.loc[fallback_mask, "turnover"] * 10000
                        / (df.loc[fallback_mask, "turnover_rate"] / 100)
                    )
                    logger.info(
                        "基于成交额/换手率估算市值: %s 只股票",
                        int(fallback_mask.sum()),
                    )
            if "market_cap" in df.columns:
                missing_caps = df["market_cap"].isna() | (df["market_cap"] <= 0)
                if missing_caps.any():
                    st.info(
                        f"ℹ️ 当前仍有 {int(missing_caps.sum())} 只股票缺少可靠市值数据，筛选时会忽略这些股票。"
                    )
            st.success(f"✅ 已加载 {len(df)} 条股票数据（最新日期: {latest_date}）")
        elif df_basic is not None and latest_date is None:
            st.error("❌ 数据库中没有市场数据，请先下载数据")
            st.stop()
        elif df_basic is not None:
            df = df_basic.rename(columns={'ts_code': 'code', 'name': 'name'})
            df['price'] = None
            df['market_cap'] = None
            df['pe'] = None
            df['pb'] = None
            st.warning(f"⚠️ 只有基础信息，共 {len(df)} 条，建议下载完整数据")
        else:
            st.error("❌ 数据库表结构不正确，请重新下载数据")
            st.stop()
except Exception as e:
    st.error(f"❌ 读取数据失败: {e}")
    import traceback
    with st.expander("查看详细错误"):
        st.code(traceback.format_exc())
    st.stop()

if df is None or df.empty:
    st.error("❌ 未能加载数据，请检查数据库")
    st.stop()

st.markdown("---")

# LLM配置
st.subheader("🔧 LLM配置")
col1, col2 = st.columns(2)

with col1:
    # 从环境变量获取默认API密钥
    default_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    api_key = st.text_input(
        "LLM API Key",
        value=default_key,
        type="password",
        help="优先使用此处填写的 Key，如果为空则使用环境变量"
    )

with col2:
    provider = st.selectbox(
        "模型提供商",
        ["dashscope", "openai", "anthropic"],
        help="选择LLM提供商"
    )

# 策略配置
st.subheader("📊 策略配置")
col1, col2 = st.columns(2)

with col1:
    strategy = st.selectbox(
        "预设策略",
        ["保守", "平衡", "激进", "价值", "成长"],
        index=1,
        help="选择投资策略类型"
    )

with col2:
    topk = st.slider("返回候选数量", 5, 50, 20, help="最多返回的股票数量")

# 筛选条件
st.subheader("🔍 筛选条件")
col1, col2, col3 = st.columns(3)

with col1:
    max_weight = st.slider("单票上限(%)", 5, 20, 10, help="单个股票在组合中的最大权重")

with col2:
    min_mcap = st.number_input(
        "最小总市值(亿元)",
        value=50.0,
        min_value=0.0,
        step=10.0,
        help="过滤掉市值过小的股票"
    )

with col3:
    allow_st = st.checkbox("包含ST股票？", value=False, help="是否包含ST、*ST等特殊处理的股票")

price_values = df["price"].dropna()
if not price_values.empty:
    min_price = float(price_values.min())
    max_price = float(price_values.max())
    if min_price == max_price:
        price_range = (min_price, max_price)
    else:
        price_step = max((max_price - min_price) / 100, 0.01)
        price_range = st.slider(
            "价格区间(元)",
            min_value=round(min_price, 2),
            max_value=round(max_price, 2),
            value=(round(min_price, 2), round(min_price + (max_price - min_price) * 0.4, 2)),
            step=round(price_step, 2),
        )
else:
    price_range = None

change_values = df["change_pct"].dropna()
if not change_values.empty:
    min_change = float(change_values.min())
    max_change = float(change_values.max())
    if min_change == max_change:
        change_range = (min_change, max_change)
    else:
        change_range = st.slider(
            "涨跌幅区间(%)",
            min_value=round(min_change, 2),
            max_value=round(max_change, 2),
            value=(round(max(min_change, -9.0), 2), round(min(max_change, 9.0), 2)),
            step=0.1,
            help="过滤当日涨跌幅",
        )
else:
    change_range = None

industry_values = []
if "industry" in df.columns:
    industry_values = df["industry"].dropna().unique().tolist()
    industry_values = sorted([i for i in industry_values if isinstance(i, str) and i.strip()])
selected_industries = []
if industry_values:
    selected_industries = st.multiselect(
        "行业筛选",
        options=industry_values,
        help="只保留所选行业的股票",
    )

pe_values = df["pe"].dropna()
if not pe_values.empty:
    min_pe = float(max(pe_values.min(), 0))
    max_pe = float(min(pe_values.quantile(0.99), 200))
    if min_pe < max_pe:
        pe_range = st.slider(
            "PE区间",
            min_value=round(min_pe, 1),
            max_value=round(max_pe, 1),
            value=(round(min(min_pe, 10.0), 1), round(min(max_pe, 40.0), 1)),
            step=0.1,
        )
    else:
        pe_range = None
else:
    pe_range = None

st.markdown("---")

# 数据预处理函数
def simple_score(row) -> float:
    """
    简单的评分函数
    实际应该结合更多因子（PE、PB、ROE等）
    """
    price = row.get("price", 0) or 0
    mcap = row.get("market_cap", 0) or 0
    
    base = 0
    if price > 0:
        base += 1
    if mcap > min_mcap * 1e8:  # 转换为元
        base += 1
    
    return float(base)


def llm_rerank(candidates: pd.DataFrame, api_key: str, provider: str, strategy: str, topk: int) -> List[Dict]:
    """
    LLM重新排序候选股票
    
    使用真实LLM API进行智能分析
    """
    # 尝试使用LLM分析
    if api_key:
        try:
            from web.utils.stock_llm_analyzer import StockLLMAnalyzer
            analyzer = StockLLMAnalyzer(api_key=api_key, provider=provider)
            results = analyzer.analyze_stocks(candidates, strategy, topk)
            return results
        except Exception as e:
            st.warning(f"⚠️ LLM分析失败，使用简单评分排序: {e}")
    
    # 降级方案：简单评分排序
    if not api_key:
        st.warning("⚠️ 未配置LLM API Key，使用简单评分排序")
    
    results = []
    for _, r in candidates.iterrows():
        # 获取code（兼容多种字段名）
        code = r.get("code") or r.get("ts_code") or r.get("stock_code") or "N/A"
        
        results.append({
            "code": code,
            "name": r.get("name", "N/A"),
            "price": f"￥{r.get('price', 0):.2f}" if pd.notna(r.get("price")) and r.get("price", 0) > 0 else "N/A",
            "market_cap": f"{r.get('market_cap', 0) / 1e8:.2f}亿" if pd.notna(r.get("market_cap")) and r.get("market_cap", 0) > 0 else "N/A",
            "pe": f"{r.get('pe', 0):.2f}" if pd.notna(r.get("pe")) and r.get("pe", 0) > 0 else "N/A",
            "pb": f"{r.get('pb', 0):.2f}" if pd.notna(r.get("pb")) and r.get("pb", 0) > 0 else "N/A",
            "score": r.get("score", 0),
            "reason": f"{strategy}策略：基于市值和价格筛选"
        })
    
    # 按评分排序
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:topk]


# 执行选股
if st.button("🚀 生成选股建议", type="primary", use_container_width=True):
    if not api_key:
        st.warning("⚠️ 建议配置LLM API Key以获得更好的选股结果")
    
    # 数据处理
    with st.spinner("🔄 正在处理数据..."):
        work = df.copy()
        filters_applied = []

        # 过滤ST股票
        if not allow_st:
            if "name" in work.columns:
                before = len(work)
                work = work[~work["name"].astype(str).str.contains("ST", case=False, na=False)]
                filters_applied.append(f"剔除ST: {before}→{len(work)}")
        
        # 确保字段名正确（适配旧代码）
        if "code" not in work.columns and "ts_code" in work.columns:
            work["code"] = work["ts_code"]
        if "code" not in work.columns and "stock_code" in work.columns:
            work["code"] = work["stock_code"]
        
        # 市值筛选
        if "market_cap" in work.columns:
            work["market_cap"] = pd.to_numeric(work["market_cap"], errors="coerce").fillna(0)
            if {"turnover", "turnover_rate"}.issubset(work.columns):
                turnover_numeric = pd.to_numeric(work["turnover"], errors="coerce")
                turnover_rate_numeric = pd.to_numeric(work["turnover_rate"], errors="coerce")
                fallback_mask = (
                    (work["market_cap"] <= 0)
                    & turnover_numeric.notna()
                    & (turnover_numeric > 0)
                    & turnover_rate_numeric.notna()
                    & (turnover_rate_numeric > 0)
                )
                if fallback_mask.any():
                    work.loc[fallback_mask, "market_cap"] = (
                        turnover_numeric[fallback_mask] * 10000
                        / (turnover_rate_numeric[fallback_mask] / 100)
                    )
                    filters_applied.append(
                        f"换手率估算市值修复 {fallback_mask.sum()} 只"
                    )
            before = len(work)
            work = work[work["market_cap"] >= min_mcap * 1e8]
            filters_applied.append(f"市值≥{min_mcap}亿: {before}→{len(work)}")
            if work.empty:
                st.warning("⚠️ 市值筛选后没有结果，建议放宽阈值或等待市值数据补全")
                st.stop()

        # 价格区间
        if price_range and price_range[0] < price_range[1] and "price" in work.columns:
            lower, upper = price_range
            before = len(work)
            work = work[(work["price"].notna()) & (work["price"] >= lower) & (work["price"] <= upper)]
            filters_applied.append(f"价格[{lower}~{upper}]元: {before}→{len(work)}")

        # 涨跌幅区间
        if change_range and change_range[0] < change_range[1] and "change_pct" in work.columns:
            lower, upper = change_range
            before = len(work)
            work = work[(work["change_pct"].notna()) & (work["change_pct"] >= lower) & (work["change_pct"] <= upper)]
            filters_applied.append(f"涨跌幅[{lower}%~{upper}%]: {before}→{len(work)}")

        # 行业筛选
        if selected_industries:
            before = len(work)
            work = work[work["industry"].isin(selected_industries)]
            filters_applied.append(f"行业 {len(selected_industries)} 项: {before}→{len(work)}")

        # PE区间
        if pe_range and pe_range[0] < pe_range[1] and "pe" in work.columns:
            lower, upper = pe_range
            before = len(work)
            work = work[(work["pe"].notna()) & (work["pe"] >= lower) & (work["pe"] <= upper)]
            filters_applied.append(f"PE[{lower}~{upper}]: {before}→{len(work)}")
        
        # 计算评分（包含财务指标）
        def enhanced_score(row) -> float:
            """增强评分函数，包含PE、PB等财务指标"""
            base_score = simple_score(row)
            
            # PE评分（越低越好，但在合理范围内）
            if pd.notna(row.get("pe")) and row.get("pe", 0) > 0:
                pe = row.get("pe")
                if 0 < pe < 30:  # 合理PE范围
                    base_score += 1
                elif pe < 50:
                    base_score += 0.5
            
            # PB评分（越低越好，但在合理范围内）
            if pd.notna(row.get("pb")) and row.get("pb", 0) > 0:
                pb = row.get("pb")
                if 0 < pb < 3:  # 合理PB范围
                    base_score += 1
                elif pb < 5:
                    base_score += 0.5
            
            return base_score
        
        work["score"] = work.apply(enhanced_score, axis=1)
        
        # 过滤掉评分为0的股票
        before = len(work)
        work = work[work["score"] > 0]
        filters_applied.append(f"评分>0: {before}→{len(work)}")
        
        if len(work) == 0:
            st.error("❌ 没有符合条件的股票，请调整筛选条件")
            st.stop()
        
        st.info(f"📊 符合筛选条件的股票: {len(work)} 只 | " + "；".join(filters_applied))
        
        # LLM重新排序
        with st.spinner("🤖 LLM智能排序中..."):
            # 准备传递给LLM的数据（包含所有可用列）
            columns_for_llm = ["code", "name", "price", "market_cap", "score"]
            if "pe" in work.columns:
                columns_for_llm.append("pe")
            if "pb" in work.columns:
                columns_for_llm.append("pb")
            if "ps" in work.columns:
                columns_for_llm.append("ps")
            if "industry" in work.columns:
                columns_for_llm.append("industry")
            
            ranked = llm_rerank(
                work[columns_for_llm], # Use columns_for_llm here
                api_key,
                provider,
                strategy,
                topk  # 传递topk参数
            )
        
        if ranked:
            st.success(f"✅ 已生成 {len(ranked)} 条候选建议")
            
            # 保存选股结果
            try:
                from web.utils.stock_selection_storage import get_storage
                storage = get_storage()
                selection_id = storage.save_selection(
                    results=ranked,
                    strategy=strategy,
                    filter_conditions={
                        "max_weight": max_weight,
                        "min_mcap": min_mcap,
                        "allow_st": allow_st,
                        "total_candidates": len(work),
                        "provider": provider
                    },
                    metadata={
                        "topk": topk,
                        "api_key_used": bool(api_key)
                    }
                )
                st.session_state.last_selection_id = selection_id
            except Exception as e:
                logger.warning(f"保存选股结果失败: {e}")
            
            # 显示结果
            st.markdown("---")
            st.subheader("📋 选股结果")
            
            # 转换为DataFrame显示
            result_df = pd.DataFrame(ranked)
            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True
            )
            
            # 统计信息
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("候选数量", len(ranked))
            with col2:
                avg_score = result_df["score"].mean() if "score" in result_df.columns else 0
                st.metric("平均评分", f"{avg_score:.2f}")
            with col3:
                total_weight = len(ranked) * (max_weight / 100)
                st.metric("预计组合权重", f"{min(total_weight, 1.0)*100:.1f}%")
            
            # 导出和保存功能
            st.markdown("---")
            st.subheader("💾 导出结果")
            
            col1, col2 = st.columns(2)
            with col1:
                csv_data = result_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 导出为 CSV",
                    csv_data.encode("utf-8-sig"),
                    file_name=f"stock_selection_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col2:
                if st.session_state.get("last_selection_id"):
                    st.success(f"✅ 结果已自动保存（ID: {st.session_state.last_selection_id[:20]}...）")
        else:
            st.error("❌ 未能生成选股建议")

# 说明信息
st.markdown("---")
with st.expander("ℹ️ 使用说明"):
    st.markdown("""
    ### 📖 功能说明
    
    1. **数据准备**: 需要先下载A股基础资料（见「数据中心 - 基础资料」页面）
    
    2. **筛选条件**:
       - **单票上限**: 控制单个股票在组合中的最大权重
       - **最小市值**: 过滤掉市值过小的股票（降低风险）
       - **ST股票**: 可选择是否包含特殊处理的股票
    
    3. **策略类型**:
       - **保守**: 侧重低估值、稳定增长
       - **平衡**: 兼顾成长性和价值
       - **激进**: 侧重高成长、高弹性
       - **价值**: 侧重低PE、低PB
       - **成长**: 侧重高ROE、高增长
    
    4. **LLM增强**: 
       - 配置LLM API Key可获得更智能的分析结果
       - 目前使用简单评分，后续会接入真实LLM分析
    
    ### ⚠️ 注意事项
    
    - 本功能基于简单的技术指标，不构成投资建议
    - 请结合其他分析工具做出投资决策
    - 投资有风险，入市需谨慎
    """)

