# -*- coding: utf-8 -*-
"""讀書 Agent v2 — 設定模組

v2 架構：書籍為主，搜尋暢銷書排行榜 → YouTube 搜尋說書影片 →
字幕擷取 → Gemini 深度重點整理 → 中英雙語 → 新 Telegram Bot 發送。

保留舊版頻道追蹤功能作為「自訂頻道」使用。
"""

import json
import os
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# === 載入環境變數 ===
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# === Telegram 設定（舊版 Bot，保留給其他 Agent） ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_SEND_DELAY = float(os.getenv("TELEGRAM_SEND_DELAY", "1.5"))
TELEGRAM_MAX_LENGTH = 4096

# === 讀書 Agent v2 專用 Telegram Bot ===
READING_BOT_TOKEN = os.getenv("READING_BOT_TOKEN", "")
READING_CHAT_ID = os.getenv("READING_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))

# === Gemini API 設定 ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# === 路徑設定 ===
DATA_DIR = _PROJECT_ROOT / "data" / "reading_agent"
VIDEOS_DIR = DATA_DIR / "videos"
REPORTS_DIR = DATA_DIR / "reports"
BOOKS_DIR = DATA_DIR / "books"
CHANNELS_FILE = DATA_DIR / "channels.json"
CUSTOM_CHANNELS_FILE = DATA_DIR / "custom_channels.json"
CUSTOM_URLS_FILE = DATA_DIR / "custom_urls.json"

# 確保目錄存在
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
BOOKS_DIR.mkdir(parents=True, exist_ok=True)

# === 暢銷書排行榜來源 ===
BESTSELLER_SOURCES = {
    "books_com_tw": {
        "name": "博客來",
        "url": "https://www.books.com.tw/web/sys_saletopb/books",
        "language": "zh",
    },
    "eslite": {
        "name": "誠品",
        "url": "https://www.eslite.com/bestseller/chinese",
        "language": "zh",
    },
    "kingstone": {
        "name": "金石堂",
        "url": "https://www.kingstone.com.tw/bestseller/book",
        "language": "zh",
    },
    "amazon": {
        "name": "Amazon",
        "url": "https://www.amazon.com/best-sellers-books-Amazon/zgbs/books",
        "language": "en",
    },
}
BESTSELLER_TOP_N = 20  # 每個來源抓前 N 名

# === YouTube 搜尋設定（v2 書籍搜尋用） ===
MIN_VIDEO_DURATION = 300   # 最短影片長度（秒）= 5 分鐘
MAX_SEARCH_RESULTS = 5     # 每本書最多搜尋幾個影片
SEARCH_KEYWORDS_ZH = "{book_title} 說書"
SEARCH_KEYWORDS_EN = "{book_title} book summary review"

# === YouTube RSS 設定 ===
YOUTUBE_RSS_BASE = "https://www.youtube.com/feeds/videos.xml"
# YouTube RSS 每個頻道最多回傳約 15 部影片
YOUTUBE_RSS_LIMIT = 15

# === HTTP 設定 ===
REQUEST_DELAY = 1.5   # 請求間隔（秒）
REQUEST_TIMEOUT = 30  # 請求超時（秒）
MAX_RETRIES = 3       # 最大重試次數

# === 預設說書頻道列表 ===
# 涵蓋繁體中文主流說書 / 知識型 YouTube 頻道
# 使用者可在 data/reading_agent/channels.json 覆寫或新增
_DEFAULT_CHANNELS = [
    {
        "channel_id": "UCPgGtH2PxZ9xR0ehzQ27FHw",
        "name": "文森說書",
        "url": "https://www.youtube.com/@vincentshuoshu",
        "category": "general",
        "description": "每週介紹一本好書，涵蓋商業、心理、科學等領域",
    },
    {
        "channel_id": "UCMUnInmOkrWN4gof9KlhNmQ",
        "name": "老高與小茉",
        "url": "https://www.youtube.com/@laogao",
        "category": "general",
        "description": "知識型頻道，涵蓋科學、歷史、哲學等各類主題",
    },
    {
        "channel_id": "UCBvQ4hOEoDdYeIBu0tE-7Sg",
        "name": "閱部客",
        "url": "https://www.youtube.com/@yuehbuker",
        "category": "business",
        "description": "商業、管理、創業類書籍重點摘要",
    },
]


def load_channels() -> list[dict]:
    """載入頻道列表

    優先載入使用者自訂的 channels.json，若不存在則使用預設列表。
    同時將預設列表寫入 channels.json 供使用者參考修改。

    Returns:
        頻道設定列表
    """
    if CHANNELS_FILE.exists():
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                channels = json.load(f)
            logger.info("從 %s 載入 %d 個自訂頻道", CHANNELS_FILE, len(channels))
            return channels
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("載入自訂頻道失敗，使用預設列表: %s", e)

    # 寫出預設列表供使用者參考修改
    try:
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_CHANNELS, f, ensure_ascii=False, indent=2)
        logger.info("已產生預設頻道列表: %s", CHANNELS_FILE)
    except OSError as e:
        logger.warning("無法寫入預設頻道列表: %s", e)

    return _DEFAULT_CHANNELS


