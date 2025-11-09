-- 扩展数据库表结构
-- 用于存储BaoStock提供的额外数据

USE stock_db;

-- ==================== 财务数据表 ====================

-- 利润表（季频）
CREATE TABLE IF NOT EXISTS stock_financials_profit (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    year INT,
    quarter INT,
    trade_date DATE,
    -- 利润表主要字段
    revenue DOUBLE COMMENT '营业收入',
    operating_profit DOUBLE COMMENT '营业利润',
    total_profit DOUBLE COMMENT '利润总额',
    net_profit DOUBLE COMMENT '净利润',
    eps DOUBLE COMMENT '每股收益',
    roe DOUBLE COMMENT '净资产收益率',
    gross_profit_margin DOUBLE COMMENT '销售毛利率',
    net_profit_margin DOUBLE COMMENT '销售净利率',
    -- 其他字段（根据BaoStock实际返回字段调整）
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_year_quarter (ts_code, year, quarter),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='利润表（季频）';

-- 资产负债表（季频）- BaoStock返回的是比率数据，不是绝对值
CREATE TABLE IF NOT EXISTS stock_financials_balance (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    year INT,
    quarter INT,
    trade_date DATE,
    -- BaoStock实际返回的比率字段
    current_ratio DOUBLE COMMENT '流动比率',
    quick_ratio DOUBLE COMMENT '速动比率',
    cash_ratio DOUBLE COMMENT '现金比率',
    yoy_liability DOUBLE COMMENT '负债同比增长率',
    liability_to_asset DOUBLE COMMENT '资产负债率',
    asset_to_equity DOUBLE COMMENT '权益乘数',
    -- 其他字段
    pub_date DATE COMMENT '发布日期',
    stat_date DATE COMMENT '统计日期',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_year_quarter (ts_code, year, quarter),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资产负债表（季频）- 比率数据';

-- 现金流量表（季频）
CREATE TABLE IF NOT EXISTS stock_financials_cashflow (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    year INT,
    quarter INT,
    trade_date DATE,
    -- 现金流量表主要字段
    operating_cashflow DOUBLE COMMENT '经营活动产生的现金流量净额',
    investing_cashflow DOUBLE COMMENT '投资活动产生的现金流量净额',
    financing_cashflow DOUBLE COMMENT '筹资活动产生的现金流量净额',
    net_cashflow DOUBLE COMMENT '现金及现金等价物净增加额',
    -- 其他字段
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_year_quarter (ts_code, year, quarter),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='现金流量表（季频）';

-- 业绩预告
CREATE TABLE IF NOT EXISTS stock_performance_forecast (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    report_date DATE COMMENT '报告期',
    publish_date DATE COMMENT '发布日期',
    forecast_type VARCHAR(50) COMMENT '预告类型',
    forecast_net_profit DOUBLE COMMENT '预告净利润',
    forecast_profit_change_pct DOUBLE COMMENT '预告净利润变动幅度(%)',
    forecast_revenue DOUBLE COMMENT '预告营业收入',
    forecast_revenue_change_pct DOUBLE COMMENT '预告营业收入变动幅度(%)',
    content TEXT COMMENT '预告内容',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ts_code (ts_code),
    INDEX idx_report_date (report_date),
    INDEX idx_publish_date (publish_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='业绩预告';

-- 业绩快报
CREATE TABLE IF NOT EXISTS stock_performance_express (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    report_date DATE COMMENT '报告期',
    publish_date DATE COMMENT '发布日期',
    revenue DOUBLE COMMENT '营业收入',
    operating_profit DOUBLE COMMENT '营业利润',
    total_profit DOUBLE COMMENT '利润总额',
    net_profit DOUBLE COMMENT '净利润',
    eps DOUBLE COMMENT '每股收益',
    roe DOUBLE COMMENT '净资产收益率',
    total_assets DOUBLE COMMENT '总资产',
    shareholders_equity DOUBLE COMMENT '股东权益合计',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_report (ts_code, report_date),
    INDEX idx_ts_code (ts_code),
    INDEX idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='业绩快报';

-- ==================== 成分股数据 ====================

-- 指数成分股
CREATE TABLE IF NOT EXISTS index_constituents (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    index_key VARCHAR(20) COMMENT '指数标识（hs300/sz50/zz500）',
    index_name VARCHAR(100) COMMENT '指数名称',
    ts_code VARCHAR(20) COMMENT '股票代码',
    code VARCHAR(20) COMMENT '原始代码',
    code_name VARCHAR(100) COMMENT '股票名称',
    weight DOUBLE COMMENT '权重',
    date DATE COMMENT '日期',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_index_code_date (index_key, ts_code, date),
    INDEX idx_index_key (index_key),
    INDEX idx_ts_code (ts_code),
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数成分股';

-- ==================== 更新现有表结构 ====================

-- 更新market_index_daily表，添加更多字段（如果不存在）
-- 注意：MySQL不支持IF NOT EXISTS，需要手动检查或忽略错误
-- ALTER TABLE market_index_daily 
--     ADD COLUMN open DOUBLE COMMENT '开盘价' AFTER name,
--     ADD COLUMN high DOUBLE COMMENT '最高价' AFTER open,
--     ADD COLUMN low DOUBLE COMMENT '最低价' AFTER high,
--     ADD COLUMN preclose DOUBLE COMMENT '昨收价' AFTER close,
--     ADD COLUMN volume BIGINT COMMENT '成交量' AFTER pct_chg,
--     ADD COLUMN amount DOUBLE COMMENT '成交额' AFTER volume;

-- 更新stock_concept_industry表，确保字段完整
-- 注意：MySQL不支持IF NOT EXISTS，需要手动检查或忽略错误
-- ALTER TABLE stock_concept_industry
--     MODIFY COLUMN ts_code VARCHAR(20) NOT NULL,
--     MODIFY COLUMN concept VARCHAR(100) DEFAULT NULL,
--     MODIFY COLUMN industry_sw VARCHAR(100) DEFAULT NULL COMMENT '申万行业',
--     MODIFY COLUMN industry_csrc VARCHAR(100) DEFAULT NULL COMMENT '证监会行业',
--     ADD INDEX idx_ts_code (ts_code),
--     ADD INDEX idx_industry_sw (industry_sw);

-- ==================== 中优先级数据表 ====================

-- 成长能力数据（季频）
CREATE TABLE IF NOT EXISTS stock_financials_growth (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    year INT,
    quarter INT,
    trade_date DATE,
    -- 成长能力主要字段
    revenue_yoy DOUBLE COMMENT '营业收入同比增长率(%)',
    net_profit_yoy DOUBLE COMMENT '净利润同比增长率(%)',
    total_assets_yoy DOUBLE COMMENT '总资产同比增长率(%)',
    shareholders_equity_yoy DOUBLE COMMENT '股东权益同比增长率(%)',
    -- 其他字段（根据BaoStock实际返回字段调整）
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_year_quarter (ts_code, year, quarter),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成长能力数据（季频）';

-- 营运能力数据（季频）
CREATE TABLE IF NOT EXISTS stock_financials_operation (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    year INT,
    quarter INT,
    trade_date DATE,
    -- 营运能力主要字段
    inventory_turnover DOUBLE COMMENT '存货周转率',
    receivables_turnover DOUBLE COMMENT '应收账款周转率',
    total_assets_turnover DOUBLE COMMENT '总资产周转率',
    current_assets_turnover DOUBLE COMMENT '流动资产周转率',
    -- 其他字段（根据BaoStock实际返回字段调整）
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_year_quarter (ts_code, year, quarter),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='营运能力数据（季频）';

-- 杜邦指数数据（季频）
CREATE TABLE IF NOT EXISTS stock_financials_dupont (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    year INT,
    quarter INT,
    trade_date DATE,
    -- 杜邦分析主要字段
    roe DOUBLE COMMENT '净资产收益率(ROE)',
    net_profit_margin DOUBLE COMMENT '销售净利率',
    total_assets_turnover DOUBLE COMMENT '总资产周转率',
    equity_multiplier DOUBLE COMMENT '权益乘数',
    -- 其他字段（根据BaoStock实际返回字段调整）
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_year_quarter (ts_code, year, quarter),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='杜邦指数数据（季频）';

-- 股息分红数据
CREATE TABLE IF NOT EXISTS stock_dividend (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    year INT,
    year_type VARCHAR(20) COMMENT '年份类型：report(报告期)或operate(操作日)',
    -- 分红相关字段
    dividend_date DATE COMMENT '除权除息日',
    dividend_ratio DOUBLE COMMENT '分红比例(每10股派息)',
    dividend_amount DOUBLE COMMENT '分红金额',
    ex_dividend_date DATE COMMENT '除权除息日',
    record_date DATE COMMENT '股权登记日',
    -- 其他字段（根据BaoStock实际返回字段调整）
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ts_code (ts_code),
    INDEX idx_year (year),
    INDEX idx_dividend_date (dividend_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股息分红数据';

-- ==================== 低优先级数据表 ====================

-- 复权因子数据
CREATE TABLE IF NOT EXISTS stock_adjust_factor (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    adjust_date DATE COMMENT '除权除息日期',
    forward_factor DOUBLE COMMENT '前复权因子',
    backward_factor DOUBLE COMMENT '后复权因子',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_date (ts_code, adjust_date),
    INDEX idx_ts_code (ts_code),
    INDEX idx_adjust_date (adjust_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='复权因子数据';

-- 交易日历
CREATE TABLE IF NOT EXISTS trade_calendar (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    trade_date DATE COMMENT '日期',
    is_trade_day TINYINT(1) COMMENT '是否交易日：1-是，0-否',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_trade_date (trade_date),
    INDEX idx_is_trade_day (is_trade_day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易日历';

