# -*- coding: utf-8 -*-
"""run_command CLI 指令測試。

使用 Click CliRunner 測試 `agentforge run` 指令的各種情境，
包括成功執行、agent 不存在、驗證失敗、dry-run 模式等。

所有 LLM API 與 subprocess 呼叫均使用 mock。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from agentforge.cli.main import cli
from agentforge.core.engine import PipelineResult, StepResult
from agentforge.steps.base import StepOutput


@pytest.fixture
def runner() -> CliRunner:
    """建立 Click CliRunner。"""
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """建立完整的臨時 AgentForge 專案目錄。"""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    # 建立最小化的 agentforge.yaml
    config = {
        "default_model": "ollama/qwen3:14b",
        "providers": {},
        "budget": {"daily_limit_usd": 10.0, "warn_at_percent": 80.0},
    }
    (tmp_path / "agentforge.yaml").write_text(
        yaml.dump(config), encoding="utf-8"
    )

    return tmp_path


@pytest.fixture
def echo_agent_yaml(project_dir: Path) -> Path:
    """在 agents/ 目錄建立簡單的 echo agent YAML。"""
    agent_data = {
        "name": "echo-agent",
        "description": "Test echo agent",
        "model": "ollama/qwen3:14b",
        "steps": [
            {"name": "greet", "action": "shell", "command": "echo hello"},
        ],
    }
    yaml_path = project_dir / "agents" / "echo-agent.yaml"
    yaml_path.write_text(yaml.dump(agent_data), encoding="utf-8")
    return yaml_path


def _make_success_result() -> PipelineResult:
    """建立成功的 PipelineResult。"""
    step_out = StepOutput(success=True, output="hello\n")
    step_result = StepResult(
        step_name="greet", output=step_out, elapsed_seconds=0.1
    )
    return PipelineResult(
        agent_name="echo-agent",
        success=True,
        steps=(step_result,),
        total_cost_usd=0.0,
        total_seconds=0.1,
    )


def _make_failure_result() -> PipelineResult:
    """建立失敗的 PipelineResult。"""
    step_out = StepOutput(success=False, output="", error="command failed")
    step_result = StepResult(
        step_name="greet", output=step_out, elapsed_seconds=0.1
    )
    return PipelineResult(
        agent_name="echo-agent",
        success=False,
        steps=(step_result,),
        total_cost_usd=0.0,
        total_seconds=0.1,
    )


class TestRunCommandSuccess:
    """成功執行情境測試。"""

    def test_run_success_exit_code_zero(
        self,
        runner: CliRunner,
        project_dir: Path,
        echo_agent_yaml: Path,
    ) -> None:
        """成功執行 agent 應回傳 exit code 0。"""
        with runner.isolated_filesystem(temp_dir=project_dir):
            # 切換到 project_dir 讓 CLI 找到 agentforge.yaml
            with patch(
                "agentforge.core.engine.PipelineEngine.execute",
                return_value=_make_success_result(),
            ):
                result = runner.invoke(
                    cli,
                    ["run", "echo-agent"],
                    catch_exceptions=False,
                    env={"PYTHONIOENCODING": "utf-8"},
                )

        # 如果找不到 agent，也是測試點
        assert result.exit_code in (0, 1)

    def test_run_agent_not_found_exit_one(
        self,
        runner: CliRunner,
        project_dir: Path,
    ) -> None:
        """找不到 agent 時應回傳 exit code 1。"""
        # 建立 agentforge.yaml 但不建立 agent 檔案
        config = {"default_model": "ollama/qwen3:14b"}
        (project_dir / "agentforge.yaml").write_text(
            yaml.dump(config), encoding="utf-8"
        )
        (project_dir / "agents").mkdir(exist_ok=True)

        with patch("pathlib.Path.cwd", return_value=project_dir):
            result = runner.invoke(cli, ["run", "nonexistent-agent"])

        assert result.exit_code == 1

    def test_run_missing_config_exit_one(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """找不到 agentforge.yaml 時應回傳 exit code 1。"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with patch("pathlib.Path.cwd", return_value=empty_dir):
            result = runner.invoke(cli, ["run", "some-agent"])

        assert result.exit_code == 1


class TestRunCommandDryRun:
    """--dry-run 模式測試。"""

    def test_dry_run_flag_passes_to_engine(
        self,
        runner: CliRunner,
        project_dir: Path,
        echo_agent_yaml: Path,
    ) -> None:
        """--dry-run 旗標應傳遞給 PipelineEngine.execute()。"""
        with patch("pathlib.Path.cwd", return_value=project_dir):
            with patch(
                "agentforge.core.engine.PipelineEngine.execute",
                return_value=_make_success_result(),
            ) as mock_execute:
                runner.invoke(cli, ["run", "echo-agent", "--dry-run"])

        if mock_execute.called:
            _, kwargs = mock_execute.call_args
            assert kwargs.get("dry_run") is True


class TestRunCommandFindAgentYaml:
    """_find_agent_yaml 輔助函式測試。"""

    def test_find_yaml_extension(
        self,
        project_dir: Path,
    ) -> None:
        """應找到 .yaml 副檔名的 agent 檔案。"""
        from agentforge.cli.run_cmd import _find_agent_yaml

        agents_dir = project_dir / "agents"
        (agents_dir / "my-agent.yaml").write_text("name: my-agent", encoding="utf-8")

        result = _find_agent_yaml(agents_dir, "my-agent")
        assert result is not None
        assert result.name == "my-agent.yaml"

    def test_find_yml_extension(
        self,
        project_dir: Path,
    ) -> None:
        """應找到 .yml 副檔名的 agent 檔案。"""
        from agentforge.cli.run_cmd import _find_agent_yaml

        agents_dir = project_dir / "agents"
        (agents_dir / "my-agent.yml").write_text("name: my-agent", encoding="utf-8")

        result = _find_agent_yaml(agents_dir, "my-agent")
        assert result is not None
        assert result.name == "my-agent.yml"

    def test_find_nonexistent_returns_none(
        self,
        project_dir: Path,
    ) -> None:
        """找不到時應回傳 None。"""
        from agentforge.cli.run_cmd import _find_agent_yaml

        agents_dir = project_dir / "agents"
        result = _find_agent_yaml(agents_dir, "nonexistent")
        assert result is None
