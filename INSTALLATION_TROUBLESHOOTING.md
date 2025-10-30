# 🔧 安装问题排查与解决方案

## 为什么安装容易卡死？

### 1. **网络连接问题** 🌐
- **原因**：Homebrew 默认从 GitHub 下载，国内访问经常超时或失败
- **表现**：下载过程卡住，无响应
- **解决方案**：使用国内镜像源（清华、中科大等）

### 2. **Git 仓库同步慢** 📦
- **原因**：Homebrew 需要从 Git 仓库拉取最新版本，网络不稳定时容易卡住
- **表现**：`brew update` 或安装时在 Git 操作阶段卡住
- **解决方案**：配置 Git 使用代理或国内镜像

### 3. **清理进程阻塞** 🧹
- **原因**：`brew cleanup` 在某些情况下会卡住，特别是在清理大量文件时
- **表现**：安装完成后在清理阶段卡住
- **解决方案**：中断清理进程不影响已安装的软件

### 4. **超时设置不当** ⏱️
- **原因**：网络慢时默认超时时间可能不够
- **表现**：中途失败或卡死
- **解决方案**：设置更长的超时时间或使用国内镜像加速

## ✅ 已实施的解决方案

### 1. 配置 Homebrew 使用国内镜像源

```bash
# 已在 ~/.zshrc 中配置
export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 2. Homebrew 核心仓库已配置清华镜像

```bash
# 验证镜像配置
cd "$(brew --repo)" && git remote -v
# 应该显示：https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew
```

### 3. 安装验证

✅ **Homebrew** 已安装：`/opt/homebrew/bin/brew`
✅ **pandoc** 已安装：`pandoc 3.8.2.1`
✅ **pypandoc** 可检测：版本 3.8.2.1

## 🛠️ 如果再次遇到卡死问题

### 方法 1: 检查并清理卡住的进程

```bash
# 查看卡住的进程
ps aux | grep -E "brew|pandoc" | grep -v grep

# 强制终止（替换 PID 为实际进程ID）
kill -9 <PID>

# 或者批量清理
ps aux | grep -E "brew cleanup|brew install" | grep -v grep | awk '{print $2}' | xargs kill -9
```

### 方法 2: 使用超时机制

```bash
# macOS 没有 timeout 命令，可以手动监控
brew install pandoc &
INSTALL_PID=$!
echo "安装进程 PID: $INSTALL_PID"
# 如果需要终止：kill $INSTALL_PID
```

### 方法 3: 验证安装是否已完成

即使进程卡住，软件可能已经安装成功：

```bash
# 检查 pandoc
which pandoc
pandoc --version

# 检查 Homebrew 安装的软件
brew list pandoc
ls -la /opt/homebrew/Cellar/pandoc
```

### 方法 4: 手动清理（如果清理进程卡住）

```bash
# 跳过自动清理
export HOMEBREW_NO_INSTALL_CLEANUP=1
brew install <package>

# 或稍后手动清理
brew cleanup
```

## 📝 推荐的安装流程

```bash
# 1. 配置环境变量
export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles
eval "$(/opt/homebrew/bin/brew shellenv)"

# 2. 安装软件（后台运行，避免阻塞）
brew install pandoc > /tmp/brew_install.log 2>&1 &
INSTALL_PID=$!

# 3. 监控进度
tail -f /tmp/brew_install.log

# 4. 验证安装
which pandoc && pandoc --version
```

## 🎯 当前状态

- ✅ Homebrew: 已安装（版本 4.6.19）
- ✅ pandoc: 已安装（版本 3.8.2.1）
- ✅ 国内镜像: 已配置（清华镜像）
- ✅ 导出功能: 已可用（Word/PDF 导出）

现在可以正常使用导出功能了！

