# -*- coding: utf-8 -*-
"""TelegramFormatter 測試套件。

驗證所有訊息格式化功能，確保輸出符合預期格式。
不依賴 Telegram SDK。
"""

from __future__ import annotations

import pytest

from agentforge.telegram.formatter import TelegramFormatter


@pytest.fixture
def formatter() -> TelegramFormatter:
    """建立 TelegramFormatter 實例。"""
    return TelegramFormatter()


class TestFormatWelcome:
    """歡迎訊息格式化測試。"""

    def test_format_welcome_contains_welcome_word(self, formatter: TelegramFormatter) -> None:
        """歡迎訊息應包含「歡迎」字樣。"""
        result = formatter.format_welcome()
        assert "歡迎" in result

    def test_format_welcome_is_string(self, formatter: TelegramFormatter) -> None:
        """歡迎訊息應回傳字串。"""
        result = formatter.format_welcome()
        assert isinstance(result, str)
        assert len(result) > 0


class TestFormatHelp:
    """指令說明格式化測試。"""

    def test_format_help_contains_list_command(self, formatter: TelegramFormatter) -> None:
        """說明應包含 /list 指令。"""
        result = formatter.format_help()
        assert "/list" in result

    def test_format_help_contains_run_command(self, formatter: TelegramFormatter) -> None:
        """說明應包含 /run 指令。"""
        result = formatter.format_help()
        assert "/run" in result

    def test_format_help_contains_status_command(self, formatter: TelegramFormatter) -> None:
        """說明應包含 /status 指令。"""
        result = formatter.format_help()
        assert "/status" in result


class TestFormatAgentList:
    """Agent 清單格式化測試。"""

    def test_format_agent_list_with_agents(self, formatter: TelegramFormatter) -> None:
        """有 Agent 時應格式化清單並包含名稱。"""
        agents = [
            {"name": "email-agent", "description": "寄送電子郵件", "steps": 3},
            {"name": "report-agent", "description": "產生報告", "steps": 5},
        ]
        result = formatter.format_agent_list(agents)
        assert "email-agent" in result
        assert "report-agent" in result

    def test_format_agent_list_empty(self, formatter: TelegramFormatter) -> None:
        """空清單應顯示「目前沒有 Agent」。"""
        result = formatter.format_agent_list([])
        assert "沒有 Agent" in result or "目前沒有" in result

    def test_format_agent_list_shows_description(self, formatter: TelegramFormatter) -> None:
        """清單應顯示 Agent 描述。"""
        agents = [{"name": "test-agent", "description": "測試用 Agent", "steps": 2}]
        result = formatter.format_agent_list(agents)
        assert "測試用 Agent" in result

    def test_format_agent_list_shows_step_count(self, formatter: TelegramFormatter) -> None:
        """清單應顯示步驟數量。"""
        agents = [{"name": "my-agent", "description": "描述", "steps": 7}]
        result = formatter.format_agent_list(agents)
        assert "7" in result


class TestFormatRunStarted:
    """執行開始訊息測試。"""

    def test_format_run_started_contains_agent_name(self, formatter: TelegramFormatter) -> None:
        """執行開始訊息應包含 Agent 名稱。"""
        result = formatter.format_run_started("my-agent")
        assert "my-agent" in result

    def test_format_run_started_contains_running_indicator(self, formatter: TelegramFormatter) -> None:
        """執行開始訊息應包含執行中指示（⏳ 或「執行」字樣）。"""
        result = formatter.format_run_started("test-agent")
        # 含有執行中的指示
        assert "⏳" in result or "執行" in result or "執行中" in result


