"""
成长 + 估值打分展示页
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import text, inspect
import altair as alt
import numpy as np
import plotly.express as px
from datetime import datetime

try:
    from streamlit_plotly_events import plotly_events

    HAS_PLOTLY_EVENTS = True
except ImportError:  # pragma: no cover
    HAS_PLOTLY_EVENTS = False

if "selected_stock_codes" not in st.session_state:
    st.session_state["selected_stock_codes"] = []
if "show_stock_detail_modal" not in st.session_state:
    st.session_state["show_stock_detail_modal"] = False

# 注入项目路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_ENGINE_PATH = PROJECT_ROOT / "data_engine"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DATA_ENGINE_PATH) not in sys.path:
    sys.path.insert(0, str(DATA_ENGINE_PATH))

from data_engine.config import DB_URL  # noqa: E402
from data_engine.utils.db_utils import get_engine  # noqa: E402
from web.components.results_display import render_results  # noqa: E402
from web.utils.analysis_runner import run_stock_analysis, format_analysis_results  # noqa: E402

st.set_page_config(page_title="成长估值评分", page_icon="📈", layout="wide")
st.title("📈 成长 + 估值评分看板")
st.caption("基于 vw_stock_basic_info_unique、stock_market_daily、stock_financials_growth 构建的综合评分")


@st.cache_resource
def get_db_engine():
    return get_engine(DB_URL)


def ensure_table_exists(engine) -> bool:
    inspector = inspect(engine)
    return "analysis_stock_scores" in inspector.get_table_names()


def load_scores(engine):
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT * FROM analysis_stock_scores"), conn)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["updated_at"] = pd.to_datetime(df.get("updated_at"))
    numeric_cols = [
        "pe",
        "pb",
        "net_profit_yoy",
        "eps_yoy",
        "value_score",
        "growth_score",
        "composite_score",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_stock_detail(engine, ts_code: str) -> dict:
    detail = {"ts_code": ts_code}
    with engine.connect() as conn:
        basic = conn.execute(
            text("SELECT ts_code, code_name, ipoDate, outDate, type, status FROM vw_stock_basic_info_unique WHERE ts_code = :code"),
            {"code": ts_code},
        ).fetchone()
        if basic:
            detail.update(dict(basic))
        market = conn.execute(
            text(
                """
                SELECT * FROM stock_market_daily
                WHERE ts_code = :code
                ORDER BY trade_date DESC
                LIMIT 1
                """
            ),
            {"code": ts_code},
        ).fetchone()
        if market:
            detail.update({f"market_{k}": v for k, v in dict(market).items()})
        growth = conn.execute(
            text(
                """
                SELECT year, quarter, net_profit_yoy, eps_yoy, shareholders_equity_yoy, total_assets_yoy, profit_yoy
                FROM stock_financials_growth
                WHERE ts_code = :code
                ORDER BY year DESC, quarter DESC
                LIMIT 1
                """
            ),
            {"code": ts_code},
        ).fetchone()
        if growth:
            detail.update({f"growth_{k}": v for k, v in dict(growth).items()})
    return detail


def normalize_stock_code(ts_code: str):
    """将 ts_code 分解为分析所需的股票代码和市场类型"""
    if not ts_code:
        return ts_code, "A股"
    ts_code = ts_code.strip().upper()
    if ts_code.endswith((".SZ", ".SH")):
        return ts_code.split(".")[0], "A股"
    if ts_code.endswith(".HK"):
        return ts_code.split(".")[0], "港股"
    # 默认按美股处理
    return ts_code.replace(".", ""), "美股"


engine = get_db_engine()
if not ensure_table_exists(engine):
    st.warning("⚠️ 未找到评分表 `analysis_stock_scores`，请先执行 `data_engine/analytics/build_growth_value_scores.py`。")
    st.stop()

scores_df = load_scores(engine)
if scores_df.empty:
    st.info("暂无评分数据，请先运行计算脚本。")
    st.stop()

latest_trade_date = scores_df["trade_date"].max().date()
latest_update_time = scores_df["updated_at"].max()

col_a, col_b, col_c = st.columns(3)
col_a.metric("覆盖股票数", f"{scores_df['ts_code'].nunique():,}")
col_b.metric("评分日期", str(latest_trade_date))
col_c.metric("最后更新", latest_update_time.strftime("%Y-%m-%d %H:%M") if pd.notna(latest_update_time) else "-")

with st.expander("筛选条件", expanded=True):
    min_score = st.slider("最低综合评分", 0.0, 1.0, 0.7, 0.05)
    sort_by = st.selectbox(
        "排序字段",
        options=["composite_score", "growth_score", "value_score", "pe", "pb", "net_profit_yoy"],
        index=0,
    )
    top_n = st.slider("显示前 N 名", 20, 200, 100, 10)
    search_keyword = st.text_input("按股票代码 / 名称搜索", "")

filtered_df = scores_df.copy()
filtered_df = filtered_df[filtered_df["composite_score"].fillna(0) >= min_score]

if search_keyword:
    keyword = search_keyword.strip().lower()
    filtered_df = filtered_df[
        filtered_df["ts_code"].str.lower().str.contains(keyword)
        | filtered_df["stock_name"].str.lower().str.contains(keyword)
    ]

if sort_by not in filtered_df.columns:
    sort_by = "composite_score"

filtered_df = filtered_df.sort_values(sort_by, ascending=sort_by in {"pe", "pb"})
filtered_df = filtered_df.head(top_n)

st.subheader("精选股票列表")
if filtered_df.empty:
    st.warning("未找到满足条件的股票，请放宽筛选条件。")
else:
    st.dataframe(
        filtered_df[
            [
                "ts_code",
                "stock_name",
                "composite_score",
                "growth_score",
                "value_score",
                "pe",
                "pb",
                "net_profit_yoy",
                "eps_yoy",
                "growth_period",
            ]
        ].reset_index(drop=True),
        use_container_width=True,
    )

manual_select = st.multiselect(
    "手动加入关注列表",
    options=filtered_df["ts_code"].tolist(),
    default=st.session_state.get("selected_stock_codes", []),
    help="在列表中勾选股票，可与图表选择结果合并。",
)
st.session_state["manual_selected_codes"] = manual_select

csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 下载当前结果",
    data=csv_bytes,
    file_name=f"stock_scores_{latest_trade_date}.csv",
    mime="text/csv",
    key="download-filtered",
)

st.markdown("---")

left, right = st.columns(2)

with left:
    st.markdown("#### 综合评分分布")
    hist_df = scores_df[["composite_score"]].dropna()
    if hist_df.empty:
        st.info("暂无数据绘制分布")
    else:
        hist_chart = (
            alt.Chart(hist_df)
            .mark_bar(opacity=0.7)
            .encode(
                x=alt.X("composite_score", bin=alt.Bin(step=0.05), title="综合得分"),
                y=alt.Y("count()", title="股票数量"),
            )
        )
        st.altair_chart(hist_chart, use_container_width=True)

with right:
    st.markdown("#### 成长 vs. 估值散点")
    if not HAS_PLOTLY_EVENTS:
        st.warning("未安装 `streamlit-plotly-events` 组件，无法启用图形选取功能。请运行 `pip install streamlit-plotly-events` 后重启应用。")
        scatter_df = scores_df.dropna(subset=["growth_score", "value_score"])
        if scatter_df.empty:
            st.info("暂无完整分数用于绘制散点图")
        else:
            chart = (
                alt.Chart(scatter_df)
                .mark_circle(size=60, opacity=0.6)
                .encode(
                    x=alt.X("value_score", scale=alt.Scale(domain=[0, 1]), title="估值得分 (越小越优)"),
                    y=alt.Y("growth_score", scale=alt.Scale(domain=[0, 1]), title="成长得分"),
                    color=alt.Color("composite_score", scale=alt.Scale(scheme="blues"), title="综合得分"),
                    tooltip=["ts_code", "stock_name", "composite_score", "growth_score", "value_score"],
                )
            )
            st.altair_chart(chart, use_container_width=True)
        selected_df = pd.DataFrame()
    else:
        scatter_df = scores_df.dropna(subset=["growth_score", "value_score"])
        if scatter_df.empty:
            st.info("暂无完整分数用于绘制散点图")
            selected_df = pd.DataFrame()
        else:
            scatter_fig = px.scatter(
                scatter_df,
                x="value_score",
                y="growth_score",
                color="composite_score",
                color_continuous_scale="Blues",
                labels={
                    "value_score": "估值得分 (越小越优)",
                    "growth_score": "成长得分",
                    "composite_score": "综合得分",
                },
                hover_data={
                    "ts_code": True,
                    "stock_name": True,
                    "pe": True,
                    "pb": True,
                    "net_profit_yoy": True,
                    "eps_yoy": True,
                    "growth_period": True,
                },
            )
            scatter_fig.update_traces(
                marker=dict(size=9, opacity=0.75, line=dict(width=0)),
                selector=dict(mode="markers"),
                customdata=np.stack(
                    [
                        scatter_df["ts_code"],
                        scatter_df["stock_name"],
                    ],
                    axis=-1,
                ),
            )
            scatter_fig.update_layout(dragmode="select", hovermode="closest")

            selected_points = plotly_events(
                scatter_fig,
                select_event=True,
                override_height=420,
                key="growth_value_scatter",
            )

            if selected_points:
                indices = [pt["pointNumber"] for pt in selected_points if "pointNumber" in pt]
                selected_df = scatter_df.iloc[indices].drop_duplicates(subset=["ts_code"])
            else:
                selected_df = pd.DataFrame()

if HAS_PLOTLY_EVENTS:
    st.markdown("### ✨ 图中选中股票明细")
    if selected_df.empty:
        st.info("在右侧散点图中拖动框选区域即可查看对应股票列表。")
    else:
        st.dataframe(
            selected_df[
                [
                    "ts_code",
                    "stock_name",
                    "composite_score",
                    "growth_score",
                    "value_score",
                    "pe",
                    "pb",
                    "net_profit_yoy",
                    "eps_yoy",
                    "growth_period",
                ]
            ].reset_index(drop=True),
            use_container_width=True,
        )
        st.download_button(
            label="📥 下载选中股票",
            data=selected_df.to_csv(index=False).encode("utf-8"),
            file_name=f"selected_stock_scores_{latest_trade_date}.csv",
            mime="text/csv",
            key="download-selected",
        )
else:
    selected_df = pd.DataFrame()

chart_selected_codes = selected_df["ts_code"].tolist() if not selected_df.empty else []
combined_codes = sorted(set(manual_select) | set(chart_selected_codes))
st.session_state["selected_stock_codes"] = combined_codes
selected_snapshot = scores_df[scores_df["ts_code"].isin(combined_codes)]
st.session_state["selected_stock_snapshot"] = selected_snapshot.copy()

st.info(
    f"🔗 当前已选择 {len(combined_codes)} 支股票，相关页面（如智能选股、简化策略）可通过 `st.session_state['selected_stock_codes']` 获取同一列表。"
)

col_detail, col_ai = st.columns([2, 1])
with col_detail:
    detail_code = st.selectbox(
        "选择一支股票查看详情",
        options=[""] + combined_codes,
        format_func=lambda code: code if code else "请选择",
    )
with col_ai:
    open_modal = st.button("查看并分析", disabled=not detail_code, type="primary")

if open_modal and detail_code:
    st.session_state["detail_stock_code"] = detail_code
    st.session_state["show_stock_detail_modal"] = True

if st.session_state.get("show_stock_detail_modal"):
    target_code = st.session_state.get("detail_stock_code")
    if target_code:
        detail = load_stock_detail(engine, target_code)
        score_row = scores_df[scores_df["ts_code"] == target_code].iloc[0]
        with st.modal(f"{target_code} 详细信息", key="stock-detail-modal"):
            st.markdown(f"### {detail.get('code_name', target_code)}")
            base_cols = st.columns(3)
            base_cols[0].metric("综合得分", f"{score_row['composite_score']:.3f}")
            base_cols[1].metric("成长得分", f"{score_row['growth_score']:.3f}")
            base_cols[2].metric("估值得分", f"{score_row['value_score']:.3f}")

            st.markdown("#### 基础信息")
            basic_table = {
                "上市日期": detail.get("ipoDate"),
                "退市日期": detail.get("outDate"),
                "类型": detail.get("type"),
                "状态": detail.get("status"),
            }
            st.table(pd.DataFrame.from_dict(basic_table, orient="index", columns=["数值"]))

            st.markdown("#### 最新行情")
            market_fields = {
                "trade_date": "交易日期",
                "close": "收盘价",
                "pct_chg": "涨跌幅%",
                "turnover_rate": "换手率%",
                "peTTM": "PE(TTM)",
                "pbMRQ": "PB(MRQ)",
                "volume": "成交量",
                "amount": "成交额",
            }
            market_data = {
                label: detail.get(f"market_{key}") for key, label in market_fields.items()
            }
            st.table(pd.DataFrame.from_dict(market_data, orient="index", columns=["数值"]))

            st.markdown("#### 最新成长指标")
            growth_fields = {
                "year": "年份",
                "quarter": "季度",
                "net_profit_yoy": "净利润YOY",
                "eps_yoy": "EPS YOY",
                "shareholders_equity_yoy": "净资产YOY",
                "total_assets_yoy": "总资产YOY",
                "profit_yoy": "利润YOY",
            }
            growth_data = {
                label: detail.get(f"growth_{key}") for key, label in growth_fields.items()
            }
            st.table(pd.DataFrame.from_dict(growth_data, orient="index", columns=["数值"]))

            st.markdown("---")
            call_ai = st.checkbox("允许调用智能体进一步分析该股票", value=False)
            analysis_prompt = st.text_area(
                "补充说明 (可选)",
                placeholder="例如：关注财务稳健性、行业竞争格局、是否适合长期持有？",
            )
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            if st.button("📤 提交给智能体", disabled=False):
                if not call_ai:
                    status_placeholder.warning("请勾选“允许调用智能体”后再提交。")
                else:
                    analysis_logs = []

                    def progress_callback(message, step=None, total_steps=None):
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        line = f"[{timestamp}] {message}"
                        analysis_logs.append(line)
                        progress_placeholder.info("\n".join(analysis_logs[-6:]))

                    stock_symbol, inferred_market = normalize_stock_code(target_code)
                    market_type_for_analysis = inferred_market
                    analysis_date = datetime.now().strftime("%Y-%m-%d")
                    analysts = ["market", "fundamentals", "news"]
                    if inferred_market == "A股":
                        analysts.append("social")
                    analysts = list(dict.fromkeys(analysts))

                    provider = st.session_state.get("llm_provider", "dashscope")
                    model = st.session_state.get("llm_model", "qwen-plus-latest")

                    with st.spinner("智能体正在分析，请稍候..."):
                        try:
                            raw_result = run_stock_analysis(
                                stock_symbol=stock_symbol,
                                analysis_date=analysis_date,
                                analysts=analysts,
                                research_depth=3,
                                llm_provider=provider,
                                llm_model=model,
                                market_type=market_type_for_analysis,
                                progress_callback=progress_callback,
                            )

                            if analysis_prompt:
                                raw_result.setdefault("metadata", {})["user_prompt"] = analysis_prompt

                            formatted_result = format_analysis_results(raw_result)
                            st.session_state["latest_ai_analysis_raw"] = raw_result
                            st.session_state["latest_ai_analysis_formatted"] = formatted_result
                            st.session_state["latest_ai_progress_log"] = analysis_logs
                            st.session_state["last_analyzed_stock"] = target_code
                            status_placeholder.success("智能体分析完成，结果已更新到页面下方。")
                            st.session_state["show_stock_detail_modal"] = False
                            st.experimental_rerun()
                        except Exception as exc:
                            status_placeholder.error(f"分析失败：{exc}")
                            st.session_state["latest_ai_progress_log"] = analysis_logs
            if st.button("关闭", key="close-modal"):
                st.session_state["show_stock_detail_modal"] = False
    else:
        st.session_state["show_stock_detail_modal"] = False

latest_ai_result = st.session_state.get("latest_ai_analysis_formatted")
if latest_ai_result:
    st.markdown("### 🤖 智能体综合分析结果")
    render_results(latest_ai_result)

if st.session_state.get("latest_ai_progress_log"):
    with st.expander("查看最近一次智能体执行日志", expanded=False):
        for line in st.session_state["latest_ai_progress_log"]:
            st.write(line)
