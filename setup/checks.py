"""Step 1: 環境檢查 — 確認必要工具已安裝。

檢查項目：
  - Python ≥ 3.10（必要）
  - Node.js（必要）
  - npm（必要）
  - Git（必要）
  - GitHub CLI gh（可選）
  - Ollama（可選）
"""

import shutil
import subprocess
import sys
from typing import Dict


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


def run_environment_checks() -> Dict:
    """執行環境檢查，回傳檢查結果 dict。

    Returns:
        dict 包含：
        - all_ok: bool — 所有必要項目是否通過
        - has_ollama: bool — Ollama 是否已安裝
        - has_gh: bool — GitHub CLI 是否已安裝
    """
    from .wizard import print_fail, print_info, print_ok, print_warn

    all_ok = True
    has_ollama = False
    has_gh = False

    # Python
    py_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}"
    )
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

    # GitHub CLI（可選）
    installed, version = _check_command("gh", ["--version"])
    if installed:
        first_line = version.split("\n")[0] if version else version
        print_ok(f"GitHub CLI: {first_line}")
        has_gh = True
    else:
        print_info("GitHub CLI (gh) — 未安裝（下一步會自動安裝）")

    # Ollama（可選）
    installed, version = _check_command("ollama", ["--version"])
    if installed:
        print_ok(f"Ollama: {version}")
        has_ollama = True
    else:
        print_info("Ollama — 未安裝（可選，用於本地模型）")

    return {
        "all_ok": all_ok,
        "has_ollama": has_ollama,
        "has_gh": has_gh,
    }
