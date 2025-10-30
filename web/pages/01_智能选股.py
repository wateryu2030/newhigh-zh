import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="智能选股", page_icon="🧠")
st.title("🧠 智能选股系统")

base = Path(__file__).resolve().parents[2]
sel_file = base / "data/selection_results.csv"

if sel_file.exists():
    selection_data = pd.read_csv(sel_file)
    st.dataframe(selection_data, use_container_width=True)
else:
    st.info("暂无 selection_results.csv 示例数据，稍后可上传或由脚本生成。")

st.markdown("---")

st.subheader("📈 因子示意图")
if sel_file.exists() and {'factor1', 'factor2'}.issubset(selection_data.columns):
    st.line_chart(selection_data[['factor1', 'factor2']])
else:
    st.caption("缺少 factor1/factor2 列，显示示意图需准备对应数据。")
