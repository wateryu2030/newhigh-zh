#!/bin/bash
# 阿里云服务器一键部署脚本
# 适用于: Ubuntu 22.04 LTS
# 使用方法: bash aliyun_deployment_script.sh

set -e  # 遇到错误立即退出

echo "🚀 TradingAgents-CN 阿里云部署脚本"
echo "=================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
    echo "使用: sudo bash aliyun_deployment_script.sh"
    exit 1
fi

# 1. 系统更新
echo -e "${GREEN}📦 更新系统包...${NC}"
apt update && apt upgrade -y

# 2. 安装基础工具
echo -e "${GREEN}📦 安装基础工具...${NC}"
apt install -y curl wget git vim ufw htop

# 3. 安装Docker
echo -e "${GREEN}🐳 安装Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | bash
    systemctl start docker
    systemctl enable docker
    echo -e "${GREEN}✅ Docker安装成功${NC}"
else
    echo -e "${YELLOW}⚠️ Docker已安装，跳过${NC}"
fi

# 4. 安装Docker Compose
echo -e "${GREEN}🐳 安装Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}✅ Docker Compose安装成功${NC}"
else
    echo -e "${YELLOW}⚠️ Docker Compose已安装，跳过${NC}"
fi

# 5. 配置防火墙
echo -e "${GREEN}🔥 配置防火墙...${NC}"
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 8501/tcp  # Streamlit
echo -e "${GREEN}✅ 防火墙配置完成${NC}"

# 6. 创建项目目录
PROJECT_DIR="/root/tradingagents"
echo -e "${GREEN}📁 创建项目目录: ${PROJECT_DIR}${NC}"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 7. 克隆项目（如果不存在）
if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo -e "${GREEN}📥 克隆项目...${NC}"
    git clone https://github.com/wateryu2030/newhigh-zh.git .
else
    echo -e "${YELLOW}⚠️ 项目已存在，跳过克隆${NC}"
    git pull
fi

# 8. 配置.env文件
echo -e "${GREEN}⚙️ 配置环境变量...${NC}"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠️ 请编辑 .env 文件配置API密钥:${NC}"
        echo "   nano $PROJECT_DIR/.env"
        echo ""
        echo -e "${YELLOW}必需配置的API密钥:${NC}"
        echo "   - DASHSCOPE_API_KEY (阿里百炼)"
        echo "   - TUSHARE_TOKEN (Tushare)"
        echo "   - FINNHUB_API_KEY (FinnHub)"
        echo ""
        read -p "是否现在编辑 .env 文件? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            nano $PROJECT_DIR/.env
        fi
    else
        echo -e "${RED}❌ 未找到 .env.example 文件${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ .env 文件已存在，跳过${NC}"
fi

# 9. 创建数据目录
echo -e "${GREEN}📁 创建数据目录...${NC}"
mkdir -p $PROJECT_DIR/data
mkdir -p $PROJECT_DIR/logs
mkdir -p $PROJECT_DIR/config
chmod -R 755 $PROJECT_DIR

# 10. 构建并启动Docker容器
echo -e "${GREEN}🚀 构建并启动Docker容器...${NC}"
cd $PROJECT_DIR

# 检查docker-compose.yml是否存在
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo -e "${RED}❌ 未找到 docker-compose.yml 文件${NC}"
    exit 1
fi

# 停止旧容器（如果有）
docker-compose down 2>/dev/null || true

# 构建镜像
echo -e "${GREEN}🔨 构建Docker镜像（这可能需要几分钟）...${NC}"
docker-compose build --no-cache

# 启动服务
echo -e "${GREEN}▶️ 启动服务...${NC}"
docker-compose up -d

# 11. 等待服务启动
echo -e "${GREEN}⏳ 等待服务启动（30秒）...${NC}"
sleep 30

# 12. 检查服务状态
echo -e "${GREEN}🔍 检查服务状态...${NC}"
docker-compose ps

# 13. 显示访问信息
SERVER_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip)
echo ""
echo -e "${GREEN}=================================="
echo "✅ 部署完成！"
echo "=================================="
echo ""
echo -e "${YELLOW}访问地址:${NC}"
echo "  Web界面: http://${SERVER_IP}:8501"
echo ""
echo -e "${YELLOW}管理工具:${NC}"
echo "  查看日志: docker-compose logs -f web"
echo "  停止服务: docker-compose down"
echo "  重启服务: docker-compose restart"
echo "  查看状态: docker-compose ps"
echo ""
echo -e "${YELLOW}重要提示:${NC}"
echo "  1. 请确保已在阿里云控制台开放8501端口"
echo "  2. 请编辑 .env 文件配置API密钥"
echo "  3. 配置完成后重启服务: docker-compose restart web"
echo ""

# 14. 创建管理脚本
cat > /usr/local/bin/tradingagents << 'EOF'
#!/bin/bash
# TradingAgents管理脚本
cd /root/tradingagents

case "$1" in
    start)
        docker-compose up -d
        ;;
    stop)
        docker-compose down
        ;;
    restart)
        docker-compose restart
        ;;
    logs)
        docker-compose logs -f web
        ;;
    status)
        docker-compose ps
        ;;
    update)
        git pull
        docker-compose build --no-cache
        docker-compose up -d
        ;;
    *)
        echo "使用方法: tradingagents {start|stop|restart|logs|status|update}"
        exit 1
        ;;
esac
EOF

chmod +x /usr/local/bin/tradingagents

echo -e "${GREEN}✅ 管理脚本已创建，使用 'tradingagents' 命令管理服务${NC}"
echo ""
echo -e "${GREEN}部署脚本执行完成！${NC}"

