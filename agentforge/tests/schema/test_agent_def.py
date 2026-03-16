# -*- coding: utf-8 -*-
"""AgentDef / StepDef Pydantic 模型的單元測試。"""

import pytest
from pydantic import ValidationError

from agentforge.schema.agent_def import AgentDef, StepDef


# ── 合法定義 ──────────────────────────────────────────────


class TestValidAgentDef:
    """合法 Agent 定義應正確解析。"""

    def test_valid_agent_def(self) -> None:
        """完整且合法的定義應成功建立。"""
        agent = AgentDef(
            name="file-analyzer",
            description="分析檔案結構",
            model="openai/gpt-4o-mini",
            max_retries=3,
            steps=[
                StepDef(name="list_files", action="shell", command="ls -la"),
                StepDef(
                    name="analyze",
                    action="llm",
                    prompt="請分析：{{ steps.list_files.output }}",
                ),
                StepDef(
                    name="save_report",
                    action="save",
                    path="report.md",
                    content="{{ steps.analyze.output }}",
                ),
            ],
        )
        assert agent.name == "file-analyzer"
        assert agent.description == "分析檔案結構"
        assert agent.model == "openai/gpt-4o-mini"
        assert agent.max_retries == 3
        assert len(agent.steps) == 3

    def test_minimal_agent_def(self) -> None:
        """只提供必要欄位也應成功。"""
        agent = AgentDef(
            name="minimal",
            steps=[StepDef(name="run", action="shell", command="echo hello")],
        )
        assert agent.name == "minimal"
        assert agent.description == ""
        assert agent.model == ""
        assert agent.max_retries == 3


# ── 缺少必要欄位 ─────────────────────────────────────────


class TestMissingFields:
    """缺少必要欄位應報錯。"""

    def test_missing_name_fails(self) -> None:
        """缺少 name 應報驗證錯誤。"""
        with pytest.raises(ValidationError):
            AgentDef(
                steps=[StepDef(name="run", action="shell", command="echo hi")]
            )

    def test_empty_steps_fails(self) -> None:
        """空 steps 列表應報錯。"""
        with pytest.raises(ValidationError, match="steps"):
            AgentDef(name="bad", steps=[])


# ── Step 驗證 ─────────────────────────────────────────────


class TestStepValidation:
    """各類型 Step 的欄位驗證。"""

    def test_duplicate_step_names_fails(self) -> None:
        """step name 重複應報錯。"""
        with pytest.raises(ValidationError, match="重複"):
            AgentDef(
                name="dup",
                steps=[
                    StepDef(name="same", action="shell", command="ls"),
                    StepDef(name="same", action="shell", command="pwd"),
                ],
            )

    def test_shell_without_command_fails(self) -> None:
        """shell 類型缺少 command 應報錯。"""
        with pytest.raises(ValidationError, match="command"):
            StepDef(name="bad_shell", action="shell")

    def test_llm_without_prompt_fails(self) -> None:
        """llm 類型缺少 prompt 應報錯。"""
        with pytest.raises(ValidationError, match="prompt"):
            StepDef(name="bad_llm", action="llm")

    def test_save_without_path_fails(self) -> None:
        """save 類型缺少 path 應報錯。"""
        with pytest.raises(ValidationError, match="path"):
            StepDef(name="bad_save", action="save", content="data")

    def test_save_without_content_fails(self) -> None:
        """save 類型缺少 content 應報錯。"""
        with pytest.raises(ValidationError, match="content"):
            StepDef(name="bad_save2", action="save", path="/tmp/out.txt")

    def test_invalid_action_fails(self) -> None:
        """不合法的 action 類型應報錯。"""
        with pytest.raises(ValidationError):
            StepDef(name="bad_action", action="unknown", command="ls")


# ── model 格式驗證 ────────────────────────────────────────


class TestModelValidation:
    """model 字串格式驗證。"""

    def test_model_format_validation_valid(self) -> None:
        """合法 model 格式應通過。"""
        step = StepDef(
            name="ok", action="shell", command="ls", model="openai/gpt-4o"
        )
        assert step.model == "openai/gpt-4o"

    def test_model_format_validation_ollama(self) -> None:
        """Ollama model 帶冒號的格式應通過。"""
        step = StepDef(
            name="ok", action="shell", command="ls", model="ollama/qwen3:14b"
        )
        assert step.model == "ollama/qwen3:14b"

    def test_model_format_validation_empty_ok(self) -> None:
        """空 model（未指定）應通過。"""
        step = StepDef(name="ok", action="shell", command="ls")
        assert step.model is None

    def test_model_format_validation_invalid(self) -> None:
        """缺少 provider 前綴的 model 應報錯。"""
        with pytest.raises(ValidationError, match="provider/model-name"):
            StepDef(name="bad", action="shell", command="ls", model="gpt-4o")

    def test_agent_model_format_invalid(self) -> None:
        """AgentDef 層級的 model 格式也須驗證。"""
        with pytest.raises(ValidationError, match="provider/model-name"):
            AgentDef(
                name="bad",
                model="gpt-4o",
                steps=[StepDef(name="s", action="shell", command="ls")],
            )


# ── max_retries 範圍 ─────────────────────────────────────


class TestMaxRetriesRange:
    """max_retries 必須在 1-10 之間。"""

    def test_max_retries_range_valid(self) -> None:
        agent = AgentDef(
            name="ok",
            max_retries=5,
            steps=[StepDef(name="s", action="shell", command="ls")],
        )
        assert agent.max_retries == 5

    def test_max_retries_too_low(self) -> None:
        with pytest.raises(ValidationError, match="max_retries"):
            AgentDef(
                name="bad",
                max_retries=0,
                steps=[StepDef(name="s", action="shell", command="ls")],
            )

    def test_max_retries_too_high(self) -> None:
        with pytest.raises(ValidationError, match="max_retries"):
            AgentDef(
                name="bad",
                max_retries=11,
                steps=[StepDef(name="s", action="shell", command="ls")],
            )


# ── frozen（不可變）────────────────────────────────────────


class TestFrozenModel:
    """確認 model 是 frozen（不可變）。"""

    def test_frozen_step(self) -> None:
        step = StepDef(name="s", action="shell", command="ls")
        with pytest.raises(ValidationError):
            step.name = "changed"  # type: ignore[misc]

    def test_frozen_agent(self) -> None:
        agent = AgentDef(
            name="a",
            steps=[StepDef(name="s", action="shell", command="ls")],
        )
        with pytest.raises(ValidationError):
            agent.name = "changed"  # type: ignore[misc]