class TestFormatRunResult:
    """執行結果格式化測試。"""

    def test_format_run_result_success(self, formatter: TelegramFormatter) -> None:
        """成功結果應包含成功指示。"""
        steps = [
            {"name": "step1", "success": True, "elapsed": 1.2},
            {"name": "step2", "success": True, "elapsed": 0.8},
        ]
        result = formatter.format_run_result(
            agent_name="my-agent",
            success=True,
            steps_summary=steps,
            elapsed=2.0,
            cost=0.005,
        )
        assert "my-agent" in result
        # 應有成功指示
        assert "成功" in result or "✅" in result

    def test_format_run_result_failure(self, formatter: TelegramFormatter) -> None:
        """失敗結果應包含失敗指示。"""
        steps = [
            {"name": "step1", "success": True, "elapsed": 1.0},
            {"name": "step2", "success": False, "elapsed": 0.5},
        ]
        result = formatter.format_run_result(
            agent_name="fail-agent",
            success=False,
            steps_summary=steps,
            elapsed=1.5,
            cost=0.002,
        )
        assert "fail-agent" in result
        # 應有失敗指示
        assert "失敗" in result or "❌" in result

    def test_format_run_result_shows_cost(self, formatter: TelegramFormatter) -> None:
        """執行結果應顯示費用資訊。"""
        steps = [{"name": "s1", "success": True, "elapsed": 1.0}]
        result = formatter.format_run_result(
            agent_name="cost-agent",
            success=True,
            steps_summary=steps,
            elapsed=1.0,
            cost=0.0123,
        )
        # 費用應出現在訊息中
        assert "0.012" in result or "cost" in result.lower() or "費用" in result or "$" in result

    def test_format_run_result_shows_elapsed(self, formatter: TelegramFormatter) -> None:
        """執行結果應顯示耗時。"""
        steps = [{"name": "s1", "success": True, "elapsed": 1.0}]
        result = formatter.format_run_result(
            agent_name="timing-agent",
            success=True,
            steps_summary=steps,
            elapsed=3.14,
            cost=0.0,
        )
        assert "3.14" in result or "3.1" in result or "秒" in result


class TestFormatStatus:
    """統計資料格式化測試。"""

    def test_format_status_with_data(self, formatter: TelegramFormatter) -> None:
        """有統計資料時應顯示 Agent 名稱與執行次數。"""
        stats = [
            {"agent": "email-agent", "runs": 10, "success": 9, "cost": 0.05},
            {"agent": "report-agent", "runs": 5, "success": 5, "cost": 0.02},
        ]
        result = formatter.format_status(stats)
        assert "email-agent" in result
        assert "report-agent" in result

    def test_format_status_empty(self, formatter: TelegramFormatter) -> None:
        """空統計應提示無資料。"""
        result = formatter.format_status([])
        # 沒有資料應有提示
        assert len(result) > 0

    def test_format_status_shows_run_count(self, formatter: TelegramFormatter) -> None:
        """統計應顯示執行次數。"""
        stats = [{"agent": "my-agent", "runs": 42, "success": 40, "cost": 0.1}]
        result = formatter.format_status(stats)
        assert "42" in result


class TestTruncate:
    """訊息截斷測試。"""

    def test_truncate_short_message_unchanged(self, formatter: TelegramFormatter) -> None:
        """短訊息不應被截斷。"""
        short = "Hello, World!"
        result = formatter._truncate(short)
        assert result == short

    def test_truncate_long_message(self, formatter: TelegramFormatter) -> None:
        """超過 4096 字元的訊息應被截斷。"""
        long_text = "A" * 5000
        result = formatter._truncate(long_text)
        assert len(result) <= TelegramFormatter.MAX_MESSAGE_LENGTH
        assert "截斷" in result or "..." in result

    def test_truncate_exact_limit_unchanged(self, formatter: TelegramFormatter) -> None:
        """恰好 4096 字元不應被截斷。"""
        exact = "B" * TelegramFormatter.MAX_MESSAGE_LENGTH
        result = formatter._truncate(exact)
        assert result == exact

    def test_truncate_over_limit_adds_suffix(self, formatter: TelegramFormatter) -> None:
        """截斷後應加上截斷提示。"""
        long_text = "C" * 5000
        result = formatter._truncate(long_text)
        assert "截斷" in result or "..." in result
