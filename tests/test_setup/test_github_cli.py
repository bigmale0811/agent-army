"""GitHub CLI 安裝與認證模組的測試。

測試涵蓋：
- gh 安裝狀態偵測
- gh 認證狀態偵測
- winget 安裝流程
- Token 認證流程
- 整合流程（setup_github_cli）
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestCheckGhInstalled:
    """測試 gh CLI 安裝偵測。"""

    @patch("shutil.which")
    def test_gh_found(self, mock_which):
        """gh 在 PATH 中找到。"""
        from setup.github_cli import check_gh_installed

        mock_which.return_value = "/c/Program Files/GitHub CLI/gh.exe"
        assert check_gh_installed() is True

    @patch("shutil.which")
    def test_gh_not_found(self, mock_which):
        """gh 不在 PATH 中。"""
        from setup.github_cli import check_gh_installed

        mock_which.return_value = None
        assert check_gh_installed() is False

    @patch("shutil.which")
    def test_checks_correct_command_name(self, mock_which):
        """確認搜尋的是 'gh' 命令。"""
        from setup.github_cli import check_gh_installed

        mock_which.return_value = None
        check_gh_installed()
        mock_which.assert_called_with("gh")


class TestCheckGhAuth:
    """測試 gh 認證狀態偵測。"""

    @patch("subprocess.run")
    def test_authenticated(self, mock_run):
        """gh 已認證 — returncode=0。"""
        from setup.github_cli import check_gh_auth

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="github.com\n  ✓ Logged in to github.com account testuser\n",
        )
        is_auth, account = check_gh_auth()
        assert is_auth is True
        assert "testuser" in account

    @patch("subprocess.run")
    def test_not_authenticated(self, mock_run):
        """gh 未認證 — returncode=1。"""
        from setup.github_cli import check_gh_auth

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="You are not logged into any GitHub hosts.",
        )
        is_auth, account = check_gh_auth()
        assert is_auth is False

    @patch("subprocess.run")
    def test_gh_not_installed_raises(self, mock_run):
        """gh 未安裝時拋出 FileNotFoundError。"""
        from setup.github_cli import check_gh_auth

        mock_run.side_effect = FileNotFoundError("gh not found")
        is_auth, account = check_gh_auth()
        assert is_auth is False

    @patch("subprocess.run")
    def test_uses_gh_auth_status_command(self, mock_run):
        """確認使用 gh auth status 命令。"""
        from setup.github_cli import check_gh_auth

        mock_run.return_value = MagicMock(returncode=0, stdout="logged in")
        check_gh_auth()
        cmd = mock_run.call_args[0][0]
        assert "auth" in cmd
        assert "status" in cmd


class TestInstallGhWithWinget:
    """測試用 winget 安裝 gh。"""

    @patch("subprocess.run")
    def test_install_success(self, mock_run):
        """winget 安裝成功。"""
        from setup.github_cli import install_gh_with_winget

        mock_run.return_value = MagicMock(returncode=0)
        assert install_gh_with_winget() is True

    @patch("subprocess.run")
    def test_install_failure(self, mock_run):
        """winget 安裝失敗。"""
        from setup.github_cli import install_gh_with_winget

        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        assert install_gh_with_winget() is False

    @patch("subprocess.run")
    def test_winget_not_found(self, mock_run):
        """winget 不存在。"""
        from setup.github_cli import install_gh_with_winget

        mock_run.side_effect = FileNotFoundError("winget not found")
        assert install_gh_with_winget() is False

    @patch("subprocess.run")
    def test_uses_correct_winget_command(self, mock_run):
        """確認 winget install 命令正確。"""
        from setup.github_cli import install_gh_with_winget

        mock_run.return_value = MagicMock(returncode=0)
        install_gh_with_winget()
        cmd = mock_run.call_args[0][0]
        assert "winget" in cmd
        assert "GitHub.cli" in cmd


class TestAuthenticateWithToken:
    """測試 Token 認證流程。"""

    @patch("subprocess.run")
    def test_auth_success(self, mock_run):
        """Token 認證成功。"""
        from setup.github_cli import authenticate_with_token

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        assert authenticate_with_token("ghp_test123") is True

    @patch("subprocess.run")
    def test_auth_failure_invalid_token(self, mock_run):
        """Token 無效。"""
        from setup.github_cli import authenticate_with_token

        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="error validating token: missing required scope",
        )
        assert authenticate_with_token("bad_token") is False

    @patch("subprocess.run")
    def test_passes_token_via_stdin(self, mock_run):
        """確認 Token 透過 stdin 傳入。"""
        from setup.github_cli import authenticate_with_token

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        authenticate_with_token("ghp_mytoken123")
        assert mock_run.call_args.kwargs.get("input") == "ghp_mytoken123"


class TestTokenValidation:
    """測試 Token 格式驗證。"""

    def test_valid_classic_token(self):
        """Classic Token (ghp_) 格式正確。"""
        from setup.github_cli import VALID_TOKEN_PREFIXES

        assert "ghp_test123".startswith(VALID_TOKEN_PREFIXES)

    def test_valid_fine_grained_token(self):
        """Fine-grained Token (github_pat_) 格式正確。"""
        from setup.github_cli import VALID_TOKEN_PREFIXES

        assert "github_pat_abc123".startswith(VALID_TOKEN_PREFIXES)

    def test_invalid_token(self):
        """不正確的 Token 格式。"""
        from setup.github_cli import VALID_TOKEN_PREFIXES

        assert not "bad_token".startswith(VALID_TOKEN_PREFIXES)
        assert not "".startswith(VALID_TOKEN_PREFIXES)
        assert not "https://github.com".startswith(VALID_TOKEN_PREFIXES)


class TestSetupGithubCli:
    """整合測試：setup_github_cli 主流程。"""

    @patch("setup.github_cli.check_gh_auth", return_value=(True, "Logged in as testuser"))
    @patch("setup.github_cli.find_gh_executable", return_value="/usr/bin/gh")
    def test_already_authenticated_skips_prompt(self, mock_find, mock_auth):
        """gh 已認證 → 直接跳過，不問 Token。"""
        from setup.github_cli import setup_github_cli

        ctx = setup_github_cli({})
        assert ctx.get("setup_github") is True
        assert ctx.get("gh_path") == "/usr/bin/gh"

    @patch("setup.github_cli.find_gh_executable", return_value=None)
    @patch("sys.platform", "linux")
    def test_gh_not_installed_non_windows(self, mock_find):
        """非 Windows 且 gh 未安裝 → 提示手動安裝並返回。"""
        from setup.github_cli import setup_github_cli

        ctx = setup_github_cli({})
        assert ctx.get("setup_github") is None

    @patch("setup.github_cli.authenticate_with_token", return_value=True)
    @patch("setup.github_cli.check_gh_auth")
    @patch("setup.github_cli.find_gh_executable", return_value="/usr/bin/gh")
    @patch("builtins.input", return_value="ghp_validtoken123")
    def test_token_auth_success(self, mock_input, mock_find, mock_auth, mock_token_auth):
        """gh 已安裝但未認證 → 輸入有效 Token → 認證成功。"""
        from setup.github_cli import setup_github_cli

        # 第一次 check_gh_auth 回傳未認證，第二次（驗證）回傳已認證
        mock_auth.side_effect = [
            (False, ""),
            (True, "Logged in as testuser"),
        ]
        ctx = setup_github_cli({})
        assert ctx.get("setup_github") is True

    @patch("setup.github_cli.check_gh_auth", return_value=(False, ""))
    @patch("setup.github_cli.find_gh_executable", return_value="/usr/bin/gh")
    @patch("builtins.input", return_value="bad_token_no_prefix")
    def test_invalid_token_format_rejected(self, mock_input, mock_find, mock_auth):
        """輸入格式不正確的 Token → 被拒絕。"""
        from setup.github_cli import setup_github_cli

        ctx = setup_github_cli({})
        assert ctx.get("setup_github") is None

    @patch("setup.github_cli.check_gh_auth", return_value=(False, ""))
    @patch("setup.github_cli.find_gh_executable", return_value="/usr/bin/gh")
    @patch("builtins.input", return_value="")
    def test_empty_token_skips(self, mock_input, mock_find, mock_auth):
        """不輸入 Token → 略過設定。"""
        from setup.github_cli import setup_github_cli

        ctx = setup_github_cli({})
        assert ctx.get("setup_github") is None


class TestFindGhExecutable:
    """測試尋找 gh 執行檔路徑。"""

    @patch("shutil.which")
    def test_found_in_path(self, mock_which):
        """gh 在 PATH 中。"""
        from setup.github_cli import find_gh_executable

        mock_which.return_value = "C:\\Program Files\\GitHub CLI\\gh.exe"
        result = find_gh_executable()
        assert result is not None
        assert "gh" in result.lower()

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    def test_found_in_common_location(self, mock_exists, mock_which):
        """gh 在常見安裝路徑中。"""
        from setup.github_cli import find_gh_executable

        mock_which.return_value = None
        # 模擬第一個常見路徑存在
        mock_exists.return_value = True
        result = find_gh_executable()
        assert result is not None

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    def test_not_found_anywhere(self, mock_exists, mock_which):
        """gh 在任何地方都找不到。"""
        from setup.github_cli import find_gh_executable

        mock_which.return_value = None
        mock_exists.return_value = False
        result = find_gh_executable()
        assert result is None


class TestInstallGhDirectDownload:
    """測試直接從 GitHub 下載 gh MSI 的備援方案。"""

    def test_function_exists(self):
        """install_gh_direct_download 函數存在。"""
        from setup.github_cli import install_gh_direct_download
        assert callable(install_gh_direct_download)

    @patch("urllib.request.urlopen")
    @patch("urllib.request.urlretrieve")
    @patch("subprocess.run")
    def test_download_success(self, mock_run, mock_retrieve, mock_urlopen):
        """成功下載並安裝 gh MSI。"""
        import json
        from setup.github_cli import install_gh_direct_download

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.65.0",
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_run.return_value = MagicMock(returncode=0)

        result = install_gh_direct_download()
        assert result is True

    @patch("urllib.request.urlopen")
    def test_download_network_error(self, mock_urlopen):
        """網路錯誤時回傳 False。"""
        import urllib.error
        from setup.github_cli import install_gh_direct_download

        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        result = install_gh_direct_download()
        assert result is False

    @patch("urllib.request.urlopen")
    @patch("urllib.request.urlretrieve")
    @patch("subprocess.run")
    def test_msiexec_failure(self, mock_run, mock_retrieve, mock_urlopen):
        """msiexec 安裝失敗時回傳 False。"""
        import json
        from setup.github_cli import install_gh_direct_download

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.65.0",
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_run.return_value = MagicMock(returncode=1)

        result = install_gh_direct_download()
        assert result is False

    @patch("urllib.request.urlopen")
    @patch("urllib.request.urlretrieve")
    @patch("subprocess.run")
    def test_downloads_correct_msi_url(self, mock_run, mock_retrieve, mock_urlopen):
        """下載的 MSI URL 包含正確版本號。"""
        import json
        from setup.github_cli import install_gh_direct_download

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.65.0",
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        mock_run.return_value = MagicMock(returncode=0)

        install_gh_direct_download()

        # 確認下載的 URL 包含版本號
        download_url = mock_retrieve.call_args[0][0]
        assert "2.65.0" in download_url
        assert "windows_amd64.msi" in download_url