# =========================================================
# AI Weekly 設定
# =========================================================

AI_CHANNELS_FILE = DATA_DIR / "ai_channels.json"

# AI 搜尋主題（中英文關鍵字，每週搜尋）
AI_SEARCH_TOPICS = [
    # 中文主題
    "AI 人工智慧 最新突破 本週",
    "ChatGPT Claude Gemini 新功能 更新",
    "AI 工具 推薦 實用",
    "人工智慧 產業應用 趨勢",
    # 英文主題
    "AI artificial intelligence news this week",
    "LLM large language model breakthrough",
    "AI tools productivity new release",
    "AI robotics autonomous driving update",
]

# 每個主題最多搜尋幾個影片
AI_MAX_SEARCH_PER_TOPIC = 3

# 預設 AI 頻道列表（中英文混合）
# channel_id 由使用者確認後填入，或透過 ai_channels.json 自訂
_DEFAULT_AI_CHANNELS = [
    {
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "name": "Two Minute Papers",
        "url": "https://www.youtube.com/@TwoMinutePapers",
        "category": "ai_research",
        "language": "en",
        "description": "AI 研究論文解讀，每週更新最新 AI 突破",
    },
    {
        "channel_id": "UCNJ1Ymd5yFuUPtn21xtRbbw",
        "name": "AI Explained",
        "url": "https://www.youtube.com/@aiexplained-official",
        "category": "ai_news",
        "language": "en",
        "description": "深度解析 AI 產業新聞與技術趨勢",
    },
    {
        "channel_id": "UCsBjURrPoezykLs9EqgamOA",
        "name": "Fireship",
        "url": "https://www.youtube.com/@Fireship",
        "category": "ai_tech",
        "language": "en",
        "description": "科技與 AI 快報，100 秒解釋技術概念",
    },
    {
        "channel_id": "UCJHnlUQJKTcTaEJmzNEOh0g",
        "name": "TheAIGRID",
        "url": "https://www.youtube.com/@TheAiGrid",
        "category": "ai_news",
        "language": "en",
        "description": "AI 產業動態、新工具、新模型發佈追蹤",
    },
    {
        "channel_id": "UCbfYPyITQ-7l4upoX8nvctg",
        "name": "Two Minute Papers (中文)",
        "url": "https://www.youtube.com/@two-minute-papers-chinese",
        "category": "ai_research",
        "language": "zh",
        "description": "Two Minute Papers 中文版，AI 論文解讀",
    },
    {
        "channel_id": "UCJMnKlBEUqBPMxnuE1Uw1HQ",
        "name": "Matt Wolfe",
        "url": "https://www.youtube.com/@maboroshi",
        "category": "ai_tools",
        "language": "en",
        "description": "AI 工具評測、每週 AI 新聞彙整",
    },
]


