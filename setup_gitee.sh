#!/bin/bash
# 设置Gitee仓库（替代GitHub）

# ====== 配置区域 ======
GITEE_USERNAME="your-gitee-username"  # 修改为你的Gitee用户名
REPO_NAME="TradingAgents-CN"  # 仓库名称

echo "🚀 设置Gitee仓库..."

# 检查是否已有git仓库
if [ ! -d ".git" ]; then
    echo "初始化Git仓库..."
    git init
    git add .
    git commit -m "初始提交"
fi

# 检查是否已有Gitee远程仓库
if git remote | grep -q "gitee"; then
    echo "Gitee远程仓库已存在，更新URL..."
    git remote set-url gitee https://gitee.com/${GITEE_USERNAME}/${REPO_NAME}.git
else
    echo "添加Gitee远程仓库..."
    git remote add gitee https://gitee.com/${GITEE_USERNAME}/${REPO_NAME}.git
fi

echo ""
echo "✅ Gitee仓库设置完成！"
echo ""
echo "📋 下一步操作："
echo "1. 在Gitee上创建仓库: https://gitee.com/new"
echo "   仓库名称: ${REPO_NAME}"
echo ""
echo "2. 推送代码到Gitee:"
echo "   git push -u gitee main"
echo ""
echo "3. 在阿里云服务器上克隆:"
echo "   git clone https://gitee.com/${GITEE_USERNAME}/${REPO_NAME}.git"

