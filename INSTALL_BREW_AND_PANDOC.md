# 🍺 Homebrew 和 Pandoc 安装指南

由于网络连接 GitHub 受限，请按以下步骤手动安装：

## 方法 1: 使用浏览器安装 Homebrew（推荐）

### 步骤 1: 安装 Homebrew

1. **打开浏览器**，访问以下任一网站：
   - 官方安装脚本：https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh
   - 或访问官网：https://brew.sh

2. **打开终端**（Terminal），运行以下命令：
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   
   如果上面的命令失败（网络问题），可以尝试：
   ```bash
   /bin/bash -c "$(curl -fsSL https://gitee.com/ineo6/homebrew-install/raw/master/install.sh)"
   ```

3. **安装过程中会提示输入管理员密码**，输入后按回车（输入时不显示字符，这是正常的）

4. **安装完成后**，根据提示将 Homebrew 添加到 PATH：
   
   如果是 Apple Silicon (M1/M2/M3)：
   ```bash
   echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
   source ~/.zshrc
   ```
   
   如果是 Intel 芯片：
   ```bash
   echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zshrc
   source ~/.zshrc
   ```

5. **验证安装**：
   ```bash
   brew --version
   ```

### 步骤 2: 安装 Pandoc

安装完 Homebrew 后，运行：

```bash
brew install pandoc
```

验证安装：
```bash
pandoc --version
```

## 方法 2: 直接下载 Pandoc 安装包（如果 Homebrew 安装失败）

1. **访问 Pandoc 官网**：https://pandoc.org/installing.html

2. **下载 macOS 安装包**：
   - 最新版本：https://github.com/jgm/pandoc/releases/latest
   - 直接下载链接：https://github.com/jgm/pandoc/releases/download/3.7.2/pandoc-3.7.2-x86_64-macOS.pkg

3. **双击 .pkg 文件**进行安装，按照安装向导完成安装

4. **验证安装**：
   ```bash
   pandoc --version
   ```

## 安装完成后验证

运行以下命令确认安装成功：

```bash
# 检查 Homebrew
which brew && brew --version

# 检查 Pandoc
which pandoc && pandoc --version
```

## 安装后重启应用

安装完 pandoc 后，需要重启 Streamlit 应用才能使用 PDF/Word 导出功能。

## 注意事项

- ✅ 安装 Homebrew 需要**管理员权限**（sudo）
- ✅ 安装过程需要**网络连接**，如果 GitHub 连接不稳定，可以使用国内镜像
- ✅ 安装 pandoc 后，PDF 导出还需要 LaTeX，但 Word 导出可以立即使用
- ✅ 如需 PDF 导出，可以安装 BasicTeX：
  ```bash
  brew install --cask basictex
  ```

---

📝 **提示**：如果您已经成功安装了 Homebrew，可以直接运行：
```bash
brew install pandoc
```

