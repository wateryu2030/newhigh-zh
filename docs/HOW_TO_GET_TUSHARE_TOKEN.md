# 如何获取Tushare Token（图文指南）

## 🎯 为什么需要Tushare Token？

当前使用akshare获取A股实时数据时，经常遇到连接中断问题，导致数据不完整。使用Tushare可以：
- ✅ 获取完整数据（价格、市值、PE、PB等）
- ✅ 避免连接中断问题
- ✅ 更稳定的API接口

## 📝 获取步骤

### 第1步：访问Tushare官网
打开浏览器，访问：**https://tushare.pro**

### 第2步：注册账号
1. 点击右上角"注册"
2. 填写邮箱和密码
3. 点击"发送验证码"并输入验证码
4. 勾选同意用户协议
5. 点击"注册"

### 第3步：登录账号
1. 使用注册的邮箱和密码登录
2. 进入个人中心

### 第4步：实名认证
1. 在个人中心，点击"实名认证"
2. 上传身份证照片（正反面）
3. 填写真实姓名和身份证号
4. 提交审核（通常1-2小时通过）

### 第5步：获取Token
1. 认证通过后，进入"接口TOKEN"页面
2. 点击"复制Token"按钮
3. Token类似：`a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

### 第6步：配置到系统
1. 打开项目根目录的`.env`文件
2. 添加以下配置：
```bash
TUSHARE_TOKEN=你的token（粘贴刚才复制的token）
TUSHARE_ENABLED=true
```
3. 保存文件

### 第7步：验证配置
运行以下命令验证：
```bash
python3 -c "from tradingagents.dataflows.tushare_adapter import get_tushare_adapter; adapter = get_tushare_adapter(); print('✅ Tushare配置成功' if adapter.provider and adapter.provider.connected else '❌ Tushare配置失败')"
```

### 第8步：重新下载数据
在Web界面中，点击"下载/更新 A股基础资料"按钮，系统会自动使用Tushare获取完整数据。

## 💰 费用说明

### 免费版
- **积分限制**：注册后送120积分
- **调用次数**：每日最多500次
- **数据字段**：基础字段（股票信息、PE、PB、市值等）
- **适合**：个人用户、测试使用

### 积分版（¥500/年）
- **调用次数**：更高限制
- **数据字段**：更多字段
- **适合**：轻度使用、个人投资者

### 专业版（¥3000/年）
- **调用次数**：无限制
- **数据字段**：全量数据
- **适合**：机构用户、量化交易

## ✅ 推荐

对于本系统的基础数据下载功能，**免费版完全够用**！

只需要：
1. 注册账号（免费）
2. 完成实名认证（免费）
3. 获取Token（免费）
4. 配置到系统

即可获得稳定的完整数据！

## 🆘 遇到问题？

1. **认证未通过**：检查身份证照片是否清晰，信息是否准确
2. **Token无效**：确认已复制完整Token，没有多余空格
3. **调用失败**：检查是否超过每日500次限制，等待次日重置
4. **其他问题**：访问Tushare官方文档或联系客服

## 📚 相关文档

- Tushare官方文档：https://tushare.pro/document/2
- 系统数据源指南：`docs/DATA_SOURCES_GUIDE.md`
- 问题排查指南：`docs/TROUBLESHOOTING_A_SHARE_DOWNLOAD.md`

