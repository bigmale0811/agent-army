# -*- coding: utf-8 -*-
"""AgentForge LLM 模組 — 大型語言模型抽象層與多供應商整合。

公開 API：
- LLMCallResult: LLM 呼叫結果資料類別
- LLMRouter: 多 Provider LLM 路由器
- BudgetTracker: API 成本追蹤與每日預算管理
- CostEntry: 單次呼叫成本記錄（不可變 dataclass）
"""

from agentforge.llm.budget import BudgetTracker, CostEntry
from agentforge.llm.router import LLMCallResult, LLMRouter

__all__ = [
    "LLMCallResult",
    "LLMRouter",
    "BudgetTracker",
    "CostEntry",
]
