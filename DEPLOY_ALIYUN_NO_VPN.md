# 阿里云部署方案（无需VPN，无需GitHub直连）

## 🎯 方案概述

**最简单方案：使用Gitee（码云）作为代码仓库，或直接文件上传**

### 优势
- ✅ **无需VPN**：Gitee是国内平台，访问稳定快速
- ✅ **无需GitHub**：完全避开GitHub访问问题
- ✅ **代码同步简单**：push到Gitee，服务器pull即可
- ✅ **零配置**：Gitee账号即可使用

---

## 🚀 方案一：使用Gitee（推荐）

### 1. 在本地设置Gitee仓库

```bash
# 在本地项目目录
cd TradingAgents-CN

# 如果已经有GitHub仓库，添加Gitee作为第二个远程仓库
git remote add gitee https://gitee.com/your-username/TradingAgents-CN.git

# 或者直接用Gitee作为主仓库
git remote set-url origin https://gitee.com/your-username/TradingAgents-CN.git
```

### 2. 推送到Gitee

```bash
# 首次推送
git push -u gitee main

# 后续更新
git push gitee main
```

### 3. 在阿里云服务器上克隆

```bash
# 在服务器上
git clone https://gitee.com/your-username/TradingAgents-CN.git
cd TradingAgents-CN
```

### 4. 后续更新代码

```bash
# 本地修改后
git add .
git commit -m "更新说明"
git push gitee main

# 服务器上更新
cd TradingAgents-CN
git pull gitee main
```

---

## 🚀 方案二：直接文件上传（最简单）

### 使用rsync同步（推荐）

#### 在本地创建同步脚本

创建 `sync_to_server.sh`：

```bash
#!/bin/bash
# 同步代码到阿里云服务器

SERVER_USER="root"  # 服务器用户名
SERVER_IP="your-server-ip"  # 服务器IP
SERVER_PATH="/root/TradingAgents-CN"  # 服务器上的路径

echo "🔄 开始同步代码到服务器..."

# 排除不需要的文件
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude 'data_engine/data_cache/' \
    --exclude '*.db' \
    --exclude '*.log' \
    ./ \
    ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

echo "✅ 同步完成！"
```

使用：
```bash
chmod +x sync_to_server.sh
./sync_to_server.sh
```

### 使用scp上传（一次性）

```bash
# 压缩项目（排除不必要的文件）
tar --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='data' \
    --exclude='*.db' \
    --exclude='*.log' \
    -czf TradingAgents-CN.tar.gz TradingAgents-CN/

# 上传到服务器
scp TradingAgents-CN.tar.gz root@your-server-ip:/root/

# 在服务器上解压
ssh root@your-server-ip
cd /root
tar -xzf TradingAgents-CN.tar.gz
```

---

## 🚀 方案三：使用GitHub镜像加速（无需VPN）

### 使用GitHub镜像站

```bash
# 在服务器上，使用镜像克隆
git clone https://ghproxy.com/https://github.com/your-username/TradingAgents-CN.git

# 或者使用其他镜像
git clone https://hub.fastgit.xyz/your-username/TradingAgents-CN.git
```

### 配置Git使用代理（如果有代理服务器）

```bash
# 如果本地有代理服务器，可以配置Git使用代理
git config --global http.proxy http://proxy-server:port
git config --global https.proxy https://proxy-server:port
```

---

## 📋 完整部署流程（推荐：Gitee方案）

### 第一步：在本地设置Gitee

```bash
# 1. 在Gitee创建仓库（https://gitee.com/new）
# 2. 在本地添加Gitee远程仓库
cd TradingAgents-CN
git remote add gitee https://gitee.com/your-username/TradingAgents-CN.git

# 3. 推送代码
git push -u gitee main
```

### 第二步：在阿里云服务器部署

```bash
# 1. 安装基础工具
sudo apt update
sudo apt install -y python3 python3-pip git

# 2. 克隆代码（从Gitee，无需VPN）
git clone https://gitee.com/your-username/TradingAgents-CN.git
cd TradingAgents-CN

# 3. 安装依赖
pip3 install pandas sqlalchemy baostock -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 配置使用SQLite
export DB_TYPE=sqlite
echo 'export DB_TYPE=sqlite' >> ~/.bashrc

# 5. 创建数据目录
mkdir -p data data_engine/data_cache

# 6. 启动下载（后台运行）
nohup python3 data_engine/fetch_extended_data.py > download.log 2>&1 &
```

### 第三步：后续更新代码

```bash
# 本地修改代码后
git add .
git commit -m "更新说明"
git push gitee main

# 服务器上更新
ssh root@your-server-ip
cd TradingAgents-CN
git pull gitee main

# 如果有新依赖，更新
pip3 install -r data_engine/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 重启下载任务（如果需要）
pkill -f fetch_extended_data
nohup python3 data_engine/fetch_extended_data.py > download.log 2>&1 &
```

---

## 🛠️ 自动化脚本

### 创建自动化同步脚本 `auto_sync.sh`

```bash
#!/bin/bash
# 自动同步代码并重启服务

SERVER_USER="root"
SERVER_IP="your-server-ip"
SERVER_PATH="/root/TradingAgents-CN"

echo "🔄 同步代码..."

# 同步代码
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude '*.db' \
    --exclude '*.log' \
    ./ \
    ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

echo "🔄 在服务器上更新依赖..."
ssh ${SERVER_USER}@${SERVER_IP} "cd ${SERVER_PATH} && pip3 install -r data_engine/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"

echo "✅ 同步完成！"
echo "💡 在服务器上运行: python3 data_engine/fetch_extended_data.py"
```

---

## 📦 最小化依赖安装（使用国内镜像）

```bash
# 使用清华大学镜像，速度更快
pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    pandas \
    sqlalchemy \
    baostock \
    pymysql

# 或者使用阿里云镜像
pip3 install -i https://mirrors.aliyun.com/pypi/simple/ \
    pandas \
    sqlalchemy \
    baostock \
    pymysql
```

---

## 🔍 验证部署

### 检查代码是否同步成功

```bash
# 在服务器上
cd TradingAgents-CN
ls -la
python3 --version
pip3 list | grep -E "pandas|sqlalchemy|baostock"
```

### 测试运行

```bash
# 测试数据库配置
python3 -c "from data_engine.config import DB_URL; print(f'数据库: {DB_URL}')"

# 测试BaoStock连接
python3 -c "import baostock as bs; lg = bs.login(); print('登录成功' if lg.error_code == '0' else lg.error_msg); bs.logout()"
```

---

## 💡 推荐方案总结

### 最佳方案：Gitee + SQLite

1. **代码同步**：使用Gitee（国内，无需VPN）
2. **数据库**：使用SQLite（文件数据库，无需安装MySQL）
3. **数据源**：BaoStock（国内数据源，无需VPN）
4. **依赖安装**：使用国内PyPI镜像（清华/阿里云）

### 优势

- ✅ **完全无需VPN**：所有服务都在国内
- ✅ **部署简单**：3步完成
- ✅ **更新方便**：git pull即可
- ✅ **成本低**：无需额外服务

---

## 📝 快速命令参考

```bash
# 本地推送代码
git add .
git commit -m "更新"
git push gitee main

# 服务器更新代码
cd TradingAgents-CN
git pull gitee main

# 服务器启动下载
export DB_TYPE=sqlite
nohup python3 data_engine/fetch_extended_data.py > download.log 2>&1 &

# 查看下载进度
tail -f download.log

# 检查数据库
ls -lh data/stock_database.db
```

---

**完成！现在可以完全避开GitHub和VPN了！** 🎉

