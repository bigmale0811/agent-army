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
from src.singer_agent.models import PipelineRequest
from src.singer_agent.pipeline import Pipeline
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
# Worker：佇列消費者 + 管線執行 + 影片回傳
# ─────────────────────────────────────────────────

def _parse_title_artist(file_name: str) -> tuple[str, str]:
    """
    從檔名推斷歌曲標題與歌手。

    嘗試以底線分割，取前兩段作為 title / artist。
    無法解析時使用檔名作為 title，artist 設為 "未知"。

    Args:
        file_name: 原始檔名（已消毒）

    Returns:
        (title, artist) 元組
    """
    stem = Path(file_name).stem
    parts = stem.split("_", maxsplit=1)
    if len(parts) >= 2:
        return parts[0], parts[1]
    return stem, "未知"


def _safe_filename(title: str, artist: str) -> str:
    """
    產生安全的 Telegram 檔名（避免編碼問題導致 send_document 失敗）。

    移除 Telegram API 不支援的控制字元與特殊符號，
    確保檔名只包含可安全傳輸的字元。

    Args:
        title: 歌曲標題
        artist: 歌手名

    Returns:
        安全的 mp4 檔名
    """
    import re
    # 移除控制字元與 Telegram 不支援的特殊符號
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title).strip()
    safe_artist = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', artist).strip()
    # 如果清理後為空，使用 fallback
    safe_title = safe_title or "MV"
    safe_artist = safe_artist or "Unknown"
    # 限制長度（Telegram 檔名限制約 64 字元）
    max_len = 50
    if len(safe_title) + len(safe_artist) > max_len:
        safe_title = safe_title[:30]
        safe_artist = safe_artist[:20]
    return f"{safe_title}_{safe_artist}.mp4"


async def worker(bot: Any) -> None:
    """
    非同步 worker：持續從 _job_queue 取出任務並執行管線。

    流程：
    1. 從佇列取出 job
    2. 通知使用者開始處理
    3. 在執行緒池中同步執行 Pipeline.run()
    4. 成功時傳送影片檔給使用者
    5. 失敗時通知使用者錯誤訊息

    此 coroutine 設計為永久迴圈，應在 Application 啟動時
    透過 asyncio.create_task() 啟動。
    """
    _logger.info("Worker 啟動，等待任務...")

    while True:
        job = await _job_queue.get()
        chat_id: int = job["chat_id"]
        file_path: str = job["file_path"]
        file_name: str = job["file_name"]

        _logger.info("Worker 取得任務：%s（chat_id=%d）", file_name, chat_id)

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"🎬 開始處理 {file_name}，8 個步驟約需 20-30 分鐘（影片渲染較耗時）...",
            )

            title, artist = _parse_title_artist(file_name)

            request = PipelineRequest(
                audio_path=Path(file_path),
                title=title,
                artist=artist,
            )

            progress_cb = make_progress_callback(bot, chat_id)
            pipeline = Pipeline(
                character_image=config.CHARACTER_IMAGE,
                progress_callback=progress_cb,
                dry_run=False,
            )

            # 在執行緒池中執行同步管線，避免阻塞事件迴圈
            loop = asyncio.get_running_loop()
            state = await loop.run_in_executor(None, pipeline.run, request)

            if state.status == "completed" and state.final_video:
                video_path = Path(state.final_video)
                if video_path.exists() and video_path.stat().st_size > 200:
                    # 使用安全檔名，避免編碼問題導致 send_document 失敗
                    safe_name = _safe_filename(title, artist)
                    try:
                        with open(str(video_path), "rb") as vf:
                            await bot.send_document(
                                chat_id=chat_id,
                                document=vf,
                                filename=safe_name,
                                caption=(
                                    f"✅ MV 製作完成！\n"
                                    f"🎵 {title} — {artist}\n"
                                    f"📋 專案 ID：{state.project_id}"
                                ),
                            )
                    except Exception as send_exc:
                        # 影片傳送失敗時，用最簡檔名重試一次
                        _logger.warning(
                            "send_document 失敗（%s），用 fallback 檔名重試",
                            send_exc,
                        )
                        with open(str(video_path), "rb") as vf:
                            await bot.send_document(
                                chat_id=chat_id,
                                document=vf,
                                filename=f"{state.project_id}.mp4",
                                caption=f"✅ MV 製作完成！專案 ID：{state.project_id}",
                            )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"⚠️ 管線完成但影片檔案異常\n"
                            f"專案 ID：{state.project_id}"
                        ),
                    )
            else:
                error_msg = state.error_message or "未知錯誤"
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ MV 製作失敗\n"
                        f"原因：{error_msg}\n"
                        f"專案 ID：{state.project_id}"
                    ),
                )

        except Exception as exc:
            _logger.error("Worker 處理任務失敗：%s", exc)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ 處理失敗：發生未預期錯誤，請稍後再試。",
                )
            except Exception as send_exc:
                _logger.error("Worker 通知失敗：%s", send_exc)
        finally:
            _job_queue.task_done()


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

    # 在 Application 啟動後自動啟動 Worker
    async def _post_init(application: Any) -> None:
        """Application 初始化完成後啟動 worker。"""
        asyncio.create_task(worker(application.bot))
        _logger.info("Worker coroutine 已啟動")

    app.post_init = _post_init

    _logger.info("Telegram Bot Application 已建立")
    return app
