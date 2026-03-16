# -*- coding: utf-8 -*-
"""LLMStep 單元測試。

所有 LLM API 呼叫均使用 mock，不實際呼叫任何 API。
測試 LLMStep 的模板渲染、模型選擇、成功/失敗回傳等邏輯。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.llm.router import LLMCallResult, LLMRouter
from agentforge.schema import GlobalConfig, StepDef
from agentforge.steps.llm_step import LLMStep
from agentforge.utils.template import TemplateEngine


@pytest.fixture
def template_engine() -> TemplateEngine:
    """建立 TemplateEngine 實例。"""
    return TemplateEngine()


@pytest.fixture
def mock_router() -> MagicMock:
    """建立 mock LLMRouter。"""
    router = MagicMock(spec=LLMRouter)
    router.call.return_value = LLMCallResult(
        content="mock LLM response",
        model="qwen3:14b",
        tokens_in=10,
        tokens_out=20,
        cost_usd=0.0,
    )
    return router


@pytest.fixture
def simple_llm_step_def() -> StepDef:
    """建立簡單的 llm StepDef。"""
    return StepDef(
        name="analyze",
        action="llm",
        prompt="Please analyze the following.",
    )


@pytest.fixture
def template_llm_step_def() -> StepDef:
    """建立含模板的 llm StepDef。"""
    return StepDef(
        name="summarize",
        action="llm",
        prompt="Summarize: {{ steps.fetch.output }}",
        input="{{ steps.fetch.error }}",
    )


@pytest.fixture
def step_with_model_def() -> StepDef:
    """建立指定 model 的 llm StepDef。"""
    return StepDef(
        name="custom_model_step",
        action="llm",
        prompt="Hello",
        model="openai/gpt-4o",
    )


class TestLLMStepExecute:
    """execute() 方法測試。"""

    def test_execute_success(
        self,
        simple_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """成功呼叫 LLM 應回傳 success=True 及回應內容。"""
        step = LLMStep(
            simple_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        output = step.execute({})

        assert output.success is True
        assert output.output == "mock LLM response"
        assert output.tokens == 30  # 10 + 20
        assert output.cost_usd == 0.0

    def test_execute_uses_default_model(
        self,
        simple_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """未設定 step-level model 時應使用 default_model。"""
        step = LLMStep(
            simple_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        step.execute({})

        mock_router.call.assert_called_once()
        call_kwargs = mock_router.call.call_args[1]
        assert call_kwargs["model_ref"] == "ollama/qwen3:14b"

    def test_execute_uses_step_model_override(
        self,
        step_with_model_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """步驟設定 model 時應覆蓋 default_model。"""
        step = LLMStep(
            step_with_model_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        step.execute({})

        call_kwargs = mock_router.call.call_args[1]
        assert call_kwargs["model_ref"] == "openai/gpt-4o"

    def test_execute_renders_prompt_template(
        self,
        template_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """prompt 中的模板應被正確替換。"""
        step = LLMStep(
            template_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        context = {"steps": {"fetch": {"output": "content here", "error": "warn"}}}
        step.execute(context)

        call_kwargs = mock_router.call.call_args[1]
        assert "content here" in call_kwargs["prompt"]

    def test_execute_renders_input_template(
        self,
        template_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """input 中的模板應被正確替換並傳入 context 參數。"""
        step = LLMStep(
            template_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        context = {"steps": {"fetch": {"output": "content here", "error": "error msg"}}}
        step.execute(context)

        call_kwargs = mock_router.call.call_args[1]
        assert call_kwargs["context"] == "error msg"

    def test_execute_no_input_field(
        self,
        simple_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """未設定 input 欄位時，context 參數應為空字串。"""
        step = LLMStep(
            simple_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        step.execute({})

        call_kwargs = mock_router.call.call_args[1]
        assert call_kwargs["context"] == ""

    def test_execute_router_exception(
        self,
        simple_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """LLM 路由器拋出例外時應回傳 success=False。"""
        mock_router.call.side_effect = ConnectionError("network error")
        step = LLMStep(
            simple_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        output = step.execute({})

        assert output.success is False
        assert "network error" in output.error


class TestLLMStepDryRun:
    """dry_run() 方法測試。"""

    def test_dry_run_returns_success(
        self,
        simple_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """dry_run 應回傳 success=True 且不呼叫 router。"""
        step = LLMStep(
            simple_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        output = step.dry_run({})

        assert output.success is True
        mock_router.call.assert_not_called()

    def test_dry_run_output_contains_model(
        self,
        simple_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """dry_run 輸出應包含使用的模型名稱。"""
        step = LLMStep(
            simple_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        output = step.dry_run({})

        assert "DRY-RUN" in output.output
        assert "LLM" in output.output
        assert "ollama/qwen3:14b" in output.output

    def test_dry_run_output_contains_prompt_preview(
        self,
        simple_llm_step_def: StepDef,
        template_engine: TemplateEngine,
        mock_router: MagicMock,
    ) -> None:
        """dry_run 輸出應包含 prompt 預覽。"""
        step = LLMStep(
            simple_llm_step_def, template_engine, mock_router, "ollama/qwen3:14b"
        )
        output = step.dry_run({})

        assert "Please analyze" in output.output
