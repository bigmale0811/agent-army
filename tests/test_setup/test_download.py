"""agent-army 下載模組的測試。

測試涵蓋：
- clone agent-army repo
- 路徑存在性檢查
- 既有專案偵測
- pip install 依賴安裝
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCloneAgentArmy:
    """測試 git clone agent-army。"""

    @patch("subprocess.run")
    def test_clone_success(self, mock_run):
        """clone 成功回傳 True。"""
        from setup.download import clone_agent_army

        mock_run.return_value = MagicMock(returncode=0)
        result = clone_agent_army(Path("/tmp/agent-army"))
        assert result is True

    @patch("subprocess.run")
    def test_clone_failure(self, mock_run):
        """clone 失敗回傳 False。"""
        from setup.download import clone_agent_army

        mock_run.return_value = MagicMock(
            returncode=128, stderr="fatal: repository not found"
        )
        result = clone_agent_army(Path("/tmp/agent-army"))
        assert result is False

    @patch("subprocess.run")
    def test_clone_uses_correct_repo(self, mock_run):
        """確認使用正確的 repo URL。"""
        from setup.download import AGENT_ARMY_REPO_URL, clone_agent_army

        mock_run.return_value = MagicMock(returncode=0)
        clone_agent_army(Path("/tmp/agent-army"))
        cmd = mock_run.call_args[0][0]
        assert "git" in cmd
        assert "clone" in cmd
        assert AGENT_ARMY_REPO_URL in cmd

    @patch("subprocess.run")
    def test_clone_with_custom_repo(self, mock_run):
        """可自訂 repo URL。"""
        from setup.download import clone_agent_army

        mock_run.return_value = MagicMock(returncode=0)
        custom_url = "https://github.com/other/repo.git"
        clone_agent_army(Path("/tmp/test"), repo_url=custom_url)
        cmd = mock_run.call_args[0][0]
        assert custom_url in cmd

    @patch("subprocess.run")
    def test_clone_timeout(self, mock_run):
        """clone 超時回傳 False。"""
        from setup.download import clone_agent_army

        mock_run.side_effect = subprocess.TimeoutExpired("git", 120)
        result = clone_agent_army(Path("/tmp/agent-army"))
        assert result is False


class TestCheckTargetPath:
    """測試目標路徑檢查。"""

    def test_path_not_exists(self, tmp_path):
        """路徑不存在 → new。"""
        from setup.download import check_target_path

        result = check_target_path(tmp_path / "nonexistent")
        assert result == "new"

    def test_path_is_valid_project(self, tmp_path):
        """路徑存在且是有效 agent-army 專案 → existing。"""
        from setup.download import check_target_path

        (tmp_path / "CLAUDE.md").write_text("test", encoding="utf-8")
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        result = check_target_path(tmp_path)
        assert result == "existing"

    def test_path_exists_but_not_project(self, tmp_path):
        """路徑存在但不是 agent-army 專案 → occupied。"""
        from setup.download import check_target_path

        (tmp_path / "somefile.txt").write_text("test", encoding="utf-8")
        result = check_target_path(tmp_path)
        assert result == "occupied"

    def test_path_is_empty_dir(self, tmp_path):
        """空目錄 → new（可以直接 clone 進去）。"""
        from setup.download import check_target_path

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = check_target_path(empty_dir)
        assert result == "new"


class TestInstallDependencies:
    """測試 pip install 依賴。"""

    @patch("subprocess.run")
    def test_install_success(self, mock_run, tmp_path):
        """pip install 成功。"""
        from setup.download import install_dependencies

        # 建立 requirements.txt 讓 Path.exists() 通過
        (tmp_path / "requirements.txt").write_text("pyyaml", encoding="utf-8")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_dependencies(tmp_path)
        assert result is True

    @patch("subprocess.run")
    def test_install_failure(self, mock_run, tmp_path):
        """pip install 失敗。"""
        from setup.download import install_dependencies

        (tmp_path / "requirements.txt").write_text("pyyaml", encoding="utf-8")
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = install_dependencies(tmp_path)
        assert result is False

    @patch("subprocess.run")
    def test_no_requirements_file(self, mock_run, tmp_path):
        """沒有 requirements.txt → 回傳 False。"""
        from setup.download import install_dependencies

        # 不 mock Path.exists，用真實的 tmp_path
        result = install_dependencies(tmp_path)
        # subprocess.run 不應被呼叫因為檔案不存在
        assert result is False


class TestVerifyProjectStructure:
    """測試專案結構驗證。"""

    def test_valid_structure(self, tmp_path):
        """完整結構通過驗證。"""
        from setup.download import verify_project_structure

        # 建立最小有效結構
        (tmp_path / "CLAUDE.md").write_text("test", encoding="utf-8")
        (tmp_path / ".claude" / "rules" / "common").mkdir(parents=True)
        (tmp_path / "scripts" / "hooks").mkdir(parents=True)
        (tmp_path / "data" / "memory").mkdir(parents=True)
        (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")

        missing = verify_project_structure(tmp_path)
        assert len(missing) == 0

    def test_missing_items(self, tmp_path):
        """缺少項目會被列出。"""
        from setup.download import verify_project_structure

        # 空目錄，什麼都沒有
        missing = verify_project_structure(tmp_path)
        assert len(missing) > 0
        assert "CLAUDE.md" in missing
