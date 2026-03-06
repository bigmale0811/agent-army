# -*- coding: utf-8 -*-
"""
DEV-14: Telegram Bot 入口模組。

提供 Singer Agent 的 Telegram Bot 介面：
- 授權閘門：只允許 ALLOWED_USER_IDS 內的使用者操作
- /start：歡迎訊息與使用說明
- /list：列出已儲存的專案
- MP3 音訊處理：接收音檔、排入佇列、啟動管線
- asyncio.Queue 任務排隊機制
- 進度回調：管線執行時回報步驟進度給使用者
- 全域錯誤處理：攔截例外並通知使用者
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import re
from typing import Any, Callable

from src.singer_agent import config
from src.singer_agent.project_store import ProjectStore

# 延遲匯入 python-telegram-bot，避免未安裝時模組載入失敗
# 測試環境透過 mock 注入
try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
except ImportError:  # pragma: no cover
    Update = None  # type: ignore[misc, assignment]
    Application = None  # type: ignore[misc, assignment]
    CommandHandler = None  # type: ignore[misc, assignment]
    MessageHandler = None  # type: ignore[misc, assignment]
    ContextTypes = None  # type: ignore[misc, assignment]
    filters = None  # type: ignore[misc, assignment]

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# asyncio.Queue：任務排隊機制
# ─────────────────────────────────────────────────

_job_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
"""
全域任務佇列。每個 job 是一個 dict，包含：
- chat_id: int — 回報進度的 Telegram chat ID
- file_path: str — 下載後的音訊檔案路徑
- file_name: str — 原始檔名
"""


# ─────────────────────────────────────────────────
# 授權閘門
# ─────────────────────────────────────────────────

def is_authorized(user_id: int) -> bool:
    """
    檢查使用者 ID 是否在允許清單中。

    空的 ALLOWED_USER_IDS 表示拒絕所有使用者（安全預設值）。

    Args:
        user_id: Telegram 使用者 ID

    Returns:
        True 表示已授權
    """
    return user_id in config.ALLOWED_USER_IDS


# ─────────────────────────────────────────────────
# 進度回調工廠
# ─────────────────────────────────────────────────

def make_progress_callback(
    bot: Any,
    chat_id: int,
) -> Callable[[int, str], None]:
    """
    建立 Pipeline 用的 progress_callback。

    Pipeline.run() 要求同步回調 (step: int, description: str) -> None，
    因此這裡使用 fire-and-forget 模式安排非同步 send_message。

    Args:
        bot: Telegram Bot 實例（有 send_message 方法）
        chat_id: 傳送進度訊息的 chat ID

    Returns:
        同步回調函式，符合 Pipeline.ProgressCallback 型別
    """
    def _callback(step: int, description: str) -> None:
        """同步回調，內部透過 asyncio 安排非同步發送。"""
        msg = f"📋 Step {step}/8: {description}"
        try:
            loop = asyncio.get_running_loop()
            # 在已有事件迴圈中安排 coroutine
            loop.create_task(bot.send_message(chat_id=chat_id, text=msg))
        except RuntimeError:
            # 沒有執行中的事件迴圈（通常僅發生在測試環境），跳過通知
            _logger.debug("無執行中事件迴圈，跳過進度通知：step=%d", step)

    return _callback


# ─────────────────────────────────────────────────
# /start 指令
# ─────────────────────────────────────────────────

async def start_command(update: Any, context: Any) -> None:
    """
    處理 /start 指令。

    已授權：回覆歡迎訊息與使用說明。
    未授權：回覆拒絕訊息。
    """
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if not is_authorized(user_id):
        await update.message.reply_text(
            f"⛔ 未授權：您的 ID ({user_id}) 不在允許清單中。"
        )
        return

    welcome = (
        f"🎤 歡迎 {user_name}！我是 Singer Agent Bot。\n\n"
        f"📤 傳送 MP3 音訊檔案給我，我會自動產出 MV。\n"
        f"📋 /list — 查看已完成的專案\n"
        f"❓ /help — 查看使用說明"
    )
    await update.message.reply_text(welcome)


# ─────────────────────────────────────────────────
# /list 指令
# ─────────────────────────────────────────────────

async def list_command(update: Any, context: Any) -> None:
    """
    處理 /list 指令：列出所有已儲存專案。

    已授權：顯示專案清單（ID、狀態、建立時間）。
    未授權：回覆拒絕訊息。
    """
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            f"⛔ 未授權：您的 ID ({user_id}) 不在允許清單中。"
        )
        return

    store = ProjectStore()
    projects = store.list_projects()

    if not projects:
        await update.message.reply_text("📭 目前沒有任何專案。")
        return

    # 組合專案清單訊息
    lines = ["📋 專案列表：\n"]
    for p in projects:
        # 狀態 emoji
        status_icon = {
            "completed": "✅",
            "failed": "❌",
            "running": "🔄",
        }.get(p.status, "❓")

        lines.append(
            f"{status_icon} {p.project_id}\n"
            f"   音訊：{p.source_audio}\n"
            f"   狀態：{p.status}\n"
            f"   建立：{p.created_at}\n"
        )

    await update.message.reply_text("\n".join(lines))


# ─────────────────────────────────────────────────
# MP3 音訊處理
# ─────────────────────────────────────────────────

async def audio_handler(update: Any, context: Any) -> None:
    """
    處理使用者傳送的音訊檔案。

    流程：
    1. 授權檢查
    2. 確認有 audio 附件
    3. 下載到 INBOX_DIR
    4. 放入 _job_queue 排隊
    5. 回覆確認訊息
    """
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(
            f"⛔ 未授權：您的 ID ({user_id}) 不在允許清單中。"
        )
        return

    # 取得音訊物件（可能是 audio 或 document）
    audio = getattr(update.message, "audio", None)
    if audio is None:
        await update.message.reply_text(
            "❌ 請傳送 MP3 音訊檔案。"
        )
        return

    file_id = audio.file_id

    # 【安全】檔名消毒：去除目錄部分、只允許安全字元，防止路徑穿越攻擊
    raw_name = Path(audio.file_name or "unknown.mp3").name
    safe_name = re.sub(r"[^\w\-.]", "_", raw_name)

    # 【安全】副檔名白名單：僅接受 MP3
    if Path(safe_name).suffix.lower() not in {".mp3"}:
        await update.message.reply_text("❌ 僅接受 MP3 格式音訊檔案。")
        return

    # 下載檔案到 inbox
    inbox_dir = config.INBOX_DIR
    inbox_dir.mkdir(parents=True, exist_ok=True)
    dest_path = (inbox_dir / safe_name).resolve()

    # 【安全】確保解析後路徑仍在 inbox_dir 內
    if not str(dest_path).startswith(str(inbox_dir.resolve())):
        await update.message.reply_text("❌ 非法檔名，拒絕處理。")
        return

    try:
        tg_file = await context.bot.get_file(file_id)
        await tg_file.download_to_drive(str(dest_path))
    except Exception as exc:
        # 記錄內部錯誤細節，但不洩漏給使用者
        _logger.error("下載音訊失敗（user_id=%d, file_id=%s）：%s", user_id, file_id, exc)
        await update.message.reply_text("❌ 下載檔案失敗，請稍後再試。")
        return

    # 放入任務佇列
    job = {
        "chat_id": update.effective_chat.id,
        "file_path": str(dest_path),
        "file_name": safe_name,
    }
    await _job_queue.put(job)

    await update.message.reply_text(
        f"✅ 已收到 {safe_name}，已排入處理佇列（目前排隊數：{_job_queue.qsize()}）"
    )


# ─────────────────────────────────────────────────
# 全域錯誤處理
# ─────────────────────────────────────────────────

async def error_handler(update: Any, context: Any) -> None:
    """
    全域錯誤處理：攔截未被捕獲的例外。

    記錄錯誤日誌，嘗試通知使用者（若 update 可用）。
    不會拋出例外，確保 Bot 持續運行。
    """
    _logger.error("Telegram Bot 錯誤：%s", context.error)

    if update is None:
        # 無法通知使用者（例如 webhook 層級錯誤）
        _logger.warning("update 為 None，無法通知使用者")
        return

    try:
        await update.message.reply_text(
            "❌ 發生錯誤，請稍後再試。如果問題持續，請聯繫管理員。"
        )
    except Exception as exc:
        _logger.error("錯誤處理中通知使用者失敗：%s", exc)


# ─────────────────────────────────────────────────
# Application 工廠
# ─────────────────────────────────────────────────

def create_application() -> Any:
    """
    建立並設定 Telegram Bot Application。

    註冊所有 handler：
    - /start → start_command
    - /list → list_command
    - audio → audio_handler
    - error → error_handler

    Returns:
        已設定的 Application 實例

    Raises:
        ValueError: TELEGRAM_BOT_TOKEN 為空
    """
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN 未設定。"
            "請在環境變數或 .env 檔案中設定 TELEGRAM_BOT_TOKEN。"
        )

    app = Application.builder().token(token).build()

    # 註冊指令處理器
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("list", list_command))

    # 註冊音訊處理器（接受 audio 類型的訊息）
    app.add_handler(MessageHandler(filters.AUDIO, audio_handler))

    # 註冊全域錯誤處理器
    app.add_error_handler(error_handler)

    _logger.info("Telegram Bot Application 已建立")
    return app
