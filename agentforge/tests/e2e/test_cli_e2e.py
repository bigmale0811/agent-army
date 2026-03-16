# -*- coding: utf-8 -*-
"""CLI 端對端測試。

使用 Click CliRunner 測試所有 CLI 指令的行為，
確認指令的 exit code、輸出訊息、--help 可用性等。

各測試類別：
- TestCliHelp: --help 旗標在所有指令都可用
- TestCliInit: init 指令建立正確目錄結構
- TestCliList: list 指令列出 agents
- TestCliRun: run 指令執行 agent（使用 mock）
- TestCliStatus: status 指令顯示執行統計
- TestCliExitCodes: 各指令的 exit code 規範
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from agentforge.cli.main import cli
from agentforge.core.engine import PipelineResult, StepResult
from agentforge.core.task_tracker import TaskTracker
from agentforge.steps.base import StepOutput


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def runner() -> CliRunner:
    """建立 Click CliRunner。"""
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """建立完整的臨時 AgentForge 專案目錄。"""
    (tmp_path / "agents").mkdir()
    (tmp_path / ".agentforge").mkdir()
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
def echo_agent(project_dir: Path) -> Path:
    """在 agents/ 建立簡單的 echo agent YAML。"""
    agent_data = {
        "name": "echo-test",
        "description": "E2E CLI 測試用 Agent",
        "model": "ollama/qwen3:14b",
        "steps": [
            {"name": "greet", "action": "shell", "command": "echo hello"},
        ],
    }
    yaml_path = project_dir / "agents" / "echo-test.yaml"
    yaml_path.write_text(yaml.dump(agent_data), encoding="utf-8")
    return yaml_path


def _make_success_result(agent_name: str = "echo-test") -> PipelineResult:
    """建立成功的 PipelineResult 用於 mock。"""
    step_out = StepOutput(success=True, output="hello\n")
    step_result = StepResult(
        step_name="greet", output=step_out, elapsed_seconds=0.01
    )
    return PipelineResult(
        agent_name=agent_name,
        success=True,
        steps=(step_result,),
        total_cost_usd=0.0,
        total_seconds=0.01,
    )


def _make_failure_result(agent_name: str = "echo-test") -> PipelineResult:
    """建立失敗的 PipelineResult 用於 mock。"""
    step_out = StepOutput(success=False, output="", error="command failed")
    step_result = StepResult(
        step_name="greet", output=step_out, elapsed_seconds=0.01
    )
    return PipelineResult(
        agent_name=agent_name,
        success=False,
        steps=(step_result,),
        total_cost_usd=0.0,
        total_seconds=0.01,
    )


# ─────────────────────────────────────────────
# --help 測試
# ─────────────────────────────────────────────

class TestCliHelp:
    """所有 CLI 指令的 --help 可用性測試。"""

    def test_main_help(self, runner: CliRunner) -> None:
        """主指令 --help 應正常顯示並 exit 0。"""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "agentforge" in result.output.lower()

    def test_init_help(self, runner: CliRunner) -> None:
        """init --help 應正常顯示並 exit 0。"""
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0

    def test_list_help(self, runner: CliRunner) -> None:
        """list --help 應正常顯示並 exit 0。"""
        result = runner.invoke(cli, ["list", "--help"])
        assert result.exit_code == 0

    def test_run_help(self, runner: CliRunner) -> None:
        """run --help 應正常顯示並 exit 0。"""
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        # 應顯示 dry-run 選項
        assert "dry-run" in result.output

    def test_status_help(self, runner: CliRunner) -> None:
        """status --help 應正常顯示並 exit 0。"""
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_version_option(self, runner: CliRunner) -> None:
        """--version 應顯示版本號並 exit 0。"""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ─────────────────────────────────────────────
# init 指令測試
# ─────────────────────────────────────────────

class TestCliInit:
    """init 指令建立正確目錄結構的測試。"""

    def test_init_creates_project_directory(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """init 應建立名稱正確的專案目錄。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
            result = runner.invoke(cli, ["init", "my-project"], catch_exceptions=False)
            assert result.exit_code == 0
            assert (Path(iso_dir) / "my-project").is_dir()

    def test_init_creates_agents_subdirectory(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """init 應建立 agents/ 子目錄。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
            runner.invoke(cli, ["init", "test-proj"], catch_exceptions=False)
            assert (Path(iso_dir) / "test-proj" / "agents").is_dir()

    def test_init_creates_agentforge_yaml(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """init 應建立 agentforge.yaml 設定檔。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
            runner.invoke(cli, ["init", "proj"], catch_exceptions=False)
            assert (Path(iso_dir) / "proj" / "agentforge.yaml").is_file()

    def test_init_creates_example_agent(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """init 應在 agents/ 目錄建立範例 agent YAML。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
            runner.invoke(cli, ["init", "proj"], catch_exceptions=False)
            agents_dir = Path(iso_dir) / "proj" / "agents"
            yaml_files = list(agents_dir.glob("*.yaml"))
            assert len(yaml_files) >= 1

    def test_init_fails_if_directory_exists(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """init 應在目錄已存在時返回 exit code 1。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
            # 先建立目錄
            (Path(iso_dir) / "existing").mkdir()
            result = runner.invoke(cli, ["init", "existing"])
            assert result.exit_code == 1

    def test_init_success_message(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """init 成功後應顯示成功訊息。"""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "new-proj"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "new-proj" in result.output


# ─────────────────────────────────────────────
# run 指令測試（mock engine）
# ─────────────────────────────────────────────

class TestCliRun:
    """run 指令的 exit code 與輸出測試。"""

    def test_run_success_exit_zero(
        self,
        runner: CliRunner,
        project_dir: Path,
        echo_agent: Path,
    ) -> None:
        """run 成功時 exit code 應為 0。"""
        with patch("pathlib.Path.cwd", return_value=project_dir), \
             patch(
                 "agentforge.core.engine.PipelineEngine.execute",
                 return_value=_make_success_result(),
             ):
            result = runner.invoke(
                cli, ["run", "echo-test"], catch_exceptions=False
            )

        assert result.exit_code == 0

    def test_run_failure_exit_one(
        self,
        runner: CliRunner,
        project_dir: Path,
        echo_agent: Path,
    ) -> None:
        """run 失敗時 exit code 應為 1。"""
        with patch("pathlib.Path.cwd", return_value=project_dir), \
             patch(
                 "agentforge.core.engine.PipelineEngine.execute",
                 return_value=_make_failure_result(),
             ):
            result = runner.invoke(cli, ["run", "echo-test"])

        assert result.exit_code == 1

    def test_run_agent_not_found_exit_one(
        self, runner: CliRunner, project_dir: Path
    ) -> None:
        """找不到 agent 時 exit code 應為 1。"""
        with patch("pathlib.Path.cwd", return_value=project_dir):
            result = runner.invoke(cli, ["run", "nonexistent-agent"])

        assert result.exit_code == 1

    def test_run_missing_config_exit_one(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """找不到 agentforge.yaml 時 exit code 應為 1。"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with patch("pathlib.Path.cwd", return_value=empty_dir):
            result = runner.invoke(cli, ["run", "some-agent"])

        assert result.exit_code == 1

    def test_run_dry_run_no_real_execution(
        self,
        runner: CliRunner,
        project_dir: Path,
        echo_agent: Path,
    ) -> None:
        """--dry-run 模式不應呼叫真實 subprocess。"""
        with patch("pathlib.Path.cwd", return_value=project_dir), \
             patch("subprocess.run") as mock_sub:
            result = runner.invoke(
                cli, ["run", "echo-test", "--dry-run"], catch_exceptions=False
            )

        # dry-run 模式不應呼叫真實 subprocess
        mock_sub.assert_not_called()
        assert result.exit_code == 0


# ─────────────────────────────────────────────
# status 指令測試
# ─────────────────────────────────────────────

class TestCliStatus:
    """status 指令的 exit code 與輸出測試。"""

    def test_status_no_db_exit_zero(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """無資料庫時 status 應 exit 0 並顯示提示。"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "尚無執行記錄" in result.output

    def test_status_with_data_shows_table(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """有資料時 status 應顯示統計表格。"""
        db_path = tmp_path / ".agentforge" / "tracker.db"
        (tmp_path / ".agentforge").mkdir()
        tracker = TaskTracker(db_path)
        run_id = tracker.start_run("cli-test-agent")
        tracker.finish_run(run_id, success=True)
        tracker.close()

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "cli-test-agent" in result.output


# ─────────────────────────────────────────────
# list 指令測試
# ─────────────────────────────────────────────

class TestCliList:
    """list 指令列出 agents 的測試。"""

    def test_list_shows_agents(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """list 應顯示 agents 目錄中的 agent。"""
        # list_command 使用相對路徑，需要在 isolated_filesystem 內操作
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
            agents_dir = Path(iso_dir) / "agents"
            agents_dir.mkdir()
            agent_data = {
                "name": "my-list-agent",
                "description": "Test",
                "steps": [{"name": "s", "action": "shell", "command": "echo hi"}],
            }
            (agents_dir / "my-list-agent.yaml").write_text(
                yaml.dump(agent_data), encoding="utf-8"
            )
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "my-list-agent" in result.output

    def test_list_empty_agents_dir(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """agents 目錄為空時 list 應顯示相應訊息並 exit 0。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as iso_dir:
            (Path(iso_dir) / "agents").mkdir()
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        assert result.exit_code == 0

    def test_list_no_agents_dir_shows_warning(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """無 agents 目錄時 list 應顯示警告並正常退出（exit 0）。"""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["list"], catch_exceptions=False)

        # list_command 找不到 agents/ 時顯示 warning 並 return（不 sys.exit(1)）
        assert result.exit_code == 0


# ─────────────────────────────────────────────
# exit code 規範測試
# ─────────────────────────────────────────────

class TestCliExitCodes:
    """各指令的 exit code 規範。

    0 = 成功
    1 = 使用者可預期的失敗（agent 不存在、設定缺失）
    2 = Click 的參數錯誤
    """

    def test_missing_required_arg_exit_two(self, runner: CliRunner) -> None:
        """缺少必要參數時 Click 應回傳 exit code 2。"""
        # init 需要 NAME 參數
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 2

    def test_run_missing_agent_arg_exit_two(self, runner: CliRunner) -> None:
        """run 缺少 agent 名稱參數時應 exit 2。"""
        result = runner.invoke(cli, ["run"])
        assert result.exit_code == 2

    def test_unknown_command_exit_two(self, runner: CliRunner) -> None:
        """未知指令應回傳 exit code 2。"""
        result = runner.invoke(cli, ["unknown-command-xyz"])
        assert result.exit_code == 2
