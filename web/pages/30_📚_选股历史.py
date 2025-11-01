"""
选股历史记录页面
查看和管理历史选股记录
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="选股历史",
    page_icon="📚",
    layout="wide"
)

st.title("📚 选股历史记录")

# 导入存储模块
try:
    from web.utils.stock_selection_storage import get_storage
    storage = get_storage()
except Exception as e:
    st.error(f"❌ 加载存储模块失败: {e}")
    st.stop()

# 筛选条件
st.subheader("🔍 筛选条件")
col1, col2, col3 = st.columns(3)

with col1:
    strategy_filter = st.selectbox(
        "策略筛选",
        ["全部"] + ["保守", "平衡", "激进", "价值", "成长"],
        help="按投资策略筛选"
    )

with col2:
    limit = st.number_input("显示数量", min_value=10, max_value=200, value=50, step=10)

with col3:
    if st.button("🔄 刷新", use_container_width=True):
        st.rerun()

# 获取选股记录
strategy = None if strategy_filter == "全部" else strategy_filter
selections = storage.list_selections(limit=limit, strategy=strategy)

if selections:
    st.success(f"✅ 找到 {len(selections)} 条选股记录")
    
    # 显示记录列表
    st.markdown("---")
    st.subheader("📋 选股记录列表")
    
    # 创建摘要表格
    summary_data = []
    for sel in selections:
        created_at = datetime.fromisoformat(sel["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        summary_data.append({
            "记录ID": sel["selection_id"][:20] + "...",
            "策略": sel["strategy"],
            "候选数": sel["selected_count"],
            "创建时间": created_at
        })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    # 详细查看
    st.markdown("---")
    st.subheader("📊 详细查看")
    
    selected_id = st.selectbox(
        "选择记录查看详情",
        [sel["selection_id"] for sel in selections],
        format_func=lambda x: f"{x[:20]}... ({selections[[s['selection_id'] for s in selections].index(x)]['strategy']})"
    )
    
    if selected_id:
        selection = storage.get_selection(selected_id)
        if selection:
            # 显示基本信息
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("策略", selection["strategy"])
            with col2:
                st.metric("候选数量", selection["selected_count"])
            with col3:
                st.metric("总候选", selection["total_candidates"])
            with col4:
                created_at = datetime.fromisoformat(selection["created_at"])
                st.metric("创建时间", created_at.strftime("%Y-%m-%d %H:%M:%S"))
            
            # 显示筛选条件
            st.markdown("### 🔍 筛选条件")
            filter_conditions = selection["filter_conditions"]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**最小市值**: {filter_conditions.get('min_mcap', 'N/A')} 亿元")
            with col2:
                st.info(f"**单票上限**: {filter_conditions.get('max_weight', 'N/A')}%")
            with col3:
                st.info(f"**包含ST**: {'是' if filter_conditions.get('allow_st', False) else '否'}")
            
            # 显示选股结果
            st.markdown("### 📋 选股结果")
            results_df = pd.DataFrame(selection["results"])
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            
            # 导出功能
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                csv_data = results_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 导出为 CSV",
                    csv_data.encode("utf-8-sig"),
                    file_name=f"selection_{selected_id}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col2:
                if st.button("🗑️ 删除记录", use_container_width=True):
                    if storage.delete_selection(selected_id):
                        st.success("✅ 记录已删除")
                        st.rerun()
                    else:
                        st.error("❌ 删除失败")
else:
    st.info("📭 暂无选股记录，请先使用「智能选股」功能生成记录")

