"""
数据中心 - A股基础资料
用于下载和管理A股股票基础资料
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import subprocess
import sys
import os

# 设置页面配置
st.set_page_config(
    page_title="数据中心 - A股基础资料",
    page_icon="📥",
    layout="wide"
)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

DATA_PATH = Path("data/stock_basic.csv")
DATA_PATH = project_root / DATA_PATH if not DATA_PATH.is_absolute() else DATA_PATH

st.title("📥 数据中心 - A股基础资料")
st.markdown("---")

# 检查数据文件是否存在
data_exists = DATA_PATH.exists()

# 显示当前状态
col1, col2 = st.columns([2, 1])
with col1:
    if data_exists:
        try:
            df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
            st.success(f"✅ 本地数据文件存在: {len(df)} 条记录")
            
            # 显示最后更新时间
            import time
            mtime = os.path.getmtime(DATA_PATH)
            from datetime import datetime
            update_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            st.caption(f"📅 最后更新时间: {update_time}")
        except Exception as e:
            st.error(f"❌ 读取数据文件失败: {e}")
            data_exists = False
    else:
        st.info("ℹ️ 未检测到本地基础资料，点击下方按钮开始下载。")

with col2:
    if st.button("🔄 刷新状态", use_container_width=True):
        st.rerun()

st.markdown("---")

# 下载功能
st.subheader("📥 数据下载")
st.markdown("""
使用 **AkShare** 从东方财富等数据源获取A股股票基础资料，包括：
- 股票代码和名称
- 最新价格
- 总市值
- 流通市值
""")

# 创建下载按钮
if st.button("🚀 下载/更新 A股基础资料", type="primary", use_container_width=True):
    with st.spinner("正在拉取数据（AkShare）...这可能需要1-3分钟..."):
        try:
            # 执行下载脚本
            script_path = project_root / "scripts" / "fetch_cn_stock_basic.py"
            
            if not script_path.exists():
                st.error(f"❌ 未找到下载脚本: {script_path}")
                st.stop()
            
            # 使用subprocess运行脚本
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                st.error(f"❌ 下载失败")
                
                # 分析错误类型并给出友好提示
                error_output = result.stderr if result.stderr else result.stdout
                if "proxy" in error_output.lower() or "ProxyError" in error_output:
                    st.warning("🔧 **代理配置问题**")
                    st.info("""
                    **问题诊断**: 系统检测到代理连接错误
                    
                    **可能的解决方案：**
                    1. 系统已自动尝试禁用代理，请重试
                    2. 如果仍有问题，检查系统代理设置：
                       - macOS: 系统设置 → 网络 → 代理
                       - 检查是否有无效的代理配置
                    3. 临时禁用代理环境变量：
                       ```bash
                       unset HTTP_PROXY
                       unset HTTPS_PROXY
                       unset http_proxy
                       unset https_proxy
                       ```
                    4. 如果确实需要代理，请确保代理服务器正常运行
                    """)
                    st.success("💡 **提示**: 下载脚本已自动禁用代理，请点击按钮重试")
                elif "connection" in error_output.lower() or "Connection" in error_output:
                    st.warning("🌐 **网络连接问题**")
                    st.info("""
                    **可能的解决方案：**
                    1. 检查网络连接是否稳定
                    2. 检查是否需要配置代理/VPN
                    3. 稍后重试（数据源服务器可能临时不可用）
                    4. 尝试在网络较好的环境下重试
                    """)
                elif "timeout" in error_output.lower():
                    st.warning("⏱️ **请求超时**")
                    st.info("""
                    **可能的解决方案：**
                    1. 数据源服务器响应较慢，请稍后重试
                    2. 检查网络连接速度
                    3. 如果是首次下载，数据量较大，可能需要更长时间
                    """)
                elif "rate limit" in error_output.lower() or "频率" in error_output:
                    st.warning("🚦 **请求频率过高**")
                    st.info("""
                    **可能的解决方案：**
                    1. 等待 1-2 分钟后重试
                    2. 数据源可能有访问频率限制
                    """)
                
                # 显示详细错误信息（可折叠）
                with st.expander("🔍 查看详细错误信息"):
                    st.code(error_output, language="bash")
            else:
                st.success("✅ 下载完成！")
                if result.stdout:
                    st.code(result.stdout, language="bash")
                
                # 刷新状态
                st.rerun()
                
        except subprocess.TimeoutExpired:
            st.error("❌ 下载超时（超过5分钟），请检查网络连接或稍后重试")
        except Exception as e:
            st.error(f"❌ 下载过程出错: {e}")
            import traceback
            st.code(traceback.format_exc(), language="python")

st.markdown("---")

# 数据展示
if data_exists:
    st.subheader("📊 数据预览")
    
    try:
        df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
        
        # 显示统计信息
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总记录数", len(df))
        with col2:
            if "code" in df.columns:
                st.metric("股票代码数", df["code"].nunique())
        with col3:
            if "price" in df.columns:
                avg_price = df["price"].mean()
                st.metric("平均价格", f"￥{avg_price:.2f}" if not pd.isna(avg_price) else "N/A")
        with col4:
            if "market_cap" in df.columns:
                total_mcap = df["market_cap"].sum() / 1e12  # 转换为万亿元
                st.metric("总市值", f"{total_mcap:.2f}万亿" if not pd.isna(total_mcap) else "N/A")
        
        # 数据表格
        st.markdown("### 📋 数据表格")
        
        # 搜索功能
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            search_keyword = st.text_input("🔍 搜索股票（代码或名称）", placeholder="例如: 000001 或 平安")
        with search_col2:
            show_count = st.number_input("显示数量", min_value=10, max_value=500, value=50, step=10)
        
        # 过滤数据
        display_df = df.copy()
        if search_keyword:
            mask = (
                display_df["code"].astype(str).str.contains(search_keyword, case=False, na=False) |
                display_df["name"].astype(str).str.contains(search_keyword, case=False, na=False)
            )
            display_df = display_df[mask]
            st.info(f"🔍 找到 {len(display_df)} 条匹配记录")
        
        # 显示数据
        st.dataframe(
            display_df.head(show_count),
            use_container_width=True,
            hide_index=True
        )
        
        # 数据统计
        with st.expander("📈 数据统计信息"):
            st.dataframe(display_df.describe(), use_container_width=True)
        
        # 导出功能
        st.markdown("---")
        st.subheader("💾 数据导出")
        
        col1, col2 = st.columns(2)
        with col1:
            csv_data = display_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 导出为 CSV",
                csv_data.encode("utf-8-sig"),
                file_name=f"stock_basic_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            if st.button("🗑️ 删除本地数据", use_container_width=True):
                if st.session_state.get("confirm_delete"):
                    try:
                        DATA_PATH.unlink()
                        st.success("✅ 数据文件已删除")
                        st.session_state.confirm_delete = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 删除失败: {e}")
                else:
                    st.session_state.confirm_delete = True
                    st.warning("⚠️ 确认删除？请再次点击按钮")

    except Exception as e:
        st.error(f"❌ 读取数据失败: {e}")
        import traceback
        st.code(traceback.format_exc(), language="python")

else:
    st.info("""
    💡 **使用说明**:
    1. 点击上方「下载/更新 A股基础资料」按钮
    2. 等待下载完成（约1-3分钟）
    3. 下载完成后即可查看和导出数据
    
    ⚠️ **注意事项**:
    - 数据来源于AkShare，需要稳定的网络连接
    - 建议每日更新一次数据以获取最新信息
    - 首次下载可能需要较长时间
    """)

# 页脚信息
st.markdown("---")
st.caption("💡 提示: 此数据用于智能选股功能，确保数据最新可获得更准确的分析结果")

