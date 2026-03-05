# -*- coding: utf-8 -*-
"""Singer Agent — Telegram Bot 互動模式

透過 Telegram 傳送 MP3 → 自動觸發 MV 生成流水線。

操作方式：
    1. 傳送 MP3/音檔，caption 格式：歌名 / 歌手 / 情緒(選填)
    2. Bot 自動分析風格、生成文案、合成影片
    3. 完成後回傳結果

啟動方式：
    python -m src.singer_agent --bot
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import (
    SINGER_BOT_TOKEN,
    SINGER_CHAT_ID,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    INBOX_DIR,
    CHARACTER_IMAGE,
    SUPPORTED_AUDIO_FORMATS,
)
from .storage import list_projects

logger = logging.getLogger(__name__)

# Telegram 單則訊息最大字元數
_MAX_MESSAGE_LENGTH = 4096


def _split_message(text: str, max_length: int = _MAX_MESSAGE_LENGTH) -> list[str]:
    """將過長訊息分段"""
    if len(text) <= max_length:
        return [text]
    segments: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > max_length:
            if current:
                segments.append(current.rstrip())
            current = line
        else:
            current += line
    if current:
        segments.append(current.rstrip())
    return segments if segments else [text[:max_length]]


class SingerBotHandler:
    """Singer Agent Telegram Bot

    指令：
        /start, /help  — 歡迎訊息與操作說明
        /list          — 列出所有 MV 專案
        /status <id>   — 查看專案狀態

    訊息處理：
        音檔（MP3/WAV/FLAC/M4A）— 儲存並觸發分析流程
        圖片                     — 儲存為角色圖片
    """

    # Telegram 指令選單
    BOT_COMMANDS = [
        BotCommand("start", "歡迎訊息與操作說明"),
        BotCommand("status", "查看最新專案即時進度"),
        BotCommand("list", "列出所有 MV 專案"),
        BotCommand("help", "顯示使用說明"),
    ]

    # 流水線階段定義（v0.3 擴充為 8 步）
    _PIPELINE_STAGES = [
        ("pending", "⏳", "等待處理"),
        ("researching", "🔍", "研究歌曲風格"),
        ("classifying", "📋", "建立風格規格"),
        ("writing_copy", "✍️", "生成 YouTube 文案"),
        ("generating_bg", "🎨", "AI 生成背景圖"),
        ("compositing", "🖼️", "角色去背合成"),
        ("prechecking", "🔎", "預檢驗證"),
        ("composing", "🎬", "合成動畫影片"),
        ("completed", "✅", "完成"),
    ]

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self._bot_token = bot_token or SINGER_BOT_TOKEN or TELEGRAM_BOT_TOKEN
        self._chat_id = str(
            chat_id or SINGER_CHAT_ID or TELEGRAM_CHAT_ID
        ).strip()

        if not self._bot_token:
            raise ValueError(
                "SINGER_BOT_TOKEN 或 TELEGRAM_BOT_TOKEN 未設定，請檢查 .env"
            )
        if not self._chat_id:
            raise ValueError(
                "SINGER_CHAT_ID 或 TELEGRAM_CHAT_ID 未設定，請檢查 .env"
            )

    def _is_authorized(self, update: Update) -> bool:
        """驗證發送者是否為授權的 chat_id"""
        if not update.effective_chat:
            return False
        return str(update.effective_chat.id) == self._chat_id

    # =========================================================
    # /start, /help
    # =========================================================

    async def cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """/start — 顯示歡迎訊息與操作說明"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        # 檢查角色圖片狀態
        char_status = "✅ 已設定" if CHARACTER_IMAGE.exists() else "❌ 未設定"

        help_text = (
            "🎤 Singer Agent — 虛擬歌手 MV 自動化\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📌 *使用方式*\n\n"
            "*傳送音檔：*\n"
            "直接傳一個 MP3/WAV 檔案，在「說明文字」打上：\n"
            "`歌名 / 歌手 / 情緒`\n\n"
            "範例：\n"
            "• `告白氣球 / 周杰倫 / romantic`\n"
            "• `告白氣球 / 周杰倫`（情緒可省略）\n"
            "• `告白氣球`（只寫歌名也行）\n\n"
            "*傳送圖片：*\n"
            "傳一張圖片 → 自動設為虛擬角色頭像\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 *指令*\n"
            "/list — 列出所有 MV 專案\n"
            "/help — 顯示此說明\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🖼️ 角色圖片：{char_status}\n"
            "🎙️ 唱歌模式：SadTalker 對嘴動畫 + 身體搖擺\n"
            "🤖 Agent Army ｜ Singer Agent v0.3"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    # =========================================================
    # /status — 查看最新專案進度
    # =========================================================

    async def cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """/status — 查看最新專案的即時進度"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        projects = list_projects()
        if not projects:
            await update.message.reply_text("目前沒有任何 MV 專案。")
            return

        # 取最新的專案
        project = projects[0]
        title = project.metadata.title if project.metadata else "未知"
        artist = project.metadata.artist if project.metadata else ""
        label = f"{title} - {artist}" if artist else title

        # 產生進度條
        progress_lines = self._build_progress_bar(project.status)

        lines = [
            f"📊 專案進度",
            f"━━━━━━━━━━━━━",
            f"🎵 {label}",
            f"🆔 {project.project_id}",
            "",
            *progress_lines,
        ]

        # 如果失敗，顯示錯誤
        if project.status == "failed" and project.error_message:
            lines.extend(["", f"❌ 錯誤：{project.error_message[:200]}"])

        # 如果完成，顯示摘要
        if project.status == "completed":
            if project.song_spec:
                lines.extend([
                    "",
                    f"🎸 風格：{project.song_spec.genre}",
                    f"💫 情緒：{project.song_spec.mood}",
                ])
            if project.youtube_title:
                lines.append(f"📌 {project.youtube_title}")
            if project.final_video:
                lines.append("🎬 影片已生成")

        # 計算時間
        if project.created_at:
            try:
                created = datetime.fromisoformat(project.created_at)
                elapsed = datetime.now() - created
                minutes = int(elapsed.total_seconds() // 60)
                seconds = int(elapsed.total_seconds() % 60)
                lines.append(f"\n⏱️ 已經過：{minutes}分{seconds}秒")
            except ValueError:
                pass

        await update.message.reply_text("\n".join(lines))

    @classmethod
    def _build_progress_bar(cls, current_status: str) -> list[str]:
        """產生視覺化進度條

        Args:
            current_status: 目前的專案狀態

        Returns:
            進度條文字列表
        """
        lines = []
        reached = False
        is_failed = current_status == "failed"

        for status_key, icon, label in cls._PIPELINE_STAGES:
            if status_key == current_status:
                # 目前正在這一步
                lines.append(f"  ▶️ {icon} {label} ← 進行中")
                reached = True
            elif not reached:
                # 已完成的步驟
                lines.append(f"  ✅ {icon} {label}")
            else:
                # 尚未到達的步驟
                lines.append(f"  ⬜ {icon} {label}")

        # 失敗的特殊處理：找到最後完成的步驟後標記失敗
        if is_failed:
            lines = []
            # 從頭找到上一個完成的階段
            stage_keys = [s[0] for s in cls._PIPELINE_STAGES]
            for status_key, icon, label in cls._PIPELINE_STAGES:
                lines.append(f"  ✅ {icon} {label}")
            # 最後一行改成失敗
            if lines:
                lines[-1] = f"  ❌ 💥 失敗"

        return lines

    # =========================================================
    # /list — 列出專案
    # =========================================================

    async def cmd_list(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """/list — 列出所有 MV 專案"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        projects = list_projects()
        if not projects:
            await update.message.reply_text("目前沒有任何 MV 專案。")
            return

        lines = [
            f"🎤 MV 專案列表（共 {len(projects)} 個）",
            "━━━━━━━━━━━━━",
        ]
        for p in projects[:20]:  # 最多顯示 20 個
            status_icon = {
                "completed": "✅", "failed": "❌", "pending": "⏳",
            }.get(p.status, "🔄")
            title = p.metadata.title if p.metadata else "未知"
            artist = p.metadata.artist if p.metadata else ""
            label = f"{title} - {artist}" if artist else title
            lines.append(f"{status_icon} {label} — {p.status}")
            if p.status == "completed" and p.final_video:
                lines.append(f"   🎬 有影片")

        message = "\n".join(lines)
        for segment in _split_message(message):
            await update.message.reply_text(segment)

    # =========================================================
    # 接收音檔 → 觸發流水線
    # =========================================================

    async def handle_audio(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """接收音檔（MP3/WAV/FLAC/M4A），儲存並觸發分析"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        # 取得檔案資訊（音檔可能在 audio 或 document 裡）
        audio = update.message.audio or update.message.document
        if not audio:
            return

        # 檢查檔案格式
        filename = audio.file_name or "unknown.mp3"
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_AUDIO_FORMATS:
            await update.message.reply_text(
                f"不支援的格式：{ext}\n"
                f"支援：{', '.join(SUPPORTED_AUDIO_FORMATS)}"
            )
            return

        # 解析 caption（歌名 / 歌手 / 情緒）
        caption = update.message.caption or ""
        title, artist, mood = _parse_caption(caption, filename)

        await update.message.reply_text(
            f"🎵 收到音檔！\n"
            f"━━━━━━━━━━━━━\n"
            f"📄 檔案：{filename}\n"
            f"🎵 歌名：{title}\n"
            f"🎤 歌手：{artist or '未知'}\n"
            f"💫 情緒：{mood or '自動判斷'}\n\n"
            f"⏳ 下載中..."
        )

        # 下載檔案
        try:
            file = await audio.get_file()
            save_path = INBOX_DIR / filename
            await file.download_to_drive(str(save_path))
            logger.info("音檔已儲存: %s", save_path)
        except Exception as e:
            logger.error("下載音檔失敗: %s", e)
            await update.message.reply_text(f"❌ 下載失敗：{e}")
            return

        await update.message.reply_text(
            f"✅ 音檔已儲存\n"
            f"🔍 開始分析歌曲風格...\n\n"
            f"⏱️ 預計需要 1-2 分鐘"
        )

        # 在背景執行流水線
        asyncio.create_task(
            self._run_pipeline_task(update, str(save_path), title, artist, mood)
        )

    async def _send_progress(
        self, update: Update, step: int, total: int, icon: str, msg: str
    ) -> None:
        """發送流水線進度訊息到 Telegram"""
        bar_filled = "█" * step
        bar_empty = "░" * (total - step)
        pct = int(step / total * 100)
        await update.message.reply_text(
            f"[{step}/{total}] {bar_filled}{bar_empty} {pct}%\n"
            f"{icon} {msg}"
        )

    async def _run_pipeline_task(
        self,
        update: Update,
        audio_path: str,
        title: str,
        artist: str,
        mood: str,
    ) -> None:
        """背景執行 Singer Agent 流水線，每步推送進度到 Telegram"""
        start_time = datetime.now()
        total_steps = 7  # 研究、文案、背景圖、合成角色、預檢、影片合成、完成
        has_character = CHARACTER_IMAGE.exists()

        try:
            from .runner import (
                _generate_project_id, _run_pipeline,
            )
            from .models import MVProject, ProjectStatus, SongMetadata

            # Step 1: 研究歌曲風格
            await self._send_progress(
                update, 1, total_steps, "🔍",
                f"研究「{title}」的風格資訊中...\n⏱️ 約需 30-60 秒"
            )

            await _run_pipeline(
                title=title,
                artist=artist,
                audio_path=audio_path,
                mood_hint=mood,
                dry_run=not has_character,
            )

            # 讀取最新的專案結果
            projects = list_projects()
            if not projects:
                await update.message.reply_text("⚠️ 流程完成但找不到專案紀錄")
                return

            project = projects[0]  # 最新的專案
            elapsed = datetime.now() - start_time

            # 根據專案狀態判斷跑到哪一步失敗
            if project.status == "failed":
                await update.message.reply_text(
                    f"❌ 處理失敗\n"
                    f"━━━━━━━━━━━━━\n"
                    f"錯誤：{project.error_message}\n"
                    f"⏱️ 已執行：{int(elapsed.total_seconds())}秒\n\n"
                    f"💡 輸入 /status 查看詳細狀態"
                )
                return

            # 完成！發送結果摘要
            await self._send_progress(
                update, total_steps, total_steps, "✅",
                "全部完成！"
            )

            # 組合結果訊息
            lines = [
                "🎉 分析完成！",
                "━━━━━━━━━━━━━",
            ]

            if project.song_spec:
                spec = project.song_spec
                lines.extend([
                    f"🎵 {spec.title} - {spec.artist}",
                    f"🎸 風格：{spec.genre}",
                    f"💫 情緒：{spec.mood}",
                    f"🏞️ 場景：{spec.scene_description}",
                    "",
                ])

            if project.youtube_title:
                lines.extend([
                    "✍️ YouTube 文案",
                    f"📌 {project.youtube_title}",
                    f"📝 {project.youtube_description[:200]}",
                    f"🏷️ {', '.join(project.youtube_tags[:5])}",
                    "",
                ])

            if project.final_video and Path(project.final_video).exists():
                lines.append("🎬 影片已生成！傳送中...")
            elif not has_character:
                lines.append(
                    "🖼️ 尚未設定角色圖片，請傳一張圖片給我，"
                    "下次就能自動合成影片！"
                )

            minutes = int(elapsed.total_seconds() // 60)
            seconds = int(elapsed.total_seconds() % 60)
            lines.append(f"\n⏱️ 耗時：{minutes}分{seconds}秒")

            result_msg = "\n".join(lines)
            for segment in _split_message(result_msg):
                await update.message.reply_text(segment)

            # 如果有影片，發送影片
            if project.final_video and Path(project.final_video).exists():
                try:
                    with open(project.final_video, "rb") as video_file:
                        await update.message.reply_video(
                            video=video_file,
                            caption=f"🎤 {title} - {artist}",
                        )
                except Exception as e:
                    logger.error("發送影片失敗: %s", e)
                    await update.message.reply_text(
                        f"⚠️ 影片發送失敗：{e}\n"
                        f"📂 檔案位置：{project.final_video}"
                    )

        except Exception as e:
            elapsed = datetime.now() - start_time
            logger.exception("流水線失敗: %s", e)
            await update.message.reply_text(
                f"❌ 處理失敗\n"
                f"━━━━━━━━━━━━━\n"
                f"錯誤：{e}\n"
                f"⏱️ 已執行：{int(elapsed.total_seconds())}秒\n\n"
                f"💡 輸入 /status 查看詳細狀態"
            )

    # =========================================================
    # 接收圖片 → 設為角色圖片
    # =========================================================

    async def handle_photo(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """接收圖片，儲存為虛擬角色頭像"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        if not update.message.photo:
            return

        # 取最高解析度的圖片
        photo = update.message.photo[-1]

        await update.message.reply_text("🖼️ 收到圖片，設定為角色頭像中...")

        try:
            file = await photo.get_file()

            # 確保目錄存在
            CHARACTER_IMAGE.parent.mkdir(parents=True, exist_ok=True)

            # 備份舊圖片
            if CHARACTER_IMAGE.exists():
                backup = CHARACTER_IMAGE.with_suffix(".bak.png")
                CHARACTER_IMAGE.rename(backup)
                logger.info("舊角色圖片已備份: %s", backup)

            await file.download_to_drive(str(CHARACTER_IMAGE))
            logger.info("角色圖片已更新: %s", CHARACTER_IMAGE)

            await update.message.reply_text(
                "✅ 角色圖片已設定！\n\n"
                "現在傳 MP3 給我就能自動合成影片了 🎬"
            )

        except Exception as e:
            logger.error("儲存角色圖片失敗: %s", e)
            await update.message.reply_text(f"❌ 儲存失敗：{e}")

    # =========================================================
    # Bot 啟動
    # =========================================================

    @staticmethod
    async def _post_init(application: Application) -> None:
        """Bot 啟動後自動註冊指令選單"""
        await application.bot.set_my_commands(SingerBotHandler.BOT_COMMANDS)
        logger.info(
            "已註冊 %d 個指令到 Telegram 選單",
            len(SingerBotHandler.BOT_COMMANDS),
        )

    def run(self) -> None:
        """啟動 Bot（長駐 polling 模式）"""
        logger.info("建立 Singer Agent Telegram Bot...")

        app = (
            Application.builder()
            .token(self._bot_token)
            .post_init(self._post_init)
            .build()
        )

        # 註冊指令
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_start))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("list", self.cmd_list))

        # 註冊訊息處理器（音檔 + 圖片）
        app.add_handler(MessageHandler(
            filters.AUDIO | filters.Document.ALL, self.handle_audio,
        ))
        app.add_handler(MessageHandler(
            filters.PHOTO, self.handle_photo,
        ))

        logger.info(
            "Singer Bot 啟動，監聽 chat_id=%s。按 Ctrl+C 停止。",
            self._chat_id,
        )

        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )


# =========================================================
# 工具函式
# =========================================================

def _parse_caption(caption: str, filename: str) -> tuple[str, str, str]:
    """從 caption 解析歌名、歌手、情緒

    支援格式：
        "歌名 / 歌手 / 情緒"
        "歌名 / 歌手"
        "歌名"
        ""（空白，從檔名推斷）

    Args:
        caption: Telegram 訊息的 caption
        filename: 檔案名稱（備用）

    Returns:
        (title, artist, mood) 三元組
    """
    if not caption.strip():
        # 從檔名推斷歌名（去掉副檔名）
        title = Path(filename).stem
        # 嘗試解析 "歌手 - 歌名" 格式的檔名
        if " - " in title:
            parts = title.split(" - ", 1)
            return parts[1].strip(), parts[0].strip(), ""
        return title, "", ""

    # 用 / 分隔
    parts = [p.strip() for p in caption.split("/")]

    title = parts[0] if len(parts) > 0 else Path(filename).stem
    artist = parts[1] if len(parts) > 1 else ""
    mood = parts[2] if len(parts) > 2 else ""

    return title, artist, mood
