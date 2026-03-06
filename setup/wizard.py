"""Setup Wizard 主流程控制。

負責 Step 4~8 的設定流程（在已有 agent-army 專案的情況下）。
Step 1~3（環境檢查、GitHub CLI、下載）由 install.py 處理。

Step 4: 專案初始化 (pip install + 結構驗證)
Step 5: 雲端模型設定
Step 6: 本地模型 Ollama
Step 7: Telegram Bot 設定
Step 8: 驗證
"""

import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .cloud_models import setup_cloud_models
from .download import install_dependencies, verify_project_structure
from .ollama import setup_ollama
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

TOTAL_STEPS = 5  # Step 4~8 共 5 步


def _enable_ansi_windows() -> None:
    """在 Windows 上啟用 ANSI 顏色支援。"""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def print_banner() -> None:
    """顯示歡迎橫幅。"""
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════╗
║   🤖 Agent Army Setup Wizard v2.0       ║
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
    """執行 Setup Wizard（Step 4~8）。

    此函數在已有 agent-army 專案的目錄內執行。
    Step 1~3 由 install.py 負責。

    Step 4: 專案初始化
    Step 5: 雲端模型設定
    Step 6: 本地模型 Ollama
    Step 7: Telegram Bot 設定
    Step 8: 驗證
    """
    _enable_ansi_windows()
    print_banner()

    # 確定專案路徑
    if project_path is None:
        project_path = Path.cwd()

    if not _is_existing_project(project_path):
        print_fail(f"{project_path} 不是有效的 agent-army 專案")
        print_info("請先執行 install.py 來下載並初始化專案")
        print_info("或確認你在正確的目錄中執行")
        sys.exit(1)

    print_ok(f"專案路徑：{project_path}")

    context: Dict = {
        "project_path": project_path,
        "project_name": project_path.name,
        "cloud_providers": [],
        "setup_ollama": False,
        "setup_telegram": False,
        "setup_github": False,
        "has_ollama": bool(shutil.which("ollama")),
    }

    # ── Step 4: 專案初始化 ──
    print_step(1, TOTAL_STEPS, "專案初始化")
    _run_initialization(context)

    # ── Step 5: 雲端模型設定 ──
    print_step(2, TOTAL_STEPS, "雲端模型設定（可選）")
    if ask_yes_no("要設定雲端模型 API 嗎？"):
        context = setup_cloud_models(context)
    else:
        print_info("略過。之後可執行 python setup.py --add-cloud-models")

    # ── Step 6: 本地模型 Ollama ──
    print_step(3, TOTAL_STEPS, "本地模型 Ollama（可選）")
    if context.get("has_ollama"):
        print_ok("偵測到 Ollama 已安裝")
        if ask_yes_no("要設定 Ollama 模型嗎？"):
            context = setup_ollama(context)
        else:
            print_info("略過。之後可執行 python setup.py --add-ollama")
    else:
        print_info("Ollama 未安裝，跳過此步驟")
        print_info("如需安裝：https://ollama.com/download")

    # ── Step 7: Telegram Bot 設定 ──
    print_step(4, TOTAL_STEPS, "Telegram Bot 設定（可選）")
    if ask_yes_no("要設定 Telegram Bot 嗎？"):
        context = setup_telegram(context)
    else:
        print_info("略過。之後可執行 python setup.py --add-telegram")

    # ── Step 8: 驗證 ──
    print_step(5, TOTAL_STEPS, "驗證安裝結果")
    run_verification(context)

    # 完成
    _print_completion(context)


def _run_initialization(context: Dict) -> None:
    """執行專案初始化。

    確認依賴已安裝、結構完整、記憶系統就緒。
    """
    project_path = Path(context["project_path"])

    # 安裝依賴
    print_info("檢查 Python 依賴...")
    if (project_path / "requirements.txt").exists():
        if install_dependencies(project_path):
            print_ok("Python 依賴已安裝")
        else:
            print_warn("依賴安裝失敗，稍後可手動執行 pip install -r requirements.txt")
    else:
        print_info("未找到 requirements.txt，跳過")

    # 驗證結構
    missing = verify_project_structure(project_path)
    if not missing:
        print_ok("專案結構完整")
    else:
        print_warn(f"缺少 {len(missing)} 個項目：{', '.join(missing)}")

    # 記憶系統
    _ensure_memory_system(project_path)

    # .env
    if (project_path / ".env").exists():
        print_ok(".env 已存在")
    else:
        print_info(".env 尚未建立（雲端模型設定步驟會自動建立）")


def _ensure_memory_system(project_path: Path) -> None:
    """確保記憶系統已初始化。"""
    memory_dir = project_path / "data" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "sessions").mkdir(exist_ok=True)

    active_context = memory_dir / "active_context.md"
    if not active_context.exists():
        active_context.write_text(
            "# 🧠 Active Context\n更新：（尚未開始）\n\n"
            "## 目前進行中\n- （無）\n\n"
            "## 最近完成\n- （無）\n\n"
            "## 下一步\n- （無）\n",
            encoding="utf-8",
        )
        print_ok("記憶系統已初始化")
    else:
        print_ok("記憶系統已存在")

    decisions = memory_dir / "decisions.md"
    if not decisions.exists():
        decisions.write_text(
            "# 📋 重大決策紀錄\n\n（尚無紀錄）\n",
            encoding="utf-8",
        )


def _print_completion(context: Dict) -> None:
    """顯示安裝完成摘要。"""
    project_path = context.get("project_path", ".")

    print(f"""
{GREEN}{BOLD}╔═══════════════════════════════════════════╗
║   🎉 安裝完成！                          ║
╚═══════════════════════════════════════════╝{RESET}

  📁 專案路徑：{project_path}
""")

    if context.get("setup_github"):
        print(f"  🔗 GitHub CLI：已認證")

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
  2. claude  （開始使用 Claude CLI）
""")

    if context.get("setup_telegram"):
        tg_path = context.get("telegram_path", "")
        print(f"  或啟動 Telegram Bot：")
        print(f"  cd {tg_path}")
        print(f"  python -m claude_code_telegram\n")
