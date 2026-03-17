# -*- coding: utf-8 -*-
"""BudgetTracker — LLM API 成本追蹤與每日預算管理。

根據模型定價表計算每次呼叫的費用，
累積記錄並在接近或超過每日限額時發出警告。

Ollama 本地模型視為免費（成本為 0.0 USD）。
未知模型不阻擋執行，成本視為 0.0 USD。
"""

from __future__ import annotations

from dataclasses import dataclass

# 定價表（每 1M tokens，美元）
# 來源：各供應商官方頁面，定期更新
PRICING: dict[str, dict[str, float]] = {
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4.1": {"input": 2.00, "output": 8.00},
    "openai/gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "openai/gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gemini/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini/gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    # Ollama 本地模型：免費（不在此表中，由 calculate_cost 處理）
}


@dataclass(frozen=True)
class CostEntry:
    """單次 LLM 呼叫的成本記錄（不可變）。

    Attributes:
        agent_name: 觸發此呼叫的 Agent 名稱。
        step_name: 步驟名稱。
        model: 使用的模型（格式：provider/model-name）。
        tokens_in: 輸入 token 數量。
        tokens_out: 輸出 token 數量。
        cost_usd: 本次呼叫費用（美元）。
    """

    agent_name: str
    step_name: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class BudgetTracker:
    """LLM API 預算追蹤器。

    追蹤所有 LLM 呼叫的累積費用，
    並在接近或超過每日預算上限時發出警告。

    使用方式：
        tracker = BudgetTracker(daily_limit_usd=5.0)
        entry = tracker.record("my-agent", "summarize", "openai/gpt-4o-mini", 100, 50)
        over_warn, msg = tracker.check_budget()
    """

    def __init__(
        self,
        daily_limit_usd: float = 10.0,
        warn_at_percent: float = 80.0,
    ) -> None:
        """初始化 BudgetTracker。

        Args:
            daily_limit_usd: 每日預算上限（美元），預設 $10。
            warn_at_percent: 達到此百分比時觸發警告，預設 80%。
        """
        self._daily_limit = daily_limit_usd
        self._warn_at = warn_at_percent
        self._entries: list[CostEntry] = []

    @staticmethod
    def calculate_cost(
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> float:
        """根據定價表計算本次呼叫成本。

        Ollama/本地模型（以 "ollama/" 開頭）回傳 0.0。
        Claude Code CLI（以 "claude-code/" 開頭）回傳 0.0（訂閱制免費）。
        未知模型也回傳 0.0，不阻擋執行流程。

        Args:
            model: 模型名稱（格式：provider/model-name）。
            tokens_in: 輸入 token 數量。
            tokens_out: 輸出 token 數量。

        Returns:
            預估費用（美元），Ollama 或未知模型為 0.0。
        """
        # Ollama 本地模型免費
        if model.startswith("ollama/"):
            return 0.0

        # Claude Code CLI 訂閱制免費
        if model.startswith("claude-code/"):
            return 0.0

        pricing = PRICING.get(model)
        if pricing is None:
            # 未知模型不阻擋，成本視為 0
            return 0.0

        return (
            tokens_in * pricing["input"] + tokens_out * pricing["output"]
        ) / 1_000_000

    def record(
        self,
        agent_name: str,
        step_name: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> CostEntry:
        """記錄一次 LLM 呼叫並回傳成本記錄。

        Args:
            agent_name: Agent 名稱。
            step_name: 步驟名稱。
            model: 使用的模型（格式：provider/model-name）。
            tokens_in: 輸入 token 數量。
            tokens_out: 輸出 token 數量。

        Returns:
            建立的 CostEntry 記錄（不可變）。
        """
        cost = self.calculate_cost(model, tokens_in, tokens_out)
        entry = CostEntry(
            agent_name=agent_name,
            step_name=step_name,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
        )
        self._entries.append(entry)
        return entry

    def get_total(self) -> float:
        """取得所有 Agent 的累積總費用（美元）。

        Returns:
            累積總費用（美元）。
        """
        return sum(e.cost_usd for e in self._entries)

    def get_agent_total(self, agent_name: str) -> float:
        """取得特定 Agent 的累積費用（美元）。

        Args:
            agent_name: 要查詢的 Agent 名稱。

        Returns:
            該 Agent 的累積費用（美元）。
        """
        return sum(
            e.cost_usd for e in self._entries if e.agent_name == agent_name
        )

    def check_budget(self) -> tuple[bool, str]:
        """檢查目前費用是否接近或超過每日預算。

        回傳 (is_warning, message)：
        - is_warning 為 True 表示需要注意（超出或接近上限）。
        - message 為空字串表示預算正常。

        Returns:
            (是否需要警告, 警告訊息字串)
        """
        total = self.get_total()
        threshold = self._daily_limit * self._warn_at / 100

        if total >= self._daily_limit:
            return (
                True,
                f"已超出每日預算！({total:.4f}/{self._daily_limit:.2f} USD)",
            )

        if total >= threshold:
            percent = total / self._daily_limit * 100
            return (
                True,
                f"接近每日預算上限 ({total:.4f}/{self._daily_limit:.2f} USD, {percent:.0f}%)",
            )

        return False, ""

    @property
    def entries(self) -> tuple[CostEntry, ...]:
        """所有成本記錄（不可變 tuple）。"""
        return tuple(self._entries)

    @property
    def daily_limit(self) -> float:
        """每日預算上限（美元）。"""
        return self._daily_limit

    @property
    def warn_at_percent(self) -> float:
        """警告觸發百分比。"""
        return self._warn_at
