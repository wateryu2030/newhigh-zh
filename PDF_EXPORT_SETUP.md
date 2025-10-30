# 📄 PDF导出功能设置指南

## 当前状态

✅ **pandoc已安装**: 版本 3.8.2.1  
⏳ **LaTeX引擎安装中**: basictex正在安装（约100MB，可能需要几分钟）

## 问题说明

PDF生成需要：
1. ✅ **pandoc** - 已安装
2. ⏳ **PDF引擎**（以下之一）：
   - `pdflatex` / `xelatex` / `lualatex` (LaTeX引擎)
   - `wkhtmltopdf` (已废弃，不建议)
   - `weasyprint` (Python库，可选)

## 安装进度

**basictex** (轻量级LaTeX，约100MB) 正在后台安装：
- 安装路径：`/Library/TeX/texbin`
- 包含引擎：`pdflatex`, `xelatex`, `lualatex`

检查安装状态：
```bash
ls -la /Library/TeX/texbin/pdflatex
# 如果文件存在，说明安装完成
```

## 已实施的修复

### 1. 自动检测PDF引擎 ✅
代码已修改为自动检测可用的PDF引擎，按优先级使用：
- `xelatex` (推荐，中文支持好)
- `lualatex`
- `pdflatex`
- `weasyprint`
- 默认引擎

### 2. 启动脚本自动配置PATH ✅
应用启动时会自动添加LaTeX路径到PATH

### 3. 智能错误处理 ✅
如果PDF引擎不可用，会尝试多个引擎，并给出清晰的错误提示

## 安装完成后的操作

### 方法1: 等待basictex安装完成（推荐）

安装完成后，重启应用即可：
```bash
# 检查安装是否完成
which pdflatex

# 如果显示路径，说明安装完成
# 重启应用
cd /Users/apple/Ahope/Amarket/TradingAgents-CN
source env/bin/activate
python start_web.py
```

### 方法2: 手动验证安装

```bash
# 更新PATH（如果已安装）
eval "$(/usr/libexec/path_helper)"

# 验证LaTeX引擎
which pdflatex xelatex lualatex
pdflatex --version
```

## 临时解决方案

在LaTeX安装完成前，您可以：

1. **使用Word格式导出** ✅
   - Word导出不需要LaTeX，已经可用

2. **使用Markdown格式导出** ✅
   - Markdown导出不需要任何额外工具，已经可用

3. **手动转换Markdown为PDF**
   ```bash
   # 安装完成后
   pandoc report.md -o report.pdf --pdf-engine=xelatex
   ```

## 验证PDF生成

安装完成后，在应用中：
1. 生成分析报告
2. 点击"导出PDF"按钮
3. 应该能成功生成PDF文件

如果仍有问题，查看日志中的PDF引擎检测信息。

## 故障排查

### 问题1: "pdflatex not found"

**解决**：
```bash
# 检查basictex是否安装
ls /Library/TeX/texbin/pdflatex

# 如果不存在，继续等待安装完成
# 或者手动安装：
brew install --cask basictex
```

### 问题2: PDF生成失败但pandoc可用

检查日志中的错误信息：
- 如果是引擎问题，重启应用让代码自动检测
- 如果是内容问题，尝试使用Markdown格式导出

### 问题3: 中文显示问题

使用 `xelatex` 引擎（代码已优先使用）：
```bash
which xelatex
# 应该显示 /Library/TeX/texbin/xelatex
```

## 安装完成后

✅ 重启应用  
✅ 刷新浏览器  
✅ 尝试导出PDF  

应用会自动检测并使用可用的PDF引擎！

