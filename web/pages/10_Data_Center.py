"""
Data Center - A-Share Basic Data
Download and manage A-share stock basic information
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import subprocess
import sys
import os
import time
import re
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# 添加项目根目录到路径（先添加，确保导入路径正确）
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入数据清洗模块
from web.utils.data_cleaner import safe_dataframe as clean_dataframe, clean_duplicate_columns

def safe_dataframe(df, **kwargs):
    """安全的st.dataframe包装函数，确保没有重复列"""
    if df is None or df.empty:
        st.dataframe(df, **kwargs)
        return
    
    # 使用数据清洗模块清理DataFrame
    df_clean = clean_dataframe(df, normalize=False)
    st.dataframe(df_clean, **kwargs)

# 设置页面配置
st.set_page_config(
    page_title="Data Center - A-Share Basic Data",
    page_icon="📥",
    layout="wide"
)

# 数据路径（用于向后兼容）
DATA_PATH = project_root / "data" / "stock_basic.csv"

st.title("📥 Data Center - A-Share Basic Data")
st.markdown("**数据中心 - A股基础资料**")  # 保留中文显示标题
st.markdown("---")

# 显示数据源信息
st.info("📊 **数据源**: BaoStock（免费、稳定、无需注册）")

st.markdown("---")

# 检查数据库（只使用新数据库）
DATA_ENGINE_DB_PATH = project_root / "data" / "stock_database.db"  # data_engine数据库（唯一数据源）
DATA_PATH = project_root / "data" / "stock_basic.csv"  # CSV备份（已废弃）

data_engine_db_exists = DATA_ENGINE_DB_PATH.exists()
csv_exists = DATA_PATH.exists()

# 尝试从数据库读取数据（只使用新数据库）
df = None
data_source = None

# 读取data_engine数据库（唯一数据源）
if data_engine_db_exists:
    try:
        import sqlite3
        conn = sqlite3.connect(str(DATA_ENGINE_DB_PATH))
        cursor = conn.cursor()
        
        # 检查表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # 优先读取stock_basic_info + 聚合日K数据
        if 'stock_basic_info' in tables and 'stock_market_daily' in tables:
            # 读取基础信息
            df_basic = pd.read_sql_query("SELECT * FROM stock_basic_info", conn)
            
            # 读取最新的市场价格和财务数据
            # 获取最新的交易日期
            cursor.execute("SELECT MAX(trade_date) FROM stock_market_daily")
            latest_date = cursor.fetchone()[0]
            
            if latest_date:
                # 读取市场数据（为每个股票获取最新有数据的日期）
                # 使用LEFT JOIN确保所有基础信息股票都能显示，即使没有市场数据
                query_market = """
                    SELECT 
                        b.ts_code,
                        m.close as price,
                        m.volume,
                        m.amount as turnover,
                        m.pct_chg as change_pct,
                        m.peTTM as pe,
                        m.pbMRQ as pb,
                        m.psTTM as ps
                    FROM stock_basic_info b
                    LEFT JOIN (
                        SELECT 
                            m1.ts_code,
                            m1.close,
                            m1.volume,
                            m1.amount,
                            m1.pct_chg,
                            m1.peTTM,
                            m1.pbMRQ,
                            m1.psTTM
                        FROM stock_market_daily m1
                        INNER JOIN (
                            SELECT ts_code, MAX(trade_date) as max_date
                            FROM stock_market_daily
                            GROUP BY ts_code
                        ) latest ON m1.ts_code = latest.ts_code AND m1.trade_date = latest.max_date
                    ) m ON b.ts_code = m.ts_code
                    ORDER BY b.ts_code
                """
                df_market = pd.read_sql_query(query_market, conn)
                
                # 读取财务数据（为每个股票获取最新有数据的日期）
                query_fin = """
                    SELECT 
                        b.ts_code,
                        f.total_mv,
                        f.circ_mv,
                        f.revenue_yoy,
                        f.net_profit_yoy,
                        f.gross_profit_margin,
                        f.roe,
                        f.roa
                    FROM stock_basic_info b
                    LEFT JOIN (
                        SELECT 
                            f1.ts_code,
                            f1.total_mv,
                            f1.circ_mv,
                            f1.revenue_yoy,
                            f1.net_profit_yoy,
                            f1.gross_profit_margin,
                            f1.roe,
                            f1.roa
                        FROM stock_financials f1
                        INNER JOIN (
                            SELECT ts_code, MAX(trade_date) as max_date
                            FROM stock_financials
                            GROUP BY ts_code
                        ) latest ON f1.ts_code = latest.ts_code AND f1.trade_date = latest.max_date
                    ) f ON b.ts_code = f.ts_code
                    ORDER BY b.ts_code
                """
                df_fin = pd.read_sql_query(query_fin, conn)
                
                # 合并数据：基础信息 + 市场数据 + 财务数据
                # 使用merge确保按ts_code正确合并
                df = df_basic.merge(df_market, on='ts_code', how='left')
                df = df.merge(df_fin, on='ts_code', how='left')
                df = df.rename(columns={'ts_code': 'stock_code', 'name': 'stock_name'})
                
                # 立即清理重复列（在合并后立即处理，防止后续操作产生问题）
                df = clean_duplicate_columns(df, keep_first=False)
                
                # 双重验证：确保绝对没有重复列
                if df.columns.duplicated().any():
                    unique_cols = list(dict.fromkeys(df.columns))
                    df = pd.DataFrame(df.values[:, :len(unique_cols)], columns=unique_cols)
                
                # 最终确保：使用数据清洗模块去重（最后一次确认）
                df = clean_duplicate_columns(df, keep_first=False)
            else:
                df = df_basic.rename(columns={'ts_code': 'stock_code', 'name': 'stock_name'})
            
            conn.close()
            if df is not None and not df.empty:
                data_source = "data_engine数据库"
                st.success(f"✅ 从data_engine数据库读取: {len(df)} 条记录")
        elif 'stock_basic_info' in tables:
            # 只有基础信息
            df = pd.read_sql_query("SELECT * FROM stock_basic_info", conn)
            df = df.rename(columns={'ts_code': 'stock_code', 'name': 'stock_name'})
            conn.close()
            if df is not None and not df.empty:
                data_source = "data_engine数据库(仅基础)"
                st.success(f"✅ 从data_engine数据库读取: {len(df)} 条记录")
        conn.close()
    except Exception as e:
        st.warning(f"⚠️ 读取data_engine数据库失败: {e}")

# 如果data_engine数据库读取失败，提示用户下载数据
if (df is None or df.empty):
    st.warning("⚠️ 未找到数据，请先下载数据。")

# 如果数据库读取失败，尝试从CSV读取
if df is None or df.empty:
    if csv_exists:
        try:
            df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
            if not df.empty:
                # 确保CSV数据也没有重复列（使用数据清洗模块）
                df = clean_duplicate_columns(df, keep_first=False)
                data_source = "CSV文件"
                st.success(f"✅ 从CSV文件读取: {len(df)} 条记录")
            else:
                st.warning(f"⚠️ CSV文件存在但数据为空")
        except Exception as e:
            st.error(f"❌ 读取CSV文件失败: {e}")

# 显示当前状态
col1, col2 = st.columns([2, 1])
with col1:
    if df is not None and not df.empty:
        # 显示最后更新时间
        if 'update_time' in df.columns:
            latest_time = df['update_time'].max() if df['update_time'].notna().any() else None
            if latest_time:
                st.caption(f"📅 最后更新时间: {latest_time}")
        elif csv_exists:
            import time
            mtime = os.path.getmtime(DATA_PATH)
            from datetime import datetime
            update_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            st.caption(f"📅 CSV文件最后更新时间: {update_time}")
    else:
        st.info("ℹ️ 未检测到本地基础资料，点击下方按钮开始下载。")

with col2:
    if st.button("🔄 刷新状态", use_container_width=True):
        st.rerun()

st.markdown("---")

# 下载功能
st.subheader("📥 数据下载")
st.markdown("""
**使用BaoStock** 获取完整的A股股票数据，包括：
- ✅ 股票代码和名称
- ✅ 最新价格、成交量、成交额
- ✅ **PE、PB、PS等财务指标**（完整数据）
- ✅ 3年历史K线数据
- ✅ 技术指标（MA/RSI/MACD/KDJ等）

