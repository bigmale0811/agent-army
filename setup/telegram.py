"""Step 6: Telegram Bot 設定（可選）。"""

import subprocess
import sys
from pathlib import Path
from typing import Dict


def setup_telegram(context: Dict) -> Dict:
    """互動式設定 Telegram Bot。"""
    from .wizard import ask_input, ask_yes_no, print_fail, print_info, print_ok, print_warn

    print_info("Telegram Bot 需要 claude-code-telegram 套件")
    print_info("GitHub：https://github.com/anthropics/claude-code-telegram")

    # 檢查 claude-code-telegram 是否已安裝
    telegram_path = _find_telegram_bot()

    if not telegram_path:
        print_warn("未偵測到 claude-code-telegram")
        if ask_yes_no("要現在 clone 嗎？"):
            telegram_path = _clone_telegram_bot(context)
            if not telegram_path:
                return context
        else:
            print_info("略過 Telegram Bot 設定")
            return context

    print_ok(f"找到 claude-code-telegram：{telegram_path}")

    # 取得 Bot Token
    print()
    print_info("步驟 1：在 Telegram 找 @BotFather")
    print_info("步驟 2：傳送 /newbot 建立新 Bot")
    print_info("步驟 3：複製 Bot Token")
    print()

    bot_token = ask_input("Telegram Bot Token")
    if not bot_token:
        print_warn("未輸入 Bot Token，略過")
        return context

    # 取得 User ID
    print()
    print_info("你的 Telegram User ID 用於授權")
    print_info("不知道？→ 傳訊息給 @userinfobot 取得")
    print()

    user_id = ask_input("你的 Telegram User ID")

    # 寫入 .env
    project_path = Path(context.get("project_path", "."))
    _write_telegram_env(
        telegram_path=telegram_path,
        bot_token=bot_token,
        user_id=user_id,
        approved_directory=str(project_path),
    )
    print_ok("Telegram Bot .env 已設定")

    # 安裝依賴
    if ask_yes_no("要安裝 Telegram Bot 依賴嗎？"):
        _install_telegram_deps(telegram_path)

    context["setup_telegram"] = True
    context["telegram_path"] = str(telegram_path)
    print_ok("Telegram Bot 設定完成")

    return context


def _find_telegram_bot() -> Path | None:
    """搜尋 claude-code-telegram 的安裝位置。"""
    common_paths = [
        Path("D:/Projects/claude-code-telegram"),
        Path.home() / "Projects" / "claude-code-telegram",
        Path.cwd().parent / "claude-code-telegram",
    ]
    for path in common_paths:
        if (path / "src").exists():
            return path
    return None


def _clone_telegram_bot(context: Dict) -> Path | None:
    """Clone claude-code-telegram。"""
    from .wizard import ask_input, print_fail, print_info, print_ok

    default_path = str(Path(context.get("project_path", ".")).parent / "claude-code-telegram")
    target = ask_input("clone 到哪裡", default=default_path)
    target_path = Path(target)

    print_info("正在 clone...")
    try:
        result = subprocess.run(
            [
                "git", "clone",
                "https://github.com/anthropics/claude-code-telegram.git",
                str(target_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print_ok("clone 完成")
            return target_path
        else:
            print_fail(f"clone 失敗：{result.stderr.strip()}")
            return None
    except Exception as e:
        print_fail(f"clone 失敗：{e}")
        return None


def _write_telegram_env(
    telegram_path: Path,
    bot_token: str,
    user_id: str,
    approved_directory: str,
) -> None:
    """寫入 Telegram Bot 的 .env 檔案。"""
    env_content = f"""# === Telegram Bot Config ===
TELEGRAM_BOT_TOKEN={bot_token}

# === Security ===
APPROVED_DIRECTORY={approved_directory.replace(chr(92), chr(92) + chr(92))}
ALLOWED_USERS={user_id}

# === Claude Settings ===
USE_SDK=true
CLAUDE_MAX_COST_PER_USER=50.0
CLAUDE_TIMEOUT_SECONDS=900
CLAUDE_MAX_TURNS=50
CLAUDE_ALLOWED_TOOLS=Read,Write,Edit,Bash,Glob,Grep,LS,Task,MultiEdit,WebFetch,TodoRead,TodoWrite,WebSearch

# === Rate Limiting ===
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW=60

# === Features ===
ENABLE_GIT_INTEGRATION=true
ENABLE_FILE_UPLOADS=true
ENABLE_QUICK_ACTIONS=true

# === Debug ===
DEBUG=false
LOG_LEVEL=INFO
"""
    env_path = telegram_path / ".env"
    env_path.write_text(env_content, encoding="utf-8")


def _install_telegram_deps(telegram_path: Path) -> None:
    """安裝 Telegram Bot 依賴。"""
    from .wizard import print_fail, print_info, print_ok

    print_info("正在安裝依賴...")
    req_file = telegram_path / "requirements.txt"
    if req_file.exists():
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                print_ok("依賴安裝完成")
            else:
                print_fail(f"安裝失敗：{result.stderr.strip()[:200]}")
        except Exception as e:
            print_fail(f"安裝失敗：{e}")
    else:
        print_fail(f"找不到 {req_file}")
