# 🔤 PDF中文支持修复说明

## 问题描述

导出的PDF文件中中文显示为空或乱码，只显示英文和数字。

## 原因分析

LaTeX默认不支持UTF-8编码的中文字符，需要特殊配置：
1. **使用正确的PDF引擎**：`xelatex`或`lualatex`（原生支持UTF-8）
2. **加载CJK包**：`xeCJK`或`luatexja`包
3. **指定中文字体**：PingFang SC（macOS系统默认）

## 已实施的修复

### 1. 优先使用xelatex引擎 ✅
代码已修改为优先使用`xelatex`（对中文支持最好）

### 2. 添加中文字体配置 ✅
在使用`xelatex`时自动添加：
```latex
-V CJKmainfont=PingFang SC    # 主字体
-V CJKsansfont=PingFang SC    # 无衬线字体
-V CJKmonofont=PingFang SC    # 等宽字体
```

### 3. 引擎优先级 ✅
- 第一选择：`xelatex`（最佳中文支持）
- 第二选择：`lualatex`（良好中文支持）
- 第三选择：`pdflatex`（需要CJK包）

## 使用方法

1. **刷新浏览器页面**
2. **生成新的分析报告**
3. **点击"导出PDF"**
4. **PDF应包含完整的中文字符**

## 验证方法

导出的PDF应该：
- ✅ 显示中文标题
- ✅ 显示中文内容
- ✅ 显示中文股票名称
- ✅ 所有中文字符正常显示

## 如果仍有问题

### 检查1: 确认使用xelatex
查看日志应该显示：
```
🔧 使用PDF引擎: xelatex
🔤 已配置xelatex中文支持（使用PingFang SC字体）
```

### 检查2: 系统字体
确认系统有PingFang SC字体：
```bash
# 检查字体
ls /System/Library/Fonts/*.ttc | grep -i ping
```

### 检查3: LaTeX包
确认xeCJK包已安装：
```bash
# 如果缺失，basictex可能不包含，需要安装完整版
# 或者使用其他字体方案
```

## 备选方案

如果PingFang SC不可用，可以尝试：
- STSong（标准宋体）
- SimSun（宋体）
- 或其他系统字体

代码会自动回退到其他引擎。

