# 🚀 切换到Dashscope（阿里百炼）快速指南

## 为什么选择Dashscope？

- ✅ **国内稳定**：国内服务器，速度快，延迟低
- ✅ **性价比高**：价格相对便宜，有免费额度
- ✅ **模型强大**：Qwen系列模型表现优异
- ✅ **无需VPN**：国内可直接访问

## 📋 切换步骤

### 步骤1：配置API密钥

1. **获取Dashscope API密钥**
   - 访问：https://dashscope.aliyun.com/
   - 注册/登录阿里云账号
   - 进入控制台 → API-KEY管理
   - 创建新的API密钥（格式：`sk-...`）

2. **配置到.env文件**
   
   ```bash
   # 进入项目目录
   cd /Users/apple/Ahope/Amarket/TradingAgents-CN
   
   # 如果.env文件不存在，从示例创建
   if [ ! -f .env ]; then
       cp .env.example .env 2>/dev/null || touch .env
   fi
   
   # 编辑.env文件，添加或修改：
   DASHSCOPE_API_KEY=sk-your-key-here
   ```

   **或者手动编辑：**
   ```bash
   # 使用任意文本编辑器打开.env文件
   nano .env
   # 或
   vim .env
   # 或
   code .env  # VS Code
   ```
   
   添加以下内容：
   ```env
   DASHSCOPE_API_KEY=sk-your-dashscope-api-key-here
   ```

### 步骤2：在Web界面切换

1. **启动Web应用**（如果未运行）
   ```bash
   python start_web.py
   ```

2. **打开侧边栏**
   - 在Web界面左侧找到侧边栏

3. **切换LLM提供商**
   - 找到 **"🧠 AI模型配置"** 区域
   - 点击 **"LLM提供商"** 下拉框
   - 选择 **"🇨🇳 阿里百炼"** （即 `dashscope`）

4. **选择模型**
   - 系统会自动显示Dashscope的模型选项：
     - **Plus - 平衡**（推荐）：`qwen-plus-latest` - 性价比最高
     - **Max - 最强**：`qwen-max` - 能力最强
     - **Turbo - 快速**：`qwen-turbo` - 速度最快
   - 推荐选择 **"Plus - 平衡"**

5. **验证配置**
   - 侧边栏会显示API密钥状态
   - 如果显示 ✅ 表示配置成功
   - 如果显示 ❌ 请检查 `.env` 文件

### 步骤3：重新运行分析

1. **刷新页面**（可选）
   - 按 `F5` 或点击浏览器的刷新按钮

2. **运行股票分析**
   - 输入股票代码
   - 选择分析师
   - 点击 **"开始分析"**
   - 系统会使用Dashscope进行分析

## ✅ 验证是否切换成功

### 方法1：查看侧边栏状态

侧边栏底部会显示：
```
✅ 阿里百炼 (Dashscope): 已配置
```

### 方法2：运行测试分析

1. 选择一个简单的股票（如：000001）
2. 只选择一个分析师（如：市场分析师）
3. 运行分析
4. 如果成功，说明已切换到Dashscope

### 方法3：查看日志

```bash
# 查看日志文件
tail -f logs/app.log | grep -i dashscope
```

应该看到类似：
```
✅ Dashscope API密钥已配置
📊 使用Dashscope进行股票分析
```

## 🔧 故障排除

### 问题1：找不到.env文件

**解决：**
```bash
cd /Users/apple/Ahope/Amarket/TradingAgents-CN
touch .env
# 然后添加配置
echo "DASHSCOPE_API_KEY=sk-your-key" >> .env
```

### 问题2：配置后仍显示未配置

**解决：**
1. **重启Web应用**
   ```bash
   # 停止当前应用（Ctrl+C）
   # 重新启动
   python start_web.py
   ```

2. **检查.env文件格式**
   ```env
   # 正确格式（没有引号，没有空格）
   DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxx
   
   # 错误格式
   DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxx"  # 不要引号
   DASHSCOPE_API_KEY = sk-xxxxxxxxxxxxx    # 不要空格
   ```

3. **检查.env文件位置**
   - 确保`.env`文件在项目根目录
   - 路径：`/Users/apple/Ahope/Amarket/TradingAgents-CN/.env`

### 问题3：API密钥无效

**解决：**
1. 登录 https://dashscope.aliyun.com/
2. 检查API密钥是否正确
3. 检查账户余额是否充足
4. 重新生成API密钥并更新`.env`文件

### 问题4：模型选择框不显示

**解决：**
1. 确保已选择"🇨🇳 阿里百炼"作为提供商
2. 刷新页面（F5）
3. 清除浏览器缓存

## 💡 推荐配置

**最优配置（平衡性能和成本）：**
```
LLM提供商: 🇨🇳 阿里百炼 (dashscope)
模型版本: Plus - 平衡 (qwen-plus-latest)
```

**高性能配置（需要更强分析能力）：**
```
LLM提供商: 🇨🇳 阿里百炼 (dashscope)
模型版本: Max - 最强 (qwen-max)
```

**快速配置（追求速度）：**
```
LLM提供商: 🇨🇳 阿里百炼 (dashscope)
模型版本: Turbo - 快速 (qwen-turbo)
```

## 📊 Dashscope模型对比

| 模型 | 速度 | 能力 | 价格 | 推荐场景 |
|------|------|------|------|----------|
| qwen-turbo | ⚡⚡⚡ | ⭐⭐ | 💰 | 简单分析、快速响应 |
| qwen-plus-latest | ⚡⚡ | ⭐⭐⭐ | 💰💰 | **日常分析（推荐）** |
| qwen-max | ⚡ | ⭐⭐⭐⭐ | 💰💰💰 | 深度分析、重要决策 |

## 🔗 相关资源

- [Dashscope官网](https://dashscope.aliyun.com/)
- [Qwen模型文档](https://help.aliyun.com/zh/model-studio/)
- [API密钥管理](https://dashscope.console.aliyun.com/apiKey)

---

**切换完成后，您就可以继续使用股票分析功能了！** 🎉

