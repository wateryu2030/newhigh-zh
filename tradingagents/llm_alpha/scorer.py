import os
import pandas as pd
from typing import Callable, Optional

try:
    from openai import OpenAI  # openai>=1.0
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    import anthropic
    from anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None  # type: ignore


class LLMScorer:
    def __init__(self, event_data: pd.DataFrame, llm_predict: Optional[Callable[[str], float]] = None):
        self.event_data = event_data.copy()
        # 优先使用传入的预测函数；否则按环境变量自动选择OpenAI或Anthropic；再回退到mock
        self.llm_predict = llm_predict or self._auto_provider_predict() or self._mock_predict

    def _auto_provider_predict(self) -> Optional[Callable[[str], float]]:
        if os.getenv("OPENAI_API_KEY") and OpenAI is not None:
            client = OpenAI()
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

            def _predict_openai(text: str) -> float:
                prompt = self._build_prompt(text)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": "You are a financial sentiment rater."},
                              {"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                val = self._extract_score(resp.choices[0].message.content or "0")
                return val

            return _predict_openai

        if os.getenv("ANTHROPIC_API_KEY") and Anthropic is not None:
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

            def _predict_anthropic(text: str) -> float:
                prompt = self._build_prompt(text)
                resp = client.messages.create(
                    model=model,
                    max_tokens=64,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = "".join([b.text for b in resp.content if getattr(b, 'type', '') == 'text'])
                val = self._extract_score(content)
                return val

            return _predict_anthropic

        return None

    def _build_prompt(self, event_text: str) -> str:
        return (
            "你是金融情绪打分助手。请根据以下事件文本对个股短期影响进行量化评分，范围为[-1, 1]：\n\n"
            f"事件：{event_text}\n\n"
            "规则：\n"
            "- 利好消息→正分，利空→负分，中性→0\n"
            "- 返回唯一的数字（可包含小数），例如：0.35 或 -0.6\n"
            "仅输出数字，不要解释。"
        )

    @staticmethod
    def _extract_score(text: str) -> float:
        try:
            # 提取第一段可解析为float的文本
            stripped = (text or "").strip().split()[0]
            val = float(stripped)
            return max(-1.0, min(1.0, val))
        except Exception:
            # 兜底：基于关键字
            return LLMScorer._mock_predict(text)

    def score(self) -> pd.DataFrame:
        if 'event_text' not in self.event_data.columns:
            raise ValueError("event_data must contain 'event_text' column")
        self.event_data['score'] = self.event_data['event_text'].astype(str).apply(self.llm_predict)
        return self.event_data

    @staticmethod
    def _mock_predict(event_text: str) -> float:
        txt = (event_text or "").lower()
        if 'positive' in txt or '利好' in txt or '增持' in txt:
            return 0.8
        if 'negative' in txt or '利空' in txt or '减持' in txt:
            return -0.8
        return 0.0
