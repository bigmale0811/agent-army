# -*- coding: utf-8 -*-
"""BudgetTracker 單元測試。

測試範圍：
- calculate_cost：OpenAI 計費、Ollama 免費、未知模型免費
- record：正確記錄 CostEntry 並計算成本
- get_total：多筆記錄累積總額
- get_agent_total：按 Agent 篩選
- check_budget：正常 / 接近上限（警告）/ 超出上限
- entries 屬性：回傳不可變 tuple
"""

from __future__ import annotations

import pytest

from agentforge.llm.budget import BudgetTracker, CostEntry, PRICING


class TestCalculateCost:
    """BudgetTracker.calculate_cost 靜態方法測試。"""

    def test_openai_gpt4o_mini_cost(self) -> None:
        """openai/gpt-4o-mini 輸入 1M tokens 費用應為 0.15 USD。"""
        cost = BudgetTracker.calculate_cost(
            "openai/gpt-4o-mini", tokens_in=1_000_000, tokens_out=0
        )
        assert abs(cost - 0.15) < 1e-9

    def test_openai_gpt4o_output_cost(self) -> None:
        """openai/gpt-4o 輸出 1M tokens 費用應為 10.00 USD。"""
        cost = BudgetTracker.calculate_cost(
            "openai/gpt-4o", tokens_in=0, tokens_out=1_000_000
        )
        assert abs(cost - 10.00) < 1e-9

    def test_openai_combined_cost(self) -> None:
        """openai/gpt-4o 100 輸入 + 50 輸出 tokens 應正確計算。

        (100 * 2.50 + 50 * 10.00) / 1_000_000 = 0.00000075
        """
        cost = BudgetTracker.calculate_cost(
            "openai/gpt-4o", tokens_in=100, tokens_out=50
        )
        expected = (100 * 2.50 + 50 * 10.00) / 1_000_000
        assert abs(cost - expected) < 1e-12

    def test_ollama_model_is_free(self) -> None:
        """ollama/ 開頭的任何模型都應回傳 0.0。"""
        assert BudgetTracker.calculate_cost("ollama/qwen3:14b", 10000, 5000) == 0.0
        assert BudgetTracker.calculate_cost("ollama/llama3", 99999, 99999) == 0.0

    def test_unknown_model_is_free(self) -> None:
        """未知模型不在定價表中，應回傳 0.0 而非拋出例外。"""
        assert BudgetTracker.calculate_cost("unknown/model-xyz", 10000, 5000) == 0.0

    def test_zero_tokens_is_zero_cost(self) -> None:
        """輸入輸出均為 0 時，費用應為 0.0。"""
        assert BudgetTracker.calculate_cost("openai/gpt-4o", 0, 0) == 0.0

    def test_gemini_flash_cost(self) -> None:
        """gemini/gemini-2.0-flash 費率應正確計算。"""
        cost = BudgetTracker.calculate_cost(
            "gemini/gemini-2.0-flash", tokens_in=1_000_000, tokens_out=0
        )
        assert abs(cost - 0.10) < 1e-9

    def test_all_pricing_models_are_calculable(self) -> None:
        """定價表中所有模型都應能正確計算費用（不拋出例外）。"""
        for model in PRICING:
            cost = BudgetTracker.calculate_cost(model, 1000, 500)
            assert cost >= 0.0


