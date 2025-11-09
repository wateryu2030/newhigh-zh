CREATE DATABASE IF NOT EXISTS stock_db DEFAULT CHARSET utf8mb4;
USE stock_db;

-- 1. 股票基础信息
CREATE TABLE IF NOT EXISTS stock_basic_info (
    ts_code VARCHAR(20) PRIMARY KEY,
    symbol VARCHAR(20),
    name VARCHAR(100),
    area VARCHAR(50),
    industry VARCHAR(100),
    market VARCHAR(20),
    list_date DATE,
    delist_date DATE,
    is_hs VARCHAR(5)
);

-- 2. 财务与估值快照（来自日频/实时表的聚合，也可直接存日频）
CREATE TABLE IF NOT EXISTS stock_financials (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    trade_date DATE,
    pe DOUBLE,
    pb DOUBLE,
    ps DOUBLE,
    pcf DOUBLE,
    roe DOUBLE,
    roa DOUBLE,
    eps DOUBLE,
    bps DOUBLE,
    total_mv DOUBLE,
    circ_mv DOUBLE,
    revenue_yoy DOUBLE,
    net_profit_yoy DOUBLE,
    gross_profit_margin DOUBLE,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date)
);

-- 3. 日行情（K线）
CREATE TABLE IF NOT EXISTS stock_market_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    trade_date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    preclose DOUBLE,
    pct_chg DOUBLE,
    volume BIGINT,
    amount DOUBLE,
    turnover_rate DOUBLE,
    amplitude DOUBLE,
    peTTM DOUBLE,
    pbMRQ DOUBLE,
    psTTM DOUBLE,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date)
);

-- 4. 技术指标（由本地计算生成）
CREATE TABLE IF NOT EXISTS stock_technical_indicators (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    trade_date DATE,
    ma5 DOUBLE,
    ma20 DOUBLE,
    ma60 DOUBLE,
    rsi DOUBLE,
    macd DOUBLE,
    kdj_k DOUBLE,
    kdj_d DOUBLE,
    atr DOUBLE,
    volatility DOUBLE,
    UNIQUE(ts_code, trade_date)
);

-- 5. 资金流向
CREATE TABLE IF NOT EXISTS stock_moneyflow (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    trade_date DATE,
    net_mf_amount DOUBLE,
    net_mf_ratio DOUBLE,
    super_large DOUBLE,
    large DOUBLE,
    medium DOUBLE,
    small DOUBLE,
    UNIQUE(ts_code, trade_date)
);

-- 6. 行业/概念映射
CREATE TABLE IF NOT EXISTS stock_concept_industry (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20),
    concept VARCHAR(100),
    industry_sw VARCHAR(100),
    industry_csrc VARCHAR(100),
    UNIQUE(ts_code, concept)
);

-- 7. 市场指数（用于基准/α计算）
CREATE TABLE IF NOT EXISTS market_index_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    index_code VARCHAR(20),
    name VARCHAR(100),
    trade_date DATE,
    close DOUBLE,
    pct_chg DOUBLE,
    pe DOUBLE,
    pb DOUBLE,
    UNIQUE(index_code, trade_date)
);

-- 创建索引以提升查询性能
-- MySQL语法：需要手动检查索引是否存在或直接创建（如果不存在会报错但可忽略）
CREATE INDEX idx_stock_basic_symbol ON stock_basic_info(symbol);
CREATE INDEX idx_financials_ts_date ON stock_financials(ts_code, trade_date);
CREATE INDEX idx_market_daily_ts_date ON stock_market_daily(ts_code, trade_date);
CREATE INDEX idx_technical_ts_date ON stock_technical_indicators(ts_code, trade_date);
CREATE INDEX idx_moneyflow_ts_date ON stock_moneyflow(ts_code, trade_date);
CREATE INDEX idx_index_daily_code_date ON market_index_daily(index_code, trade_date);

CREATE TABLE IF NOT EXISTS stock_industry_classified (
    ts_code VARCHAR(20) PRIMARY KEY,
    industry VARCHAR(128) NULL,
    industry_classification VARCHAR(128) NULL,
    update_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE stock_basic_info
    ADD COLUMN IF NOT EXISTS industry VARCHAR(128) NULL AFTER status;

ALTER TABLE stock_market_daily
    ADD COLUMN IF NOT EXISTS turnover_rate DOUBLE NULL,
    ADD COLUMN IF NOT EXISTS total_mv DOUBLE NULL,
    ADD COLUMN IF NOT EXISTS float_mv DOUBLE NULL,
    ADD COLUMN IF NOT EXISTS capitalization DOUBLE NULL,
    ADD COLUMN IF NOT EXISTS circulating_cap DOUBLE NULL;

ALTER TABLE stock_financials
    ADD COLUMN IF NOT EXISTS total_mv DOUBLE NULL,
    ADD COLUMN IF NOT EXISTS circ_mv DOUBLE NULL;