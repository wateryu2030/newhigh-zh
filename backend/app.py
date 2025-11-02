#!/usr/bin/env python3
"""
FastAPI后端应用
提供股票数据查询和同步API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.stock import stock_router

app = FastAPI(
    title="TradingAgents-CN API",
    description="股票分析系统后端API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册股票数据相关的API路由
app.include_router(stock_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "TradingAgents-CN API is running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
