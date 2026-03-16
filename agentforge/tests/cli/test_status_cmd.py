# -*- coding: utf-8 -*-
"""status_command CLI 指令測試。

使用 Click CliRunner 測試 `agentforge status` 指令的各種情境：
- 資料庫不存在時顯示提示訊息
- 資料庫存在但無記錄
- 正常顯示統計表格
- --db 參數指定路徑
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agentforge.cli.main import cli
from agentforge.core.task_tracker import AgentStats, TaskTracker


@pytest.fixture
def runner() -> CliRunner:
    """建立 Click CliRunner。"""
    return CliRunner()


@pytest.fixture
def db_project(tmp_path: Path) -> Path:
    """建立含有 .agentforge/tracker.db 的臨時專案目錄。

    Returns:
        專案根目錄路徑（包含 .agentforge/ 子目錄）。
    """
    dot_dir = tmp_path / ".agentforge"
    dot_dir.mkdir()
    return tmp_path


class TestStatusCommandNoDb:
    """資料庫不存在時的行為測試。"""

    def test_no_db_shows_warning(self, runner: CliRunner, tmp_path: Path) -> None:
        """資料庫不存在時應顯示尚無執行記錄的提示。"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "尚無執行記錄" in result.output

    def test_no_db_exit_code_zero(self, runner: CliRunner, tmp_path: Path) -> None:
        """資料庫不存在時應正常退出（exit code 0）。"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0


class TestStatusCommandWithDb:
    """資料庫存在時的行為測試。"""

    def test_empty_db_shows_info(
        self, runner: CliRunner, db_project: Path
    ) -> None:
        """資料庫存在但無記錄時應顯示無記錄提示。"""
        db_path = db_project / ".agentforge" / "tracker.db"
        # 建立空白資料庫
        tracker = TaskTracker(db_path)
        tracker.close()

        with patch("pathlib.Path.cwd", return_value=db_project):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "尚無執行記錄" in result.output or "無" in result.output

    def test_with_records_shows_table(
        self, runner: CliRunner, db_project: Path
    ) -> None:
        """有執行記錄時應顯示統計表格，包含 Agent 名稱。"""
        db_path = db_project / ".agentforge" / "tracker.db"
        # 插入測試記錄
        tracker = TaskTracker(db_path)
        run_id = tracker.start_run("test-agent")
        tracker.finish_run(run_id, success=True, total_cost_usd=0.001)
        tracker.close()

        with patch("pathlib.Path.cwd", return_value=db_project):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "test-agent" in result.output

    def test_shows_run_count(
        self, runner: CliRunner, db_project: Path
    ) -> None:
        """表格應顯示執行次數。"""
        db_path = db_project / ".agentforge" / "tracker.db"
        tracker = TaskTracker(db_path)
        # 插入 3 次執行（2 成功，1 失敗）
        r1 = tracker.start_run("agent-x")
        tracker.finish_run(r1, success=True)
        r2 = tracker.start_run("agent-x")
        tracker.finish_run(r2, success=True)
        r3 = tracker.start_run("agent-x")
        tracker.finish_run(r3, success=False)
        tracker.close()

        with patch("pathlib.Path.cwd", return_value=db_project):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "agent-x" in result.output
        # 應顯示 3 次執行
        assert "3" in result.output

    def test_shows_cost(
        self, runner: CliRunner, db_project: Path
    ) -> None:
        """表格應顯示累積費用。"""
        db_path = db_project / ".agentforge" / "tracker.db"
        tracker = TaskTracker(db_path)
        run_id = tracker.start_run("costly-agent")
        tracker.finish_run(run_id, success=True, total_cost_usd=0.123456)
        tracker.close()

        with patch("pathlib.Path.cwd", return_value=db_project):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        # 費用應出現在輸出中
        assert "0.123456" in result.output

    def test_multiple_agents_in_table(
        self, runner: CliRunner, db_project: Path
    ) -> None:
        """多個 Agent 時所有 Agent 名稱都應出現在輸出中。"""
        db_path = db_project / ".agentforge" / "tracker.db"
        tracker = TaskTracker(db_path)
        for agent in ["agent-alpha", "agent-beta", "agent-gamma"]:
            run_id = tracker.start_run(agent)
            tracker.finish_run(run_id, success=True)
        tracker.close()

        with patch("pathlib.Path.cwd", return_value=db_project):
            result = runner.invoke(cli, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "agent-alpha" in result.output
        assert "agent-beta" in result.output
        assert "agent-gamma" in result.output


class TestStatusCommandDbOption:
    """--db 參數測試。"""

    def test_explicit_db_path(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--db 指定的路徑應被正確讀取。"""
        db_path = tmp_path / "custom_tracker.db"
        # 建立並填入測試資料
        tracker = TaskTracker(db_path)
        run_id = tracker.start_run("custom-agent")
        tracker.finish_run(run_id, success=True)
        tracker.close()

        result = runner.invoke(
            cli,
            ["status", "--db", str(db_path)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "custom-agent" in result.output

    def test_explicit_nonexistent_db_shows_warning(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--db 指定不存在的路徑時應顯示警告並正常退出。"""
        fake_db = tmp_path / "nonexistent.db"

        result = runner.invoke(
            cli,
            ["status", "--db", str(fake_db)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "尚無執行記錄" in result.output


class TestStatusHelp:
    """status 指令 --help 測試。"""

    def test_help_is_available(self, runner: CliRunner) -> None:
        """status --help 應顯示說明文字且 exit code 為 0。"""
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower() or "AgentForge" in result.output
