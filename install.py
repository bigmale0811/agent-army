#!/usr/bin/env python3
"""Agent Army 一鍵安裝包。

此檔案是完全獨立的，不依賴 agent-army 的任何模組。
只使用 Python 標準庫，可在全新電腦上直接執行。

使用方式：
    python install.py              # 完整安裝
    python install.py --path D:\\Projects\\agent-army  # 指定路徑

流程：
    Step 1: 環境檢查 (Python, Node, Git)
    Step 2: GitHub CLI 設定 (安裝 + Token 認證)
    Step 3: 下載 agent-army (git clone)
    Step 4~8: 自動執行 setup.py 完成剩餘設定
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# ── 常數 ──
AGENT_ARMY_REPO = "https://github.com/bigmale0811/agent-army.git"
DEFAULT_INSTALL_PATH = "D:\\Projects\\agent-army"

# ANSI 顏色
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# gh Token 有效前綴
VALID_TOKEN_PREFIXES = ("ghp_", "github_pat_", "gho_", "ghs_", "ghr_")

# gh 常見安裝路徑（Windows）
_localappdata = os.environ.get("LOCALAPPDATA", "")
GH_COMMON_PATHS = [
    Path("C:/Program Files/GitHub CLI/gh.exe"),
    Path("C:/Program Files (x86)/GitHub CLI/gh.exe"),
    Path(_localappdata) / "Programs" / "gh" / "bin" / "gh.exe" if _localappdata else None,
]
GH_COMMON_PATHS = [p for p in GH_COMMON_PATHS if p is not None]


# ── 輸出工具 ──

def _enable_ansi():
    """在 Windows 上啟用 ANSI 顏色。"""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def ok(msg):
    print(f"  {GREEN}✅ {msg}{RESET}")


def fail(msg):
    print(f"  {RED}❌ {msg}{RESET}")


def warn(msg):
    print(f"  {YELLOW}⚠️  {msg}{RESET}")


def info(msg):
    print(f"  {CYAN}ℹ️  {msg}{RESET}")


def step_header(num, total, title):
    print(f"\n{BLUE}{BOLD}{'─' * 50}")
    print(f"  Step {num}/{total} — {title}")
    print(f"{'─' * 50}{RESET}\n")


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or default


def ask_yn(prompt, default=True):
    suffix = "(Y/n)" if default else "(y/N)"
    while True:
        answer = input(f"  {prompt} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


# ── Step 1: 環境檢查 ──

def check_environment():
    """檢查必要工具是否已安裝。

    Returns:
        dict 包含各工具的安裝狀態。
    """
    result = {
        "has_python": True,  # 能跑到這裡就有 Python
        "has_node": False,
        "has_npm": False,
        "has_git": False,
        "has_gh": False,
        "has_ollama": False,
        "all_ok": True,
    }

    # Python
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        ok(f"Python {py_ver}")
    else:
        warn(f"Python {py_ver}（建議 3.10+）")

    # Node.js
    if shutil.which("node"):
        result["has_node"] = True
        ok("Node.js ✓")
    else:
        fail("Node.js — 未安裝")
        info("下載：https://nodejs.org/")
        result["all_ok"] = False

    # npm
    if shutil.which("npm"):
        result["has_npm"] = True
        ok("npm ✓")
    else:
        fail("npm — 未安裝")
        result["all_ok"] = False

    # Git
    if shutil.which("git"):
        result["has_git"] = True
        ok("Git ✓")
    else:
        fail("Git — 未安裝")
        info("下載：https://git-scm.com/")
        result["all_ok"] = False

    # GitHub CLI（可選）
    if _find_gh():
        result["has_gh"] = True
        ok("GitHub CLI (gh) ✓")
    else:
        info("GitHub CLI (gh) — 未安裝（下一步會自動安裝）")

    # Ollama（可選）
    if shutil.which("ollama"):
        result["has_ollama"] = True
        ok("Ollama ✓")
    else:
        info("Ollama — 未安裝（可選）")

    return result


# ── Step 2: GitHub CLI ──

def _find_gh():
    """尋找 gh 執行檔。"""
    path = shutil.which("gh")
    if path:
        return path
    for p in GH_COMMON_PATHS:
        if p.exists():
            return str(p)
    return None


def _download_gh_msi():
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
        info(f"下載 gh v{version}...")
        tmp_dir = tempfile.mkdtemp()
        msi_path = os.path.join(tmp_dir, f"gh_{version}_windows_amd64.msi")
        urllib.request.urlretrieve(msi_url, msi_path)

        # 3. 靜默安裝
        info("正在安裝（msiexec）...")
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

    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        fail(f"下載失敗：{e}")
        return False
    except subprocess.TimeoutExpired:
        fail("安裝逾時")
        return False
    except Exception as e:
        fail(f"直接下載安裝失敗：{e}")
        return False


def _download_gh_zip():
    """從 GitHub Releases 下載 gh CLI zip 並解壓縮（不需管理員權限）。

    解壓縮到 %LOCALAPPDATA%\\Programs\\gh\\，不需要 msiexec 或管理員權限。

    Returns:
        True 代表安裝成功。
    """
    try:
        # 1. 取得最新版本
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

        # 2. 下載 zip
        zip_url = (
            f"https://github.com/cli/cli/releases/download/"
            f"{tag}/gh_{version}_windows_amd64.zip"
        )
        info(f"下載 gh v{version} (zip)...")
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, f"gh_{version}_windows_amd64.zip")
        urllib.request.urlretrieve(zip_url, zip_path)

        # 3. 解壓縮到 LOCALAPPDATA\Programs\gh
        local_app = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        gh_install_dir = os.path.join(local_app, "Programs", "gh")
        os.makedirs(gh_install_dir, exist_ok=True)

        info(f"解壓縮到 {gh_install_dir}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            # zip 裡面有一層目錄 gh_X.Y.Z_windows_amd64/
            for member in zf.namelist():
                # 去掉第一層目錄前綴
                parts = member.split("/", 1)
                if len(parts) > 1 and parts[1]:
                    target_path = os.path.join(gh_install_dir, parts[1])
                    if member.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zf.open(member) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())

        # 4. 清理暫存檔
        try:
            os.unlink(zip_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

        # 5. 確認 gh.exe 存在
        gh_exe = os.path.join(gh_install_dir, "bin", "gh.exe")
        if os.path.exists(gh_exe):
            ok(f"gh 已安裝到 {gh_exe}")
            return True

        warn("解壓縮完成但找不到 gh.exe")
        return False

    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        fail(f"下載失敗：{e}")
        return False
    except Exception as e:
        fail(f"zip 安裝失敗：{e}")
        return False


def setup_github_cli():
    """安裝並認證 GitHub CLI。

    安裝順序：winget → MSI → zip 解壓縮 → 手動提示。

    Returns:
        gh 執行檔路徑，或 None。
    """
    gh = _find_gh()

    # 安裝
    if not gh:
        if sys.platform != "win32":
            warn("非 Windows 系統，請手動安裝 gh：https://cli.github.com/")
            return None

        # 方法 1：winget
        info("正在用 winget 安裝 GitHub CLI...")
        winget_ok = False
        try:
            r = subprocess.run(
                ["winget", "install", "--id", "GitHub.cli",
                 "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode == 0:
                ok("GitHub CLI 安裝成功（winget）")
                winget_ok = True
                gh = _find_gh()
        except Exception:
            warn("winget 不可用，嘗試直接下載...")

        # 方法 2：直接從 GitHub 下載 MSI（需管理員權限）
        if not winget_ok:
            info("嘗試從 GitHub Releases 直接下載 MSI...")
            if _download_gh_msi():
                ok("GitHub CLI 安裝成功（MSI）")
                gh = _find_gh()

        # 方法 3：下載 zip 解壓縮（不需管理員權限）
        if not winget_ok and not gh:
            info("MSI 需管理員權限，改用 zip 解壓縮...")
            if _download_gh_zip():
                ok("GitHub CLI 安裝成功（zip 解壓縮）")
                gh = _find_gh()
            else:
                fail("自動安裝失敗，請手動安裝：https://cli.github.com/")
                info("下載頁面：https://github.com/cli/cli/releases/latest")
                return None

    if not gh:
        fail("找不到 gh 執行檔")
        return None

    ok(f"GitHub CLI: {gh}")

    # 認證
    try:
        r = subprocess.run(
            [gh, "auth", "status"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            ok("GitHub 已認證")
            return gh
    except Exception:
        pass

    warn("GitHub CLI 尚未登入")
    info("需要 Personal Access Token (Classic)")
    info("建立方式：https://github.com/settings/tokens/new")
    info("勾選：repo, read:org")
    print()

    token = ask("GitHub Token（ghp_ 開頭）")
    if not token:
        warn("略過 GitHub 認證")
        return gh

    if not token.startswith(VALID_TOKEN_PREFIXES):
        fail("Token 格式不正確")
        return gh

    info("正在認證...")
    try:
        r = subprocess.run(
            [gh, "auth", "login", "--with-token"],
            input=token, capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            ok("GitHub CLI 認證成功！")
        else:
            fail("認證失敗，請確認 Token 權限")
    except Exception as e:
        fail(f"認證失敗：{e}")

    return gh


# ── Step 3: Clone agent-army ──

def _check_existing_repo(target_path):
    """檢查目標路徑是否為既有的 git repo。

    Args:
        target_path: 要檢查的路徑。

    Returns:
        'agent-army': 是 agent-army repo。
        'other-repo': 是其他 git repo。
        'not-repo': 不是 git repo。
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(target_path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            url = r.stdout.strip()
            if "agent-army" in url:
                return "agent-army"
            return "other-repo"
        return "not-repo"
    except Exception:
        return "not-repo"


def _pull_agent_army(target_path):
    """在既有的 agent-army repo 中執行 git pull。

    Args:
        target_path: agent-army 專案路徑。

    Returns:
        True 代表成功。
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(target_path), "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return r.returncode == 0
    except Exception:
        return False


def clone_agent_army(target_path, repo_url=None):
    """Clone agent-army 到指定路徑。

    Args:
        target_path: 安裝目標路徑。
        repo_url: 自訂 repo URL。

    Returns:
        True 代表成功。
    """
    url = repo_url or AGENT_ARMY_REPO

    try:
        r = subprocess.run(
            ["git", "clone", url, str(target_path)],
            capture_output=True, text=True, timeout=120,
        )
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        fail("clone 逾時")
        return False
    except FileNotFoundError:
        fail("Git 未安裝")
        return False
    except Exception as e:
        fail(f"clone 失敗：{e}")
        return False


# ── Step 4~8: 呼叫 setup.py ──

def run_setup_wizard(project_path):
    """在 clone 好的專案中執行 setup.py。

    Args:
        project_path: agent-army 專案路徑。

    Returns:
        True 代表成功。
    """
    setup_py = project_path / "setup.py"
    if not setup_py.exists():
        fail(f"找不到 {setup_py}")
        return False

    info("啟動 Setup Wizard...")
    try:
        r = subprocess.run(
            [sys.executable, str(setup_py)],
            cwd=str(project_path),
            timeout=600,
        )
        return r.returncode == 0
    except Exception as e:
        fail(f"Setup Wizard 執行失敗：{e}")
        return False


# ── 主程式 ──

def main():
    """安裝包主流程。"""
    _enable_ansi()

    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════╗
║   🤖 Agent Army Installer v1.0          ║
║   一鍵安裝，從零到完成                  ║
╚══════════════════════════════════════════╝{RESET}
""")

    total = 4  # 前 3 步在這裡，Step 4~8 交給 setup.py

    # ── Step 1: 環境檢查 ──
    step_header(1, total, "環境檢查")
    env = check_environment()
    if not env["all_ok"]:
        fail("有必要工具未安裝")
        if not ask_yn("是否繼續？", default=False):
            print("\n  👋 請安裝缺少的工具後重新執行。\n")
            sys.exit(1)

    # ── Step 2: GitHub CLI ──
    step_header(2, total, "GitHub CLI 設定")
    if ask_yn("要設定 GitHub CLI 嗎？（用於自動化 push/PR）"):
        setup_github_cli()
    else:
        info("略過")

    # ── Step 3: 下載 agent-army ──
    step_header(3, total, "下載 Agent Army")
    install_path = ask("安裝路徑", default=DEFAULT_INSTALL_PATH)
    target = Path(install_path)

    if target.exists() and (target / "CLAUDE.md").exists():
        ok(f"偵測到既有專案：{target}")
        # 檢查是否為 agent-army repo，如果是就 pull 最新
        repo_status = _check_existing_repo(target)
        if repo_status == "agent-army":
            info("嘗試更新到最新版本...")
            if _pull_agent_army(target):
                ok("已更新到最新版本")
            else:
                warn("更新失敗，使用既有版本繼續")
        else:
            info("跳過下載")
    elif target.exists() and any(target.iterdir()):
        # 非空目錄 — 檢查是否為 git repo
        repo_status = _check_existing_repo(target)
        if repo_status == "agent-army":
            ok(f"偵測到既有 agent-army repo：{target}")
            info("嘗試更新到最新版本...")
            if _pull_agent_army(target):
                ok("已更新到最新版本")
            else:
                warn("更新失敗，使用既有版本繼續")
        elif repo_status == "other-repo":
            fail(f"路徑 {target} 是其他 git 專案")
            info("請選擇其他安裝路徑")
            new_path = ask("新的安裝路徑", default=str(target.parent / "agent-army"))
            target = Path(new_path)
            if not clone_agent_army(target):
                fail("下載失敗")
                sys.exit(1)
            ok("下載完成！")
        else:
            warn(f"路徑 {target} 已有檔案（非 git repo）")
            info("git clone 無法在非空目錄執行")
            new_path = ask("請選擇空的安裝路徑", default=str(target.parent / "agent-army"))
            target = Path(new_path)
            if target.exists() and any(target.iterdir()):
                fail("該路徑也非空，請手動清理後重新執行")
                sys.exit(1)
            if not clone_agent_army(target):
                fail("下載失敗")
                sys.exit(1)
            ok("下載完成！")
    else:
        info(f"正在從 GitHub 下載...")
        info(f"來源：{AGENT_ARMY_REPO}")
        if clone_agent_army(target):
            ok("下載完成！")
        else:
            fail("下載失敗，請檢查網路和 Git 設定")
            info(f"手動下載：git clone {AGENT_ARMY_REPO} {target}")
            sys.exit(1)

    # ── Step 4: 交給 setup.py ──
    step_header(4, total, "執行 Setup Wizard（Step 4~8）")
    info(f"進入 {target}")
    info("接下來由 Setup Wizard 完成剩餘步驟...")
    print()

    run_setup_wizard(target)


if __name__ == "__main__":
    # 支援 --path 參數
    if len(sys.argv) > 2 and sys.argv[1] == "--path":
        DEFAULT_INSTALL_PATH = sys.argv[2]
    main()
