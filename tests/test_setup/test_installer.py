"""獨立安裝包 install.py 的測試。

install.py 是一個零依賴、純 stdlib 的單一檔案，
可以在完全沒有 agent-army 的環境下執行。
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

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

    def test_has_download_gh_msi(self):
        """有 _download_gh_msi 函數（直接下載備援）。"""
        assert hasattr(self.mod, "_download_gh_msi")
        assert callable(self.mod._download_gh_msi)


class TestInstallerGhFallback:
    """測試 install.py 的 gh 直接下載備援機制。"""

    @pytest.fixture(autouse=True)
    def _import_installer(self):
        """動態匯入 install.py。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("installer", INSTALL_SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    @patch("urllib.request.urlopen")
    def test_download_gh_msi_fetches_latest_version(self, mock_urlopen):
        """_download_gh_msi 會呼叫 GitHub API 取得最新版本。"""
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.65.0",
            "assets": [],
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("urllib.request.urlretrieve") as mock_retrieve, \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.mod._download_gh_msi()

        # 確認有呼叫 GitHub API
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert "api.github.com" in (req.full_url if hasattr(req, 'full_url') else str(req))

    @patch("urllib.request.urlopen")
    @patch("urllib.request.urlretrieve")
    @patch("subprocess.run")
    def test_download_gh_msi_installs_with_msiexec(self, mock_run, mock_retrieve, mock_urlopen):
        """_download_gh_msi 用 msiexec 靜默安裝。"""
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.65.0",
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_run.return_value = MagicMock(returncode=0)

        result = self.mod._download_gh_msi()
        assert result is True

        # 確認有呼叫 msiexec
        msiexec_call = mock_run.call_args[0][0]
        assert "msiexec" in msiexec_call

    @patch("urllib.request.urlopen")
    def test_download_gh_msi_handles_network_error(self, mock_urlopen):
        """網路錯誤時回傳 False。"""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")
        result = self.mod._download_gh_msi()
        assert result is False

    @patch("shutil.which", return_value=None)
    @patch("pathlib.Path.exists", return_value=False)
    def test_setup_gh_tries_winget_then_download(self, mock_exists, mock_which):
        """setup_github_cli 先試 winget，失敗再試直接下載。"""
        with patch.object(self.mod, "_download_gh_msi", return_value=False) as mock_msi, \
             patch.object(self.mod, "_download_gh_zip", return_value=True) as mock_zip, \
             patch("subprocess.run") as mock_run, \
             patch.object(self.mod, "_find_gh", side_effect=[None, None, None, "/usr/bin/gh"]), \
             patch("builtins.input", return_value=""):
            # winget 失敗
            mock_run.side_effect = [
                FileNotFoundError("winget not found"),
            ]
            self.mod.setup_github_cli()
            # MSI 失敗後應嘗試 zip
            mock_msi.assert_called_once()
            mock_zip.assert_called_once()


class TestInstallerGhZipFallback:
    """測試 install.py 的 gh zip 下載備援（不需管理員權限）。"""

    @pytest.fixture(autouse=True)
    def _import_installer(self):
        """動態匯入 install.py。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("installer", INSTALL_SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_has_download_gh_zip(self):
        """有 _download_gh_zip 函數。"""
        assert hasattr(self.mod, "_download_gh_zip")
        assert callable(self.mod._download_gh_zip)

    @patch("urllib.request.urlopen")
    @patch("urllib.request.urlretrieve")
    def test_download_gh_zip_extracts_to_local(self, mock_retrieve, mock_urlopen):
        """_download_gh_zip 解壓縮到 LOCALAPPDATA。"""
        import json
        import tempfile
        import zipfile

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.87.3",
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        # 建立假的 zip 檔案
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "gh.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("gh_2.87.3_windows_amd64/bin/gh.exe", b"fake")

            def fake_retrieve(url, path):
                import shutil
                shutil.copy2(zip_path, path)

            mock_retrieve.side_effect = fake_retrieve

            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                result = self.mod._download_gh_zip()

            # 檢查 gh.exe 是否被解壓縮到正確位置
            gh_exe = os.path.join(tmp, "Programs", "gh", "bin", "gh.exe")
            assert os.path.exists(gh_exe)
            assert result is True

    @patch("urllib.request.urlopen")
    def test_download_gh_zip_handles_network_error(self, mock_urlopen):
        """網路錯誤時回傳 False。"""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        result = self.mod._download_gh_zip()
        assert result is False


class TestInstallerExistingRepo:
    """測試 install.py 對既有目錄的處理。"""

    @pytest.fixture(autouse=True)
    def _import_installer(self):
        """動態匯入 install.py。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("installer", INSTALL_SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_has_check_existing_repo(self):
        """有 _check_existing_repo 函數。"""
        assert hasattr(self.mod, "_check_existing_repo")
        assert callable(self.mod._check_existing_repo)

    @patch("subprocess.run")
    def test_detects_agent_army_repo(self, mock_run, tmp_path):
        """偵測到既有 agent-army git repo → 回傳 'agent-army'。"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/bigmale0811/agent-army.git\n",
        )
        result = self.mod._check_existing_repo(tmp_path)
        assert result == "agent-army"

    @patch("subprocess.run")
    def test_detects_other_repo(self, mock_run, tmp_path):
        """偵測到其他 git repo → 回傳 'other-repo'。"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/someone/other-project.git\n",
        )
        result = self.mod._check_existing_repo(tmp_path)
        assert result == "other-repo"

    @patch("subprocess.run")
    def test_detects_not_a_repo(self, mock_run, tmp_path):
        """不是 git repo → 回傳 'not-repo'。"""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal")
        result = self.mod._check_existing_repo(tmp_path)
        assert result == "not-repo"

    @patch("subprocess.run")
    def test_pull_agent_army_success(self, mock_run, tmp_path):
        """有 _pull_agent_army 函數且正確呼叫 git pull。"""
        mock_run.return_value = MagicMock(returncode=0)
        result = self.mod._pull_agent_army(tmp_path)
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "pull" in cmd
