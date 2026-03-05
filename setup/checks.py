"""Step 1: 環境檢查 — 確認必要工具已安裝。"""

import shutil
import subprocess
import sys


def _check_command(name: str, args: list, extract_version=None) -> tuple:
    """檢查命令是否存在並取得版本。

    Returns:
        (is_installed, version_string)
    """
    path = shutil.which(name)
    if not path:
        return False, ""

    try:
        result = subprocess.run(
            [name] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout.strip() or result.stderr.strip()
        if extract_version:
            output = extract_version(output)
        return True, output
    except Exception:
        return True, "(版本未知)"


def run_environment_checks() -> bool:
    """執行環境檢查，回傳是否全部通過。"""
    from .wizard import print_fail, print_info, print_ok, print_warn

    all_ok = True

    # Python
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        print_ok(f"Python {py_version}")
    else:
        print_warn(f"Python {py_version}（建議 3.10+）")

    # Node.js
    installed, version = _check_command("node", ["--version"])
    if installed:
        print_ok(f"Node.js {version}")
    else:
        print_fail("Node.js — 未安裝")
        print_info("下載：https://nodejs.org/")
        all_ok = False

    # npm
    installed, version = _check_command("npm", ["--version"])
    if installed:
        print_ok(f"npm {version}")
    else:
        print_fail("npm — 未安裝（通常隨 Node.js 一起安裝）")
        all_ok = False

    # Git
    installed, version = _check_command("git", ["--version"])
    if installed:
        print_ok(f"Git: {version}")
    else:
        print_fail("Git — 未安裝")
        print_info("下載：https://git-scm.com/")
        all_ok = False

    # Claude CLI
    installed, version = _check_command("claude", ["--version"])
    if installed:
        print_ok(f"Claude CLI: {version}")
    else:
        print_warn("Claude CLI — 未安裝")
        print_info("安裝：npm install -g @anthropic-ai/claude-code")
        # 不是必要條件（可以之後裝），但建議
        from .wizard import ask_yes_no
        if ask_yes_no("是否自動安裝 Claude CLI？"):
            _install_claude_cli()
            # 再檢查一次
            installed, version = _check_command("claude", ["--version"])
            if installed:
                print_ok(f"Claude CLI: {version}（剛安裝）")
            else:
                print_fail("Claude CLI 安裝失敗，請手動執行：npm install -g @anthropic-ai/claude-code")

    # Ollama（可選）
    installed, version = _check_command("ollama", ["--version"])
    if installed:
        print_ok(f"Ollama: {version}")
    else:
        print_info("Ollama — 未安裝（可選，用於本地模型）")

    return all_ok


def _install_claude_cli() -> None:
    """自動安裝 Claude CLI。"""
    from .wizard import print_fail, print_info, print_ok

    print_info("正在安裝 Claude CLI...")
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "@anthropic-ai/claude-code"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print_ok("Claude CLI 安裝成功")
        else:
            print_fail(f"安裝失敗：{result.stderr.strip()}")
    except Exception as e:
        print_fail(f"安裝過程出錯：{e}")
