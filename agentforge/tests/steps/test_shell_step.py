# -*- coding: utf-8 -*-
"""ShellStep 單元測試。

測試 Shell 步驟的執行邏輯，所有 subprocess.run 呼叫均使用 mock，
不實際執行系統命令。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.schema import StepDef
from agentforge.steps.shell_step import ShellStep
from agentforge.utils.template import TemplateEngine


@pytest.fixture
def template_engine() -> TemplateEngine:
    """建立 TemplateEngine 實例。"""
    return TemplateEngine()


@pytest.fixture
def simple_step_def() -> StepDef:
    """建立簡單的 shell StepDef。"""
    return StepDef(name="test_shell", action="shell", command="echo hello")


@pytest.fixture
def template_step_def() -> StepDef:
    """建立含模板的 shell StepDef。"""
    return StepDef(
        name="process",
        action="shell",
        command="echo {{ steps.fetch.output }}",
    )


class TestShellStepExecute:
    """execute() 方法測試。"""

    def test_execute_success(
        self, simple_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """成功執行命令應回傳 success=True 及輸出內容。"""
        step = ShellStep(simple_step_def, template_engine)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            output = step.execute({})

        assert output.success is True
        assert output.output == "hello\n"
        assert output.error == ""
        assert output.cost_usd == 0.0
        assert output.tokens == 0
        mock_run.assert_called_once_with(
            "echo hello",
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )

    def test_execute_failure(
        self, simple_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """命令回傳非零退出碼應回傳 success=False。"""
        step = ShellStep(simple_step_def, template_engine)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command not found"

        with patch("subprocess.run", return_value=mock_result):
            output = step.execute({})

        assert output.success is False
        assert output.error == "command not found"

    def test_execute_with_template(
        self, template_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """命令中的模板應被正確替換後再執行。"""
        step = ShellStep(template_step_def, template_engine)
        context = {"steps": {"fetch": {"output": "world", "error": ""}}}

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "world\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            output = step.execute(context)

        assert output.success is True
        # 驗證命令中的佔位符已被替換
        call_args = mock_run.call_args[0][0]
        assert call_args == "echo world"

    def test_execute_timeout(
        self, simple_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """命令逾時應回傳 success=False 及逾時錯誤訊息。"""
        import subprocess

        step = ShellStep(simple_step_def, template_engine)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 300)):
            output = step.execute({})

        assert output.success is False
        assert "逾時" in output.error

    def test_execute_exception(
        self, simple_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """subprocess 拋出例外應回傳 success=False。"""
        step = ShellStep(simple_step_def, template_engine)

        with patch("subprocess.run", side_effect=OSError("permission denied")):
            output = step.execute({})

        assert output.success is False
        assert "permission denied" in output.error


class TestShellStepDryRun:
    """dry_run() 方法測試。"""

    def test_dry_run_returns_success(
        self, simple_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """dry_run 應回傳 success=True 且不呼叫 subprocess。"""
        step = ShellStep(simple_step_def, template_engine)

        with patch("subprocess.run") as mock_run:
            output = step.dry_run({})

        assert output.success is True
        mock_run.assert_not_called()

    def test_dry_run_output_contains_command(
        self, simple_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """dry_run 輸出應包含要執行的命令。"""
        step = ShellStep(simple_step_def, template_engine)
        output = step.dry_run({})

        assert "DRY-RUN" in output.output
        assert "SHELL" in output.output
        assert "echo hello" in output.output

    def test_dry_run_with_template(
        self, template_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """dry_run 應渲染模板並在輸出中顯示渲染後的命令。"""
        step = ShellStep(template_step_def, template_engine)
        context = {"steps": {"fetch": {"output": "world", "error": ""}}}
        output = step.dry_run(context)

        assert "echo world" in output.output


class TestShellStepProperties:
    """步驟屬性測試。"""

    def test_name_property(
        self, simple_step_def: StepDef, template_engine: TemplateEngine
    ) -> None:
        """name 屬性應回傳步驟定義的名稱。"""
        step = ShellStep(simple_step_def, template_engine)
        assert step.name == "test_shell"
