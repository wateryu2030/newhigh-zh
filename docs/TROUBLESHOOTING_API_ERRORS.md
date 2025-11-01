# 🔧 API错误故障排除指南

## 常见错误类型及解决方案

### 1. 402 - Insufficient Balance（余额不足）

**错误信息：**
```
Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknown_error'}}
```

**原因：**
- OpenAI账户余额不足
- 账户未设置支付方式

**解决方案：**

#### 方案1：充值OpenAI账户 ⭐推荐

1. **访问OpenAI平台**
   ```
   https://platform.openai.com/
   ```

2. **登录账户**
   - 使用您的OpenAI账户登录

3. **添加支付方式**
   - 点击右上角头像 → **Settings** → **Billing**
   - 添加支付方式（信用卡等）
   - 设置使用额度限制（可选）

4. **充值**
   - 在 **Billing** 页面充值
   - 最低充值金额：$5

5. **等待生效**
   - 充值后等待1-5分钟
   - 重新运行分析

#### 方案2：切换到备用LLM提供商 ⭐推荐

系统支持多个LLM提供商，可以无缝切换：

**步骤：**
1. 打开Web应用侧边栏
2. 找到 **"AI模型配置"** 区域
3. 选择 **"LLM提供商"**：
   - 从 `OpenAI` 切换到 `Dashscope`（推荐）
   - 或切换到 `Anthropic`
   - 或切换到 `DeepSeek`
4. 选择对应的模型
5. 重新运行分析

**推荐的备用提供商：**

| 提供商 | 配置项 | 模型 | 特点 |
|--------|--------|------|------|
| **阿里百炼** | `DASHSCOPE_API_KEY` | `qwen-plus`, `qwen-max` | 国内稳定，速度快 |
| **Anthropic** | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet` | 推理能力强 |
| **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-chat` | 性价比高 |

**配置方法：**
```bash
# 编辑 .env 文件
DASHSCOPE_API_KEY=sk-your-dashscope-key
ANTHROPIC_API_KEY=sk-ant-your-key
DEEPSEEK_API_KEY=sk-your-deepseek-key
```

### 2. 401 - Unauthorized（密钥无效）

**错误信息：**
```
Error code: 401 - Invalid API key
```

**原因：**
- API密钥配置错误
- API密钥已过期或被撤销
- 密钥格式不正确

**解决方案：**

1. **检查`.env`文件**
   ```bash
   # 确保密钥格式正确
   OPENAI_API_KEY=sk-proj-...或sk-...
   ```

2. **重新生成密钥**
   - 访问：https://platform.openai.com/api-keys
   - 删除旧密钥（如需要）
   - 创建新密钥
   - 复制到`.env`文件

3. **验证密钥**
   ```python
   import os
   from openai import OpenAI
   
   client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
   # 尝试简单调用验证
   ```

### 3. 429 - Rate Limit（频率限制）

**错误信息：**
```
Error code: 429 - Rate limit exceeded
```

**原因：**
- API请求过于频繁
- 账户配额已达到上限

**解决方案：**

1. **等待重试**
   - 等待1-5分钟
   - 系统会自动重试

2. **减少请求频率**
   - 避免连续多次点击分析按钮
   - 等待当前分析完成

3. **升级账户**
   - 升级到付费账户
   - 获取更高的请求配额

4. **切换到备用提供商**
   - 使用Dashscope等提供商
   - 通常有更宽松的限制

### 4. 500/503 - 服务错误

**错误信息：**
```
Error code: 500 - Internal Server Error
```

**原因：**
- API服务端临时故障
- 服务维护中

**解决方案：**

1. **等待后重试**
   - 等待5-10分钟后重试
   - 检查API服务状态

2. **检查服务状态**
   - OpenAI: https://status.openai.com/
   - Dashscope: https://status.dashscope.com/

3. **切换到备用提供商**

## 🔄 自动故障转移

系统支持自动切换到备用LLM提供商（开发中）：

```python
# 未来功能
if openai_fails:
    try_dashscope()
elif dashscope_fails:
    try_anthropic()
```

## 📊 检查API状态

### 检查配置

```python
# 在Python中检查
import os

providers = {
    "OpenAI": os.getenv("OPENAI_API_KEY"),
    "Dashscope": os.getenv("DASHSCOPE_API_KEY"),
    "Anthropic": os.getenv("ANTHROPIC_API_KEY"),
    "DeepSeek": os.getenv("DEEPSEEK_API_KEY")
}

for name, key in providers.items():
    if key:
        print(f"✅ {name}: 已配置")
    else:
        print(f"❌ {name}: 未配置")
```

### 检查余额（OpenAI）

1. 访问：https://platform.openai.com/usage
2. 查看当前使用情况和余额

## 💡 最佳实践

1. **配置多个提供商**
   - 至少配置2个LLM提供商
   - 确保服务可用性

2. **监控使用情况**
   - 定期检查API使用量
   - 设置使用额度警报

3. **合理使用**
   - 避免不必要的重复分析
   - 使用缓存减少API调用

4. **及时充值**
   - 设置自动充值（如支持）
   - 保持账户余额充足

## 🔗 相关文档

- [API密钥配置](A_SHARE_DATA.md)
- [使用指南](usage_guide.md)
- [频率限制处理](RATE_LIMIT_GUIDE.md)

---

**遇到问题？查看日志文件 `logs/` 获取详细错误信息。**

