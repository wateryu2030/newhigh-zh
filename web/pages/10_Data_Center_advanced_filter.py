"""
高级筛选功能模块
提供综合筛选功能，包括快速筛选、高级筛选和预设模板
"""

import pandas as pd
import streamlit as st
from web.utils.data_cleaner import clean_duplicate_columns

def apply_quick_filter(df, mv_range, pe_range, pb_range, price_range, selected_industry):
    """应用快速筛选"""
    display_df = df.copy()
    display_df = clean_duplicate_columns(display_df, keep_first=False)
    
    has_mv = 'total_mv' in display_df.columns and display_df['total_mv'].notna().any()
    has_pe = 'pe' in display_df.columns and display_df['pe'].notna().any()
    has_pb = 'pb' in display_df.columns and display_df['pb'].notna().any()
    has_price = 'price' in display_df.columns and display_df['price'].notna().any()
    
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
    return display_df


def apply_advanced_filter(df, filter_params):
    """应用高级筛选"""
    display_df = df.copy()
    display_df = clean_duplicate_columns(display_df, keep_first=False)
    
    # 估值指标筛选
    if filter_params.get('pe_enable') and filter_params.get('pe_min') is not None:
        if 'pe' in display_df.columns:
            display_df = display_df[
                (display_df['pe'] >= filter_params['pe_min']) &
                (display_df['pe'] <= filter_params['pe_max'])
            ]
    
    if filter_params.get('pb_enable') and filter_params.get('pb_min') is not None:
        if 'pb' in display_df.columns:
            display_df = display_df[
                (display_df['pb'] >= filter_params['pb_min']) &
                (display_df['pb'] <= filter_params['pb_max'])
            ]
    
    if filter_params.get('ps_enable') and filter_params.get('ps_min') is not None:
        if 'ps' in display_df.columns:
            display_df = display_df[
                (display_df['ps'] >= filter_params['ps_min']) &
                (display_df['ps'] <= filter_params['ps_max'])
            ]
    
    if filter_params.get('price_enable') and filter_params.get('price_min') is not None:
        if 'price' in display_df.columns:
            display_df = display_df[
                (display_df['price'] >= filter_params['price_min']) &
                (display_df['price'] <= filter_params['price_max'])
            ]
    
    # 财务指标筛选
    if filter_params.get('roe_enable') and filter_params.get('roe_min') is not None:
        if 'roe' in display_df.columns:
            display_df = display_df[
                (display_df['roe'] >= filter_params['roe_min']) &
                (display_df['roe'] <= filter_params['roe_max'])
            ]
    
    if filter_params.get('roa_enable') and filter_params.get('roa_min') is not None:
        if 'roa' in display_df.columns:
            display_df = display_df[
                (display_df['roa'] >= filter_params['roa_min']) &
                (display_df['roa'] <= filter_params['roa_max'])
            ]
    
    if filter_params.get('revenue_enable') and filter_params.get('revenue_min') is not None:
        if 'revenue_yoy' in display_df.columns:
            display_df = display_df[
                (display_df['revenue_yoy'] >= filter_params['revenue_min']) &
                (display_df['revenue_yoy'] <= filter_params['revenue_max'])
            ]
    
    if filter_params.get('profit_enable') and filter_params.get('profit_min') is not None:
        if 'net_profit_yoy' in display_df.columns:
            display_df = display_df[
                (display_df['net_profit_yoy'] >= filter_params['profit_min']) &
                (display_df['net_profit_yoy'] <= filter_params['profit_max'])
            ]
    
    # 市值指标筛选
    if filter_params.get('mv_enable') and filter_params.get('mv_min') is not None:
        if 'total_mv' in display_df.columns:
            display_df = display_df[
                (display_df['total_mv'] / 1e8 >= filter_params['mv_min']) &
                (display_df['total_mv'] / 1e8 <= filter_params['mv_max'])
            ]
    
    if filter_params.get('circ_mv_enable') and filter_params.get('circ_mv_min') is not None:
        if 'circ_mv' in display_df.columns:
            display_df = display_df[
                (display_df['circ_mv'] / 1e8 >= filter_params['circ_mv_min']) &
                (display_df['circ_mv'] / 1e8 <= filter_params['circ_mv_max'])
            ]
    
    if filter_params.get('turnover_enable') and filter_params.get('turnover_min') is not None:
        if 'turnover_rate' in display_df.columns:
            display_df = display_df[
                (display_df['turnover_rate'] >= filter_params['turnover_min']) &
                (display_df['turnover_rate'] <= filter_params['turnover_max'])
            ]
    
    if filter_params.get('change_enable') and filter_params.get('change_min') is not None:
        if 'change_pct' in display_df.columns:
            display_df = display_df[
                (display_df['change_pct'] >= filter_params['change_min']) &
                (display_df['change_pct'] <= filter_params['change_max'])
            ]
    
    # 分类筛选
    if filter_params.get('industry_enable') and filter_params.get('selected_industry') != '全部':
        if 'industry' in display_df.columns:
            display_df = display_df[display_df['industry'] == filter_params['selected_industry']]
    
    if filter_params.get('area_enable') and filter_params.get('selected_area') != '全部':
        if 'area' in display_df.columns:
            display_df = display_df[display_df['area'] == filter_params['selected_area']]
    
    if filter_params.get('market_enable') and filter_params.get('selected_market') != '全部':
        if 'market' in display_df.columns:
            display_df = display_df[display_df['market'] == filter_params['selected_market']]
    
    if filter_params.get('list_date_enable') and filter_params.get('date_min') is not None:
        if 'list_date' in display_df.columns:
            display_df['list_date'] = pd.to_datetime(display_df['list_date'], errors='coerce')
            display_df = display_df[
                (display_df['list_date'] >= pd.to_datetime(filter_params['date_min'])) &
                (display_df['list_date'] <= pd.to_datetime(filter_params['date_max']))
            ]
    
    display_df = clean_duplicate_columns(display_df, keep_first=False)
    return display_df


def apply_template_filter(df, template):
    """应用预设模板筛选"""
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
    
    display_df = clean_duplicate_columns(display_df, keep_first=False)
    return display_df