**注意**: 新版本使用data_engine，数据更完整且支持增量更新！
""")

# 只使用BaoStock
data_source = "BaoStock"
st.info("✅ 使用BaoStock数据源：免费、稳定、数据完整（包含PE/PB/PS等财务指标）")

# 使用data_engine进行BaoStock数据下载
script_path = project_root / "data_engine" / "update_all.py"
os.environ['USE_TUSHARE'] = 'false'
os.environ['USE_BAOSTOCK'] = 'true'

# 创建下载按钮
if st.button("🚀 下载/更新 A股基础资料", type="primary", use_container_width=True):
    data_source_name = data_source.replace("（推荐）", "")
    
    # 创建进度显示区域
    progress_container = st.container()
    with progress_container:
        st.markdown("### 📥 下载进度")
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_output = st.empty()
    
    try:
        if not script_path.exists():
            st.error(f"❌ 未找到下载脚本: {script_path}")
            st.stop()
        
        # 确定正确的Python可执行文件
        # 优先使用当前Streamlit进程的Python
        python_exe = sys.executable
        # 备用方案：尝试多个可能的位置
        if not os.path.exists(python_exe):
            for alt_python in [
                '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3',
                '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12',
                '/usr/local/bin/python3'
            ]:
                if os.path.exists(alt_python):
                    python_exe = alt_python
                    break
        
        # 使用Popen实时读取输出
        process = subprocess.Popen(
            [python_exe, str(script_path)],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 实时读取输出
        output_lines = []
        last_progress = 0
        current_status = "初始化中..."
        
        status_text.info(f"🔄 **状态**: {current_status}")
        
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            
            line = line.strip()
            if line:
                output_lines.append(line)
                
                # 解析进度信息
                progress_match = re.search(r'进度:\s*(\d+)/(\d+)\s*\(([\d.]+)%\)', line)
                if progress_match:
                    processed = int(progress_match.group(1))
                    total = int(progress_match.group(2))
                    percentage = float(progress_match.group(3))
                    last_progress = percentage / 100.0
                    progress_bar.progress(min(last_progress, 1.0))
                    current_status = f"已处理 {processed}/{total} 只股票 ({percentage:.1f}%)"
                    status_text.info(f"🔄 **状态**: {current_status}")
                
                # 更新状态文本
                elif "✅" in line or "完成" in line:
                    if "获取到" in line and "只股票" in line:
                        status_text.success(f"✅ {line}")
                    elif "下载完成" in line or "数据整理完成" in line:
                        status_text.success(f"✅ {line}")
                        progress_bar.progress(1.0)
                        current_status = "下载完成"
                elif "❌" in line or "失败" in line:
                    status_text.error(f"❌ {line}")
                elif "⏳" in line:
                    status_text.info(f"⏳ {line}")
                
                # 显示最后几行日志
                if len(output_lines) > 10:
                    log_output.text_area(
                        "下载日志",
                        "\n".join(output_lines[-10:]),
                        height=150,
                        disabled=True
                    )
                else:
                    log_output.text_area(
                        "下载日志",
                        "\n".join(output_lines),
                        height=150,
                        disabled=True
                    )
        
        # 等待进程完成
        process.wait()
        
        # 获取最终输出
        final_output = "\n".join(output_lines)
        
        # 检查是否成功
        if process.returncode == 0:
            st.success("✅ 下载完成！正在刷新数据...")
            status_text.success(f"✅ 下载成功完成！")
            progress_bar.progress(1.0)
            
            # 刷新页面以显示新数据
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"❌ 下载失败")
            
            # 分析错误类型并给出友好提示
            error_output = final_output
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
            elif "token" in error_output.lower() or "权限" in error_output.lower() or "积分" in error_output.lower():
                st.warning("🔑 **数据源权限问题**")
                st.info("""
                **问题分析**: 数据源可能有限制或网络问题
                
                **解决方案：**
                1. **检查网络连接**: 确保能访问BaoStock数据源
                2. **稍后重试**: 可能是临时网络问题
                3. **查看日志**: 点击下方展开查看详细错误信息
                
                **注意**: BaoStock是免费数据源，通常不需要特殊权限
                """)
            
            # 显示详细错误信息（可折叠）
            with st.expander("🔍 查看详细错误信息"):
                st.code(error_output, language="bash")
                
    except subprocess.TimeoutExpired:
        st.error("❌ 下载超时（超过5分钟），请检查网络连接或稍后重试")
    except Exception as e:
        st.error(f"❌ 下载过程出错: {e}")
        import traceback
        st.code(traceback.format_exc(), language="python")

st.markdown("---")

# 数据展示（即使数据不完整也显示，至少显示代码和名称）
# 添加调试信息
if 'df' not in locals():
    df = None

if df is not None and not df.empty:
    # 确保df本身没有重复列（在显示前再次检查，使用数据清洗模块）
    df = clean_duplicate_columns(df, keep_first=False)
    
    st.subheader("📊 完整数据列表")
    st.info(f"💡 共 {len(df)} 条股票数据，以下为完整列表（可滚动查看）")
    
    try:
        # 使用之前读取的df（来自数据库或CSV），不再重新读取
        
        # 显示统计信息
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总记录数", len(df))
        with col2:
            code_col = 'stock_code' if 'stock_code' in df.columns else 'code'
            if code_col in df.columns:
                st.metric("股票代码数", df[code_col].nunique())
        with col3:
            if "price" in df.columns:
                avg_price = df["price"].mean()
                st.metric("平均价格", f"￥{avg_price:.2f}" if not pd.isna(avg_price) else "N/A")
        with col4:
            if "total_mv" in df.columns:
                total_mcap = df["total_mv"].sum() / 1e12 if df["total_mv"].notna().any() else 0  # 转换为万亿元
                st.metric("总市值", f"{total_mcap:.2f}万亿" if total_mcap > 0 else "N/A")
        
        # ========== 股票筛选功能 ==========
        st.markdown("---")
        st.subheader("🔍 综合股票筛选")
        
        # 筛选模式选择
        filter_mode = st.radio(
            "筛选模式",
            ["📊 快速筛选", "🎯 高级筛选", "📋 预设模板"],
            horizontal=True,
            key="filter_mode"
        )
        
        if filter_mode == "📋 预设模板":
            # 预设模板筛选
            template_col1, template_col2 = st.columns([2, 1])
            with template_col1:
                template = st.selectbox(
                    "选择预设模板",
                    [
                        "全部股票",
                        "💰 价值股（低PE低PB）",
                        "🚀 成长股（高ROE高增长）",
                        "💎 优质股（ROE>15%，PE<30）",
                        "📈 小盘股（市值<100亿）",
                        "🏢 大盘股（市值>500亿）",
                        "💹 活跃股（换手率>3%）",
                        "📊 低波动股（波动率<20%）",
                        "🎯 高股息股（PB<2，ROE>10%）",
                        "🔥 热门股（涨幅>5%）"
                    ],
                    key="template_selector"
                )
            with template_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("应用模板", use_container_width=True, type="primary"):
                    st.session_state.apply_template = True
            
            # 应用预设模板
            if st.session_state.get("apply_template", False):
                display_df = df.copy()
                display_df = clean_duplicate_columns(display_df, keep_first=False)
                
                if template == "💰 价值股（低PE低PB）":
                    if 'pe' in display_df.columns:
                        display_df = display_df[(display_df['pe'] > 0) & (display_df['pe'] < 20)]
                    if 'pb' in display_df.columns:
                        display_df = display_df[(display_df['pb'] > 0) & (display_df['pb'] < 2)]
                elif template == "🚀 成长股（高ROE高增长）":
                    if 'roe' in display_df.columns:
                        display_df = display_df[(display_df['roe'] > 15)]
                    if 'revenue_yoy' in display_df.columns:
                        display_df = display_df[(display_df['revenue_yoy'] > 20)]
                elif template == "💎 优质股（ROE>15%，PE<30）":
                    if 'roe' in display_df.columns:
                        display_df = display_df[(display_df['roe'] > 15)]
                    if 'pe' in display_df.columns:
                        display_df = display_df[(display_df['pe'] > 0) & (display_df['pe'] < 30)]
                elif template == "📈 小盘股（市值<100亿）":
                    if 'total_mv' in display_df.columns:
                        display_df = display_df[(display_df['total_mv'] / 1e8 < 100)]
                elif template == "🏢 大盘股（市值>500亿）":
                    if 'total_mv' in display_df.columns:
                        display_df = display_df[(display_df['total_mv'] / 1e8 > 500)]
                elif template == "💹 活跃股（换手率>3%）":
                    if 'turnover_rate' in display_df.columns:
                        display_df = display_df[(display_df['turnover_rate'] > 3)]
                elif template == "📊 低波动股（波动率<20%）":
                    if 'amplitude' in display_df.columns:
                        display_df = display_df[(display_df['amplitude'] < 20)]
                elif template == "🎯 高股息股（PB<2，ROE>10%）":
                    if 'pb' in display_df.columns:
                        display_df = display_df[(display_df['pb'] > 0) & (display_df['pb'] < 2)]
                    if 'roe' in display_df.columns:
                        display_df = display_df[(display_df['roe'] > 10)]
                elif template == "🔥 热门股（涨幅>5%）":
                    if 'change_pct' in display_df.columns:
                        display_df = display_df[(display_df['change_pct'] > 5)]
                
                st.session_state.apply_template = False
                st.success(f"✅ 应用模板「{template}」，找到 {len(display_df)} 只股票")
        elif filter_mode == "📊 快速筛选":
            # 快速筛选模式（原有功能）
            with st.expander("📊 筛选条件", expanded=True):
                st.info("💡 快速筛选模式：使用简单的滑块和下拉框进行筛选")
                
                filter_col1, filter_col2, filter_col3 = st.columns(3)
            
            # 市值筛选（注意：BaoStock不提供市值数据，此功能暂时不可用）
            with filter_col1:
                st.markdown("**💰 总市值（亿元）**")
                has_mv = 'total_mv' in df.columns and df['total_mv'].notna().any()
                if not has_mv:
                    st.info("⚠️ 市值数据暂不可用（BaoStock不提供），筛选将跳过市值条件")
                if has_mv:
                    mv_min = float(df['total_mv'].min() / 1e8) if df['total_mv'].notna().any() else 0
                    mv_max = float(df['total_mv'].max() / 1e8) if df['total_mv'].notna().any() else 10000
                    mv_range = st.slider(
                        "市值范围",
                        min_value=0.0,
                        max_value=float(mv_max),
                        value=(0.0, float(mv_max)),
                        step=10.0,
                        key="mv_filter",
                        label_visibility="collapsed"
                    )
                else:
                    st.info("市值数据不可用")
                    mv_range = (0.0, 10000.0)
            
            # 市盈率筛选
            with filter_col2:
                st.markdown("**📈 市盈率（PE）**")
                has_pe = 'pe' in df.columns and df['pe'].notna().any()
                if has_pe:
                    pe_min = float(df['pe'].min()) if df['pe'].notna().any() else 0
                    pe_max = float(df['pe'].max()) if df['pe'].notna().any() else 100
                    pe_range = st.slider(
                        "PE范围",
                        min_value=0.0,
                        max_value=float(pe_max),
                        value=(0.0, float(pe_max)),
                        step=1.0,
                        key="pe_filter",
                        label_visibility="collapsed"
                    )
                else:
                    st.info("PE数据不可用")
                    pe_range = (0.0, 100.0)
            
            # 市净率筛选
            with filter_col3:
                st.markdown("**📊 市净率（PB）**")
                has_pb = 'pb' in df.columns and df['pb'].notna().any()
                if has_pb:
                    pb_min = float(df['pb'].min()) if df['pb'].notna().any() else 0
                    pb_max = float(df['pb'].max()) if df['pb'].notna().any() else 10
                    pb_range = st.slider(
                        "PB范围",
                        min_value=0.0,
                        max_value=float(pb_max),
                        value=(0.0, float(pb_max)),
                        step=0.1,
                        key="pb_filter",
                        label_visibility="collapsed"
                    )
                else:
                    st.info("PB数据不可用")
                    pb_range = (0.0, 10.0)
            
            # 价格筛选
            filter_col4, filter_col5 = st.columns(2)
            with filter_col4:
                st.markdown("**💵 价格（元）**")
                has_price = 'price' in df.columns and df['price'].notna().any()
                if has_price:
                    price_min = float(df['price'].min()) if df['price'].notna().any() else 0
                    price_max = float(df['price'].max()) if df['price'].notna().any() else 500
                    price_range = st.slider(
                        "价格范围",
                        min_value=0.0,
                        max_value=float(price_max),
                        value=(0.0, float(price_max)),
                        step=1.0,
                        key="price_filter",
                        label_visibility="collapsed"
                    )
                else:
                    price_range = (0.0, 500.0)
            
            with filter_col5:
                st.markdown("**📊 行业筛选**")
                if 'industry' in df.columns:
                    industries = ['全部'] + sorted([str(x) for x in df['industry'].dropna().unique() if pd.notna(x)])
                    selected_industry = st.selectbox(
                        "选择行业",
                        industries,
                        key="industry_filter",
                        label_visibility="collapsed"
                    )
                else:
                    selected_industry = '全部'
            
            # 应用快速筛选
            display_df = df.copy()
            display_df = clean_duplicate_columns(display_df, keep_first=False)
            
            # 市值筛选
            if has_mv and 'total_mv' in display_df.columns and display_df['total_mv'].notna().any():
                display_df = display_df[
                    (display_df['total_mv'] / 1e8 >= mv_range[0]) &
                    (display_df['total_mv'] / 1e8 <= mv_range[1])
                ]
            
            # PE筛选
            if has_pe and 'pe' in display_df.columns:
                display_df = display_df[
                    ((display_df['pe'] >= pe_range[0]) & (display_df['pe'] <= pe_range[1])) |
                    (display_df['pe'].isna())
                ]
            
            # PB筛选
            if has_pb and 'pb' in display_df.columns:
                display_df = display_df[
                    ((display_df['pb'] >= pb_range[0]) & (display_df['pb'] <= pb_range[1])) |
                    (display_df['pb'].isna())
                ]
            
            # 价格筛选
            if has_price and 'price' in display_df.columns:
                display_df = display_df[
                    ((display_df['price'] >= price_range[0]) & (display_df['price'] <= price_range[1])) |
                    (display_df['price'].isna())
                ]
            
            # 行业筛选
            if selected_industry != '全部' and 'industry' in display_df.columns:
                display_df = display_df[display_df['industry'] == selected_industry]
            
            display_df = clean_duplicate_columns(display_df, keep_first=False)
            st.success(f"✅ 快速筛选结果: 找到 {len(display_df)} 只符合条件的股票（共 {len(df)} 只）")
        
        # 如果display_df未定义，使用原始df
        if 'display_df' not in locals():
            display_df = df.copy()
            display_df = clean_duplicate_columns(display_df, keep_first=False)
        
        # 所有筛选操作完成后，再次去重（防止筛选过程中产生重复列）
        display_df = clean_duplicate_columns(display_df, keep_first=False)
        
        # 如果没有任何筛选结果，显示提示
        if len(display_df) == 0:
            st.warning("⚠️ 没有找到符合条件的股票，请调整筛选条件")
            st.stop()
        
        # ========== 可视化展示 ==========
        if len(display_df) > 0:
            # 在可视化前确保display_df没有重复列
            display_df = clean_duplicate_columns(display_df, keep_first=False)
            
            st.markdown("---")
            st.subheader("📊 数据可视化")
            
            viz_tab1, viz_tab2, viz_tab3 = st.tabs(["📈 PE/PB分布", "💰 市值分布", "💵 价格分布"])
            
            with viz_tab1:
                if has_pe and has_pb:
                    if PLOTLY_AVAILABLE:
                        # 确保传递给Plotly的DataFrame没有重复列
                        plot_df = display_df.dropna(subset=['pe', 'pb']).copy()
                        plot_df = clean_duplicate_columns(plot_df, keep_first=False)
                        
                        # 双重验证：确保绝对没有重复列（在传递给Plotly之前）
                        if plot_df.columns.duplicated().any():
                            unique_cols = list(dict.fromkeys(plot_df.columns))
                            plot_df = pd.DataFrame(plot_df.values[:, :len(unique_cols)], columns=unique_cols)
                        
                        fig = px.scatter(
                            plot_df,
                            x='pe',
                            y='pb',
                            hover_data=['stock_code', 'stock_name', 'price'],
                            labels={'pe': '市盈率 (PE)', 'pb': '市净率 (PB)'},
                            title='PE vs PB 散点图'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.scatter_chart(display_df[['pe', 'pb']].dropna(), x='pe', y='pb')
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if PLOTLY_AVAILABLE:
                            # 确保传递给Plotly的DataFrame没有重复列
                            plot_df_pe = display_df.dropna(subset=['pe']).copy()
                            plot_df_pe = clean_duplicate_columns(plot_df_pe, keep_first=False)
                            
                            # 双重验证：确保绝对没有重复列（在传递给Plotly之前）
                            if plot_df_pe.columns.duplicated().any():
                                unique_cols = list(dict.fromkeys(plot_df_pe.columns))
                                plot_df_pe = pd.DataFrame(plot_df_pe.values[:, :len(unique_cols)], columns=unique_cols)
                            
                            fig_pe = px.histogram(plot_df_pe, x='pe', nbins=30, title='PE分布直方图')
                            st.plotly_chart(fig_pe, use_container_width=True)
                        else:
                            st.bar_chart(display_df['pe'].value_counts().head(20))
                    
                    with col2:
                        if PLOTLY_AVAILABLE:
                            # 确保传递给Plotly的DataFrame没有重复列
                            plot_df_pb = display_df.dropna(subset=['pb']).copy()
                            plot_df_pb = clean_duplicate_columns(plot_df_pb, keep_first=False)
                            
                            # 双重验证：确保绝对没有重复列（在传递给Plotly之前）
                            if plot_df_pb.columns.duplicated().any():
                                unique_cols = list(dict.fromkeys(plot_df_pb.columns))
                                plot_df_pb = pd.DataFrame(plot_df_pb.values[:, :len(unique_cols)], columns=unique_cols)
                            
                            fig_pb = px.histogram(plot_df_pb, x='pb', nbins=30, title='PB分布直方图')
                            st.plotly_chart(fig_pb, use_container_width=True)
                        else:
                            st.bar_chart(display_df['pb'].value_counts().head(20))
                else:
                    st.info("PE或PB数据不足，无法绘制图表")
            
            with viz_tab2:
                if has_mv and 'total_mv' in display_df.columns and display_df['total_mv'].notna().any():
                    mv_data = display_df.dropna(subset=['total_mv']).copy()
                    # 确保没有重复列（在dropna后立即清理）
                    mv_data = clean_duplicate_columns(mv_data, keep_first=False)
                    
                    # 双重验证：确保绝对没有重复列
                    if mv_data.columns.duplicated().any():
                        unique_cols = list(dict.fromkeys(mv_data.columns))
                        mv_data = pd.DataFrame(mv_data.values[:, :len(unique_cols)], columns=unique_cols)
                    
                    mv_data['total_mv_billion'] = mv_data['total_mv'] / 1e8
                    top_mv = mv_data.nlargest(20, 'total_mv_billion')
                    
                    # 再次验证：确保nlargest后没有重复列
                    top_mv = clean_duplicate_columns(top_mv, keep_first=False)
                    
                    # 最终验证：在传递给Plotly之前绝对确保没有重复列
                    if top_mv.columns.duplicated().any():
                        unique_cols = list(dict.fromkeys(top_mv.columns))
                        top_mv = pd.DataFrame(top_mv.values[:, :len(unique_cols)], columns=unique_cols)
                    
                    # 最后一次强制清理（确保绝对没有重复列）
                    top_mv = clean_duplicate_columns(top_mv, keep_first=False)
                    
                    if PLOTLY_AVAILABLE:
                        # 在创建图表前再次验证（确保传递给Plotly的DataFrame绝对干净）
                        if top_mv.columns.duplicated().any():
                            unique_cols = list(dict.fromkeys(top_mv.columns))
                            top_mv = pd.DataFrame(top_mv.values[:, :len(unique_cols)], columns=unique_cols)
                        
                        fig_mv = px.bar(
                            top_mv,
                            x='stock_name',
                            y='total_mv_billion',
                            labels={'total_mv_billion': '总市值（亿元）', 'stock_name': '股票名称'},
                            title='市值TOP20（亿元）'
                        )
                        fig_mv.update_layout(xaxis=dict(tickangle=45))
                        st.plotly_chart(fig_mv, use_container_width=True)
                    else:
                        st.bar_chart(top_mv.set_index('stock_name')['total_mv_billion'])
                else:
                    st.info("💰 市值数据暂不可用（BaoStock不提供市值数据）")
                    st.info("💡 可以使用PE/PB/PS等估值指标进行筛选和分析")
                    
                    # 显示价格分布作为替代
                    if 'price' in display_df.columns and display_df['price'].notna().any():
                        price_data = display_df.dropna(subset=['price']).copy()
                        # 确保没有重复列（在dropna后立即清理）
                        price_data = clean_duplicate_columns(price_data, keep_first=False)
                        
                        # 双重验证：确保绝对没有重复列（在传递给Plotly之前）
                        if price_data.columns.duplicated().any():
                            unique_cols = list(dict.fromkeys(price_data.columns))
                            price_data = pd.DataFrame(price_data.values[:, :len(unique_cols)], columns=unique_cols)
                        
                        price_data = price_data.nlargest(20, 'price')
                        
                        # 再次验证：确保nlargest后没有重复列
                        price_data = clean_duplicate_columns(price_data, keep_first=False)
                        
                        if PLOTLY_AVAILABLE:
                            fig_price_top = px.bar(
                                price_data,
                                x='stock_name',
                                y='price',
                                labels={'price': '股价（元）', 'stock_name': '股票名称'},
                                title='股价TOP20（元）'
                            )
                            fig_price_top.update_layout(xaxis=dict(tickangle=45))
                            st.plotly_chart(fig_price_top, use_container_width=True)
            
            with viz_tab3:
                if has_price and 'price' in display_df.columns:
                    price_data = display_df.dropna(subset=['price']).copy()
                    # 确保没有重复列（在dropna后立即清理）
                    price_data = clean_duplicate_columns(price_data, keep_first=False)
                    
                    # 双重验证：确保绝对没有重复列（在访问columns之前）
                    if price_data.columns.duplicated().any():
                        unique_cols = list(dict.fromkeys(price_data.columns))
                        price_data = pd.DataFrame(price_data.values[:, :len(unique_cols)], columns=unique_cols)
                    
                    if PLOTLY_AVAILABLE:
                        fig_price = px.histogram(price_data, x='price', nbins=50, title='股价分布直方图')
                        st.plotly_chart(fig_price, use_container_width=True)
                        
                        # 价格与市值关系（在访问columns前再次确保无重复列）
                        if price_data.columns.duplicated().any():
                            price_data = clean_duplicate_columns(price_data, keep_first=False)
                        
                        if 'total_mv' in price_data.columns:
                            price_mv = price_data.dropna(subset=['total_mv']).copy()
                            # 确保没有重复列（在dropna后立即清理）
                            price_mv = clean_duplicate_columns(price_mv, keep_first=False)
                            
                            # 双重验证：确保绝对没有重复列（在传递给Plotly之前）
                            if price_mv.columns.duplicated().any():
                                unique_cols = list(dict.fromkeys(price_mv.columns))
                                price_mv = pd.DataFrame(price_mv.values[:, :len(unique_cols)], columns=unique_cols)
                            
                            price_mv['total_mv_billion'] = price_mv['total_mv'] / 1e8
                            
                            # 再次验证：确保创建新列后没有重复列
                            price_mv = clean_duplicate_columns(price_mv, keep_first=False)
                            
                            fig_scatter = px.scatter(
                                price_mv,
                                x='price',
                                y='total_mv_billion',
                                hover_data=['stock_code', 'stock_name'],
                                labels={'price': '股价（元）', 'total_mv_billion': '总市值（亿元）'},
                                title='股价 vs 市值'
                            )
                            st.plotly_chart(fig_scatter, use_container_width=True)
                    else:
                        st.line_chart(price_data['price'])
                else:
                    st.info("价格数据不足，无法绘制图表")
        
        # 数据表格
        st.markdown("---")
        st.markdown("### 📋 筛选结果表格")
        
        # 搜索功能（在筛选后的数据中搜索）
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            search_keyword = st.text_input("🔍 在筛选结果中搜索（代码或名称）", placeholder="例如: 000001 或 平安", value="")
        with search_col2:
            st.markdown("<br>", unsafe_allow_html=True)  # 占位符
        
        # 在筛选后的数据中进一步搜索
        if search_keyword:
            code_col = 'stock_code' if 'stock_code' in display_df.columns else 'code'
            name_col = 'stock_name' if 'stock_name' in display_df.columns else 'name'
            mask = (
                display_df[code_col].astype(str).str.contains(search_keyword, case=False, na=False) |
                display_df[name_col].astype(str).str.contains(search_keyword, case=False, na=False)
            )
            display_df = display_df[mask]
            # 搜索后再次去重（使用数据清洗模块）
            display_df = clean_duplicate_columns(display_df, keep_first=False)
            st.info(f"🔍 搜索后找到 {len(display_df)} 条匹配记录")
        
        # 显示数据完整性提示
        code_col = 'stock_code' if 'stock_code' in display_df.columns else 'code'
        has_price = 'price' in display_df.columns and display_df['price'].notna().any()
        has_pe = 'pe' in display_df.columns and display_df['pe'].notna().any()
        has_pb = 'pb' in display_df.columns and display_df['pb'].notna().any()
        
        if not has_price or not has_pe or not has_pb:
            st.warning(f"""
            ⚠️ **数据不完整提示**:
            - 价格数据: {'✅' if has_price else '❌ 缺失'}
            - PE数据: {'✅' if has_pe else '❌ 缺失'}
            - PB数据: {'✅' if has_pb else '❌ 缺失'}
            
            💡 **建议**: 重新点击「下载/更新 A股基础资料」按钮，确保网络连接稳定。
            """)
        
        # 显示数据（确保至少显示代码和名称）
        # 选择要显示的列（优先显示有数据的列）
        
        # 确保display_df没有重复列（一次性处理，避免重复检查，使用数据清洗模块）
        display_df = clean_duplicate_columns(display_df, keep_first=False)
        
        # 再次验证：确保绝对没有重复列（在访问columns之前）
        if display_df.columns.duplicated().any():
            unique_cols = list(dict.fromkeys(display_df.columns))
            display_df = pd.DataFrame(display_df.values[:, :len(unique_cols)], columns=unique_cols)
        
        display_columns = []
        
        # 必须显示的列
        code_col = 'stock_code' if 'stock_code' in display_df.columns else 'code'
        name_col = 'stock_name' if 'stock_name' in display_df.columns else 'name'
        
        if code_col in display_df.columns:
            display_columns.append(code_col)
        if name_col in display_df.columns:
            display_columns.append(name_col)
        
        # 可选显示的列（如果有数据）
        optional_cols = ['price', 'pe', 'pb', 'ps', 'total_mv', 'circ_mv', 'volume', 'turnover', 
                        'change_pct', 'industry', 'area', 'market', 
                        'list_date', 'update_time']
        
        for col in optional_cols:
            if col in display_df.columns:
                # 如果有数据就显示（至少有一条非空）
                if display_df[col].notna().any() or col in ['industry', 'area', 'market', 'list_date', 'update_time']:
                    display_columns.append(col)
        
        # 如果display_columns为空，显示所有列
        if not display_columns:
            display_columns = list(display_df.columns)
        
        # 去除重复列（保持顺序）
        display_columns = list(dict.fromkeys(display_columns))
        
        # 只选择存在的列
        display_columns = [col for col in display_columns if col in display_df.columns]
        
        # 创建最终的数据框（确保没有重复列）
        # 先确保display_df本身没有重复列
        display_df = clean_duplicate_columns(display_df, keep_first=False)
        
        # 然后创建final_df
        final_df = display_df[display_columns] if display_columns else display_df
        
        # 最终确保没有重复列（使用数据清洗模块）
        final_df = clean_duplicate_columns(final_df, keep_first=False)
        
        # 显示完整数据列表（移除head限制，显示全部）
        safe_dataframe(
            final_df,
            use_container_width=True,
            height=600,  # 设置固定高度，支持滚动
            hide_index=True
        )
        
        # 数据统计
        with st.expander("📈 数据统计信息"):
            # 确保统计时也没有重复列（使用数据清洗模块）
            stats_df = clean_duplicate_columns(display_df, keep_first=False)
            safe_dataframe(stats_df.describe(), use_container_width=True)
        
        # 导出功能
        st.markdown("---")
        st.subheader("💾 数据导出")
        
        col1, col2 = st.columns(2)
        with col1:
            # 确保导出时也没有重复列（使用数据清洗模块）
            export_df = display_df[display_columns] if display_columns else display_df
            export_df = clean_duplicate_columns(export_df, keep_first=False)
            csv_data = export_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 导出为 CSV",
                csv_data.encode("utf-8-sig"),
                file_name=f"stock_basic_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            if st.button("🗑️ 删除数据库数据", use_container_width=True):
                if st.session_state.get("confirm_delete"):
                    try:
                        # 删除data_engine数据库
                        if DATA_ENGINE_DB_PATH.exists():
                            DATA_ENGINE_DB_PATH.unlink()
                        # 同时删除CSV备份（如果存在）
                        if DATA_PATH.exists():
                            DATA_PATH.unlink()
                        st.success("✅ 数据已删除（data_engine数据库和CSV备份）")
                        st.session_state.confirm_delete = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 删除失败: {e}")
                else:
                    st.session_state.confirm_delete = True
                    st.warning("⚠️ 确认删除数据库和CSV？请再次点击按钮")

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
    - 数据来源于BaoStock，需要稳定的网络连接
    - 建议每日更新一次数据以获取最新信息
    - 首次下载可能需要较长时间（约10-15分钟）
    """)

# 页脚信息
st.markdown("---")
st.caption("💡 提示: 此数据用于智能选股功能，确保数据最新可获得更准确的分析结果")

