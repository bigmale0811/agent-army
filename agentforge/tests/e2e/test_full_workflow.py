# -*- coding: utf-8 -*-
"""完整工作流程端對端測試。

測試從 AgentDef 建立到 Pipeline 執行完成的完整流程，
包含 dry-run、失敗恢復、成本追蹤等情境。
所有外部呼叫（subprocess、LLM API）均使用 mock。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agentforge.core.engine import PipelineEngine, PipelineResult
from agentforge.core.task_tracker import TaskTracker
from agentforge.llm.budget import BudgetTracker
from agentforge.llm.providers.base import LLMResponse
from agentforge.llm.router import LLMCallResult, LLMRouter
from agentforge.schema import GlobalConfig, load_agent_def
from agentforge.steps.base import StepOutput


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def minimal_config() -> GlobalConfig:
    """最小化的全域設定（使用 Ollama）。"""
    return GlobalConfig(default_model="ollama/qwen3:14b")


@pytest.fixture
def router(minimal_config: GlobalConfig) -> LLMRouter:
    """建立 LLMRouter。"""
    return LLMRouter(minimal_config)


@pytest.fixture
def mock_llm_response() -> LLMResponse:
    """模擬 LLM API 回應。"""
    return LLMResponse(
        content="This is a mocked LLM response.",
        model="qwen3:14b",
        provider="ollama",
        usage={"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
    )


@pytest.fixture
def simple_agent_yaml(tmp_path: Path) -> Path:
    """建立含 shell → save 兩步驟的簡單 Agent YAML。"""
    agent_data = {
        "name": "simple-test-agent",
        "description": "E2E 測試用簡單 Agent",
        "model": "ollama/qwen3:14b",
        "max_retries": 1,
        "steps": [
            {
                "name": "greet",
                "action": "shell",
                "command": "echo 'Hello AgentForge'",
            },
            {
                "name": "save_output",
                "action": "save",
                "path": str(tmp_path / "output.txt"),
                "content": "{{ steps.greet.output }}",
            },
        ],
    }
    yaml_path = tmp_path / "simple-test-agent.yaml"
    yaml_path.write_text(yaml.dump(agent_data), encoding="utf-8")
    return yaml_path


@pytest.fixture
def llm_agent_yaml(tmp_path: Path) -> Path:
    """建立含 shell → llm → save 三步驟的 Agent YAML。"""
    agent_data = {
        "name": "llm-test-agent",
        "description": "E2E 測試用 LLM Agent",
        "model": "ollama/qwen3:14b",
        "max_retries": 1,
        "steps": [
            {
                "name": "read_data",
                "action": "shell",
                "command": "echo 'sample data'",
            },
            {
                "name": "analyze",
                "action": "llm",
                "prompt": "Analyze: {{ steps.read_data.output }}",
            },
            {
                "name": "save_result",
                "action": "save",
                "path": str(tmp_path / "analysis.txt"),
                "content": "{{ steps.analyze.output }}",
            },
        ],
    }
    yaml_path = tmp_path / "llm-test-agent.yaml"
    yaml_path.write_text(yaml.dump(agent_data), encoding="utf-8")
    return yaml_path


# ─────────────────────────────────────────────
# 完整工作流程測試
# ─────────────────────────────────────────────

class TestCompleteWorkflow:
    """完整工作流程：init → load YAML → run → verify output。"""

    def test_shell_save_workflow_succeeds(
        self, router: LLMRouter, simple_agent_yaml: Path, tmp_path: Path
    ) -> None:
        """shell → save 兩步驟的 Agent 應能成功執行。"""
        agent_def = load_agent_def(simple_agent_yaml)
        engine = PipelineEngine(router=router)

        # mock subprocess（避免真實 shell 呼叫）
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Hello AgentForge\n",
                stderr="",
            )
            result = engine.execute(agent_def)

        assert result.success is True
        assert result.agent_name == "simple-test-agent"
        assert len(result.steps) == 2

    def test_llm_workflow_with_mock(
        self,
        router: LLMRouter,
        llm_agent_yaml: Path,
        mock_llm_response: LLMResponse,
        tmp_path: Path,
    ) -> None:
        """shell → llm → save 三步驟工作流應能成功執行（mock LLM）。"""
        agent_def = load_agent_def(llm_agent_yaml)
        engine = PipelineEngine(router=router)

        with patch("subprocess.run") as mock_run, \
             patch.object(
                 type(router)._get_or_create_provider.__func__ if hasattr(type(router)._get_or_create_provider, '__func__') else type(router),
                 "_get_or_create_provider",
                 autospec=True
             ) if False else patch(
                 "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
                 return_value=mock_llm_response,
             ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="sample data\n",
                stderr="",
            )
            result = engine.execute(agent_def)

        assert result.agent_name == "llm-test-agent"
        assert len(result.steps) == 3

    def test_output_file_is_created_by_save_step(
        self, router: LLMRouter, simple_agent_yaml: Path, tmp_path: Path
    ) -> None:
        """save 步驟應建立輸出檔案。"""
        agent_def = load_agent_def(simple_agent_yaml)
        engine = PipelineEngine(router=router)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Hello AgentForge\n",
                stderr="",
            )
            result = engine.execute(agent_def)

        # save 步驟應建立輸出檔案
        output_file = tmp_path / "output.txt"
        assert output_file.exists(), "save 步驟應建立輸出檔案"

    def test_pipeline_result_contains_step_results(
        self, router: LLMRouter, simple_agent_yaml: Path
    ) -> None:
        """PipelineResult 應包含每個步驟的執行結果。"""
        agent_def = load_agent_def(simple_agent_yaml)
        engine = PipelineEngine(router=router)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="test output\n",
                stderr="",
            )
            result = engine.execute(agent_def)

        step_names = [s.step_name for s in result.steps]
        assert "greet" in step_names


# ─────────────────────────────────────────────
# Dry-run 測試
# ─────────────────────────────────────────────

class TestDryRun:
    """dry_run=True 時不產生副作用的測試。"""

    def test_dry_run_succeeds_without_real_subprocess(
        self, router: LLMRouter, simple_agent_yaml: Path, tmp_path: Path
    ) -> None:
        """dry_run 模式應不呼叫真實 subprocess。"""
        agent_def = load_agent_def(simple_agent_yaml)
        engine = PipelineEngine(router=router)

        with patch("subprocess.run") as mock_run:
            result = engine.execute(agent_def, dry_run=True)

        # dry_run 模式不應呼叫 subprocess
        mock_run.assert_not_called()

    def test_dry_run_returns_success(
        self, router: LLMRouter, simple_agent_yaml: Path
    ) -> None:
        """dry_run 應回傳成功結果。"""
        agent_def = load_agent_def(simple_agent_yaml)
        engine = PipelineEngine(router=router)

        result = engine.execute(agent_def, dry_run=True)

        assert result.success is True

    def test_dry_run_does_not_create_output_files(
        self, router: LLMRouter, simple_agent_yaml: Path, tmp_path: Path
    ) -> None:
        """dry_run 模式的 save 步驟不應建立實際檔案。"""
        agent_def = load_agent_def(simple_agent_yaml)
        engine = PipelineEngine(router=router)

        result = engine.execute(agent_def, dry_run=True)

        output_file = tmp_path / "output.txt"
        # dry_run 模式不應建立實際檔案
        assert not output_file.exists(), "dry_run 不應建立輸出檔案"

    def test_dry_run_step_output_contains_dry_run_marker(
        self, router: LLMRouter, simple_agent_yaml: Path
    ) -> None:
        """dry_run 步驟輸出應包含 DRY-RUN 標記。"""
        agent_def = load_agent_def(simple_agent_yaml)
        engine = PipelineEngine(router=router)

        result = engine.execute(agent_def, dry_run=True)

        # 至少一個步驟的輸出應包含 DRY-RUN 標記
        has_dry_run_marker = any(
            "DRY-RUN" in step.output.output for step in result.steps
        )
        assert has_dry_run_marker


# ─────────────────────────────────────────────
# 失敗恢復測試
# ─────────────────────────────────────────────

class TestFailureRecovery:
    """失敗步驟的行為與恢復測試。"""

    def test_first_step_failure_stops_pipeline(
        self, router: LLMRouter, simple_agent_yaml: Path
    ) -> None:
        """第一步驟持續失敗後，Pipeline 應中止並標記為失敗。"""
        from agentforge.schema import AgentDef, StepDef
        fail_step = StepDef(name="fail-step", action="shell", command="exit 1")
        ok_step = StepDef(name="ok-step", action="shell", command="echo ok")
        # max_retries 最小為 1，失敗超過 max_retries 次後 Pipeline 停止
        agent_def_fail = AgentDef(
            name="fail-agent",
            steps=[fail_step, ok_step],
            max_retries=1,
        )

        engine = PipelineEngine(router=router)

        with patch("subprocess.run") as mock_run:
            # 所有呼叫都返回失敗，讓重試也失敗
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="command failed",
            )
            result = engine.execute(agent_def_fail)

        # Pipeline 應失敗
        assert result.success is False

    def test_failed_step_has_error_in_output(
        self, router: LLMRouter
    ) -> None:
        """失敗的步驟應在 StepOutput 中包含錯誤訊息。"""
        from agentforge.schema import AgentDef, StepDef
        step = StepDef(name="test-step", action="shell", command="echo test")
        # max_retries 最小為 1
        agent_def = AgentDef(name="test-agent", steps=[step], max_retries=1)

        engine = PipelineEngine(router=router)

        with patch("subprocess.run") as mock_run:
            # 所有呼叫都失敗（含重試）
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="some error occurred",
            )
            result = engine.execute(agent_def)

        failed_steps = [s for s in result.steps if not s.output.success]
        assert len(failed_steps) >= 1
        assert "some error occurred" in failed_steps[0].output.error


# ─────────────────────────────────────────────
# 成本追蹤端對端測試
# ─────────────────────────────────────────────

class TestCostTrackingE2E:
    """成本追蹤從 record → get_total 的端對端測試。"""

    def test_budget_tracker_records_llm_call(self) -> None:
        """BudgetTracker 應能記錄 LLM 呼叫並計算費用。"""
        tracker = BudgetTracker(daily_limit_usd=10.0)
        # 模擬一次 openai/gpt-4o-mini 呼叫（1M 輸入 token）
        entry = tracker.record("my-agent", "summarize", "openai/gpt-4o-mini", 1_000_000, 0)

        assert abs(entry.cost_usd - 0.15) < 1e-9
        assert abs(tracker.get_total() - 0.15) < 1e-9

    def test_multiple_agents_total_cost(self) -> None:
        """多個 Agent 的費用應能正確累積。"""
        tracker = BudgetTracker(daily_limit_usd=100.0)
        tracker.record("agent-a", "step1", "openai/gpt-4o-mini", 1_000_000, 0)
        tracker.record("agent-b", "step1", "openai/gpt-4o-mini", 1_000_000, 0)
        tracker.record("agent-a", "step2", "ollama/qwen3:14b", 50000, 20000)

        # agent-a 成本：0.15 + 0 = 0.15 USD
        assert abs(tracker.get_agent_total("agent-a") - 0.15) < 1e-9
        # 總計：0.15 + 0.15 = 0.30 USD
        assert abs(tracker.get_total() - 0.30) < 1e-9

    def test_budget_warning_end_to_end(self) -> None:
        """消費接近預算上限時應觸發警告。"""
        tracker = BudgetTracker(daily_limit_usd=1.0, warn_at_percent=80.0)
        # 消費 0.85 USD (85%)
        tracker.record("agent", "step", "openai/gpt-4o-mini", 0, 1_416_667)

        is_warn, msg = tracker.check_budget()
        assert is_warn is True

    def test_task_tracker_and_budget_tracker_integration(
        self, tmp_path: Path
    ) -> None:
        """TaskTracker（SQLite）與 BudgetTracker 應各自獨立正常運作。"""
        db_path = tmp_path / "test_tracker.db"
        task_tracker = TaskTracker(db_path)
        budget_tracker = BudgetTracker()

        # 模擬一次完整執行
        run_id = task_tracker.start_run("integrated-agent")
        budget_entry = budget_tracker.record(
            "integrated-agent", "llm-step", "openai/gpt-4o-mini", 500, 200
        )
        task_tracker.record_step(
            run_id, "llm-step", "llm",
            success=True,
            cost_usd=budget_entry.cost_usd,
        )
        task_tracker.finish_run(
            run_id, success=True, total_cost_usd=budget_entry.cost_usd
        )
        task_tracker.close()

        # 驗證兩個追蹤器的記錄一致
        assert budget_tracker.get_total() > 0
        task_tracker2 = TaskTracker(db_path)
        stats = task_tracker2.get_agent_stats("integrated-agent")
        task_tracker2.close()
        assert stats.total_runs == 1
        assert stats.success_count == 1
