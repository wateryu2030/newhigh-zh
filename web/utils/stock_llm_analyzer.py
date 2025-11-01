"""
股票选股LLM分析工具
集成真实LLM API进行智能选股分析
"""

import os
import json
import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.logging_init import get_logger

logger = get_logger('web.stock_llm_analyzer')


class StockLLMAnalyzer:
    """股票选股LLM分析器"""
    
    def __init__(self, api_key: str, provider: str = "dashscope"):
        """
        初始化LLM分析器
        
        Args:
            api_key: LLM API密钥
            provider: 提供商 (dashscope/openai/anthropic)
        """
        self.api_key = api_key
        self.provider = provider.lower()
        self._client = None
        
        # 初始化客户端
        self._init_client()
    
    def _init_client(self):
        """初始化LLM客户端"""
        try:
            if self.provider == "dashscope":
                try:
                    import dashscope
                    dashscope.api_key = self.api_key
                    self._client = dashscope
                    self._model = "qwen-plus-latest"
                except ImportError:
                    logger.warning("dashscope未安装，尝试使用OpenAI兼容接口")
                    self._init_openai_compatible()
            
            elif self.provider == "openai":
                try:
                    from openai import OpenAI
                    self._client = OpenAI(api_key=self.api_key)
                    self._model = "gpt-4o-mini"
                except ImportError:
                    raise ImportError("openai包未安装")
            
            elif self.provider == "anthropic":
                try:
                    import anthropic
                    self._client = anthropic.Anthropic(api_key=self.api_key)
                    self._model = "claude-3-5-sonnet-latest"
                except ImportError:
                    raise ImportError("anthropic包未安装")
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")
        
        except Exception as e:
            logger.error(f"初始化LLM客户端失败: {e}")
            raise
    
    def _init_openai_compatible(self):
        """使用OpenAI兼容接口（Dashscope）"""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            self._model = "qwen-plus-latest"
            self.provider = "dashscope"
        except ImportError:
            raise ImportError("openai包未安装")
    
    def analyze_stocks(
        self,
        candidates: pd.DataFrame,
        strategy: str,
        topk: int = 20
    ) -> List[Dict]:
        """
        使用LLM分析股票并排序
        
        Args:
            candidates: 候选股票DataFrame
            strategy: 投资策略（保守/平衡/激进/价值/成长）
            topk: 返回前K只股票
        
        Returns:
            分析结果列表
        """
        if self._client is None:
            raise ValueError("LLM客户端未初始化")
        
        # 构建分析提示
        prompt = self._build_analysis_prompt(candidates, strategy, topk)
        
        # 调用LLM
        try:
            response = self._call_llm(prompt)
            
            # 解析响应
            results = self._parse_response(response, candidates, topk)
            
            return results
        
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            # 返回基于简单评分的排序结果作为降级方案
            return self._fallback_ranking(candidates, topk)
    
    def _build_analysis_prompt(self, candidates: pd.DataFrame, strategy: str, topk: int) -> str:
        """构建分析提示"""
        
        # 准备股票数据摘要
        stock_summary = []
        for idx, row in candidates.head(50).iterrows():  # 限制前50只避免token过多
            stock_info = {
                "code": str(row.get("code", "N/A")),
                "name": str(row.get("name", "N/A")),
                "price": float(row.get("price", 0)) if pd.notna(row.get("price")) else 0,
                "market_cap": float(row.get("market_cap", 0)) / 1e8 if pd.notna(row.get("market_cap")) else 0,  # 转换为亿元
            }
            
            # 添加财务指标（如果有）
            if "pe" in row and pd.notna(row.get("pe")):
                stock_info["pe"] = float(row.get("pe"))
            if "pb" in row and pd.notna(row.get("pb")):
                stock_info["pb"] = float(row.get("pb"))
            if "ps" in row and pd.notna(row.get("ps")):
                stock_info["ps"] = float(row.get("ps"))
            
            stock_summary.append(stock_info)
        
        # 策略说明
        strategy_desc = {
            "保守": "侧重低估值、稳定增长、高分红率",
            "平衡": "兼顾成长性和价值，适中的估值水平",
            "激进": "侧重高成长、高弹性，可接受较高估值",
            "价值": "侧重低PE、低PB，寻找被低估的股票",
            "成长": "侧重高ROE、高增长潜力，关注业绩增速"
        }
        
        prompt = f"""你是一位专业的股票投资分析师。请根据以下股票数据和投资策略，分析并推荐最合适的{topk}只股票。

**投资策略**: {strategy}
**策略说明**: {strategy_desc.get(strategy, '平衡投资')}

**候选股票数据**（共{len(candidates)}只）:
{json.dumps(stock_summary, ensure_ascii=False, indent=2)}

**分析要求**:
1. 根据{strategy}策略，综合考虑估值水平、市值规模、财务指标等因素
2. 优先选择符合策略特点的股票
3. 返回JSON格式，包含以下字段：
   - code: 股票代码
   - name: 股票名称
   - score: 评分（0-100，越高越好）
   - reason: 推荐理由（简要说明）

**输出格式**（严格JSON数组）:
[
  {{"code": "000001", "name": "股票名称", "score": 85, "reason": "推荐理由"}},
  ...
]

请只返回JSON数组，不要其他说明文字。"""

        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        try:
            if self.provider == "dashscope" and hasattr(self._client, 'Generation'):
                # 使用DashScope原生API
                from dashscope import Generation
                response = Generation.call(
                    model=self._model,
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=2000
                )
                if response.status_code == 200:
                    return response.output.text
                else:
                    raise Exception(f"DashScope API错误: {response.message}")
            
            elif self.provider == "openai" or (self.provider == "dashscope" and hasattr(self._client, 'chat')):
                # 使用OpenAI兼容接口
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": "你是一位专业的股票投资分析师，严格按照JSON格式返回分析结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2000
                )
                return response.choices[0].message.content
            
            elif self.provider == "anthropic":
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=2000,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                return "".join([b.text for b in response.content if getattr(b, 'type', '') == 'text'])
            
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")
        
        except Exception as e:
            logger.error(f"LLM API调用失败: {e}")
            raise
    
    def _parse_response(self, response: str, candidates: pd.DataFrame, topk: int) -> List[Dict]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                json_str = json_match.group(0)
                results = json.loads(json_str)
            else:
                # 如果不是JSON，尝试按行解析
                results = []
                for line in response.split('\n'):
                    if '{' in line and '}' in line:
                        try:
                            obj = json.loads(line)
                            results.append(obj)
                        except:
                            pass
        except Exception as e:
            logger.warning(f"JSON解析失败，使用降级方案: {e}")
            return self._fallback_ranking(candidates, topk)
        
        # 转换为统一格式
        formatted_results = []
        for item in results[:topk]:
            code = str(item.get("code", ""))
            name = item.get("name", "")
            score = float(item.get("score", 0))
            reason = item.get("reason", "基于LLM分析推荐")
            
            # 从原始数据中获取更多信息
            stock_row = candidates[candidates["code"] == code]
            if not stock_row.empty:
                row = stock_row.iloc[0]
                formatted_results.append({
                    "code": code,
                    "name": name or str(row.get("name", "")),
                    "price": f"￥{row.get('price', 0):.2f}" if pd.notna(row.get("price")) else "N/A",
                    "market_cap": f"{row.get('market_cap', 0) / 1e8:.2f}亿" if pd.notna(row.get("market_cap")) else "N/A",
                    "pe": f"{row.get('pe', 0):.2f}" if pd.notna(row.get("pe")) and row.get("pe", 0) > 0 else "N/A",
                    "pb": f"{row.get('pb', 0):.2f}" if pd.notna(row.get("pb")) and row.get("pb", 0) > 0 else "N/A",
                    "score": score,
                    "reason": reason
                })
        
        # 按评分排序
        formatted_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return formatted_results[:topk]
    
    def _fallback_ranking(self, candidates: pd.DataFrame, topk: int) -> List[Dict]:
        """降级方案：基于简单评分排序"""
        results = []
        for _, row in candidates.head(topk * 2).iterrows():
            score = row.get("score", 0)
            if score > 0:
                results.append({
                    "code": str(row.get("code", "N/A")),
                    "name": str(row.get("name", "N/A")),
                    "price": f"￥{row.get('price', 0):.2f}" if pd.notna(row.get("price")) else "N/A",
                    "market_cap": f"{row.get('market_cap', 0) / 1e8:.2f}亿" if pd.notna(row.get("market_cap")) else "N/A",
                    "pe": f"{row.get('pe', 0):.2f}" if pd.notna(row.get("pe")) and row.get("pe", 0) > 0 else "N/A",
                    "pb": f"{row.get('pb', 0):.2f}" if pd.notna(row.get("pb")) and row.get("pb", 0) > 0 else "N/A",
                    "score": float(score),
                    "reason": "基于简单评分筛选"
                })
        
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:topk]

