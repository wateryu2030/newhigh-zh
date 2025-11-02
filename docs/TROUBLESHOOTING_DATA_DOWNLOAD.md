# 数据下载问题排查指南

## 📋 常见问题

### 问题1: PE、PB等财务指标为None

**症状**: 下载的数据中，PE、PB、市值等字段都是空的（None）

**原因分析**:
1. `stock_zh_a_spot_em()`接口调用失败（最常见）
   - 代理配置问题
   - 网络连接不稳定
   - 数据源服务器临时不可用
2. 列名匹配失败
   - AKShare返回的列名与预期不符
   - 数据格式变化

**解决方案**:

#### 方案A: 检查网络和代理
```bash
# 1. 检查系统代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 2. 临时禁用代理
unset HTTP_PROXY
unset HTTPS_PROXY
unset http_proxy
unset https_proxy

# 3. 重新运行下载脚本
python scripts/fetch_cn_stock_basic_complete.py
```

#### 方案B: 手动测试AKShare接口
```python
import akshare as ak
import os

# 清除代理
for var in ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy']:
    os.environ.pop(var, None)

# 测试接口
try:
    spot = ak.stock_zh_a_spot_em()
    print(f"成功获取 {len(spot)} 条数据")
    print(f"列名: {list(spot.columns)}")
    print(spot.head())
except Exception as e:
    print(f"错误: {e}")
```

#### 方案C: 查看下载日志
下载脚本会输出详细的调试信息：
- 实际获取到的列名
- 数据完整性检查结果
- 错误信息

查看这些信息可以帮助定位问题。

### 问题2: 数据库查询失败

**症状**: Web界面显示"数据库查询失败"

**原因**: 
- 数据库文件不存在
- 表结构不匹配
- 数据库文件损坏

**解决方案**:
```bash
# 1. 检查数据库文件
ls -lh data/a_share_basic.db

# 2. 检查表结构
sqlite3 data/a_share_basic.db ".schema stock_data"

# 3. 重新运行下载脚本（会自动创建数据库和表）
python scripts/fetch_cn_stock_basic_complete.py
```

### 问题3: 数据不完整（部分字段为空）

**症状**: 某些字段有数据，某些字段为空

**可能原因**:
1. 数据源本身不完整
2. 列名匹配失败
3. 数据格式转换失败

**解决方案**:
1. 查看下载日志中的数据完整性检查
2. 检查CSV文件，确认原始数据是否有值
3. 如果原始数据有值但保存后为空，检查数据清洗逻辑

## 🔍 调试步骤

### 步骤1: 检查当前数据状态
```bash
# 检查CSV文件
head -5 data/stock_basic.csv

# 检查数据库
sqlite3 data/a_share_basic.db "SELECT COUNT(*) FROM stock_data;"
sqlite3 data/a_share_basic.db "SELECT COUNT(pe) as pe_count, COUNT(pb) as pb_count FROM stock_data;"
```

### 步骤2: 手动测试AKShare接口
使用上面的"方案B"手动测试接口，确认接口是否可用。

### 步骤3: 查看详细日志
重新运行下载脚本，查看完整的输出日志：
```bash
python scripts/fetch_cn_stock_basic_complete.py 2>&1 | tee download.log
```

关键信息：
- `实际获取到的列名`: 确认AKShare返回的列名
- `包含PE/PB相关的列`: 确认是否找到PE/PB列
- `数据完整性检查`: 查看各字段的数据覆盖率

### 步骤4: 检查网络连接
```bash
# 测试数据源连接
curl -I https://82.push2.eastmoney.com

# 如果失败，可能是网络或代理问题
```

## 🚀 推荐的解决流程

1. **清除代理环境变量**
   ```bash
   unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
   ```

2. **重新运行下载脚本**
   ```bash
   python scripts/fetch_cn_stock_basic_complete.py
   ```

3. **检查日志输出**
   - 确认是否成功获取实时行情数据
   - 查看列名匹配情况
   - 查看数据完整性统计

4. **如果仍然失败**
   - 检查网络连接
   - 尝试在不同时间重试（避开高峰）
   - 考虑使用Tushare（需要Token和实名认证）

## 📝 数据完整性验证

下载完成后，应该检查：
1. **总记录数**: 应该有5000+条
2. **PE覆盖率**: 应该>80%（如果有数据）
3. **PB覆盖率**: 应该>80%（如果有数据）
4. **价格覆盖率**: 应该>90%

如果覆盖率很低，说明数据获取不完整，需要重新下载。

## 💡 最佳实践

1. **定期更新**: 建议每天更新一次数据
2. **网络环境**: 在稳定的网络环境下下载
3. **避开高峰**: 避开市场开盘/收盘时段
4. **备份数据**: 保留之前的CSV文件作为备份

