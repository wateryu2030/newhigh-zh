#!/usr/bin/env python3
"""
股票搜索页面
支持按代码、名称、行业、PE、PB、市值等条件搜索
使用新的data_engine数据库
"""

import streamlit as st
import pandas as pd
import sqlite3  # 保留用于向后兼容检查
from pathlib import Path
import sys
import subprocess
import os
import time
import re

# 添加项目路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# 设置页面配置（英文标题，避免URL编码问题）
st.set_page_config(page_title="股票搜索", page_icon="🔍", layout="wide")
st.title("🔍 A股股票搜索")

# 数据库路径
# 使用MySQL或SQLite（根据配置）
# DATA_ENGINE_DB_PATH已废弃，改用data_engine的配置

# 侧边栏：数据管理
with st.sidebar:
    st.header("📊 数据管理")
    
    st.markdown("### 📥 数据下载")
    
    # 使用缓存的选项（增量更新）
    use_cache = st.checkbox(
        "使用缓存 (仅更新缺失数据)",
        value=True,
        help="勾选：仅更新缺失数据，更快；取消：全量更新所有数据"
    )
    
    # 一键下载按钮
    if st.button("🔄 一键下载/更新所有A股数据", type="primary", use_container_width=True):
        script_path = project_root / "data_engine" / "update_all.py"
        
        if not script_path.exists():
            st.error(f"❌ 未找到下载脚本: {script_path}")
        else:
            # 设置环境变量
            os.environ['USE_TUSHARE'] = 'false'
            os.environ['USE_BAOSTOCK'] = 'true'
            
            # 根据use_cache设置BATCH_SIZE
            if use_cache:
                # 增量更新：只更新前400只（或已设置的值）
                batch_size = os.getenv("BATCH_SIZE", "400")
            else:
                # 全量更新：设置为"full"
                batch_size = "full"
            
            os.environ['BATCH_SIZE'] = batch_size
            
            # 创建进度显示区域
            progress_container = st.container()
            with progress_container:
                st.markdown("### 📥 下载进度")
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_output = st.empty()
            
            try:
                # 确定Python可执行文件
                python_exe = sys.executable
                if not os.path.exists(python_exe):
                    for alt_python in [
                        '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3',
                        '/usr/local/bin/python3',
                        'python3'
                    ]:
                        if os.path.exists(alt_python):
                            python_exe = alt_python
                            break
                
                # 使用Popen实时读取输出（与Data Center页面一致）
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
                            elif "下载完成" in line or "全部完成" in line:
                                status_text.success(f"✅ {line}")
                                progress_bar.progress(1.0)
                                current_status = "下载完成"
                        elif "❌" in line or "失败" in line:
                            status_text.error(f"❌ {line}")
                        elif "⏳" in line or "进度" in line:
                            status_text.info(f"⏳ {line}")
                        
                        # 显示最后几行日志（使用唯一的key）
                        display_lines = output_lines[-10:] if len(output_lines) > 10 else output_lines
                        log_output.text_area(
                            "下载日志",
                            "\n".join(display_lines),
                            height=150,
                            disabled=True,
                            key=f"download_log_{id(log_output)}"
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
                    status_text.error(f"❌ 下载失败，请查看日志")
                    
                    # 显示完整错误日志
                    with st.expander("查看详细错误"):
                        st.code(final_output)
            except Exception as e:
                st.error(f"❌ 下载出错: {e}")
                import traceback
                with st.expander("查看详细错误"):
                    st.code(traceback.format_exc())
    
    st.markdown("---")
    
    # 数据统计
    try:
        # 使用MySQL或SQLite（根据配置）
        sys.path.insert(0, str(project_root / "data_engine"))
        from data_engine.config import DB_URL
        from data_engine.utils.db_utils import get_engine
        from sqlalchemy import text
        
        engine = get_engine(DB_URL)
        
        with engine.connect() as conn:
            # 股票总数
            result = conn.execute(text("SELECT COUNT(*) FROM stock_basic_info"))
            total_count = result.fetchone()[0]
            st.metric("数据库股票总数", f"{total_count:,}")
            
            # 行业数量
            result = conn.execute(text("SELECT COUNT(DISTINCT industry) FROM stock_basic_info WHERE industry IS NOT NULL AND industry != ''"))
            industry_count = result.fetchone()[0]
            st.metric("行业数量", industry_count)
            
            # 最新数据日期
            result = conn.execute(text("SELECT MAX(trade_date) FROM stock_market_daily"))
            latest_date = result.fetchone()[0]
            if latest_date:
                st.metric("最新数据日期", latest_date)
    except Exception as e:
        st.warning(f"⚠️ 无法连接数据库: {e}")

# 主搜索区域
col1, col2, col3 = st.columns(3)

with col1:
    keyword = st.text_input("🔎 关键字搜索", placeholder="输入代码或名称，如：000001 或 平安")

with col2:
    industry = st.text_input("🏢 行业筛选", placeholder="如：银行、科技、医药")

with col3:
    # 市值筛选（BaoStock不提供，但保留接口）
    min_market_cap = st.number_input("💰 最小市值(亿元)", min_value=0.0, value=0.0, step=10.0, disabled=True, help="BaoStock不提供市值数据，此功能暂不可用")

col4, col5 = st.columns(2)

with col4:
    max_pe = st.number_input("📊 最大市盈率(PE)", min_value=0.0, value=100.0, step=5.0)

with col5:
    max_pb = st.number_input("📈 最大市净率(PB)", min_value=0.0, value=10.0, step=0.5)

limit = st.slider("返回数量", min_value=10, max_value=500, value=100)

if st.button("🔍 搜索", type="primary", use_container_width=True):
    try:
        # 使用MySQL或SQLite（根据配置）
        sys.path.insert(0, str(project_root / "data_engine"))
        from data_engine.config import DB_URL
        from data_engine.utils.db_utils import get_engine
        from sqlalchemy import text
        
        engine = get_engine(DB_URL)
        
        # 获取最新交易日期
        with engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(trade_date) FROM stock_market_daily"))
            latest_date = result.fetchone()[0]
        
        if not latest_date:
            st.error("❌ 数据库中没有市场数据，请先下载数据")
            st.stop()
        
        # 构建查询（使用参数化查询，避免SQL注入和性能问题）
        query = """
            SELECT 
                b.ts_code,
                SUBSTR(b.ts_code, 1, 6) as symbol,
                COALESCE(b.code_name, b.name) as name,
                b.industry,
                b.area,
                b.market,
                b.list_date,
                m.close as price,
                m.peTTM as pe,
                m.pbMRQ as pb,
                m.psTTM as ps,
                m.volume,
                m.amount,
                m.pct_chg as change_pct,
                m.trade_date as update_time
            FROM stock_basic_info b
            INNER JOIN stock_market_daily m ON b.ts_code = m.ts_code
            WHERE m.trade_date = :latest_date
        """
        
        params = {"latest_date": latest_date}
        
        # 关键字筛选（使用参数化查询）
        if keyword:
            keyword_clean = keyword.strip()
            query += " AND (SUBSTR(b.ts_code, 1, 6) LIKE :keyword1 OR COALESCE(b.code_name, b.name) LIKE :keyword2)"
            params["keyword1"] = f"%{keyword_clean}%"
            params["keyword2"] = f"%{keyword_clean}%"
        
        # 行业筛选
        if industry:
            industry_clean = industry.strip()
            query += " AND b.industry LIKE :industry"
            params["industry"] = f"%{industry_clean}%"
        
        # PE筛选
        if max_pe and max_pe < 1000:
            query += " AND (m.peTTM <= :max_pe OR m.peTTM IS NULL)"
            params["max_pe"] = max_pe
        
        # PB筛选
        if max_pb and max_pb < 1000:
            query += " AND (m.pbMRQ <= :max_pb OR m.pbMRQ IS NULL)"
            params["max_pb"] = max_pb
        
        query += " ORDER BY b.ts_code LIMIT :limit"
        params["limit"] = limit
        
        # 执行查询（添加错误处理）
        try:
            result = pd.read_sql_query(query, engine, params=params)
        except Exception as e:
            st.error(f"❌ 查询执行失败: {e}")
            import traceback
            st.code(traceback.format_exc())
            result = pd.DataFrame()
        
        if result.empty:
            st.warning("⚠️ 未找到符合条件的股票")
            st.info("💡 提示：可以尝试放宽筛选条件，或检查关键字是否正确")
        else:
            st.success(f"✅ 找到 {len(result)} 只股票")
            
            # 显示结果
            display_cols = ['symbol', 'name', 'industry', 'market', 'price', 'pe', 'pb', 'ps']
            
            # 如果有市值数据（虽然BaoStock不提供，但保留字段）
            if 'total_mv' in result.columns and result['total_mv'].notna().any():
                result['市值(亿元)'] = result['total_mv'] / 1e8
                display_cols.insert(-1, '市值(亿元)')
            
            if 'circ_mv' in result.columns and result['circ_mv'].notna().any():
                result['流通市值(亿元)'] = result['circ_mv'] / 1e8
                display_cols.insert(-1, '流通市值(亿元)')
            
            display_cols.append('update_time')
            
            # 过滤存在的列
            display_cols = [col for col in display_cols if col in result.columns]
            
            st.dataframe(
                result[display_cols].sort_values('symbol'),
                use_container_width=True,
                height=600
            )
            
            # 下载CSV
            csv = result[display_cols].to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 下载搜索结果",
                csv,
                file_name=f"股票搜索结果_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            # 显示筛选结果统计
            with st.expander("📊 筛选结果统计"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if 'pe' in result.columns:
                        avg_pe = result['pe'].mean()
                        st.metric("平均PE", f"{avg_pe:.2f}" if not pd.isna(avg_pe) else "N/A")
                with col2:
                    if 'pb' in result.columns:
                        avg_pb = result['pb'].mean()
                        st.metric("平均PB", f"{avg_pb:.2f}" if not pd.isna(avg_pb) else "N/A")
                with col3:
                    if 'price' in result.columns:
                        avg_price = result['price'].mean()
                        st.metric("平均价格", f"￥{avg_price:.2f}" if not pd.isna(avg_price) else "N/A")
                with col4:
                    st.metric("股票数量", len(result))
            
    except Exception as e:
        st.error(f"❌ 搜索失败: {e}")
        import traceback
        with st.expander("查看详细错误"):
            st.code(traceback.format_exc())

# 详细信息查看
st.markdown("---")
st.subheader("📋 查看股票详细信息")

symbol_input = st.text_input("输入股票代码", placeholder="如：000001 或 600000")

if symbol_input:
    try:
        # 使用MySQL或SQLite（根据配置）
        sys.path.insert(0, str(project_root / "data_engine"))
        from data_engine.config import DB_URL
        from data_engine.utils.db_utils import get_engine
        from sqlalchemy import text
        
        engine = get_engine(DB_URL)
        
        # 清理输入：支持6位代码或完整代码
        symbol_clean = symbol_input.strip()
        if len(symbol_clean) == 6:
            # 自动添加.SH或.SZ后缀
            if symbol_clean.startswith('6'):
                symbol_clean = symbol_clean + '.SH'
            elif symbol_clean.startswith(('0', '3')):
                symbol_clean = symbol_clean + '.SZ'
        
        # 获取最新日期
        with engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(trade_date) FROM stock_market_daily"))
            latest_date = result.fetchone()[0]
        
        if not latest_date:
            st.error("❌ 数据库中没有市场数据，请先下载数据")
            st.stop()
        
        # 使用参数化查询
        query = """
            SELECT 
                b.ts_code,
                SUBSTR(b.ts_code, 1, 6) as symbol,
                COALESCE(b.code_name, b.name) as name,
                b.industry,
                b.area,
                b.market,
                b.list_date,
                m.close as price,
                m.peTTM as pe,
                m.pbMRQ as pb,
                m.psTTM as ps,
                m.volume,
                m.amount,
                m.pct_chg as change_pct,
                m.trade_date as update_time
            FROM stock_basic_info b
            INNER JOIN stock_market_daily m ON b.ts_code = m.ts_code
            WHERE (b.ts_code = :symbol_clean OR SUBSTR(b.ts_code, 1, 6) = :symbol_input)
                AND m.trade_date = :latest_date
            LIMIT 1
        """
        
        params = {
            "symbol_clean": symbol_clean,
            "symbol_input": symbol_input.strip(),
            "latest_date": latest_date
        }
        
        try:
            info_df = pd.read_sql_query(query, engine, params=params)
        except Exception as e:
            st.error(f"❌ 查询执行失败: {e}")
            import traceback
            st.code(traceback.format_exc())
            info_df = pd.DataFrame()
        
        if not info_df.empty:
            info = info_df.iloc[0]
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**股票代码：** {info.get('symbol', info.get('ts_code', 'N/A'))}")
                st.markdown(f"**股票名称：** {info.get('name', 'N/A')}")
                st.markdown(f"**所属行业：** {info.get('industry', 'N/A')}")
                st.markdown(f"**所属地区：** {info.get('area', 'N/A')}")
                st.markdown(f"**上市市场：** {info.get('market', 'N/A')}")
                st.markdown(f"**上市日期：** {info.get('list_date', 'N/A')}")
            
            with col2:
                if pd.notna(info.get('pe')):
                    st.metric("市盈率(PE)", f"{info['pe']:.2f}")
                if pd.notna(info.get('pb')):
                    st.metric("市净率(PB)", f"{info['pb']:.2f}")
                if pd.notna(info.get('ps')):
                    st.metric("市销率(PS)", f"{info['ps']:.2f}")
                if pd.notna(info.get('price')):
                    st.metric("最新价格", f"￥{info['price']:.2f}")
                if pd.notna(info.get('change_pct')):
                    color = "normal" if info['change_pct'] >= 0 else "inverse"
                    st.metric("涨跌幅", f"{info['change_pct']:.2f}%", delta=f"{info['change_pct']:.2f}%")
                st.markdown(f"**更新时间：** {info.get('update_time', 'N/A')}")
        else:
            st.warning(f"⚠️ 未找到代码为 {symbol_input} 的股票")
            st.info("💡 提示：请检查代码是否正确，或该股票可能已退市")
    except Exception as e:
        st.error(f"❌ 查询失败: {e}")
        import traceback
        with st.expander("查看详细错误"):
            st.code(traceback.format_exc())

# 行业列表
st.markdown("---")
st.subheader("📂 行业列表")

if st.button("显示所有行业", use_container_width=True):
    if not DATA_ENGINE_DB_PATH.exists():
        st.error("❌ 数据库不存在，请先到 Data Center 页面下载数据")
        st.stop()
    
    try:
        conn = sqlite3.connect(str(DATA_ENGINE_DB_PATH))
        
        query = "SELECT DISTINCT industry FROM stock_basic_info WHERE industry IS NOT NULL AND industry != '' ORDER BY industry LIMIT 500"
        try:
            industries_df = pd.read_sql_query(query, conn)
        except sqlite3.OperationalError as e:
            st.error(f"❌ 查询执行失败: {e}")
            industries_df = pd.DataFrame()
        finally:
            conn.close()
        
        if not industries_df.empty:
            industries = industries_df['industry'].tolist()
            st.write(f"共 {len(industries)} 个行业：")
            # 按列显示
            cols_per_row = 4
            for i in range(0, len(industries), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    if i + j < len(industries):
                        with col:
                            st.text(industries[i + j])
        else:
            st.info("暂无行业数据（BaoStock可能不提供行业信息）")
            st.info("💡 可以使用其他筛选条件，如PE、PB、价格等")
    except Exception as e:
        st.error(f"❌ 获取行业列表失败: {e}")
