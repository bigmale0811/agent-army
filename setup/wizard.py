"""Setup Wizard 主流程控制。

協調所有安裝步驟，提供統一的互動介面。
只使用 Python 標準庫。
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

from .checks import run_environment_checks
from .cloud_models import setup_cloud_models
from .github_cli import setup_github_cli
from .ollama import setup_ollama
from .scaffold import scaffold_project
from .telegram import setup_telegram
from .verify import run_verification

# ANSI 顏色碼（Windows 10+ 支援）
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _enable_ansi_windows() -> None:
    """在 Windows 上啟用 ANSI 顏色支援。"""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # 啟用 ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def print_banner() -> None:
    """顯示歡迎橫幅。"""
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════╗
║   🤖 Agent Army Setup Wizard v1.0       ║
║   Universal Agent Framework Installer    ║
╚══════════════════════════════════════════╝{RESET}
""")


def print_step(step: int, total: int, title: str) -> None:
    """顯示步驟標題。"""
    print(f"\n{BLUE}{BOLD}{'─' * 50}")
    print(f"  Step {step}/{total} — {title}")
    print(f"{'─' * 50}{RESET}\n")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """詢問使用者 Yes/No 問題。"""
    suffix = "(Y/n)" if default else "(y/N)"
    while True:
        answer = input(f"  {prompt} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print(f"  {YELLOW}請輸入 y 或 n{RESET}")


def ask_input(prompt: str, default: str = "") -> str:
    """詢問使用者輸入。"""
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or default


def ask_choice(prompt: str, choices: List[str]) -> str:
    """讓使用者從選項中選擇。"""
    print(f"  {prompt}")
    for i, choice in enumerate(choices, 1):
        print(f"    {i}. {choice}")
    while True:
        answer = input(f"  選擇 (1-{len(choices)}): ").strip()
        try:
            idx = int(answer) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"  {YELLOW}請輸入 1 到 {len(choices)} 之間的數字{RESET}")


def ask_multi_choice(prompt: str, choices: List[str]) -> List[str]:
    """讓使用者選擇多個選項（用逗號分隔）。"""
    print(f"  {prompt}")
    for i, choice in enumerate(choices, 1):
        print(f"    {i}. {choice}")
    print(f"  {CYAN}（可用逗號分隔多個選項，如 1,2,3）{RESET}")
    while True:
        answer = input(f"  選擇: ").strip()
        if not answer:
            return []
        try:
            indices = [int(x.strip()) - 1 for x in answer.split(",")]
            selected = []
            for idx in indices:
                if 0 <= idx < len(choices):
                    selected.append(choices[idx])
                else:
                    raise ValueError
            return selected
        except ValueError:
            print(f"  {YELLOW}格式錯誤，請用逗號分隔數字{RESET}")


def print_ok(msg: str) -> None:
    """顯示成功訊息。"""
    print(f"  {GREEN}✅ {msg}{RESET}")


def print_fail(msg: str) -> None:
    """顯示失敗訊息。"""
    print(f"  {RED}❌ {msg}{RESET}")


def print_warn(msg: str) -> None:
    """顯示警告訊息。"""
    print(f"  {YELLOW}⚠️  {msg}{RESET}")


def print_info(msg: str) -> None:
    """顯示資訊訊息。"""
    print(f"  {CYAN}ℹ️  {msg}{RESET}")


def _is_existing_project(path: Path) -> bool:
    """判斷是否為已存在的 agent-army 專案（例如 git clone 下來的）。"""
    return (path / "CLAUDE.md").exists() and (path / ".claude" / "settings.json").exists()


