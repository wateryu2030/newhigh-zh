import pandas as pd
from typing import Callable


class LLMScorer:
    def __init__(self, event_data: pd.DataFrame, llm_predict: Callable[[str], float] | None = None):
        self.event_data = event_data.copy()
        self.llm_predict = llm_predict or self._mock_predict

    def score(self) -> pd.DataFrame:
        if 'event_text' not in self.event_data.columns:
            raise ValueError("event_data must contain 'event_text' column")
        self.event_data['score'] = self.event_data['event_text'].astype(str).apply(self.llm_predict)
        return self.event_data

    @staticmethod
    def _mock_predict(event_text: str) -> float:
        txt = event_text.lower()
        if 'positive' in txt or '利好' in txt or '增持' in txt:
            return 1.0
        if 'negative' in txt or '利空' in txt or '减持' in txt:
            return -1.0
        return 0.0
