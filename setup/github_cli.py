"""Step: GitHub CLI 安裝與認證。

自動偵測、安裝、認證 GitHub CLI (gh)，
實現 git push / repo create / PR 全自動化。
只使用 Python 標準庫。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

# 有效的 GitHub Token 前綴
VALID_TOKEN_PREFIXES = ("ghp_", "github_pat_", "gho_", "ghs_", "ghr_")


# gh 常見安裝路徑（Windows）
_localappdata = os.environ.get("LOCALAPPDATA", "")
_COMMON_GH_PATHS = [
    Path("C:/Program Files/GitHub CLI/gh.exe"),
    Path("C:/Program Files (x86)/GitHub CLI/gh.exe"),
    Path.home() / "scoop" / "shims" / "gh.exe",
]
if _localappdata:
    _COMMON_GH_PATHS.append(Path(_localappdata) / "Programs" / "gh" / "bin" / "gh.exe")


def find_gh_executable() -> Optional[str]:
    """尋找 gh 執行檔路徑。

    優先在 PATH 中搜尋，找不到則檢查常見安裝路徑。

    Returns:
        gh 執行檔完整路徑，找不到回傳 None。
    """
    # 先查 PATH
    path = shutil.which("gh")
    if path:
        return path

    # 再查常見路徑
    for common_path in _COMMON_GH_PATHS:
        if common_path.exists():
            return str(common_path)

    return None


def check_gh_installed() -> bool:
    """檢查 gh CLI 是否已安裝。

    Returns:
        True 代表 gh 已安裝。
    """
    return shutil.which("gh") is not None


def check_gh_auth(gh_path: Optional[str] = None) -> Tuple[bool, str]:
    """檢查 gh 是否已認證。

    Args:
        gh_path: gh 執行檔路徑，預設自動偵測。

    Returns:
        (is_authenticated, account_info) 的 tuple。
    """
    cmd = gh_path or find_gh_executable() or "gh"

    try:
        result = subprocess.run(
            [cmd, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            return True, output
        return False, result.stderr.strip() if result.stderr else ""
    except FileNotFoundError:
        return False, ""
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError:
        return False, ""


def install_gh_with_winget() -> bool:
    """使用 winget 安裝 GitHub CLI。

    Returns:
        True 代表安裝成功。
    """
    try:
        result = subprocess.run(
            [
                "winget", "install",
                "--id", "GitHub.cli",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        return False
    except OSError:
        return False


def install_gh_direct_download() -> bool:
    """從 GitHub Releases 直接下載並安裝 gh CLI MSI。

    不依賴 winget，使用 urllib（stdlib）直接下載。
    僅支援 Windows amd64。

    Returns:
        True 代表安裝成功。
    """
    try:
        # 1. 從 GitHub API 取得最新版本
        api_url = "https://api.github.com/repos/cli/cli/releases/latest"
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "agent-army-installer",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        tag = data["tag_name"]  # 例：v2.65.0
        version = tag.lstrip("v")

        # 2. 下載 MSI
        msi_url = (
            f"https://github.com/cli/cli/releases/download/"
            f"{tag}/gh_{version}_windows_amd64.msi"
        )
        tmp_dir = tempfile.mkdtemp()
        msi_path = os.path.join(tmp_dir, f"gh_{version}_windows_amd64.msi")
        urllib.request.urlretrieve(msi_url, msi_path)

        # 3. 靜默安裝
        r = subprocess.run(
            ["msiexec", "/i", msi_path, "/quiet", "/norestart"],
            capture_output=True,
            text=True,
            timeout=180,
        )

        # 4. 清理暫存檔
        try:
            os.unlink(msi_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

        return r.returncode == 0

    except (urllib.error.URLError, urllib.error.HTTPError):
        return False
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def install_gh_direct_download_zip() -> bool:
    """從 GitHub Releases 下載 gh CLI zip 並解壓縮（不需管理員權限）。

    解壓縮到 %LOCALAPPDATA%\\Programs\\gh\\。

    Returns:
        True 代表安裝成功。
    """
    try:
        api_url = "https://api.github.com/repos/cli/cli/releases/latest"
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "agent-army-installer",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        tag = data["tag_name"]
        version = tag.lstrip("v")

        zip_url = (
            f"https://github.com/cli/cli/releases/download/"
            f"{tag}/gh_{version}_windows_amd64.zip"
        )
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, f"gh_{version}_windows_amd64.zip")
        urllib.request.urlretrieve(zip_url, zip_path)

        local_app = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        gh_install_dir = os.path.join(local_app, "Programs", "gh")
        os.makedirs(gh_install_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                parts = member.split("/", 1)
                if len(parts) > 1 and parts[1]:
                    target_path = os.path.join(gh_install_dir, parts[1])
                    if member.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zf.open(member) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())

        try:
            os.unlink(zip_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

        gh_exe = os.path.join(gh_install_dir, "bin", "gh.exe")
        return os.path.exists(gh_exe)

    except (urllib.error.URLError, urllib.error.HTTPError):
        return False
    except Exception:
        return False


def authenticate_with_token(token: str, gh_path: Optional[str] = None) -> bool:
    """使用 Personal Access Token 認證 gh。

    Args:
        token: GitHub Personal Access Token（ghp_ 或 github_pat_ 開頭）。
        gh_path: gh 執行檔路徑，預設自動偵測。

    Returns:
        True 代表認證成功。
    """
    cmd = gh_path or find_gh_executable() or "gh"

    try:
        result = subprocess.run(
            [cmd, "auth", "login", "--with-token"],
            input=token,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        return False
    except OSError:
        return False


def setup_github_cli(context: Dict) -> Dict:
    """互動式設定 GitHub CLI。

    流程：
    1. 檢查 gh 是否已安裝 → 沒有就用 winget 安裝
    2. 檢查 gh auth status → 已登入就跳過
    3. 未登入 → 請使用者提供 Classic Token
    4. 用 Token 完成認證
    5. 驗證成功

    Args:
        context: 安裝精靈的上下文 dict。

    Returns:
        更新後的 context。
    """
    from .wizard import ask_input, ask_yes_no, print_fail, print_info, print_ok, print_warn

    # Step 1: 檢查 gh 是否已安裝
    gh_path = find_gh_executable()

    if not gh_path:
        print_warn("GitHub CLI (gh) 未安裝")
        print_info("GitHub CLI 用於自動化 repo 建立、push、PR 等操作")

        if sys.platform == "win32":
            # 方法 1：winget
            print_info("正在用 winget 自動安裝...")
            winget_ok = install_gh_with_winget()
            if winget_ok:
                print_ok("GitHub CLI 安裝成功（winget）")
                gh_path = find_gh_executable()
            else:
                # 方法 2：直接從 GitHub 下載 MSI（需管理員權限）
                print_warn("winget 不可用，嘗試直接下載...")
                print_info("嘗試 MSI 安裝...")
                msi_ok = install_gh_direct_download()
                if msi_ok:
                    print_ok("GitHub CLI 安裝成功（MSI）")
                    gh_path = find_gh_executable()
                else:
                    # 方法 3：zip 解壓縮（不需管理員權限）
                    print_warn("MSI 需管理員權限，改用 zip 解壓縮...")
                    zip_ok = install_gh_direct_download_zip()
                    if zip_ok:
                        print_ok("GitHub CLI 安裝成功（zip 解壓縮）")
                        gh_path = find_gh_executable()
                    else:
                        print_fail("自動安裝失敗")
                        print_info("請手動安裝：https://cli.github.com/")
                        print_info("下載頁面：https://github.com/cli/cli/releases/latest")
                        return context
        else:
            print_info("請手動安裝：https://cli.github.com/")
            return context

    if not gh_path:
        print_fail("找不到 gh 執行檔")
        return context

    print_ok(f"GitHub CLI: {gh_path}")

    # Step 2: 檢查認證狀態
    is_auth, account_info = check_gh_auth(gh_path)

    if is_auth:
        print_ok(f"已認證 GitHub")
        if account_info:
            # 顯示帳號資訊（只取第一行）
            first_line = account_info.split("\n")[0].strip()
            print_info(first_line)
        context["setup_github"] = True
        context["gh_path"] = gh_path
        return context

    # Step 3: 需要認證
    print_warn("GitHub CLI 尚未登入")
    print()
    print_info("需要 GitHub Personal Access Token (Classic) 來認證")
    print_info("建立方式：")
    print_info("  1. 打開 https://github.com/settings/tokens/new")
    print_info("  2. Note: agent-army-cli")
    print_info("  3. 勾選: repo, read:org, delete_repo")
    print_info("  4. Generate token → 複製 ghp_... 開頭的字串")
    print()

    token = ask_input("GitHub Token（ghp_ 開頭）")

    if not token:
        print_warn("未輸入 Token，略過 GitHub 設定")
        print_info("之後可執行 python setup.py --add-github")
        return context

    # 驗證 Token 格式
    if not token.startswith(VALID_TOKEN_PREFIXES):
        print_fail("Token 格式不正確，必須以 ghp_ 或 github_pat_ 開頭")
        print_info("請到 https://github.com/settings/tokens/new 建立 Classic Token")
        return context

    # Step 4: 認證
    print_info("正在認證...")
    success = authenticate_with_token(token, gh_path)

    if success:
        print_ok("GitHub CLI 認證成功！")
        # 驗證一次
        is_auth, account_info = check_gh_auth(gh_path)
        if is_auth and account_info:
            first_line = account_info.split("\n")[0].strip()
            print_info(first_line)
        context["setup_github"] = True
        context["gh_path"] = gh_path
    else:
        print_fail("認證失敗，請確認 Token 權限是否包含 repo 和 read:org")
        print_info("可重新建立 Token：https://github.com/settings/tokens/new")
        print_info("之後可執行 python setup.py --add-github")

    return context
