# TradingAgents-CN 框架状态说明

## 📊 当前技术栈

### 后端框架
- **框架**: Streamlit (Python)
- **类型**: 单页应用，无独立后端服务
- **特点**: 
  - Streamlit同时承担了后端逻辑和前端UI展示
  - 所有页面在 `web/pages/` 目录下
  - 使用 `streamlit run web/app.py` 启动

### 前端框架
- **框架**: Streamlit内置UI
- **类型**: 无独立前端框架
- **特点**:
  - 完全基于Streamlit组件构建
  - 没有Vue、React等前端框架
  - 没有package.json或前端构建工具

### 数据库
- **SQLite**: `data/stock_database.db` (data_engine使用的股票数据库)
- **MongoDB**: 用于存储分析结果和历史记录
- **Redis**: 用于会话管理和缓存

### 数据引擎
- **位置**: `TradingAgents-CN/data_engine/`
- **技术**: Python + BaoStock API
- **功能**: A股股票数据下载和管理
- **数据库**: SQLite

## 🎯 目标架构

### 后端
- **推荐框架**: FastAPI (轻量、高性能、自动API文档)
- **备选框架**: Flask (成熟、生态丰富)

### 前端
- **推荐**: Vue 3 + Element Plus (中文支持好、组件丰富)
- **备选**: React + Ant Design

### 架构特点
- **前后端分离**: RESTful API + SPA前端
- **数据库**: 保持SQLite + MongoDB + Redis
- **数据引擎**: 集成到后端API

## 🔄 迁移路径建议

### 阶段1: 后端API设计
1. 使用FastAPI重新设计后端API
2. 将Streamlit的业务逻辑提取为API端点
3. 保留data_engine模块

### 阶段2: 前端开发
1. 使用Vue 3 + Element Plus构建前端
2. 迁移Streamlit UI到Vue组件
3. 实现前后端通信

### 阶段3: 数据引擎集成
1. 将data_engine封装为后端服务
2. 提供股票数据查询API
3. 实现数据同步和更新接口

## 📝 向ChatGPT提供的信息

1. **当前框架**: Streamlit (单页应用，无独立前后端)
2. **目标后端**: FastAPI 或 Flask
3. **目标前端**: Vue 3 + Element Plus 或 React + Ant Design
4. **数据库**: SQLite (data_engine) + MongoDB + Redis
5. **现有功能**: 股票分析、数据下载、历史记录等

## ✅ 期望ChatGPT完成的任务

1. 设计FastAPI/Flask后端架构
2. 设计Vue 3/React前端架构
3. 提供API接口规范
4. 提供前后端分离的迁移方案
5. 集成data_engine到后端服务