class TestBudgetTrackerRecord:
    """BudgetTracker.record 方法測試。"""

    def test_record_returns_cost_entry(self) -> None:
        """record() 應回傳 CostEntry dataclass。"""
        tracker = BudgetTracker()
        entry = tracker.record("agent-a", "step-1", "openai/gpt-4o-mini", 100, 50)

        assert isinstance(entry, CostEntry)
        assert entry.agent_name == "agent-a"
        assert entry.step_name == "step-1"
        assert entry.model == "openai/gpt-4o-mini"
        assert entry.tokens_in == 100
        assert entry.tokens_out == 50

    def test_record_calculates_correct_cost(self) -> None:
        """record() 應依定價表計算正確費用。"""
        tracker = BudgetTracker()
        entry = tracker.record("agent-a", "step-1", "openai/gpt-4o-mini", 1_000_000, 0)
        assert abs(entry.cost_usd - 0.15) < 1e-9

    def test_record_ollama_is_free(self) -> None:
        """record() Ollama 模型費用應為 0.0。"""
        tracker = BudgetTracker()
        entry = tracker.record("agent-a", "step-1", "ollama/qwen3:14b", 50000, 20000)
        assert entry.cost_usd == 0.0

    def test_record_accumulates_entries(self) -> None:
        """多次 record() 應累積在 entries 清單中。"""
        tracker = BudgetTracker()
        tracker.record("agent-a", "step-1", "openai/gpt-4o-mini", 100, 50)
        tracker.record("agent-b", "step-2", "ollama/qwen3:14b", 200, 100)

        assert len(tracker.entries) == 2

    def test_cost_entry_is_immutable(self) -> None:
        """CostEntry 是 frozen dataclass，不應允許修改屬性。"""
        entry = CostEntry(
            agent_name="a", step_name="s", model="openai/gpt-4o",
            tokens_in=1, tokens_out=1, cost_usd=0.01
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.cost_usd = 999.0  # type: ignore[misc]


class TestBudgetTrackerGetTotal:
    """BudgetTracker.get_total / get_agent_total 測試。"""

    def test_get_total_empty_is_zero(self) -> None:
        """無記錄時總費用應為 0.0。"""
        tracker = BudgetTracker()
        assert tracker.get_total() == 0.0

    def test_get_total_single_entry(self) -> None:
        """單筆記錄的總費用應等於該記錄的費用。"""
        tracker = BudgetTracker()
        entry = tracker.record("a", "s", "openai/gpt-4o-mini", 1_000_000, 0)
        assert abs(tracker.get_total() - entry.cost_usd) < 1e-12

    def test_get_total_multiple_entries(self) -> None:
        """多筆記錄的總費用應為各筆之和。"""
        tracker = BudgetTracker()
        e1 = tracker.record("a", "s1", "openai/gpt-4o-mini", 1_000_000, 0)
        e2 = tracker.record("b", "s2", "openai/gpt-4o", 0, 1_000_000)
        expected = e1.cost_usd + e2.cost_usd
        assert abs(tracker.get_total() - expected) < 1e-12

    def test_get_agent_total_filters_correctly(self) -> None:
        """get_agent_total() 應只計算指定 Agent 的費用。"""
        tracker = BudgetTracker()
        e1 = tracker.record("agent-a", "s", "openai/gpt-4o-mini", 1_000_000, 0)
        tracker.record("agent-b", "s", "openai/gpt-4o-mini", 1_000_000, 0)

        agent_a_total = tracker.get_agent_total("agent-a")
        assert abs(agent_a_total - e1.cost_usd) < 1e-12

    def test_get_agent_total_no_entries_is_zero(self) -> None:
        """查詢無記錄的 Agent 應回傳 0.0。"""
        tracker = BudgetTracker()
        tracker.record("agent-a", "s", "ollama/qwen3:14b", 100, 50)
        assert tracker.get_agent_total("agent-b") == 0.0

    def test_get_agent_total_multiple_steps(self) -> None:
        """同一 Agent 多個步驟的費用應累加。"""
        tracker = BudgetTracker()
        tracker.record("agent-a", "step-1", "openai/gpt-4o-mini", 1_000_000, 0)
        tracker.record("agent-a", "step-2", "openai/gpt-4o-mini", 1_000_000, 0)
        assert abs(tracker.get_agent_total("agent-a") - 0.30) < 1e-9


class TestBudgetTrackerCheckBudget:
    """BudgetTracker.check_budget 測試。"""

    def test_no_spend_is_ok(self) -> None:
        """無支出時應回傳 (False, '')。"""
        tracker = BudgetTracker(daily_limit_usd=10.0, warn_at_percent=80.0)
        is_warn, msg = tracker.check_budget()
        assert is_warn is False
        assert msg == ""

    def test_below_threshold_is_ok(self) -> None:
        """費用低於警告閾值時應回傳 (False, '')。"""
        tracker = BudgetTracker(daily_limit_usd=10.0, warn_at_percent=80.0)
        # 花費 5 USD（50%），低於 80% 閾值
        tracker.record("a", "s", "openai/gpt-4o", 0, 500_000)  # 5 USD
        is_warn, msg = tracker.check_budget()
        assert is_warn is False
        assert msg == ""

    def test_at_warning_threshold_triggers_warn(self) -> None:
        """費用達到警告閾值（80%）時應觸發警告。"""
        tracker = BudgetTracker(daily_limit_usd=10.0, warn_at_percent=80.0)
        # 花費 8 USD（80%），剛好觸發警告
        tracker.record("a", "s", "openai/gpt-4o", 0, 800_000)  # 8 USD
        is_warn, msg = tracker.check_budget()
        assert is_warn is True
        assert "接近" in msg or "80" in msg

    def test_above_threshold_triggers_warn(self) -> None:
        """費用超過警告閾值但未超過上限時應觸發警告。"""
        tracker = BudgetTracker(daily_limit_usd=10.0, warn_at_percent=80.0)
        # 花費 9 USD（90%）
        tracker.record("a", "s", "openai/gpt-4o", 0, 900_000)  # 9 USD
        is_warn, msg = tracker.check_budget()
        assert is_warn is True

    def test_over_daily_limit_triggers_over_budget(self) -> None:
        """超過每日預算時應回傳包含「超出」的警告訊息。"""
        tracker = BudgetTracker(daily_limit_usd=10.0, warn_at_percent=80.0)
        # 花費 11 USD，超過 10 USD 上限
        tracker.record("a", "s", "openai/gpt-4o", 0, 1_100_000)  # 11 USD
        is_warn, msg = tracker.check_budget()
        assert is_warn is True
        assert "超出" in msg

    def test_exactly_at_daily_limit(self) -> None:
        """費用恰好等於每日限額時應觸發超出警告。"""
        tracker = BudgetTracker(daily_limit_usd=10.0, warn_at_percent=80.0)
        # 花費恰好 10 USD
        tracker.record("a", "s", "openai/gpt-4o", 0, 1_000_000)  # 10 USD
        is_warn, msg = tracker.check_budget()
        assert is_warn is True
        assert "超出" in msg

    def test_custom_warn_at_percent(self) -> None:
        """自訂警告百分比應正確觸發。"""
        tracker = BudgetTracker(daily_limit_usd=100.0, warn_at_percent=50.0)
        # 花費 50 USD，剛好觸發 50% 警告
        tracker.record("a", "s", "openai/gpt-4o", 0, 5_000_000)  # 50 USD
        is_warn, msg = tracker.check_budget()
        assert is_warn is True


class TestBudgetTrackerEntries:
    """BudgetTracker.entries 屬性測試。"""

    def test_entries_returns_tuple(self) -> None:
        """entries 屬性應回傳 tuple（不可變）。"""
        tracker = BudgetTracker()
        assert isinstance(tracker.entries, tuple)

    def test_entries_initially_empty(self) -> None:
        """初始時 entries 應為空 tuple。"""
        tracker = BudgetTracker()
        assert tracker.entries == ()

    def test_entries_reflects_records(self) -> None:
        """entries 應反映所有已記錄的 CostEntry。"""
        tracker = BudgetTracker()
        tracker.record("a", "s1", "ollama/qwen3:14b", 100, 50)
        tracker.record("b", "s2", "openai/gpt-4o-mini", 200, 100)
        entries = tracker.entries
        assert len(entries) == 2
        assert entries[0].agent_name == "a"
        assert entries[1].agent_name == "b"

    def test_entries_are_immutable_copy(self) -> None:
        """entries 回傳的 tuple 不應允許直接修改 tracker 狀態。"""
        tracker = BudgetTracker()
        tracker.record("a", "s", "ollama/qwen3:14b", 100, 50)
        entries_snapshot = tracker.entries
        # 新增第二筆後舊的 snapshot 不應改變
        tracker.record("b", "s", "ollama/qwen3:14b", 200, 100)
        assert len(entries_snapshot) == 1
        assert len(tracker.entries) == 2
