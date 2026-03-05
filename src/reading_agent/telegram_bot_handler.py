# -*- coding: utf-8 -*-
"""讀書 Agent v2 — Telegram Bot 互動模式處理器

使用 python-telegram-bot v20+ 的 async API 實作長駐 polling bot。
支援影片瀏覽、暢銷書查詢、頻道管理、YouTube 影片分析等功能。

啟動方式：
    from src.reading_agent.telegram_bot_handler import TelegramBotHandler
    handler = TelegramBotHandler()
    handler.run()
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .config import (
    BOOK_CATEGORIES,
    AI_CATEGORIES,
    CHANNELS_FILE,
    READING_BOT_TOKEN,
    READING_CHAT_ID,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    VIDEOS_DIR,
    load_channels,
)
from .models import Video

logger = logging.getLogger(__name__)

# Telegram 單則訊息最大字元數
_MAX_MESSAGE_LENGTH = 4096


def _split_message(text: str, max_length: int = _MAX_MESSAGE_LENGTH) -> list[str]:
    """將過長訊息分段，確保每段不超過 Telegram 上限

    以換行符號為切割點，盡量保持段落完整性。

    Args:
        text: 原始訊息文字
        max_length: 單段最大字元數

    Returns:
        分段後的訊息列表
    """
    if len(text) <= max_length:
        return [text]

    segments: list[str] = []
    current = ""

    for line in text.splitlines(keepends=True):
        # 若加入此行會超過上限，先將目前內容存入 segments
        if len(current) + len(line) > max_length:
            if current:
                segments.append(current.rstrip())
            current = line
        else:
            current += line

    if current:
        segments.append(current.rstrip())

    return segments if segments else [text[:max_length]]


async def _send_long_message(
    update: Update,
    text: str,
    parse_mode: Optional[str] = None,
) -> None:
    """發送可能超長的訊息，自動分段

    Args:
        update: Telegram Update 物件
        text: 要發送的訊息文字
        parse_mode: 解析模式（如 "HTML"、"Markdown"）
    """
    segments = _split_message(text)
    for segment in segments:
        await update.message.reply_text(
            segment,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )


class TelegramBotHandler:
    """Telegram Bot 互動模式處理器

    長駐 polling 模式，支援以下指令：
        /start、/help  — 歡迎訊息與指令說明
        /videos        — 列出最近蒐集的影片
        /books         — 列出暢銷書排行榜
        /channels      — 列出追蹤頻道
        /weekly        — 執行每週蒐集
        /ai            — 執行 AI Weekly 蒐集
        /add <url>     — 新增追蹤頻道
        /remove <名稱> — 移除追蹤頻道
        /analyze <url> — 分析指定 YouTube 影片
        /discover      — 探索並推薦新的說書頻道與書評網站

    安全性：只有設定的 chat_id 才能執行操作。
    """

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        # 優先使用讀書 Agent 專用 Bot，未設定時降級為舊 Bot
        self._bot_token = bot_token or READING_BOT_TOKEN or TELEGRAM_BOT_TOKEN
        self._chat_id = str(chat_id or READING_CHAT_ID or TELEGRAM_CHAT_ID).strip()

        if not self._bot_token:
            raise ValueError(
                "READING_BOT_TOKEN 或 TELEGRAM_BOT_TOKEN 未設定，請檢查 .env 檔案"
            )
        if not self._chat_id:
            raise ValueError(
                "READING_CHAT_ID 或 TELEGRAM_CHAT_ID 未設定，請檢查 .env 檔案"
            )

    # =========================================================
    # 安全性驗證
    # =========================================================

    def _is_authorized(self, update: Update) -> bool:
        """驗證發送者是否為授權的 chat_id

        比對 update.effective_chat.id 與設定的 chat_id，
        防止未授權使用者操控 Bot。

        Args:
            update: Telegram Update 物件

        Returns:
            True 表示已授權，False 表示未授權
        """
        if not update.effective_chat:
            return False
        return str(update.effective_chat.id) == self._chat_id

    # =========================================================
    # /start 與 /help
    # =========================================================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/start 或 /help — 顯示歡迎訊息與所有可用指令"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        help_text = (
            "📚 讀書 Agent v2 — Telegram Bot\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "歡迎使用讀書 Agent！以下是可用的指令：\n\n"
            "📖 *內容查詢*\n"
            "/videos — 列出最近蒐集的影片摘要\n"
            "/books  — 列出暢銷書排行榜\n\n"
            "📡 *頻道管理*\n"
            "/channels        — 列出目前追蹤的頻道\n"
            "/add <url>       — 新增追蹤頻道\n"
            "/remove <名稱>   — 移除追蹤頻道\n\n"
            "🚀 *蒐集任務*\n"
            "/collect — 執行完整蒐集（含完成通知）\n"
            "/weekly  — 執行每週說書影片蒐集\n"
            "/ai      — 執行 AI Weekly 蒐集\n\n"
            "🔍 *分析工具*\n"
            "/analyze <youtube_url> — 分析指定 YouTube 影片\n\n"
            "🧭 *來源探索*\n"
            "/discover — 探索並推薦新的說書頻道與書評網站\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 Agent Army ｜ 讀書 Agent v2"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    # =========================================================
    # /videos — 列出最近蒐集的影片
    # =========================================================

    async def cmd_videos(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/videos — 從 data/reading_agent/videos/ 讀取最新 JSON 並顯示影片摘要"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        try:
            # 找到最新的日期 JSON 檔案
            json_files = sorted(VIDEOS_DIR.glob("*.json"), reverse=True)
            if not json_files:
                await update.message.reply_text("目前沒有蒐集到的影片資料。")
                return

            latest_file = json_files[0]
            date_str = latest_file.stem  # 取得 YYYY-MM-DD

            # 讀取影片資料
            with open(latest_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            videos = [Video.from_dict(v) for v in raw_data]

            if not videos:
                await update.message.reply_text(f"日期 {date_str} 的影片資料為空。")
                return

            # 分類影片：一般說書 vs AI Weekly
            book_videos = [v for v in videos if v.category not in AI_CATEGORIES]
            ai_videos = [v for v in videos if v.category in AI_CATEGORIES]

            # 組合訊息
            lines = [
                f"📚 最近蒐集的影片（{date_str}）",
                "━━━━━━━━━━━━━",
                f"共 {len(videos)} 部影片",
            ]

            # 一般說書影片區塊
            if book_videos:
                lines.append("\n📖 說書影片：")
                for i, video in enumerate(book_videos[:20], 1):
                    title_display = f"《{video.book_title}》" if video.book_title else video.title
                    lines.append(f"{i}. {title_display} - {video.channel_name}")

            # AI Weekly 影片區塊
            if ai_videos:
                lines.append("\n🤖 AI Weekly：")
                for i, video in enumerate(ai_videos[:15], 1):
                    lines.append(f"{i}. {video.title} - {video.channel_name}")

            message = "\n".join(lines)
            await _send_long_message(update, message)

        except (json.JSONDecodeError, OSError) as e:
            logger.error("讀取影片資料失敗: %s", e)
            await update.message.reply_text(f"讀取影片資料失敗：{e}")
        except Exception as e:
            logger.exception("cmd_videos 發生未預期錯誤")
            await update.message.reply_text(f"發生錯誤：{e}")

    # =========================================================
    # /books — 列出暢銷書排行榜
    # =========================================================

    async def cmd_books(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/books — 呼叫 BestsellerScraper 抓取最新暢銷書排行榜"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        # 耗時操作：先回覆「處理中」
        await update.message.reply_text("📊 正在抓取暢銷書排行榜，請稍候...")

        try:
            # 延遲匯入，避免啟動時載入不必要的模組
            from .bestseller_scraper import BestsellerScraper

            scraper = BestsellerScraper()
            books = await scraper.scrape_all()

            if not books:
                await update.message.reply_text("目前無法取得暢銷書資料，請稍後再試。")
                return

            lines = [
                "📚 暢銷書排行榜（跨平台合併）",
                "━━━━━━━━━━━━━",
                f"共 {len(books)} 本書",
                "",
            ]

            for i, book in enumerate(books[:30], 1):
                # 依語言顯示不同圖示
                lang_icon = "🌐" if book.language == "en" else "🇹🇼"
                sources_str = " / ".join(book.sources) if book.sources else "未知來源"
                line = f"{i}. {lang_icon} 《{book.title}》"
                if book.author:
                    line += f" — {book.author}"
                lines.append(line)
                lines.append(f"    📍 {sources_str}")

            message = "\n".join(lines)
            await _send_long_message(update, message)

        except Exception as e:
            logger.exception("cmd_books 發生未預期錯誤")
            await update.message.reply_text(f"抓取暢銷書失敗：{e}")

    # =========================================================
    # /channels — 列出追蹤頻道
    # =========================================================

    async def cmd_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/channels — 讀取 channels.json 並顯示目前追蹤的頻道列表"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        try:
            channels = load_channels()

            if not channels:
                await update.message.reply_text("目前沒有追蹤任何頻道。")
                return

            lines = [
                f"📚 追蹤頻道（共 {len(channels)} 個）",
                "━━━━━━━━━━━━━",
            ]

            for i, ch in enumerate(channels, 1):
                cat = ch.get("category", "general")
                cat_info = BOOK_CATEGORIES.get(cat, {"icon": "📺", "name": cat})
                name = ch.get("name", "未命名頻道")
                cat_name = cat_info["name"]
                icon = cat_info["icon"]
                lines.append(f"{i}. {icon} {name} - {cat_name}")

            lines.append("")
            lines.append("💡 /add <url> 新增 | /remove <名稱> 移除")

            message = "\n".join(lines)
            await _send_long_message(update, message)

        except Exception as e:
            logger.exception("cmd_channels 發生未預期錯誤")
            await update.message.reply_text(f"讀取頻道列表失敗：{e}")

    # =========================================================
    # /weekly — 執行每週蒐集
    # =========================================================

    async def cmd_weekly(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/weekly — 觸發完整的每週說書影片蒐集流程

        耗時操作，先回覆「蒐集中」再於背景執行。
        """
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        await update.message.reply_text(
            "📚 開始執行每週蒐集...\n"
            "此流程包含：暢銷書爬取 → YouTube 搜尋 → 字幕擷取 → Gemini 整理 → Telegram 發送\n"
            "預計需要數分鐘，完成後會自動發送報告。"
        )

        try:
            # 延遲匯入 runner，避免啟動時載入
            from .runner import _run_v2_collect

            # 在背景執行，不阻塞 Bot 的事件迴圈
            asyncio.create_task(_run_v2_collect("weekly", dry_run=False))

        except Exception as e:
            logger.exception("cmd_weekly 啟動失敗")
            await update.message.reply_text(f"啟動每週蒐集失敗：{e}")

    # =========================================================
    # /ai — 執行 AI Weekly 蒐集
    # =========================================================

    async def cmd_ai(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/ai — 觸發 AI Weekly 蒐集流程

        耗時操作，先回覆「蒐集中」再於背景執行。
        """
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        await update.message.reply_text(
            "🤖 開始執行 AI Weekly 蒐集...\n"
            "此流程包含：AI 頻道 RSS → 關鍵字搜尋 → 字幕擷取 → Gemini 整理 → Telegram 發送\n"
            "預計需要數分鐘，完成後會自動發送報告。"
        )

        try:
            from .runner import _run_ai_weekly

            asyncio.create_task(_run_ai_weekly(dry_run=False))

        except Exception as e:
            logger.exception("cmd_ai 啟動失敗")
            await update.message.reply_text(f"啟動 AI Weekly 失敗：{e}")

    # =========================================================
    # /collect — 執行完整蒐集流程（含完成通知）
    # =========================================================

    async def cmd_collect(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/collect — 執行完整蒐集流程：暢銷書 + 說書影片 + AI Weekly

        與 /weekly 的差別：
        - /collect 會在完成後主動回覆通知
        - 可選 --dry-run 參數（不發送 Telegram 報告）
        """
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        # 解析參數（是否 dry-run）
        dry_run = bool(context.args and "dry" in " ".join(context.args).lower())

        mode_label = "🔇 Dry Run（不發送報告）" if dry_run else "📨 完整模式（含發送）"
        await update.message.reply_text(
            f"📚 開始執行完整蒐集流程\n"
            f"模式：{mode_label}\n"
            f"━━━━━━━━━━━━━\n"
            f"流程：來源探索 → 暢銷書爬取 → YouTube 搜尋 →\n"
            f"字幕擷取 → Gemini 整理 → AI Weekly → 發送報告\n\n"
            f"⏱️ 預計需要 5-10 分鐘，完成後會主動通知你。"
        )

        # 在背景執行，完成後主動回覆結果
        asyncio.create_task(self._collect_task(update, dry_run))

    async def _collect_task(self, update: Update, dry_run: bool) -> None:
        """背景執行完整蒐集流程，完成後回覆結果摘要

        Args:
            update: Telegram Update 物件
            dry_run: 是否為 dry-run 模式
        """
        start_time = datetime.now()
        try:
            from .runner import _run_v2_collect

            await _run_v2_collect("weekly", dry_run=dry_run)

            elapsed = datetime.now() - start_time
            minutes = int(elapsed.total_seconds() // 60)
            seconds = int(elapsed.total_seconds() % 60)

            await update.message.reply_text(
                f"✅ 蒐集流程完成！\n"
                f"━━━━━━━━━━━━━\n"
                f"⏱️ 耗時：{minutes} 分 {seconds} 秒\n"
                f"{'🔇 Dry Run 模式，未發送報告' if dry_run else '📨 報告已發送至 Telegram'}\n\n"
                f"💡 用 /videos 查看蒐集到的影片"
            )

        except Exception as e:
            elapsed = datetime.now() - start_time
            logger.exception("collect 流程失敗: %s", e)
            await update.message.reply_text(
                f"❌ 蒐集流程失敗\n"
                f"━━━━━━━━━━━━━\n"
                f"錯誤：{e}\n"
                f"⏱️ 已執行：{int(elapsed.total_seconds())} 秒"
            )

    # =========================================================
    # /add <channel_url> — 新增追蹤頻道
    # =========================================================

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/add <channel_url> — 新增追蹤頻道到 channels.json"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        # 取得參數（去掉指令本身後的其餘文字）
        args = context.args
        if not args:
            await update.message.reply_text(
                "用法：/add <channel_url>\n"
                "範例：/add https://www.youtube.com/@vincentshuoshu"
            )
            return

        channel_url = args[0].strip()

        # 基本格式驗證：必須是 http(s) 開頭
        if not channel_url.startswith("http"):
            await update.message.reply_text(
                "請提供完整的頻道 URL（需以 http 或 https 開頭）。"
            )
            return

        try:
            # 讀取現有頻道列表
            channels = self._load_channels_file()

            # 檢查是否已存在（比對 URL）
            for ch in channels:
                if ch.get("url") == channel_url:
                    name = ch.get("name", channel_url)
                    await update.message.reply_text(f"頻道已存在：{name}")
                    return

            # 從 URL 嘗試解析頻道名稱（取 @ 後面的部分作為預設名稱）
            channel_name = self._extract_channel_name_from_url(channel_url)

            # 建立新頻道記錄
            new_channel = {
                "channel_id": "",          # 使用者可後續手動填入
                "name": channel_name,
                "url": channel_url,
                "category": "general",
                "description": "使用者透過 Bot 新增的頻道",
            }
            channels.append(new_channel)

            # 寫回 channels.json
            self._save_channels_file(channels)

            await update.message.reply_text(
                f"已新增頻道：{channel_name}\n"
                f"URL：{channel_url}\n\n"
                f"💡 可編輯 channels.json 修改頻道名稱、分類和 channel_id。"
            )

        except (OSError, json.JSONDecodeError) as e:
            logger.error("新增頻道失敗: %s", e)
            await update.message.reply_text(f"新增頻道失敗：{e}")
        except Exception as e:
            logger.exception("cmd_add 發生未預期錯誤")
            await update.message.reply_text(f"發生錯誤：{e}")

    # =========================================================
    # /remove <channel_name> — 移除追蹤頻道
    # =========================================================

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/remove <channel_name> — 從 channels.json 移除指定頻道"""
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        args = context.args
        if not args:
            await update.message.reply_text(
                "用法：/remove <頻道名稱>\n"
                "範例：/remove 文森說書\n\n"
                "用 /channels 查看目前追蹤的頻道名稱。"
            )
            return

        # 支援名稱含空格（合併所有 args）
        target_name = " ".join(args).strip()

        try:
            channels = self._load_channels_file()

            if not channels:
                await update.message.reply_text("目前沒有追蹤任何頻道。")
                return

            # 用名稱比對（不分大小寫）
            original_count = len(channels)
            remaining = [
                ch for ch in channels
                if ch.get("name", "").lower() != target_name.lower()
            ]

            if len(remaining) == original_count:
                await update.message.reply_text(
                    f"找不到頻道：{target_name}\n"
                    "請用 /channels 確認頻道名稱。"
                )
                return

            # 寫回 channels.json
            self._save_channels_file(remaining)

            removed_count = original_count - len(remaining)
            await update.message.reply_text(
                f"已移除頻道：{target_name}（共移除 {removed_count} 筆）"
            )

        except (OSError, json.JSONDecodeError) as e:
            logger.error("移除頻道失敗: %s", e)
            await update.message.reply_text(f"移除頻道失敗：{e}")
        except Exception as e:
            logger.exception("cmd_remove 發生未預期錯誤")
            await update.message.reply_text(f"發生錯誤：{e}")

    # =========================================================
    # /analyze <youtube_url> — 分析 YouTube 影片
    # =========================================================

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/analyze <youtube_url> — 擷取字幕並用 Gemini 整理重點

        耗時操作，先回覆「處理中」，再在背景執行分析，結果直接透過 Bot 回覆。
        """
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        args = context.args
        if not args:
            await update.message.reply_text(
                "用法：/analyze <youtube_url>\n"
                "範例：/analyze https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            return

        youtube_url = args[0].strip()

        # 驗證是否為 YouTube URL
        if not self._is_youtube_url(youtube_url):
            await update.message.reply_text(
                "請提供有效的 YouTube URL。\n"
                "支援格式：youtube.com/watch?v=...、youtu.be/..."
            )
            return

        await update.message.reply_text(
            f"🔍 正在分析影片，請稍候...\n{youtube_url}\n\n"
            "流程：擷取字幕 → Gemini 深度整理 → 回傳結果"
        )

        # 在背景執行分析，完成後直接回覆結果
        asyncio.create_task(
            self._analyze_video_task(update, youtube_url)
        )

    async def _analyze_video_task(self, update: Update, url: str) -> None:
        """在背景執行影片分析，完成後將結果發送回 Telegram

        Args:
            update: Telegram Update 物件（用於回覆訊息）
            url: YouTube 影片 URL
        """
        try:
            from .transcript_extractor import TranscriptExtractor
            from .content_analyzer import ContentAnalyzer

            # 從 URL 擷取 video_id
            video_id = self._extract_video_id(url)
            if not video_id:
                await update.message.reply_text(f"無法從 URL 解析影片 ID：{url}")
                return

            # 建立基本 Video 物件
            video = Video(
                title="",
                url=url,
                channel_name="（直接分析）",
                channel_id="",
                published_at=datetime.now().isoformat(),
                video_id=video_id,
            )

            # 擷取字幕
            extractor = TranscriptExtractor()
            videos = await extractor.extract_batch([video])
            video = videos[0]

            if not video.transcript:
                await update.message.reply_text(
                    "⚠️ 無法取得字幕，將嘗試以影片描述進行整理..."
                )

            # Gemini 重點整理
            analyzer = ContentAnalyzer()
            videos = await analyzer.analyze_batch([video])
            video = videos[0]

            # 組合結果訊息
            lines = [
                "📺 影片分析結果",
                "━━━━━━━━━━━━━━━━━━",
                f"🔗 {url}",
            ]

            if video.title:
                lines.append(f"📌 {video.title}")

            if video.key_points_zh:
                lines.append("\n【中文重點整理】")
                lines.append(video.key_points_zh)

            if video.key_points_original and video.language == "en":
                lines.append("\n【English Key Points】")
                lines.append(video.key_points_original)

            if not video.key_points_zh and not video.key_points_original:
                lines.append("\n⚠️ 無法整理重點（可能無字幕或分析失敗）")

            lines.append("\n━━━━━━━━━━━━━━━━━━")
            lines.append("🤖 Agent Army ｜ 讀書 Agent v2")

            result = "\n".join(lines)
            await _send_long_message(update, result)

        except Exception as e:
            logger.exception("影片分析失敗: %s", e)
            await update.message.reply_text(f"影片分析失敗：{e}")

    # =========================================================
    # /discover — 探索推薦新來源
    # =========================================================

    async def cmd_discover(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """/discover — 觸發 Source Discovery 流程

        搜尋 YouTube 說書頻道 + 書評網站，Gemini 評分後
        以 Inline Keyboard 讓使用者確認或拒絕。
        """
        if not self._is_authorized(update):
            await update.message.reply_text("未授權的存取。")
            return

        await update.message.reply_text(
            "🔍 開始研究推薦來源...\n"
            "搜尋 YouTube 頻道 + 書評網站 + Gemini 評分\n"
            "預計需要 2-3 分鐘，完成後會逐一列出候選清單。"
        )

        asyncio.create_task(self._discover_sources_task(update))

    async def _discover_sources_task(self, update: Update) -> None:
        """背景執行探索，完成後發送帶 Inline Keyboard 按鈕的候選清單

        Args:
            update: Telegram Update 物件（用於回覆訊息）
        """
        try:
            from .source_discovery import SourceDiscovery

            discovery = SourceDiscovery()
            candidates = await discovery.run_discovery()

            if not candidates:
                await update.message.reply_text(
                    "本次未發現新的推薦來源（可能都已在追蹤清單中）。"
                )
                return

            await update.message.reply_text(
                f"🎯 研究完成！找到 {len(candidates)} 個推薦來源："
            )

            # 逐一發送候選，附帶 Inline Keyboard 按鈕
            for i, source in enumerate(candidates, 1):
                type_icon = (
                    "📺" if source.source_type == "youtube_channel" else "🌐"
                )
                lang_label = {
                    "zh": "中文", "en": "英文", "both": "中英文"
                }.get(source.language, source.language)

                freq = source.metadata.get("update_frequency", "unknown")
                freq_label = {
                    "high": "高頻更新", "medium": "定期更新",
                    "low": "低頻更新",
                }.get(freq, "")

                # 近期影片標題（最多 2 個）
                recent = source.metadata.get("recent_titles", [])[:2]
                recent_str = "\n".join(f"  · {t}" for t in recent)

                message = (
                    f"{i}. {type_icon} ⭐ {source.score:.0f}分 | "
                    f"{source.name}\n"
                    f"   {lang_label}"
                )
                if freq_label:
                    message += f" · {freq_label}"
                message += f"\n   {source.reason}"
                if recent_str:
                    message += f"\n   近期內容：\n{recent_str}"

                # Inline Keyboard：確認追蹤 / 略過 / 查看頻道
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "✅ 確認追蹤",
                            callback_data=f"discover_approve:{source.name}",
                        ),
                        InlineKeyboardButton(
                            "❌ 略過",
                            callback_data=f"discover_reject:{source.name}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🔗 查看頻道", url=source.url,
                        ),
                    ],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    message, reply_markup=reply_markup,
                )

        except Exception as e:
            logger.exception("Source Discovery 失敗: %s", e)
            await update.message.reply_text(f"來源探索失敗：{e}")

    async def handle_discover_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """處理 /discover Inline Keyboard 的回呼

        callback_data 格式：
            "discover_approve:<source_name>"
            "discover_reject:<source_name>"
        """
        query = update.callback_query
        # 必須先 answer，否則 Telegram 按鈕會一直轉圈
        await query.answer()

        if not self._is_authorized(update):
            return

        data = query.data or ""

        if data.startswith("discover_approve:"):
            source_name = data[len("discover_approve:"):]
            await self._handle_approve(query, source_name)

        elif data.startswith("discover_reject:"):
            source_name = data[len("discover_reject:"):]
            await self._handle_reject(query, source_name)

    async def _handle_approve(self, query, source_name: str) -> None:
        """確認追蹤：更新 status=approved，寫入 channels.json

        Args:
            query: Telegram CallbackQuery 物件
            source_name: 來源名稱
        """
        try:
            from .source_discovery import SourceDiscovery

            discovery = SourceDiscovery()
            success = discovery.approve_source(source_name)

            if success:
                await query.edit_message_text(
                    f"✅ 已確認追蹤：{source_name}\n"
                    f"下次執行 /weekly 時將自動納入蒐集範圍。"
                )
            else:
                await query.edit_message_text(
                    f"⚠️ 找不到來源：{source_name}"
                )
        except Exception as e:
            logger.exception("approve_source 失敗: %s", e)
            await query.edit_message_text(f"確認追蹤失敗：{e}")

    async def _handle_reject(self, query, source_name: str) -> None:
        """略過：更新 status=rejected，未來不再推薦

        Args:
            query: Telegram CallbackQuery 物件
            source_name: 來源名稱
        """
        try:
            from .source_discovery import SourceDiscovery

            discovery = SourceDiscovery()
            discovery.reject_source(source_name)

            await query.edit_message_text(f"❌ 已略過：{source_name}")
        except Exception as e:
            logger.exception("reject_source 失敗: %s", e)
            await query.edit_message_text(f"略過失敗：{e}")

    # =========================================================
    # 內部工具方法
    # =========================================================

    def _load_channels_file(self) -> list[dict]:
        """讀取 channels.json

        若檔案不存在，回傳空列表。

        Returns:
            頻道設定列表
        """
        if not CHANNELS_FILE.exists():
            return []
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_channels_file(self, channels: list[dict]) -> None:
        """寫回 channels.json

        Args:
            channels: 要儲存的頻道列表
        """
        CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _extract_channel_name_from_url(url: str) -> str:
        """從 YouTube 頻道 URL 解析頻道名稱

        例：https://www.youtube.com/@vincentshuoshu -> vincentshuoshu
        例：https://www.youtube.com/channel/UCxxx -> UCxxx（截短）

        Args:
            url: YouTube 頻道 URL

        Returns:
            解析出的頻道名稱（若解析失敗則回傳 URL 本身）
        """
        # 處理 @handle 格式
        at_match = re.search(r"@([^/?&]+)", url)
        if at_match:
            return at_match.group(1)

        # 處理 /channel/UCxxxx 格式
        channel_match = re.search(r"/channel/([a-zA-Z0-9_-]+)", url)
        if channel_match:
            channel_id = channel_match.group(1)
            # channel_id 太長時截短
            return channel_id[:20] if len(channel_id) > 20 else channel_id

        # 處理 /c/name 格式（舊式自訂 URL）
        custom_match = re.search(r"/c/([^/?&]+)", url)
        if custom_match:
            return custom_match.group(1)

        # 無法解析時，使用 URL 最後一段
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else url

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        """驗證是否為有效的 YouTube URL

        Args:
            url: 待驗證的 URL

        Returns:
            True 表示是 YouTube URL
        """
        youtube_patterns = [
            r"youtube\.com/watch",
            r"youtu\.be/",
            r"youtube\.com/embed/",
            r"youtube\.com/shorts/",
        ]
        return any(re.search(p, url) for p in youtube_patterns)

    @staticmethod
    def _extract_video_id(url: str) -> str:
        """從 YouTube URL 擷取影片 ID

        Args:
            url: YouTube 影片 URL

        Returns:
            11 位的影片 ID，若無法解析則回傳空字串
        """
        patterns = [
            r"(?:v=|/v/)([a-zA-Z0-9_-]{11})",
            r"youtu\.be/([a-zA-Z0-9_-]{11})",
            r"(?:embed|shorts)/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return ""

    # =========================================================
    # 指令選單定義（Telegram Menu Button）
    # =========================================================

    # 使用者在 Telegram 點開選單按鈕時會看到的指令列表
    BOT_COMMANDS = [
        BotCommand("start", "歡迎訊息與指令說明"),
        BotCommand("videos", "列出最近蒐集的影片摘要"),
        BotCommand("books", "列出暢銷書排行榜"),
        BotCommand("channels", "列出追蹤頻道"),
        BotCommand("collect", "執行完整蒐集（含通知）"),
        BotCommand("weekly", "執行每週說書影片蒐集"),
        BotCommand("ai", "執行 AI Weekly 蒐集"),
        BotCommand("analyze", "分析指定 YouTube 影片"),
        BotCommand("discover", "探索推薦新的說書頻道"),
        BotCommand("add", "新增追蹤頻道"),
        BotCommand("remove", "移除追蹤頻道"),
        BotCommand("help", "顯示所有可用指令"),
    ]

    @staticmethod
    async def _post_init(application: Application) -> None:
        """Bot 啟動後自動註冊指令選單

        透過 Telegram Bot API 的 setMyCommands 設定指令清單，
        讓使用者可以在聊天室左下角的「選單按鈕」中看到所有可用指令。

        Args:
            application: python-telegram-bot 的 Application 物件
        """
        await application.bot.set_my_commands(TelegramBotHandler.BOT_COMMANDS)
        logger.info(
            "已註冊 %d 個指令到 Telegram 選單",
            len(TelegramBotHandler.BOT_COMMANDS),
        )

    # =========================================================
    # 啟動 Bot
    # =========================================================

    def run(self) -> None:
        """啟動 Bot（長駐 polling 模式）

        建立 Application，註冊所有指令 Handler，然後進入 polling 迴圈。
        按 Ctrl+C 可停止。
        """
        logger.info("建立 Telegram Bot Application...")

        app = (
            Application.builder()
            .token(self._bot_token)
            .post_init(self._post_init)
            .build()
        )

        # 註冊指令 Handler
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_start))
        app.add_handler(CommandHandler("videos", self.cmd_videos))
        app.add_handler(CommandHandler("books", self.cmd_books))
        app.add_handler(CommandHandler("channels", self.cmd_channels))
        app.add_handler(CommandHandler("weekly", self.cmd_weekly))
        app.add_handler(CommandHandler("ai", self.cmd_ai))
        app.add_handler(CommandHandler("add", self.cmd_add))
        app.add_handler(CommandHandler("remove", self.cmd_remove))
        app.add_handler(CommandHandler("analyze", self.cmd_analyze))
        app.add_handler(CommandHandler("collect", self.cmd_collect))
        app.add_handler(CommandHandler("discover", self.cmd_discover))
        app.add_handler(
            CallbackQueryHandler(
                self.handle_discover_callback,
                pattern=r"^discover_(approve|reject):",
            )
        )

        logger.info(
            "Telegram Bot 啟動，監聽 chat_id=%s。按 Ctrl+C 停止。",
            self._chat_id,
        )

        # 進入 polling 迴圈（blocking）
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,   # 啟動時忽略積壓的舊訊息
        )
