# -*- coding: utf-8 -*-
"""PipelineEngine 單元測試。

測試 Pipeline 執行引擎的核心邏輯，包括：
- 步驟順序執行與 context 傳遞
- 步驟失敗時中止執行
- dry_run 模式
- ProgressCallback 回呼
- _create_step 工廠方法

所有外部呼叫（subprocess、LLM API）均使用 mock。
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from agentforge.core.engine import (
    PipelineEngine,
    PipelineResult,
    ProgressCallback,
    StepResult,
)
from agentforge.llm.router import LLMCallResult, LLMRouter
from agentforge.schema import AgentDef, GlobalConfig, StepDef
from agentforge.steps.base import StepOutput
from agentforge.steps.llm_step import LLMStep
from agentforge.steps.save_step import SaveStep
from agentforge.steps.shell_step import ShellStep


@pytest.fixture
def minimal_config() -> GlobalConfig:
    """最小化 GlobalConfig。"""
    return GlobalConfig(default_model="ollama/qwen3:14b")


@pytest.fixture
def mock_router() -> MagicMock:
    """建立 mock LLMRouter。"""
    router = MagicMock(spec=LLMRouter)
    router.call.return_value = LLMCallResult(
        content="LLM output",
        model="qwen3:14b",
        tokens_in=5,
        tokens_out=10,
        cost_usd=0.001,
    )
    return router


@pytest.fixture
def shell_agent_def() -> AgentDef:
    """只含 shell 步驟的 AgentDef。"""
    return AgentDef(
        name="test-shell-agent",
        model="ollama/qwen3:14b",
        steps=[
            StepDef(name="step1", action="shell", command="echo hello"),
        ],
    )


@pytest.fixture
def multi_step_agent_def(tmp_path) -> AgentDef:
    """含多個步驟的 AgentDef。"""
    return AgentDef(
        name="multi-step-agent",
        model="ollama/qwen3:14b",
        steps=[
            StepDef(name="fetch", action="shell", command="echo data"),
            StepDef(
                name="analyze",
                action="llm",
                prompt="Analyze: {{ steps.fetch.output }}",
            ),
            StepDef(
                name="save_result",
                action="save",
                path=str(tmp_path / "result.txt"),
                content="{{ steps.analyze.output }}",
            ),
        ],
    )


class TestPipelineEngineExecute:
    """execute() 方法測試。"""

    def test_execute_single_shell_step_success(
        self,
        shell_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """單一 shell 步驟成功執行應回傳 success=True 的 PipelineResult。"""
        engine = PipelineEngine(router=mock_router)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = engine.execute(shell_agent_def)

        assert isinstance(result, PipelineResult)
        assert result.success is True
        assert result.agent_name == "test-shell-agent"
        assert len(result.steps) == 1

    def test_execute_multi_step_success(
        self,
        multi_step_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """多步驟 agent 成功執行所有步驟應回傳 success=True。"""
        engine = PipelineEngine(router=mock_router)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "fetched data\n"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            result = engine.execute(multi_step_agent_def)

        assert result.success is True
        assert len(result.steps) == 3

    def test_execute_context_passes_between_steps(
        self,
        multi_step_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """前一步驟的輸出應透過 context 傳遞給後續步驟。"""
        engine = PipelineEngine(router=mock_router)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "step1 output"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            engine.execute(multi_step_agent_def)

        # LLM 呼叫的 prompt 應包含 shell 步驟的輸出
        call_kwargs = mock_router.call.call_args[1]
        assert "step1 output" in call_kwargs["prompt"]

    def test_execute_stops_on_failure(
        self,
        mock_router: MagicMock,
    ) -> None:
        """步驟失敗時應中止後續步驟執行。"""
        agent_def = AgentDef(
            name="failing-agent",
            model="ollama/qwen3:14b",
            steps=[
                StepDef(name="step1", action="shell", command="echo ok"),
                StepDef(name="step2", action="shell", command="exit 1"),
                StepDef(name="step3", action="shell", command="echo never"),
            ],
        )
        engine = PipelineEngine(router=mock_router)

        def side_effect(cmd, **kwargs):
            mock = MagicMock()
            if "exit 1" in cmd:
                mock.returncode = 1
                mock.stdout = ""
                mock.stderr = "failed"
            else:
                mock.returncode = 0
                mock.stdout = "ok"
                mock.stderr = ""
            return mock

        with patch("subprocess.run", side_effect=side_effect):
            result = engine.execute(agent_def)

        assert result.success is False
        # 只有 2 個步驟執行了（第 3 個被中止）
        assert len(result.steps) == 2

    def test_execute_dry_run_mode(
        self,
        multi_step_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """dry_run=True 時不應呼叫 subprocess 或 LLM API。"""
        engine = PipelineEngine(router=mock_router)

        with patch("subprocess.run") as mock_sub:
            result = engine.execute(multi_step_agent_def, dry_run=True)

        mock_sub.assert_not_called()
        mock_router.call.assert_not_called()
        assert result.success is True

    def test_execute_accumulates_cost(
        self,
        multi_step_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """total_cost_usd 應為所有步驟費用的總和。"""
        # mock_router 每次呼叫花費 0.001
        engine = PipelineEngine(router=mock_router)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "data"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            result = engine.execute(multi_step_agent_def)

        # LLM 步驟花費 0.001，shell 和 save 步驟花費 0
        assert result.total_cost_usd == pytest.approx(0.001)

    def test_execute_result_is_immutable(
        self,
        shell_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """PipelineResult 應為 frozen dataclass（不可變）。"""
        engine = PipelineEngine(router=mock_router)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "ok"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            result = engine.execute(shell_agent_def)

        from dataclasses import fields
        assert result.__dataclass_params__.frozen is True


class TestPipelineEngineCallback:
    """ProgressCallback 回呼測試。"""

    def test_callback_on_step_start_called(
        self,
        shell_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """on_step_start 應在步驟開始前被呼叫。"""
        callback = MagicMock()
        engine = PipelineEngine(router=mock_router, callback=callback)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "ok"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            engine.execute(shell_agent_def)

        callback.on_step_start.assert_called_once_with(0, 1, "step1")

    def test_callback_on_step_complete_called(
        self,
        shell_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """on_step_complete 應在步驟完成後被呼叫。"""
        callback = MagicMock()
        engine = PipelineEngine(router=mock_router, callback=callback)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "ok"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            engine.execute(shell_agent_def)

        callback.on_step_complete.assert_called_once()
        args = callback.on_step_complete.call_args[0]
        assert args[0] == 0   # step_index
        assert args[1] == "step1"  # step_name

    def test_callback_on_pipeline_complete_called(
        self,
        shell_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """on_pipeline_complete 應在 Pipeline 完成後被呼叫一次。"""
        callback = MagicMock()
        engine = PipelineEngine(router=mock_router, callback=callback)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "ok"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            engine.execute(shell_agent_def)

        callback.on_pipeline_complete.assert_called_once()

    def test_no_callback_does_not_raise(
        self,
        shell_agent_def: AgentDef,
        mock_router: MagicMock,
    ) -> None:
        """未提供 callback 時應正常執行不報錯。"""
        engine = PipelineEngine(router=mock_router, callback=None)

        mock_sub = MagicMock()
        mock_sub.returncode = 0
        mock_sub.stdout = "ok"
        mock_sub.stderr = ""

        with patch("subprocess.run", return_value=mock_sub):
            result = engine.execute(shell_agent_def)

        assert result is not None


class TestPipelineEngineCreateStep:
    """_create_step() 工廠方法測試。"""

    def test_create_shell_step(self, mock_router: MagicMock) -> None:
        """shell action 應建立 ShellStep 實例。"""
        engine = PipelineEngine(router=mock_router)
        step_def = StepDef(name="s", action="shell", command="echo hi")
        step = engine._create_step(step_def, "ollama/qwen3:14b")
        assert isinstance(step, ShellStep)

    def test_create_llm_step(self, mock_router: MagicMock) -> None:
        """llm action 應建立 LLMStep 實例。"""
        engine = PipelineEngine(router=mock_router)
        step_def = StepDef(name="s", action="llm", prompt="hello")
        step = engine._create_step(step_def, "ollama/qwen3:14b")
        assert isinstance(step, LLMStep)

    def test_create_save_step(self, mock_router: MagicMock, tmp_path) -> None:
        """save action 應建立 SaveStep 實例。"""
        engine = PipelineEngine(router=mock_router)
        step_def = StepDef(
            name="s",
            action="save",
            path=str(tmp_path / "out.txt"),
            content="hi",
        )
        step = engine._create_step(step_def, "ollama/qwen3:14b")
        assert isinstance(step, SaveStep)
