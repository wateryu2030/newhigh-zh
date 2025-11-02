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
    pre_close DOUBLE,
    pct_chg DOUBLE,
    vol BIGINT,
    amount DOUBLE,
    turnover_rate DOUBLE,
    amplitude DOUBLE,
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
