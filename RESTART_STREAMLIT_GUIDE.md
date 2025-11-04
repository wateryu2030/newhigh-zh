# 🔄 Streamlit重启指南

## 问题症状

如果修改代码后页面没有更新，可能是Streamlit缓存了旧代码。需要重启Streamlit服务。

## 🚀 重启方法

### 方法1：命令行重启（推荐）

1. **找到Streamlit进程**
   ```bash
   ps aux | grep streamlit
   ```

2. **停止Streamlit服务**
   ```bash
   # 方法A：使用进程ID停止
   kill <PID>
   
   # 方法B：强制停止所有streamlit进程
   pkill -f streamlit
   ```

3. **重新启动Streamlit**
   ```bash
   cd /Users/apple/Ahope/Amarket/TradingAgents-CN
   source env/bin/activate  # 如果使用虚拟环境
   streamlit run web/app.py --server.port 8501
   ```

### 方法2：如果使用了启动脚本

如果有启动脚本，直接运行：
```bash
cd /Users/apple/Ahope/Amarket/TradingAgents-CN
./start.sh  # 或相应的启动脚本
```

### 方法3：完全清理重启

如果方法1和2都不行，完全清理：

```bash
# 1. 停止所有Python/Streamlit进程
pkill -f streamlit
pkill -f python

# 2. 清理Streamlit缓存（可选）
rm -rf ~/.streamlit/cache

# 3. 重新启动
cd /Users/apple/Ahope/Amarket/TradingAgents-CN
source env/bin/activate
streamlit run web/app.py --server.port 8501
```

## ✅ 验证修复

重启后：
1. 刷新浏览器（Ctrl+F5 或 Cmd+Shift+R）
2. 访问：http://localhost:8501/智能选股
3. 如果看到"✅ 已加载 X 条股票数据"，说明修复成功

## 🔍 如果仍然不工作

1. **检查数据库是否存在**
   ```bash
   ls -lh /Users/apple/Ahope/Amarket/TradingAgents-CN/data/stock_database.db
   ```

2. **查看Streamlit日志**
   - 检查终端输出是否有错误
   - 检查浏览器控制台是否有错误

3. **验证路径计算**
   - 展开"智能选股"页面上的"🔍 调试信息"
   - 检查显示的路径是否正确

4. **手动测试**
   ```bash
   cd /Users/apple/Ahope/Amarket/TradingAgents-CN
   python3 -c "from pathlib import Path; print((Path('web/pages/20_🧠_智能选股.py').resolve().parents[2] / 'data' / 'stock_database.db').exists())"
   ```
   应该输出 `True`

## 📝 常见问题

### Q: 重启后仍然显示旧错误？
A: 尝试清除浏览器缓存，或使用无痕模式访问

### Q: 如何确认Streamlit已重启？
A: 查看终端输出，应该看到 "You can now view your Streamlit app in your browser"

### Q: 端口被占用怎么办？
A: 
```bash
lsof -ti:8501 | xargs kill -9
streamlit run web/app.py --server.port 8501
```

