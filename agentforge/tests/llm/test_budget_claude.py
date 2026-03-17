# -*- coding: utf-8 -*-
"""BudgetTracker claude-code 整合測試。

驗證 claude-code/ 前綴的模型費用為 $0（訂閱制免費）。
"""

from __future__ import annotations

import pytest

from agentforge.llm.budget import BudgetTracker


class TestBudgetClaudeCode:
    """BudgetTracker 對 claude-code provider 的費用測試。"""

    def test_claude_code_cost_zero(self) -> None:
        """claude-code/sonnet 費用應為 0.0 USD。"""
        cost = BudgetTracker.calculate_cost(
            "claude-code/sonnet", tokens_in=100_000, tokens_out=50_000
        )
        assert cost == 0.0

    def test_claude_code_any_model_cost_zero(self) -> None:
        """claude-code/ 開頭的任何模型費用都應為 0.0 USD。"""
        assert BudgetTracker.calculate_cost(
            "claude-code/opus", 999_999, 999_999
        ) == 0.0
        assert BudgetTracker.calculate_cost(
            "claude-code/haiku", 1, 1
        ) == 0.0
        assert BudgetTracker.calculate_cost(
            "claude-code/claude-sonnet-4-20250514", 50_000, 20_000
        ) == 0.0

    def test_claude_code_record_cost_zero(self) -> None:
        """透過 BudgetTracker.record() 記錄 claude-code 費用應為 0.0。"""
        tracker = BudgetTracker()
        entry = tracker.record(
            "test-agent", "step-1", "claude-code/sonnet", 10_000, 5_000
        )
        assert entry.cost_usd == 0.0
        assert tracker.get_total() == 0.0
