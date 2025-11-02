-- SQLite版本数据库初始化脚本
-- 注意: SQLite不支持BIGINT AUTO_INCREMENT，使用INTEGER PRIMARY KEY AUTOINCREMENT

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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code VARCHAR(20),
    trade_date DATE,
    pe REAL,
    pb REAL,
    ps REAL,
    pcf REAL,
    roe REAL,
    roa REAL,
    eps REAL,
    bps REAL,
    total_mv REAL,
    circ_mv REAL,
    revenue_yoy REAL,
    net_profit_yoy REAL,
    gross_profit_margin REAL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date)
);

-- 3. 日行情（K线）
CREATE TABLE IF NOT EXISTS stock_market_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code VARCHAR(20),
    trade_date DATE,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    preclose REAL,
    pct_chg REAL,
    volume INTEGER,
    amount REAL,
    turnover_rate REAL,
    amplitude REAL,
    peTTM REAL,
    pbMRQ REAL,
    psTTM REAL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date)
);

-- 4. 技术指标（由本地计算生成）
CREATE TABLE IF NOT EXISTS stock_technical_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code VARCHAR(20),
    trade_date DATE,
    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    rsi REAL,
    macd REAL,
    kdj_k REAL,
    kdj_d REAL,
    atr REAL,
    volatility REAL,
    UNIQUE(ts_code, trade_date)
);

-- 5. 资金流向
CREATE TABLE IF NOT EXISTS stock_moneyflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code VARCHAR(20),
    trade_date DATE,
    net_mf_amount REAL,
    net_mf_ratio REAL,
    super_large REAL,
    large REAL,
    medium REAL,
    small REAL,
    UNIQUE(ts_code, trade_date)
);

-- 6. 行业/概念映射
CREATE TABLE IF NOT EXISTS stock_concept_industry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code VARCHAR(20),
    concept VARCHAR(100),
    industry_sw VARCHAR(100),
    industry_csrc VARCHAR(100),
    UNIQUE(ts_code, concept)
);

-- 7. 市场指数（用于基准/α计算）
CREATE TABLE IF NOT EXISTS market_index_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_code VARCHAR(20),
    name VARCHAR(100),
    trade_date DATE,
    close REAL,
    pct_chg REAL,
    pe REAL,
    pb REAL,
    UNIQUE(index_code, trade_date)
);

-- 创建索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_stock_basic_symbol ON stock_basic_info(symbol);
CREATE INDEX IF NOT EXISTS idx_financials_ts_date ON stock_financials(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_market_daily_ts_date ON stock_market_daily(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_technical_ts_date ON stock_technical_indicators(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_moneyflow_ts_date ON stock_moneyflow(ts_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_index_daily_code_date ON market_index_daily(index_code, trade_date);
