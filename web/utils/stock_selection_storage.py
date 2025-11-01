"""
选股结果持久化存储
保存历史选股记录到数据库或文件
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import sqlite3
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.logging_init import get_logger

logger = get_logger('web.stock_selection_storage')


class StockSelectionStorage:
    """选股结果存储管理器"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化存储管理器
        
        Args:
            db_path: 数据库路径，默认在data目录
        """
        if db_path is None:
            db_path = project_root / "data" / "stock_selections.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 选股记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS selections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                selection_id TEXT UNIQUE NOT NULL,
                strategy TEXT NOT NULL,
                filter_conditions TEXT,
                total_candidates INTEGER,
                selected_count INTEGER,
                created_at TEXT NOT NULL,
                results TEXT,
                metadata TEXT
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_selection_id ON selections(selection_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON selections(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy ON selections(strategy)")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ 选股结果存储数据库初始化完成: {self.db_path}")
    
    def save_selection(
        self,
        results: List[Dict],
        strategy: str,
        filter_conditions: Dict,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        保存选股结果
        
        Args:
            results: 选股结果列表
            strategy: 投资策略
            filter_conditions: 筛选条件
            metadata: 额外元数据
        
        Returns:
            选股记录ID
        """
        selection_id = f"selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(results)}"
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO selections (
                    selection_id, strategy, filter_conditions, total_candidates,
                    selected_count, created_at, results, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                selection_id,
                strategy,
                json.dumps(filter_conditions, ensure_ascii=False),
                filter_conditions.get("total_candidates", len(results)),
                len(results),
                datetime.now().isoformat(),
                json.dumps(results, ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False)
            ))
            
            conn.commit()
            logger.info(f"✅ 选股结果已保存: {selection_id}")
            return selection_id
        
        except sqlite3.IntegrityError:
            # 如果ID已存在，使用时间戳生成新ID
            selection_id = f"selection_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{len(results)}"
            cursor.execute("""
                INSERT INTO selections (
                    selection_id, strategy, filter_conditions, total_candidates,
                    selected_count, created_at, results, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                selection_id,
                strategy,
                json.dumps(filter_conditions, ensure_ascii=False),
                filter_conditions.get("total_candidates", len(results)),
                len(results),
                datetime.now().isoformat(),
                json.dumps(results, ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False)
            ))
            conn.commit()
            return selection_id
        
        finally:
            conn.close()
    
    def get_selection(self, selection_id: str) -> Optional[Dict]:
        """获取选股记录"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM selections WHERE selection_id = ?
        """, (selection_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "selection_id": row[1],
                "strategy": row[2],
                "filter_conditions": json.loads(row[3]),
                "total_candidates": row[4],
                "selected_count": row[5],
                "created_at": row[6],
                "results": json.loads(row[7]),
                "metadata": json.loads(row[8])
            }
        
        return None
    
    def list_selections(
        self,
        limit: int = 50,
        strategy: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        列出选股记录
        
        Args:
            limit: 返回记录数限制
            strategy: 筛选策略
            start_date: 开始日期（ISO格式）
            end_date: 结束日期（ISO格式）
        
        Returns:
            选股记录列表
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = "SELECT * FROM selections WHERE 1=1"
        params = []
        
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "selection_id": row[1],
                "strategy": row[2],
                "filter_conditions": json.loads(row[3]),
                "total_candidates": row[4],
                "selected_count": row[5],
                "created_at": row[6],
                "results": json.loads(row[7]),
                "metadata": json.loads(row[8])
            })
        
        return results
    
    def delete_selection(self, selection_id: str) -> bool:
        """删除选股记录"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM selections WHERE selection_id = ?", (selection_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"✅ 选股记录已删除: {selection_id}")
        
        return deleted


# 全局实例
_storage_instance = None

def get_storage() -> StockSelectionStorage:
    """获取存储管理器实例（单例）"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StockSelectionStorage()
    return _storage_instance

