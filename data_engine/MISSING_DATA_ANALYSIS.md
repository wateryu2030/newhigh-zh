# BaoStock未采集数据分析

## 📊 已实现的数据接口

### 基础信息类
- ✅ `query_stock_basic` - 股票基础信息（已实现）
- ✅ `query_stock_industry` - 行业分类（已实现）

### 行情数据类
- ✅ `query_history_k_data_plus` - 历史K线数据（已实现，用于股票和指数）

### 财务数据类
- ✅ `query_profit_data` - 利润表数据（已实现）
- ⚠️ `query_balance_data` - 资产负债表（表结构已创建，未实现下载）
- ⚠️ `query_cash_flow_data` - 现金流量表（表结构已创建，未实现下载）
- ⚠️ `query_forecast_report` - 业绩预告（已实现，但数据为空）
- ⚠️ `query_performance_express_report` - 业绩快报（表结构已创建，未实现下载）
- ⚠️ `query_growth_data` - 成长能力数据（未实现）
- ⚠️ `query_operation_data` - 营运能力数据（未实现）
- ⚠️ `query_dupont_data` - 杜邦指数（未实现）
- ⚠️ `query_dividend_data` - 股息分红（未实现）

### 指数相关类
- ✅ `query_hs300_stocks` - 沪深300成分股（已实现）
- ✅ `query_sz50_stocks` - 上证50成分股（已实现）
- ✅ `query_zz500_stocks` - 中证500成分股（已实现）

### 其他类
- ⚠️ `query_adjust_factor` - 复权因子（未实现）
- ⚠️ `query_all_stock` - 查询给定日期的所有证券（未实现，与query_stock_basic类似）
- ⚠️ `query_trade_dates` - 交易日历（未实现）
- ⚠️ `query_deposit_rate_data` - 存款利率（非个股数据）
- ⚠️ `query_loan_rate_data` - 贷款利率（非个股数据）
- ⚠️ `query_money_supply_data_month` - 货币供应量（非个股数据）
- ⚠️ `query_money_supply_data_year` - 货币供应量（非个股数据）
- ⚠️ `query_required_reserve_ratio_data` - 存款准备金率（非个股数据）

---

## 🎯 未实现的个股相关数据（优先级排序）

### 高优先级（建议立即实现）

#### 1. 资产负债表数据
- **接口**: `bs.query_balance_data(code, year, quarter)`
- **表**: `stock_financials_balance`（已创建）
- **字段**: 总资产、总负债、股东权益、流动资产、流动负债等
- **用途**: 完整的财务分析，计算资产负债率、流动比率等
- **实现难度**: ⭐⭐（与利润表类似）

#### 2. 现金流量表数据
- **接口**: `bs.query_cash_flow_data(code, year, quarter)`
- **表**: `stock_financials_cashflow`（已创建）
- **字段**: 经营活动现金流、投资活动现金流、筹资活动现金流等
- **用途**: 现金流分析，评估企业资金状况
- **实现难度**: ⭐⭐（与利润表类似）

#### 3. 业绩快报数据
- **接口**: `bs.query_performance_express_report(code, start_date, end_date)`
- **表**: `stock_performance_express`（已创建）
- **字段**: 营业收入、净利润、每股收益、ROE等
- **用途**: 业绩快报分析，比正式财报更早
- **实现难度**: ⭐⭐（与业绩预告类似）

### 中优先级（建议后续实现）

#### 4. 成长能力数据
- **接口**: `bs.query_growth_data(code, year, quarter)`
- **表**: 需新建 `stock_financials_growth`
- **字段**: 营收增长率、净利润增长率、总资产增长率等
- **用途**: 成长性分析
- **实现难度**: ⭐⭐

#### 5. 营运能力数据
- **接口**: `bs.query_operation_data(code, year, quarter)`
- **表**: 需新建 `stock_financials_operation`
- **字段**: 存货周转率、应收账款周转率、总资产周转率等
- **用途**: 营运效率分析
- **实现难度**: ⭐⭐

#### 6. 杜邦指数数据
- **接口**: `bs.query_dupont_data(code, year, quarter)`
- **表**: 需新建 `stock_financials_dupont`
- **字段**: 杜邦分析相关指标
- **用途**: 杜邦分析，分解ROE
- **实现难度**: ⭐⭐

#### 7. 股息分红数据
- **接口**: `bs.query_dividend_data(code, year, yearType='report')`
- **表**: 需新建 `stock_dividend`
- **字段**: 分红金额、分红比例、除权除息日等
- **用途**: 股息率分析，高股息策略
- **实现难度**: ⭐⭐

### 低优先级（可选实现）

#### 8. 复权因子数据
- **接口**: `bs.query_adjust_factor(code, start_date, end_date)`
- **表**: 需新建 `stock_adjust_factor`
- **字段**: 前复权因子、后复权因子
- **用途**: 价格复权计算
- **实现难度**: ⭐
- **说明**: 如果使用BaoStock的adjustflag参数，可能不需要单独存储

#### 9. 交易日历
- **接口**: `bs.query_trade_dates(start_date, end_date)`
- **表**: 需新建 `trade_calendar`
- **字段**: 交易日、是否交易日
- **用途**: 交易日判断，数据完整性检查
- **实现难度**: ⭐

---

## 📋 实现建议

### 立即实现（高优先级）
1. **资产负债表** - 参考 `fetch_profit_data` 实现
2. **现金流量表** - 参考 `fetch_profit_data` 实现
3. **业绩快报** - 参考 `fetch_performance_forecast` 实现

### 后续实现（中优先级）
4. **成长能力数据** - 新建表和下载函数
5. **营运能力数据** - 新建表和下载函数
6. **杜邦指数** - 新建表和下载函数
7. **股息分红** - 新建表和下载函数

### 可选实现（低优先级）
8. **复权因子** - 如果确实需要
9. **交易日历** - 用于数据完整性检查

---

## 🔧 实现模板

可以参考以下模板快速实现新的财务数据下载：

```python
@retry(tries=5, delay=1.0)
def fetch_balance_data(ts_codes: pd.Series, years=None, quarters=None):
    """获取资产负债表数据（季频）"""
    # 参考 fetch_profit_data 的实现
    # 使用 bs.query_balance_data(code, year, quarter)
    # 写入 stock_financials_balance 表
    pass
```

---

## 📊 数据完整性评估

### 当前数据覆盖
- ✅ 基础信息: 100%
- ✅ 行情数据: 100%（日K）
- ⚠️ 财务数据: 约30%（只有利润表）
- ✅ 指数数据: 100%
- ✅ 成分股: 100%

### 完整财务数据需要
- 利润表 ✅
- 资产负债表 ⚠️
- 现金流量表 ⚠️
- 成长能力 ⚠️
- 营运能力 ⚠️
- 杜邦指数 ⚠️

---

## 💡 总结

**未实现的个股相关数据（共9类）**：
1. 资产负债表（高优先级）
2. 现金流量表（高优先级）
3. 业绩快报（高优先级）
4. 成长能力数据（中优先级）
5. 营运能力数据（中优先级）
6. 杜邦指数（中优先级）
7. 股息分红（中优先级）
8. 复权因子（低优先级）
9. 交易日历（低优先级）

**建议**：优先实现资产负债表、现金流量表和业绩快报，这三类数据对完整的财务分析至关重要。

