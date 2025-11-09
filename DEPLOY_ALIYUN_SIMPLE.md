# 阿里云服务器部署指南（最简单方案）

## 📋 方案概述

**最简单部署方案：使用SQLite数据库 + 无需VPN + BaoStock国内直连**

### 优势
- ✅ **无需安装MySQL**：使用SQLite文件数据库，即插即用
- ✅ **无需VPN**：BaoStock是国内数据源，可直接访问
- ✅ **数据库实体化**：SQLite是单个文件，可备份、迁移、传输
- ✅ **零配置**：只需设置环境变量即可切换
- ✅ **轻量级**：适合小型服务器，资源占用小

---

## 🚀 快速部署步骤

### 1. 上传代码到服务器

```bash
# 在本地
cd TradingAgents-CN
git add .
git commit -m "准备部署到阿里云"
git push

# 在阿里云服务器上
git clone <your-github-repo-url>
cd TradingAgents-CN
```

### 2. 安装Python依赖（仅必需包）

```bash
# 安装Python 3.8+
python3 --version

# 安装必需依赖
pip3 install -r data_engine/requirements.txt

# 或者最小化安装（只安装核心包）
pip3 install pandas sqlalchemy baostock pymysql
```

### 3. 配置使用SQLite（关键步骤）

```bash
# 设置环境变量，使用SQLite
export DB_TYPE=sqlite

# 可选：设置下载速度（默认0.05秒）
export SLEEP_SEC_WEB=0.05

# 永久设置（推荐）
echo 'export DB_TYPE=sqlite' >> ~/.bashrc
source ~/.bashrc
```

### 4. 创建数据目录

```bash
cd TradingAgents-CN
mkdir -p data
mkdir -p data_engine/data_cache
```

### 5. 初始化数据库（自动）

首次运行时会自动创建SQLite数据库和表结构，无需手动初始化。

### 6. 启动数据下载

```bash
cd TradingAgents-CN

# 方式1：下载基础数据
python3 data_engine/fetch_data.py

# 方式2：下载扩展数据（财务数据等）
python3 data_engine/fetch_extended_data.py

# 方式3：后台运行
nohup python3 data_engine/fetch_extended_data.py > download.log 2>&1 &
```

---

## 📁 数据库文件位置

SQLite数据库文件位置：
```
TradingAgents-CN/data/stock_database.db
```

### 数据库文件特点
- **单个文件**：所有数据存储在一个`.db`文件中
- **可备份**：直接复制文件即可备份
- **可迁移**：复制文件到其他服务器即可使用
- **可压缩**：可以使用SQLite的VACUUM命令压缩

### 备份数据库
```bash
# 简单备份
cp data/stock_database.db data/stock_database.db.backup

# 压缩备份（减小文件大小）
sqlite3 data/stock_database.db "VACUUM;"
cp data/stock_database.db data/stock_database.db.backup
```

---

## 🔧 配置说明

### 环境变量配置（可选）

创建 `.env` 文件或在 `~/.bashrc` 中设置：

```bash
# 使用SQLite数据库
export DB_TYPE=sqlite

# 下载速度控制（秒）
export SLEEP_SEC_WEB=0.05

# 批量大小（可选）
export CACHE_BATCH_SIZE=10000
export DB_WRITE_BATCH_SIZE=200
```

### 修改配置文件（如果不想用环境变量）

编辑 `data_engine/config.py`：

```python
# 改为默认使用SQLite
_DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # 改为默认sqlite
```

---

## 📊 数据下载说明

### BaoStock数据源

- ✅ **国内直连**：无需VPN，直接访问
- ✅ **免费使用**：无需注册，直接调用API
- ✅ **数据完整**：A股所有数据
- ✅ **稳定性好**：官方数据源

### 下载的数据类型

1. **基础数据**
   - 股票基本信息（5,481只股票）
   - 市场日行情数据（K线）
   - 财务快照数据

2. **扩展数据**（可选）
   - 利润表
   - 资产负债表
   - 现金流量表
   - 成长能力、营运能力、杜邦指数
   - 股息分红
   - 业绩预告/快报

---

## 🛠️ 常见问题

### Q1: SQLite性能如何？

**A:** 对于单机使用，SQLite性能足够：
- 读取速度：与MySQL相当
- 写入速度：稍慢于MySQL，但够用
- 并发能力：支持多读单写（适合数据下载场景）

### Q2: 数据库文件会很大吗？

**A:** 取决于数据量：
- 基础数据（3年K线）：约1-2GB
- 完整财务数据：约3-5GB
- 可以使用VACUUM压缩

### Q3: 如何迁移数据库？

**A:** 直接复制文件：
```bash
# 备份
scp user@server:/path/to/stock_database.db ./backup.db

# 恢复
scp ./backup.db user@server:/path/to/stock_database.db
```

### Q4: 可以在本地开发，服务器运行吗？

**A:** 可以：
- 本地：设置 `DB_TYPE=sqlite`
- 服务器：同样设置 `DB_TYPE=sqlite`
- 数据库文件可以互相传输

---

## 📝 一键部署脚本

创建 `deploy.sh`：

```bash
#!/bin/bash
# 一键部署脚本

echo "🚀 开始部署..."

# 1. 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 2. 安装依赖
echo "📦 安装依赖..."
pip3 install pandas sqlalchemy baostock pymysql -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 设置环境变量
echo "⚙️  配置环境..."
export DB_TYPE=sqlite
echo 'export DB_TYPE=sqlite' >> ~/.bashrc

# 4. 创建目录
echo "📁 创建目录..."
mkdir -p data
mkdir -p data_engine/data_cache

# 5. 测试运行
echo "🧪 测试运行..."
python3 data_engine/fetch_data.py --help

echo "✅ 部署完成！"
echo ""
echo "💡 启动下载："
echo "   export DB_TYPE=sqlite"
echo "   python3 data_engine/fetch_extended_data.py"
```

---

## 🔍 验证部署

### 检查数据库

```bash
# 检查SQLite文件是否存在
ls -lh data/stock_database.db

# 查看数据库内容（需要安装sqlite3命令行工具）
sqlite3 data/stock_database.db "SELECT COUNT(*) FROM stock_basic_info;"
```

### 检查下载进度

```bash
# 查看日志
tail -f data_engine/data_cache/update.log

# 查看扩展数据日志
tail -f /tmp/extended_data_download_final.log
```

---

## 📦 最小化依赖列表

如果只需要核心功能，最小依赖：

```txt
pandas>=1.3.0
sqlalchemy>=1.4.0
baostock>=0.8.8
```

**注意**：如果只使用SQLite，可以去掉 `pymysql`。

---

## 🎯 总结

### 最简单的部署方式：

1. **上传代码**：`git clone` 或直接上传
2. **安装依赖**：`pip3 install pandas sqlalchemy baostock`
3. **设置环境变量**：`export DB_TYPE=sqlite`
4. **运行下载**：`python3 data_engine/fetch_extended_data.py`

### 数据库文件：
- 位置：`data/stock_database.db`
- 备份：直接复制文件
- 迁移：复制文件即可

### 优势：
- ✅ 无需MySQL
- ✅ 无需VPN
- ✅ 零配置
- ✅ 可移植

---

**完成！** 🎉

