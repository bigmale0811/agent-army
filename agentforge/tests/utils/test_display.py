# -*- coding: utf-8 -*-
"""DisplayManager 與輸出函式測試。

測試 Rich 終端輸出工具，使用 mock Console 驗證輸出格式。
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from agentforge.core.engine import PipelineResult, StepResult
from agentforge.steps.base import StepOutput
from agentforge.utils.display import (
    DisplayManager,
    print_error,
    print_info,
    print_success,
    print_warning,
)


def _make_step_result(name: str, success: bool, output: str = "", error: str = "") -> StepResult:
    """建立測試用 StepResult。"""
    return StepResult(
        step_name=name,
        output=StepOutput(success=success, output=output, error=error),
        elapsed_seconds=0.5,
    )


def _make_pipeline_result(
    agent_name: str,
    success: bool,
    steps: tuple,
    total_cost: float = 0.0,
) -> PipelineResult:
    """建立測試用 PipelineResult。"""
    return PipelineResult(
        agent_name=agent_name,
        success=success,
        steps=steps,
        total_cost_usd=total_cost,
        total_seconds=1.0,
    )


class TestDisplayManagerOnStepStart:
    """on_step_start() 方法測試。"""

    def test_on_step_start_prints_progress(self) -> None:
        """on_step_start 應顯示步驟進度資訊。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        mgr.on_step_start(0, 3, "fetch_data")

        mock_console.print.assert_called_once()
        output = mock_console.print.call_args[0][0]
        assert "1/3" in output
        assert "fetch_data" in output

    def test_on_step_start_shows_correct_step_number(self) -> None:
        """on_step_start 應顯示從 1 起算的步驟編號。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        mgr.on_step_start(2, 5, "analyze")

        output = mock_console.print.call_args[0][0]
        assert "3/5" in output


class TestDisplayManagerOnStepComplete:
    """on_step_complete() 方法測試。"""

    def test_on_step_complete_success(self) -> None:
        """成功步驟應顯示 OK 標記。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        output = StepOutput(success=True, output="done")
        mgr.on_step_complete(0, "step1", output, 0.5)

        call_str = mock_console.print.call_args[0][0]
        assert "OK" in call_str
        assert "step1" in call_str

    def test_on_step_complete_failure(self) -> None:
        """失敗步驟應顯示 FAIL 標記。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        output = StepOutput(success=False, error="something went wrong")
        mgr.on_step_complete(0, "step1", output, 0.1)

        calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("FAIL" in c for c in calls)

    def test_on_step_complete_failure_shows_error(self) -> None:
        """失敗步驟應顯示錯誤訊息。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        output = StepOutput(success=False, error="command not found")
        mgr.on_step_complete(0, "step1", output, 0.1)

        all_output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "command not found" in all_output

    def test_on_step_complete_verbose_shows_output(self) -> None:
        """verbose=True 時成功步驟應顯示輸出內容。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console, verbose=True)
        output = StepOutput(success=True, output="detailed output here")
        mgr.on_step_complete(0, "step1", output, 0.1)

        all_output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "detailed output here" in all_output

    def test_on_step_complete_non_verbose_hides_output(self) -> None:
        """verbose=False 時不應顯示步驟輸出詳情。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console, verbose=False)
        output = StepOutput(success=True, output="hidden output content")
        mgr.on_step_complete(0, "step1", output, 0.1)

        all_output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "hidden output content" not in all_output

    def test_on_step_complete_shows_elapsed_time(self) -> None:
        """應顯示步驟耗時。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        output = StepOutput(success=True, output="")
        mgr.on_step_complete(0, "step1", output, 1.234)

        call_str = mock_console.print.call_args[0][0]
        assert "1.23s" in call_str


class TestDisplayManagerOnPipelineComplete:
    """on_pipeline_complete() 方法測試。"""

    def test_on_pipeline_complete_success(self) -> None:
        """成功 Pipeline 應顯示 DONE 訊息。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        step = _make_step_result("step1", True, "ok")
        result = _make_pipeline_result("my-agent", True, (step,))
        mgr.on_pipeline_complete(result)

        all_output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "DONE" in all_output
        assert "my-agent" in all_output

    def test_on_pipeline_complete_failure(self) -> None:
        """失敗 Pipeline 應顯示 FAIL 訊息。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        step = _make_step_result("failing_step", False, error="crash")
        result = _make_pipeline_result("my-agent", False, (step,))
        mgr.on_pipeline_complete(result)

        all_output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "FAIL" in all_output
        assert "failing_step" in all_output

    def test_on_pipeline_complete_shows_cost_when_nonzero(self) -> None:
        """total_cost_usd > 0 時應顯示費用資訊。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        step = _make_step_result("step1", True)
        result = _make_pipeline_result("my-agent", True, (step,), total_cost=0.005)
        mgr.on_pipeline_complete(result)

        all_output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "0.005" in all_output or "cost" in all_output.lower()

    def test_on_pipeline_complete_no_cost_when_zero(self) -> None:
        """total_cost_usd == 0 時不應顯示費用資訊。"""
        mock_console = MagicMock()
        mgr = DisplayManager(console=mock_console)
        step = _make_step_result("step1", True)
        result = _make_pipeline_result("my-agent", True, (step,), total_cost=0.0)
        mgr.on_pipeline_complete(result)

        all_output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "USD" not in all_output


class TestPrintFunctions:
    """print_success/error/info/warning 函式測試（smoke tests）。"""

    def test_print_success_does_not_raise(self) -> None:
        """print_success 應不拋出例外。"""
        # 使用 patch 避免實際輸出到終端
        from unittest.mock import patch
        with patch("agentforge.utils.display.console"):
            print_success("all good")

    def test_print_error_does_not_raise(self) -> None:
        from unittest.mock import patch
        with patch("agentforge.utils.display.console"):
            print_error("something bad")

    def test_print_info_does_not_raise(self) -> None:
        from unittest.mock import patch
        with patch("agentforge.utils.display.console"):
            print_info("just info")

    def test_print_warning_does_not_raise(self) -> None:
        from unittest.mock import patch
        with patch("agentforge.utils.display.console"):
            print_warning("be careful")
