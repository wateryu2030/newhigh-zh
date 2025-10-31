import os, json, re
import pandas as pd
from typing import Callable, Optional, Dict, Any

try:
    from openai import OpenAI  # openai>=1.0
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    import anthropic
    from anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None  # type: ignore


_STRUCT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": -1.0, "maximum": 1.0},
        "rationale": {"type": "string"},
        "event_type": {"type": "string"}
    },
    "required": ["score"]
}


class LLMScorer:
    def __init__(self, event_data: pd.DataFrame, llm_predict: Optional[Callable[[str], float]] = None):
        self.event_data = event_data.copy()
        self.llm_predict = llm_predict or self._auto_provider_predict() or self._mock_predict

    def _auto_provider_predict(self) -> Optional[Callable[[str], float]]:
        if os.getenv("OPENAI_API_KEY") and OpenAI is not None:
            client = OpenAI()
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

            def _predict_openai(text: str) -> float:
                prompt = self._build_prompt(text)
                # 尽量让模型返回JSON
                sys_instr = (
                    "You are a financial sentiment rater. Return ONLY a compact JSON that matches this schema: "
                    f"{json.dumps(_STRUCT_SCHEMA)}."
                )
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": sys_instr},
                              {"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                content = resp.choices[0].message.content or ""
                val = self._extract_score(content)
                return val

            return _predict_openai

        if os.getenv("ANTHROPIC_API_KEY") and Anthropic is not None:
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

            def _predict_anthropic(text: str) -> float:
                prompt = (
                    "You are a financial sentiment rater. Return ONLY a compact JSON that matches this schema: "
                    f"{json.dumps(_STRUCT_SCHEMA)}.\n" + self._build_prompt(text)
                )
                resp = client.messages.create(
                    model=model,
                    max_tokens=128,
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
            "请为以下事件对个股短期影响进行量化评分，范围[-1,1]。\n"
            f"事件：{event_text}\n"
            "严格输出JSON对象，如 {\"score\":0.35,\"rationale\":\"订单增长\",\"event_type\":\"earnings\"}"
        )

    @staticmethod
    def _extract_score(text: str) -> float:
        # 优先尝试JSON解析
        try:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                obj = json.loads(m.group(0))
                score = float(obj.get('score'))
                return max(-1.0, min(1.0, score))
        except Exception:
            pass
        # 其次尝试直接float
        try:
            stripped = (text or "").strip().split()[0]
            return max(-1.0, min(1.0, float(stripped)))
        except Exception:
            return LLMScorer._mock_predict(text)

    @staticmethod
    def _extract_struct(text: str) -> Dict[str, Any]:
        """Return {'score': float, 'rationale': str, 'event_type': str} if possible."""
        out = {'score': 0.0, 'rationale': '', 'event_type': ''}
        try:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                obj = json.loads(m.group(0))
                if 'score' in obj:
                    out['score'] = max(-1.0, min(1.0, float(obj['score'])))
                out['rationale'] = str(obj.get('rationale', ''))
                out['event_type'] = str(obj.get('event_type', ''))
                return out
        except Exception:
            pass
        # fallback
        out['score'] = LLMScorer._mock_predict(text)
        return out

    def score(self) -> pd.DataFrame:
        if 'event_text' not in self.event_data.columns:
            raise ValueError("event_data must contain 'event_text' column")
        # 生成结构化列
        structs = self.event_data['event_text'].astype(str).apply(
            lambda t: {'score': self.llm_predict(t)} if self.llm_predict == self._mock_predict else self._extract_struct(self._build_prompt(t))
        )
        self.event_data['score'] = structs.apply(lambda d: d.get('score', 0.0))
        self.event_data['rationale'] = structs.apply(lambda d: d.get('rationale', ''))
        self.event_data['event_type'] = structs.apply(lambda d: d.get('event_type', ''))
        return self.event_data

    @staticmethod
    def _mock_predict(event_text: str) -> float:
        txt = (event_text or "").lower()
        if 'positive' in txt or '利好' in txt or '增持' in txt:
            return 0.8
        if 'negative' in txt or '利空' in txt or '减持' in txt:
            return -0.8
        return 0.0
