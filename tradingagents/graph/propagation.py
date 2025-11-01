# TradingAgents/graph/propagation.py

from typing import Dict, Any

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=500):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit
        logger.info(f"🔧 [Propagator] 初始化递归限制: {max_recur_limit}")
        if max_recur_limit < 300:
            logger.warning(f"⚠️ [Propagator] 递归限制({max_recur_limit})可能过低，建议至少300")

    def create_initial_state(
        self, company_name: str, trade_date: str
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        return {
            "messages": [("human", company_name)],
            "company_of_interest": company_name,
            "trade_date": str(trade_date),
            "investment_debate_state": InvestDebateState(
                {"history": "", "current_response": "", "count": 0}
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "history": "",
                    "current_risky_response": "",
                    "current_safe_response": "",
                    "current_neutral_response": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
        }

    def get_graph_args(self) -> Dict[str, Any]:
        """Get arguments for the graph invocation."""
        # LangGraph的config需要直接传递，而不是嵌套在字典中
        args = {
            "config": {
                "recursion_limit": self.max_recur_limit,
            },
        }
        logger.info(f"🔧 [Propagator] Graph配置 - recursion_limit: {self.max_recur_limit}")
        return args
    
    def get_stream_config(self) -> Dict[str, Any]:
        """Get config for graph.stream (需要单独的stream_mode参数)."""
        return {
            "stream_mode": "values",
            "config": {
                "recursion_limit": self.max_recur_limit,
            },
        }
