# -*- coding: utf-8 -*-
"""讀書 Agent v2 — 暢銷書說書影片蒐集與深度整理

v2 核心流程：暢銷書排行榜 → YouTube 搜尋說書影片 →
字幕擷取 → Gemini 深度重點整理 → 中英雙語 → Telegram 發送。
"""

from .ai_weekly import AIWeeklyCollector
from .models import Book, Video, ReadingReport
from .telegram_bot_handler import TelegramBotHandler
from .youtube_client import YouTubeClient
from .reporter import ReportGenerator

__all__ = [
    "AIWeeklyCollector",
    "Book",
    "Video",
    "ReadingReport",
    "TelegramBotHandler",
    "YouTubeClient",
    "ReportGenerator",
]