def run_wizard(project_path: Optional[Path] = None) -> None:
    """執行安裝精靈主流程。"""
    _enable_ansi_windows()
    print_banner()

    # 自動偵測：如果是在 clone 下來的專案裡執行，就用當前目錄
    cwd = Path.cwd()
    is_existing = _is_existing_project(project_path or cwd)

    if is_existing and project_path is None:
        project_path = cwd

    context: Dict = {
        "project_path": project_path,
        "project_name": project_path.name if project_path else None,
        "language": None,
        "cloud_providers": [],
        "setup_ollama": False,
        "setup_telegram": False,
        "is_existing_project": is_existing,
    }

    if is_existing:
        total_steps = 6
        print_ok(f"偵測到既有專案：{project_path}")
        print_info("跳過專案初始化，只進行環境設定\n")
    else:
        total_steps = 8

    step = 0

    # Step: 環境檢查
    step += 1
    print_step(step, total_steps, "環境檢查")
    env_ok = run_environment_checks()
    if not env_ok:
        print_fail("環境檢查未通過，請先安裝缺少的工具")
        if not ask_yes_no("是否繼續？", default=False):
            print("\n  👋 安裝中止。請安裝缺少的工具後重新執行。\n")
            sys.exit(1)

    # Step: Claude 登入確認
    step += 1
    print_step(step, total_steps, "Claude CLI 登入")
    _check_claude_auth()

    # Step: 專案初始化（只有新專案才需要）
    if not is_existing:
        step += 1
        print_step(step, total_steps, "專案初始化")
        context = scaffold_project(context)

    # Step: GitHub CLI 設定
    step += 1
    print_step(step, total_steps, "GitHub CLI 設定（可選）")
    if ask_yes_no("要設定 GitHub CLI 嗎？（用於自動化 push / PR / repo 建立）"):
        context = setup_github_cli(context)
    else:
        print_info("略過。之後可執行 python setup.py --add-github")

    # Step: 雲端模型設定
    step += 1
    print_step(step, total_steps, "雲端模型設定（可選）")
    if ask_yes_no("要設定雲端模型 API 嗎？"):
        context = setup_cloud_models(context)
    else:
        print_info("略過。之後可執行 python setup.py --add-cloud-models")

    # Step: 本地模型設定
    step += 1
    print_step(step, total_steps, "本地模型 Ollama 設定（可選）")
    if ask_yes_no("要設定本地 Ollama 嗎？", default=False):
        context = setup_ollama(context)
    else:
        print_info("略過。之後可執行 python setup.py --add-ollama")

    # Step: Telegram Bot 設定
    step += 1
    print_step(step, total_steps, "Telegram Bot 設定（可選）")
    if ask_yes_no("要設定 Telegram Bot 嗎？"):
        context = setup_telegram(context)
    else:
        print_info("略過。之後可執行 python setup.py --add-telegram")

    # Step: 驗證
    step += 1
    print_step(step, total_steps, "驗證安裝結果")
    run_verification(context)

    # 完成
    _print_completion(context)


def _check_claude_auth() -> None:
    """檢查 Claude CLI 是否已登入。"""
    import subprocess

    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print_ok(f"Claude CLI: {result.stdout.strip()}")
        else:
            print_warn("Claude CLI 已安裝但可能未登入")
            print_info("請在安裝完成後執行：claude login")
    except FileNotFoundError:
        print_fail("Claude CLI 未安裝")
        print_info("安裝指令：npm install -g @anthropic-ai/claude-code")
    except Exception as e:
        print_warn(f"無法確認 Claude CLI 狀態：{e}")


def _print_completion(context: Dict) -> None:
    """顯示安裝完成摘要。"""
    project_path = context.get("project_path", ".")

    print(f"""
{GREEN}{BOLD}╔═══════════════════════════════════════════╗
║   🎉 安裝完成！                          ║
╚═══════════════════════════════════════════╝{RESET}

  📁 專案路徑：{project_path}
""")

    if context.get("cloud_providers"):
        providers = ", ".join(context["cloud_providers"])
        print(f"  ☁️  雲端模型：{providers}")

    if context.get("setup_ollama"):
        print(f"  🖥️  本地模型：Ollama 已設定")

    if context.get("setup_telegram"):
        print(f"  📱 Telegram Bot：已設定")

    print(f"""
  {CYAN}下一步：{RESET}
  1. cd {project_path}
  2. pip install -r requirements.txt
  3. claude  （直接使用 Claude CLI）
""")

    if context.get("setup_telegram"):
        print(f"  或啟動 Telegram Bot：")
        print(f"  python -m claude_code_telegram\n")
