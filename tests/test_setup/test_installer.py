"""獨立安裝包 install.py 的測試。

install.py 是一個零依賴、純 stdlib 的單一檔案，
可以在完全沒有 agent-army 的環境下執行。
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# install.py 在專案根目錄
INSTALL_SCRIPT = Path(__file__).parent.parent.parent / "install.py"


class TestInstallerExists:
    """確認 install.py 存在且可匯入。"""

    def test_file_exists(self):
        """install.py 存在於專案根目錄。"""
        assert INSTALL_SCRIPT.exists(), f"找不到 {INSTALL_SCRIPT}"

    def test_is_standalone_no_local_imports(self):
        """install.py 不能 import setup/ 下的任何東西（它必須獨立運作）。"""
        content = INSTALL_SCRIPT.read_text(encoding="utf-8")
        # 不應該有 from setup. 或 import setup.
        assert "from setup." not in content, "install.py 不可依賴 setup/ 模組"
        assert "import setup." not in content, "install.py 不可依賴 setup/ 模組"

    def test_only_uses_stdlib(self):
        """install.py 只能使用標準庫。"""
        content = INSTALL_SCRIPT.read_text(encoding="utf-8")
        # 常見的第三方庫不應出現
        forbidden = ["import requests", "import yaml", "import click", "import openai"]
        for lib in forbidden:
            assert lib not in content, f"install.py 不可使用第三方庫：{lib}"


class TestInstallerSyntax:
    """確認 install.py 語法正確。"""

    def test_compiles_without_error(self):
        """install.py 可以被 Python 編譯。"""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(INSTALL_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"語法錯誤：{result.stderr}"


class TestInstallerFunctions:
    """測試 install.py 內的核心函數。"""

    @pytest.fixture(autouse=True)
    def _import_installer(self):
        """動態匯入 install.py 為模組。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("installer", INSTALL_SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_has_check_environment(self):
        """有 check_environment 函數。"""
        assert hasattr(self.mod, "check_environment")
        assert callable(self.mod.check_environment)

    def test_has_setup_github_cli(self):
        """有 setup_github_cli 函數。"""
        assert hasattr(self.mod, "setup_github_cli")
        assert callable(self.mod.setup_github_cli)

    def test_has_clone_agent_army(self):
        """有 clone_agent_army 函數。"""
        assert hasattr(self.mod, "clone_agent_army")
        assert callable(self.mod.clone_agent_army)

    def test_has_run_setup_wizard(self):
        """有 run_setup_wizard 函數。"""
        assert hasattr(self.mod, "run_setup_wizard")
        assert callable(self.mod.run_setup_wizard)

    def test_has_main(self):
        """有 main 函數。"""
        assert hasattr(self.mod, "main")
        assert callable(self.mod.main)

    @patch("shutil.which")
    def test_check_environment_detects_missing_git(self, mock_which):
        """偵測到 Git 未安裝。"""

        def which_side_effect(name):
            if name == "git":
                return None
            return f"/usr/bin/{name}"

        mock_which.side_effect = which_side_effect
        result = self.mod.check_environment()
        assert result["has_git"] is False

    @patch("shutil.which")
    def test_check_environment_all_present(self, mock_which):
        """所有工具都已安裝。"""
        mock_which.return_value = "/usr/bin/something"
        result = self.mod.check_environment()
        assert result["has_git"] is True
        assert result["has_node"] is True

    @patch("subprocess.run")
    def test_clone_agent_army_success(self, mock_run):
        """clone 成功回傳 True。"""
        mock_run.return_value = MagicMock(returncode=0)
        result = self.mod.clone_agent_army(Path("/tmp/test"))
        assert result is True

    @patch("subprocess.run")
    def test_clone_agent_army_failure(self, mock_run):
        """clone 失敗回傳 False。"""
        mock_run.return_value = MagicMock(returncode=128, stderr="not found")
        result = self.mod.clone_agent_army(Path("/tmp/test"))
        assert result is False
