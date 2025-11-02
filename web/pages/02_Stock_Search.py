#!/usr/bin/env python3
"""
股票搜索页面
支持按代码、名称、行业、PE、PB、市值等条件搜索
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.a_share_downloader import AShareDownloader, get_downloader
from tradingagents.dataflows.stock_search import StockSearcher, get_searcher

# 设置页面配置（英文标题，避免URL编码问题）
st.set_page_config(page_title="股票搜索", page_icon="🔍", layout="wide")
st.title("🔍 A股股票搜索")

# 侧边栏：数据管理
with st.sidebar:
    st.header("📊 数据管理")
    
    st.markdown("### 📥 数据下载")
    
    # 下载选项
    use_cache = st.checkbox("使用缓存（仅更新缺失数据）", value=False, help="勾选后只下载新数据，不勾选则全量更新")
    
    if st.button("🔄 一键下载/更新所有A股数据", type="primary", use_container_width=True):
        progress_container = st.container()
        status_container = st.container()
        
        with status_container:
            st.info("📥 开始下载，请耐心等待（首次下载可能需要5-15分钟）...")
        
        try:
            downloader = get_downloader()
            
            # 显示进度信息
            progress_bar = progress_container.progress(0)
            status_text = status_container.empty()
            
            # 模拟进度更新（实际进度由下载器内部处理）
            import time
            status_messages = [
                "🔍 连接数据源...",
                "📊 获取股票列表...",
                "⏳ 分批下载数据...",
                "💾 保存到数据库...",
                "✅ 完成！"
            ]
            
            for i, msg in enumerate(status_messages):
                status_text.info(msg)
                progress_bar.progress((i + 1) / len(status_messages))
                time.sleep(0.5)
            
            # 实际下载
            status_text.info("📥 正在下载数据，请稍候（这可能需要几分钟）...")
            df = downloader.download_all_stocks(use_cache=use_cache)
            
            if not df.empty:
                progress_bar.progress(1.0)
                status_text.empty()
                
                st.success(f"✅ 成功更新 {len(df)} 只股票数据！")
                
                # 显示数据统计
                with st.expander("📊 查看下载统计", expanded=False):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("总股票数", len(df))
                    with col2:
                        st.metric("有PE数据", df['pe'].notna().sum())
                    with col3:
                        st.metric("有PB数据", df['pb'].notna().sum())
                    with col4:
                        st.metric("行业数量", df['industry'].nunique())
                    
                    # 数据预览
                    st.markdown("**数据预览（前10条）:**")
                    preview_cols = ['symbol', 'name', 'industry', 'pe', 'pb']
                    preview_cols = [col for col in preview_cols if col in df.columns]
                    st.dataframe(df[preview_cols].head(10), use_container_width=True)
                
                # 刷新页面数据
                st.rerun()
            else:
                status_text.error("❌ 数据更新失败：未获取到任何数据")
                st.error("""
                ❌ 下载失败，可能的原因：
                1. API密钥未配置或已过期
                2. 网络连接问题
                3. 数据源服务暂时不可用
                
                💡 解决建议：
                - 检查 `.env` 文件中的 `TUSHARE_TOKEN` 配置
                - 等待几分钟后重试
                - 查看控制台日志了解详细错误
                """)
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ 下载过程出错: {error_msg}")
            
            # 提供更友好的错误提示
            if "Too Many Requests" in error_msg or "Rate limited" in error_msg:
                st.warning("""
                ⚠️ **API频率限制**
                
                系统已自动重试，但可能仍然达到频率上限。建议：
                - 等待5-10分钟后重试
                - 勾选"使用缓存"选项，减少API调用
                - 升级Tushare账户获取更高配额
                """)
            elif "token" in error_msg.lower() or "密钥" in error_msg:
                st.warning("""
                ⚠️ **API密钥问题**
                
                请检查：
                - `.env` 文件中的 `TUSHARE_TOKEN` 是否正确
                - API密钥是否已激活
                - 账户积分是否充足
                """)
            else:
                st.info("💡 提示：首次使用请确保已配置API密钥（见README.md）")
    
    # 数据统计
    try:
        searcher = get_searcher()
        all_stocks = searcher.downloader.search_stocks(limit=1)
        if not all_stocks.empty:
            total_count = len(searcher.downloader.search_stocks(limit=100000))
            st.metric("数据库股票总数", total_count)
            
            industries = searcher.get_industry_list()
            st.metric("行业数量", len(industries))
    except Exception as e:
        st.warning(f"⚠️ 无法连接数据库: {e}")

# 主搜索区域
col1, col2, col3 = st.columns(3)

with col1:
    keyword = st.text_input("🔎 关键字搜索", placeholder="输入代码或名称，如：000001 或 平安")

with col2:
    industry = st.text_input("🏢 行业筛选", placeholder="如：银行、科技、医药")

with col3:
    min_market_cap = st.number_input("💰 最小市值(亿元)", min_value=0.0, value=0.0, step=10.0)

col4, col5 = st.columns(2)

with col4:
    max_pe = st.number_input("📊 最大市盈率(PE)", min_value=0.0, value=100.0, step=5.0)

with col5:
    max_pb = st.number_input("📈 最大市净率(PB)", min_value=0.0, value=10.0, step=0.5)

limit = st.slider("返回数量", min_value=10, max_value=500, value=100)

if st.button("🔍 搜索", type="primary", use_container_width=True):
    try:
        searcher = get_searcher()
        
        result = searcher.search(
            keyword=keyword if keyword else None,
            industry=industry if industry else None,
            min_market_cap=min_market_cap if min_market_cap > 0 else None,
            max_pe=max_pe if max_pe < 1000 else None,
            max_pb=max_pb if max_pb < 1000 else None,
            limit=limit
        )
        
        if result.empty:
            st.warning("⚠️ 未找到符合条件的股票")
        else:
            st.success(f"✅ 找到 {len(result)} 只股票")
            
            # 显示结果
            display_cols = ['symbol', 'name', 'industry', 'market', 'pe', 'pb']
            
            # 市值转换为亿元显示
            if 'total_mv' in result.columns:
                result['市值(亿元)'] = result['total_mv'] / 1e8
                display_cols.append('市值(亿元)')
            
            if 'circ_mv' in result.columns:
                result['流通市值(亿元)'] = result['circ_mv'] / 1e8
                display_cols.append('流通市值(亿元)')
            
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
            
    except Exception as e:
        st.error(f"❌ 搜索失败: {e}")
        st.info("💡 提示：如果是首次使用，请先在侧边栏点击'更新股票数据'下载数据")

# 详细信息查看
st.markdown("---")
st.subheader("📋 查看股票详细信息")

symbol_input = st.text_input("输入股票代码", placeholder="如：000001")

if symbol_input:
    try:
        searcher = get_searcher()
        info = searcher.get_info(symbol_input.strip())
        
        if info:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**股票代码：** {info['symbol']}")
                st.markdown(f"**股票名称：** {info['name']}")
                st.markdown(f"**所属行业：** {info.get('industry', 'N/A')}")
                st.markdown(f"**所属地区：** {info.get('area', 'N/A')}")
                st.markdown(f"**上市市场：** {info.get('market', 'N/A')}")
                st.markdown(f"**上市日期：** {info.get('list_date', 'N/A')}")
            
            with col2:
                if info.get('pe'):
                    st.metric("市盈率(PE)", f"{info['pe']:.2f}")
                if info.get('pb'):
                    st.metric("市净率(PB)", f"{info['pb']:.2f}")
                if info.get('total_mv'):
                    st.metric("总市值", f"{info['total_mv']/1e8:.2f}亿元")
                if info.get('circ_mv'):
                    st.metric("流通市值", f"{info['circ_mv']/1e8:.2f}亿元")
                st.markdown(f"**更新时间：** {info.get('update_time', 'N/A')}")
        else:
            st.warning(f"⚠️ 未找到代码为 {symbol_input} 的股票")
    except Exception as e:
        st.error(f"❌ 查询失败: {e}")

# 行业列表
st.markdown("---")
st.subheader("📂 行业列表")

if st.button("显示所有行业", use_container_width=True):
    try:
        searcher = get_searcher()
        industries = searcher.get_industry_list()
        
        if industries:
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
            st.info("暂无行业数据，请先更新股票数据")
    except Exception as e:
        st.error(f"❌ 获取行业列表失败: {e}")

