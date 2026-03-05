# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — 設定模組

載入環境變數並定義所有常數：搜尋關鍵字、來源 URL、分類對照表等。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# === 載入 .env 環境變數 ===
# 從專案根目錄載入 .env 檔案，override=True 確保 .env 優先於系統環境變數
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# === Telegram 設定 ===
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# === Gemini API 設定 ===
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# === 路徑設定 ===
DATA_DIR: Path = _PROJECT_ROOT / "data" / "japan_intel"
ARTICLES_DIR: Path = DATA_DIR / "articles"
REPORTS_DIR: Path = DATA_DIR / "reports"

# === HTTP 客戶端設定 ===
# 請求間隔（秒），避免對來源網站造成負擔
REQUEST_DELAY: float = 1.5
# 請求超時（秒）
REQUEST_TIMEOUT: int = 30
# 最大重試次數
MAX_RETRIES: int = 3
# User-Agent 標頭
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# === 蒐集模式設定 ===
# initial 模式蒐集天數（約一年）
INITIAL_DAYS: int = 365
# weekly 模式蒐集天數
WEEKLY_DAYS: int = 7

# === 文章分類 ===
# 分類代碼與對應的繁中顯示名稱、圖示
CATEGORIES: dict[str, dict[str, str]] = {
    "ir_casino": {
        "name": "IR 綜合度假村",
        "icon": "🏗️",
    },
    "online_gambling": {
        "name": "線上博弈",
        "icon": "🎰",
    },
    "pachinko": {
        "name": "柏青哥/角子機",
        "icon": "🎯",
    },
    "gaming": {
        "name": "電子遊戲 & 運彩",
        "icon": "🎮",
    },
    "regulation": {
        "name": "法規與政策",
        "icon": "📜",
    },
    "other": {
        "name": "其他",
        "icon": "📰",
    },
}

# === 搜尋關鍵字 ===
# 日文關鍵字（用於 Google News JP、Yahoo Japan、NHK）
SEARCH_KEYWORDS_JA: list[str] = [
    "日本 カジノ IR",
    "大阪 IR 統合型リゾート",
    "日本 オンラインカジノ",
    "オンラインカジノ 規制",
    "パチンコ パチスロ 規制",
    "パチンコ 業界 動向",
    "日本 ギャンブル 法律",
    "日本 スポーツベッティング",
    "日本 宝くじ toto",
    "カジノ管理委員会",
    "長崎 IR",
    "横浜 カジノ",
]

# 英文關鍵字（用於 Google News EN、GGRAsia、CalvinAyre 等）
SEARCH_KEYWORDS_EN: list[str] = [
    "Japan casino IR",
    "Japan integrated resort",
    "Osaka IR MGM",
    "Japan online gambling",
    "Japan gambling regulation",
    "pachinko industry Japan",
    "Japan sports betting",
    "Japan gaming market",
    "Nagasaki IR",
    "Japan casino commission",
]

# === 分類關鍵字對照表 ===
# 用於自動將文章歸類到對應分類
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ir_casino": [
        "IR", "integrated resort", "統合型リゾート", "カジノ",
        "casino", "MGM", "大阪", "Osaka", "長崎", "Nagasaki",
        "横浜", "Yokohama", "度假村", "賭場",
    ],
    "online_gambling": [
        "オンラインカジノ", "online casino", "online gambling",
        "線上博弈", "線上賭場", "internet gambling", "iGaming",
        "オンラインギャンブル",
    ],
    "pachinko": [
        "パチンコ", "パチスロ", "pachinko", "pachislot",
        "柏青哥", "角子機", "遊技機", "遊技場",
    ],
    "gaming": [
        "ゲーミング", "gaming", "スポーツベッティング",
        "sports betting", "toto", "宝くじ", "lottery",
        "運彩", "電子遊戲", "esports", "eスポーツ",
    ],
    "regulation": [
        "規制", "法律", "regulation", "law", "legal",
        "カジノ管理委員会", "casino commission", "法規",
        "取り締まり", "enforcement", "違法", "illegal",
    ],
}

# === 資訊來源 URL ===
SOURCES: dict[str, dict[str, str]] = {
    "google_news_ja": {
        "name": "Google News (日本語)",
        "base_url": "https://news.google.com/rss/search",
        "language": "ja",
    },
    "google_news_en": {
        "name": "Google News (English)",
        "base_url": "https://news.google.com/rss/search",
        "language": "en",
    },
    "ggr_asia": {
        "name": "GGRAsia",
        "base_url": "https://www.ggrasia.com",
        "language": "en",
    },
    "inside_asian_gaming": {
        "name": "Inside Asian Gaming",
        "base_url": "https://www.asgam.com",
        "language": "en",
    },
    "calvin_ayre": {
        "name": "CalvinAyre",
        "base_url": "https://calvinayre.com/tag/japan",
        "language": "en",
    },
    "agb_nippon": {
        "name": "AGB Nippon",
        "base_url": "https://agbrief.com/market/japan",
        "language": "en",
    },
    "yahoo_japan": {
        "name": "Yahoo Japan News",
        "base_url": "https://news.yahoo.co.jp",
        "language": "ja",
    },
}

# === Telegram 訊息設定 ===
# Telegram 單則訊息最大字元數
TELEGRAM_MAX_LENGTH: int = 4096
# 分段發送間隔（秒），避免觸發 Telegram 限速
TELEGRAM_SEND_DELAY: float = 1.0
