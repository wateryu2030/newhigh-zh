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

# 添加项目根目录到路径（使用resolve()确保绝对路径）
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="智能选股_简化版",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 智能选股（基于本地基础资料 + LLM）")

# 从数据库加载数据（使用MySQL或SQLite，根据配置）
df = None
try:
    # 使用MySQL或SQLite（根据配置）
    sys.path.insert(0, str(project_root / "data_engine"))
    from config import DB_URL
    from utils.db_utils import get_engine
    from sqlalchemy import text, inspect
    
    engine = get_engine(DB_URL)
    
    # 检查表
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'stock_basic_info' in tables and 'stock_market_daily' in tables:
        # 读取基础信息
        df_basic = pd.read_sql_query("SELECT * FROM stock_basic_info", engine)
        
        # 获取最新的交易日期
        with engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(trade_date) FROM stock_market_daily"))
            latest_date = result.fetchone()[0]
        
        if latest_date:
            # 读取最新日期的市场数据
            query_market = f"""
                SELECT 
                    m.ts_code,
                    m.close as price,
                    m.volume,
                    m.amount as turnover,
                    m.pct_chg as change_pct,
                    m.peTTM as pe,
                    m.pbMRQ as pb,
                    m.psTTM as ps
                FROM stock_market_daily m
                WHERE m.trade_date = '{latest_date}'
            """
            df_market = pd.read_sql_query(query_market, conn)
            
            # 读取财务数据（如果有）
            if 'stock_financials' in tables:
                query_fin = f"""
                    SELECT 
                        f.ts_code,
                        f.total_mv,
                        f.circ_mv
                    FROM stock_financials f
                    WHERE f.trade_date = (
                        SELECT MAX(trade_date) FROM stock_financials
                    )
                """
                df_fin = pd.read_sql_query(query_fin, conn)
                
                # 合并数据
                df = df_basic.merge(df_market, on='ts_code', how='left')
                df = df.merge(df_fin, on='ts_code', how='left')
            else:
                # 合并市场数据
                df = df_basic.merge(df_market, on='ts_code', how='left')
            
            # 字段映射（适配旧代码的字段名）
            # 注意：数据库中的字段是peTTM/pbMRQ/psTTM，需要正确映射
            rename_map = {
                'ts_code': 'code',
                'name': 'name',
                'price': 'price',
                'total_mv': 'market_cap',
                'circ_mv': 'float_cap',
                'volume': 'volume',
                'turnover': 'turnover',
                'change_pct': 'change_pct'
            }
            # PE/PB/PS字段映射（从peTTM/pbMRQ/psTTM）
            if 'peTTM' in df.columns:
                rename_map['peTTM'] = 'pe'
            if 'pbMRQ' in df.columns:
                rename_map['pbMRQ'] = 'pb'
            if 'psTTM' in df.columns:
                rename_map['psTTM'] = 'ps'
            
            df = df.rename(columns=rename_map)
            
            # 确保必要的字段存在
            if 'market_cap' not in df.columns:
                df['market_cap'] = None
            if 'pe' not in df.columns:
                df['pe'] = None
            if 'pb' not in df.columns:
                df['pb'] = None
            
            st.success(f"✅ 已加载 {len(df)} 条股票数据（最新日期: {latest_date}）")
        else:
            st.error("❌ 数据库中没有市场数据，请先下载数据")
            st.stop()
    elif 'stock_basic_info' in tables:
        # 只有基础信息
        df = pd.read_sql_query("SELECT * FROM stock_basic_info", conn)
        df = df.rename(columns={'ts_code': 'code', 'name': 'name'})
        df['price'] = None
        df['market_cap'] = None
        df['pe'] = None
        df['pb'] = None
        st.warning(f"⚠️ 只有基础信息，共 {len(df)} 条，建议下载完整数据")
    else:
        st.error("❌ 数据库表结构不正确，请重新下载数据")
        st.stop()
    
    conn.close()
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
        
        # 过滤ST股票
        if not allow_st:
            if "name" in work.columns:
                work = work[~work["name"].astype(str).str.contains("ST", case=False, na=False)]
        
        # 确保字段名正确（适配旧代码）
        if "code" not in work.columns and "ts_code" in work.columns:
            work["code"] = work["ts_code"]
        if "code" not in work.columns and "stock_code" in work.columns:
            work["code"] = work["stock_code"]
        
        # 市值筛选
        if "market_cap" in work.columns:
            work["market_cap"] = pd.to_numeric(work["market_cap"], errors="coerce").fillna(0)
            work = work[work["market_cap"] >= min_mcap * 1e8]
        
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
        work = work[work["score"] > 0]
        
        if len(work) == 0:
            st.error("❌ 没有符合条件的股票，请调整筛选条件")
            st.stop()
        
        st.info(f"📊 符合筛选条件的股票: {len(work)} 只")
        
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
            
            ranked = llm_rerank(
                work[available_cols],
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

