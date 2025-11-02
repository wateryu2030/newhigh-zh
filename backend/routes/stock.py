#!/usr/bin/env python3
"""
股票数据相关API路由
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import subprocess
import os
import sys
import pandas as pd
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.db_utils import get_engine, read_sql

stock_router = APIRouter()

# 获取数据库URL（使用data_engine的配置）
DB_URL = f"sqlite:///{project_root / 'data' / 'stock_database.db'}"

# 获取基础信息的API
@stock_router.get("/stock/basic")
async def get_stock_basic():
    """获取股票基础信息"""
    try:
        engine = get_engine(DB_URL)
        query = "SELECT code as ts_code, code_name as name, type as industry FROM stock_basic_info LIMIT 10;"
        df = pd.read_sql(query, engine)
        return JSONResponse(content={"data": df.to_dict(orient="records")})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# 触发数据同步的API
@stock_router.post("/data_sync")
async def run_data_sync():
    """触发A股数据同步"""
    try:
        data_engine_script = project_root / "data_engine" / "update_all.py"
        result = subprocess.run(
            [sys.executable, str(data_engine_script)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode == 0:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "数据更新成功",
                    "output": result.stdout
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": result.stderr or "数据同步失败",
                    "output": result.stdout
                }
            )
    except subprocess.TimeoutExpired:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "数据同步超时"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
