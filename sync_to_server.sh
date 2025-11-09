#!/bin/bash
# 同步代码到阿里云服务器（使用rsync）

# ====== 配置区域 ======
SERVER_USER="root"  # 修改为你的服务器用户名
SERVER_IP="your-server-ip"  # 修改为你的服务器IP
SERVER_PATH="/root/TradingAgents-CN"  # 服务器上的项目路径

# ====== 颜色输出 ======
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 开始同步代码到服务器...${NC}"
echo "服务器: ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}"

# 检查rsync是否安装
if ! command -v rsync &> /dev/null; then
    echo -e "${YELLOW}⚠️  rsync未安装，正在安装...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install rsync
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo apt-get install -y rsync
    fi
fi

# 同步代码（排除不必要的文件）
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.DS_Store' \
    --exclude 'data/' \
    --exclude 'data_engine/data_cache/' \
    --exclude '*.db' \
    --exclude '*.db-journal' \
    --exclude '*.log' \
    --exclude '*.tmp' \
    --exclude 'node_modules/' \
    --exclude '.streamlit/' \
    ./ \
    ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 代码同步完成！${NC}"
    echo ""
    echo "💡 下一步操作："
    echo "   ssh ${SERVER_USER}@${SERVER_IP}"
    echo "   cd ${SERVER_PATH}"
    echo "   export DB_TYPE=sqlite"
    echo "   python3 data_engine/fetch_extended_data.py"
else
    echo -e "${YELLOW}❌ 同步失败，请检查网络连接和服务器配置${NC}"
    exit 1
fi