def load_ai_channels() -> list[dict]:
    """載入 AI 頻道列表

    優先載入使用者自訂的 ai_channels.json，若不存在則使用預設列表。

    Returns:
        AI 頻道設定列表
    """
    if AI_CHANNELS_FILE.exists():
        try:
            with open(AI_CHANNELS_FILE, "r", encoding="utf-8") as f:
                channels = json.load(f)
            logger.info("從 %s 載入 %d 個 AI 頻道", AI_CHANNELS_FILE, len(channels))
            return channels
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("載入 AI 頻道失敗，使用預設列表: %s", e)

    # 寫出預設列表
    try:
        with open(AI_CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_AI_CHANNELS, f, ensure_ascii=False, indent=2)
        logger.info("已產生預設 AI 頻道列表: %s", AI_CHANNELS_FILE)
    except OSError as e:
        logger.warning("無法寫入預設 AI 頻道列表: %s", e)

    return _DEFAULT_AI_CHANNELS


# AI 內容分類
AI_CATEGORIES = {
    "ai_news": {"name": "AI 新聞", "icon": "📰"},
    "ai_research": {"name": "AI 研究", "icon": "🔬"},
    "ai_tools": {"name": "AI 工具", "icon": "🛠️"},
    "ai_application": {"name": "AI 應用", "icon": "💡"},
    "ai_tech": {"name": "AI 技術", "icon": "⚙️"},
    "ai_general": {"name": "AI 綜合", "icon": "🤖"},
}

# === 書籍分類 ===
BOOK_CATEGORIES = {
    "business": {"name": "商業管理", "icon": "💼"},
    "self_help": {"name": "自我成長", "icon": "🌱"},
    "science": {"name": "科學新知", "icon": "🔬"},
    "philosophy": {"name": "哲學思辨", "icon": "🤔"},
    "history": {"name": "歷史人文", "icon": "📜"},
    "psychology": {"name": "心理學", "icon": "🧠"},
    "fiction": {"name": "文學小說", "icon": "📖"},
    "tech": {"name": "科技趨勢", "icon": "💻"},
    "finance": {"name": "投資理財", "icon": "💰"},
    "current_affairs": {"name": "時事議題", "icon": "📰"},
    "general": {"name": "綜合知識", "icon": "📚"},
}


# =========================================================
# Source Discovery 設定（來源探索模組）
# =========================================================

DISCOVERY_DIR = DATA_DIR / "discovery"
DISCOVERED_SOURCES_FILE = DISCOVERY_DIR / "discovered_sources.json"
DISCOVERY_LOG_FILE = DISCOVERY_DIR / "discovery_log.json"

# 確保目錄存在
DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)

# Gemini 評分門檻：高於此分數才進入候選清單
DISCOVERY_MIN_SCORE = 60.0

# 每次探索最多回傳幾個候選
DISCOVERY_MAX_CANDIDATES = 10

# 自動探索週期（天）
DISCOVERY_INTERVAL_DAYS = 30

# YouTube 頻道探索搜尋關鍵字（中文）
DISCOVERY_YOUTUBE_KEYWORDS_ZH = [
    "推薦說書頻道 2026",
    "說書 知識型 YouTube 頻道",
    "書評 好書推薦 頻道",
    "閱讀分享 每週一書",
    "商業書 自我成長 說書",
]

# YouTube 頻道探索搜尋關鍵字（英文）
DISCOVERY_YOUTUBE_KEYWORDS_EN = [
    "best book summary channel 2026",
    "book review YouTube channel",
    "nonfiction book summary",
    "business book summary channel",
]

# 每個關鍵字搜尋幾個影片（用來提取頻道資訊）
DISCOVERY_SEARCH_LIMIT_PER_KEYWORD = 5

# 固定書評網站清單（用於網站探索）
DISCOVERY_KNOWN_WEBSITES = [
    {
        "name": "Goodreads",
        "url": "https://www.goodreads.com",
        "language": "en",
        "description": "全球最大書評社群，讀者評分與書單推薦",
    },
    {
        "name": "豆瓣讀書",
        "url": "https://book.douban.com",
        "language": "zh",
        "description": "中文書評社群，書籍評分與閱讀分享",
    },
    {
        "name": "閱讀前哨站",
        "url": "https://readingoutpost.com",
        "language": "zh",
        "description": "繁體中文說書部落格，深度書評與閱讀心得",
    },
]
