# -*- coding: utf-8 -*-
"""讀書 Agent v2 — CLI 入口

v2 核心流程：暢銷書排行榜 → YouTube 搜尋說書影片 → 字幕擷取 →
Gemini 深度重點整理 → 中英雙語 → 新 Telegram Bot 發送。

保留舊版頻道 RSS 蒐集作為自訂頻道追蹤功能。

用法：
    python -m src.reading_agent --mode weekly          # 暢銷書 → 搜尋 → 整理 → 發送
    python -m src.reading_agent --mode initial         # 首次蒐集（範圍更大）
    python -m src.reading_agent --analyze-url <url>    # 直接整理指定 YouTube 影片
    python -m src.reading_agent --list-books           # 列出本週暢銷書
    python -m src.reading_agent --test-telegram        # 測試新 Bot 連線
    python -m src.reading_agent --list-channels        # 列出自訂追蹤頻道
    python -m src.reading_agent --dry-run              # 只蒐集不發送
"""

import argparse
import asyncio
import io
import json
import logging
import re
import sys
from datetime import datetime

from .ai_weekly import AIWeeklyCollector
from .bestseller_scraper import BestsellerScraper
from .config import (
    BOOK_CATEGORIES,
    CUSTOM_CHANNELS_FILE,
    CUSTOM_URLS_FILE,
    load_channels,
)
from .content_analyzer import ContentAnalyzer
from .models import Book, Video
from .reporter import ReportGenerator
from .storage import VideoStorage
from .telegram_sender import TelegramSender
from .transcript_extractor import TranscriptExtractor
from .youtube_client import YouTubeClient
from .youtube_searcher import YouTubeSearcher

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False):
    """設定日誌格式與等級

    Windows 終端預設使用 cp950 編碼，無法顯示 emoji，
    因此強制使用 UTF-8 編碼輸出。
    """
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    )
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.basicConfig(level=level, handlers=[handler])


# =========================================================
# v2 主流程：暢銷書 → YouTube 搜尋 → 字幕 → 重點整理 → 發送
# =========================================================

async def _run_v2_collect(mode: str, dry_run: bool = False):
    """v2 蒐集流程

    1. 爬取暢銷書排行榜（博客來/誠品/金石堂/Amazon）
    2. 用書名搜尋 YouTube 說書影片
    3. 擷取影片字幕
    4. Gemini 深度重點整理（英文翻譯成中文）
    5. 檢查自訂頻道（若有）
    6. 產生報告並發送 Telegram

    Args:
        mode: 蒐集模式（weekly / initial）
        dry_run: 若為 True，只蒐集不發送
    """
    start_time = datetime.now()
    logger.info("=" * 50)
    logger.info("📚 讀書 Agent v2 啟動")
    logger.info("模式: %s | Dry Run: %s", mode, dry_run)
    logger.info("=" * 50)

    # === 0. 來源探索（若超過週期則自動觸發） ===
    try:
        from .source_discovery import SourceDiscovery
        discovery = SourceDiscovery()
        await discovery.discover_if_due()
    except Exception as e:
        # 來源探索失敗不影響主流程
        logger.warning("⚠️ 來源探索檢查失敗（不影響主流程）: %s", e)

    # === 1. 爬取暢銷書排行榜 ===
    logger.info("📊 開始爬取暢銷書排行榜...")
    scraper = BestsellerScraper()
    books = await scraper.scrape_all()
    logger.info("📚 暢銷書蒐集完成：共 %d 本（去重後）", len(books))

    if not books:
        logger.warning("⚠️ 未取得任何暢銷書，流程中止")
        return

    # === 2. YouTube 搜尋說書影片 ===
    logger.info("🔍 開始搜尋 YouTube 說書影片...")
    searcher = YouTubeSearcher()
    book_videos: dict[str, list[Video]] = {}
    book_videos = await searcher.search_all_books(books)

    # 統計搜尋結果
    total_videos = sum(len(v) for v in book_videos.values())
    books_with_videos = sum(1 for v in book_videos.values() if v)
    logger.info(
        "🎬 搜尋完成：%d 本書找到影片，共 %d 部（>5分鐘）",
        books_with_videos, total_videos,
    )

    # === 3. 擷取影片字幕 ===
    logger.info("📝 開始擷取影片字幕...")
    extractor = TranscriptExtractor()
    for book_title, videos in book_videos.items():
        if videos:
            book_videos[book_title] = await extractor.extract_batch(videos)

    transcript_count = sum(
        1 for vlist in book_videos.values()
        for v in vlist if v.transcript
    )
    logger.info("📝 字幕擷取完成：%d 部影片取得字幕", transcript_count)

    # === 4. Gemini 深度重點整理 ===
    logger.info("🧠 開始 Gemini 深度重點整理...")
    analyzer = ContentAnalyzer()
    for book_title, videos in book_videos.items():
        if videos:
            try:
                book_videos[book_title] = await analyzer.analyze_batch(videos)
            except Exception as e:
                logger.warning("⚠️ 書籍 [%s] 整理失敗: %s", book_title, e)

    analyzed_count = sum(
        1 for vlist in book_videos.values()
        for v in vlist if v.key_points_zh
    )
    logger.info("🧠 重點整理完成：%d 部影片已整理", analyzed_count)

    # === 5. 自訂頻道檢查（若有） ===
    custom_videos = await _check_custom_channels(mode)

    # === 5.5 AI Weekly（--mode weekly 時同時執行） ===
    ai_videos: list[Video] = []
    try:
        ai_collector = AIWeeklyCollector()
        days_back = 30 if mode == "initial" else 7
        ai_videos = await ai_collector.collect(days_back=days_back)
        logger.info("🤖 AI Weekly 蒐集完成：%d 部影片", len(ai_videos))
    except Exception as e:
        logger.warning("⚠️ AI Weekly 蒐集失敗（不影響暢銷書流程）: %s", e)

    # === 6. 儲存影片資料 ===
    all_videos = []
    for vlist in book_videos.values():
        all_videos.extend(vlist)
    all_videos.extend(custom_videos)
    all_videos.extend(ai_videos)

    if all_videos:
        video_storage = VideoStorage()
        video_storage.save_videos(all_videos)

    # === 7. 產生報告 ===
    reporter = ReportGenerator()
    # 只保留有找到影片的書
    active_books = [b for b in books if book_videos.get(b.title)]
    segments = reporter.generate_v2(active_books, book_videos, custom_videos or None)

    # AI Weekly 報告（獨立分段，接在暢銷書報告後面）
    if ai_videos:
        ai_segments = reporter.generate_ai_weekly(ai_videos)
        segments.extend(ai_segments)

    # === 8. 預覽報告 ===
    logger.info("📋 報告預覽：")
    utf8_out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace",
    )
    for segment in segments:
        utf8_out.write("\n" + segment + "\n")
        utf8_out.flush()

    # === 9. 發送 Telegram ===
    if dry_run:
        logger.info("🔇 Dry Run 模式，跳過 Telegram 發送")
    else:
        logger.info("📨 發送 Telegram 報告...")
        try:
            sender = TelegramSender()
            success = await sender.send_segments(segments)
            if success:
                logger.info("✅ Telegram 報告發送成功！")
            else:
                logger.error("❌ Telegram 報告部分發送失敗")
        except ValueError as e:
            logger.error("❌ Telegram 設定錯誤: %s", e)
        except Exception as e:
            logger.error("❌ Telegram 發送失敗: %s", e)

    # === 10. 完成統計 ===
    elapsed = datetime.now() - start_time
    logger.info("=" * 50)
    logger.info("✅ 讀書 Agent v2 蒐集流程完成")
    logger.info(
        "📚 暢銷書: %d | 📺 影片: %d | 🧠 已整理: %d | 🤖 AI: %d | 耗時: %s",
        len(active_books), total_videos, analyzed_count, len(ai_videos), elapsed,
    )
    logger.info("=" * 50)


# =========================================================
# 自訂頻道追蹤（沿用舊版 RSS 機制）
# =========================================================

async def _check_custom_channels(mode: str = "weekly") -> list[Video]:
    """檢查自訂追蹤頻道的新影片

    使用舊版 YouTubeClient (RSS) 來監控使用者自訂的頻道。
    取得新影片後，擷取字幕並做重點整理。

    Args:
        mode: 蒐集模式

    Returns:
        已整理的自訂頻道影片列表
    """
    if not CUSTOM_CHANNELS_FILE.exists():
        return []

    try:
        with open(CUSTOM_CHANNELS_FILE, "r", encoding="utf-8") as f:
            custom_channels = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("載入自訂頻道失敗: %s", e)
        return []

    if not custom_channels:
        return []

    days_back = 30 if mode == "initial" else 7
    logger.info("📡 檢查 %d 個自訂頻道（%d 天內）...", len(custom_channels), days_back)

    async with YouTubeClient(channels=custom_channels) as client:
        videos = await client.fetch_all_channels(days_back=days_back)

    if not videos:
        logger.info("📭 自訂頻道無新影片")
        return []

    logger.info("📺 自訂頻道找到 %d 部新影片，開始整理...", len(videos))

    # 字幕擷取 + 重點整理
    extractor = TranscriptExtractor()
    videos = await extractor.extract_batch(videos)

    analyzer = ContentAnalyzer()
    try:
        videos = await analyzer.analyze_batch(videos)
    except Exception as e:
        logger.warning("⚠️ 自訂頻道影片整理失敗: %s", e)

    return videos


# =========================================================
# 直接分析指定 YouTube URL
# =========================================================

async def _run_analyze_url(url: str, dry_run: bool = False):
    """直接分析指定的 YouTube 影片 URL

    擷取字幕 → Gemini 重點整理 → 發送 Telegram

    Args:
        url: YouTube 影片 URL
        dry_run: 若為 True，只整理不發送
    """
    logger.info("=" * 50)
    logger.info("📺 直接分析 YouTube 影片")
    logger.info("URL: %s", url)
    logger.info("=" * 50)

    # 從 URL 擷取 video_id
    video_id = _extract_video_id_from_url(url)
    if not video_id:
        logger.error("❌ 無法從 URL 擷取影片 ID: %s", url)
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
    logger.info("📝 擷取字幕...")
    extractor = TranscriptExtractor()
    videos = await extractor.extract_batch([video])
    video = videos[0]

    if not video.transcript:
        logger.warning("⚠️ 無法取得字幕，嘗試以描述進行整理")

    # Gemini 重點整理
    logger.info("🧠 Gemini 深度重點整理...")
    analyzer = ContentAnalyzer()
    try:
        videos = await analyzer.analyze_batch([video])
        video = videos[0]
    except Exception as e:
        logger.error("❌ 重點整理失敗: %s", e)
        return

    # 顯示結果
    utf8_out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace",
    )
    result_text = (
        f"📺 影片分析結果\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔗 {url}\n"
    )
    if video.key_points_zh:
        result_text += f"\n【中文重點整理】\n{video.key_points_zh}\n"
    if video.key_points_original and video.language == "en":
        result_text += f"\n【English Key Points】\n{video.key_points_original}\n"
    result_text += f"━━━━━━━━━━━━━━━━━━\n🤖 Agent Army ｜ 讀書 Agent v2"

    utf8_out.write("\n" + result_text + "\n")
    utf8_out.flush()

    # 發送 Telegram
    if dry_run:
        logger.info("🔇 Dry Run 模式，跳過 Telegram 發送")
    else:
        logger.info("📨 發送 Telegram...")
        try:
            sender = TelegramSender()
            success = await sender.send_segments([result_text])
            if success:
                logger.info("✅ 發送成功！")
            else:
                logger.error("❌ 發送失敗")
        except Exception as e:
            logger.error("❌ 發送失敗: %s", e)


def _extract_video_id_from_url(url: str) -> str:
    """從 YouTube URL 擷取影片 ID"""
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
# 自訂頻道管理
# =========================================================

def _add_custom_channel(channel_input: str):
    """新增自訂追蹤頻道

    Args:
        channel_input: 頻道 URL 或 channel ID
    """
    # 嘗試從 URL 中取得 channel 資訊
    channel_id = channel_input.strip()
    channel_name = channel_id

    # 載入現有自訂頻道列表
    custom_channels = []
    if CUSTOM_CHANNELS_FILE.exists():
        try:
            with open(CUSTOM_CHANNELS_FILE, "r", encoding="utf-8") as f:
                custom_channels = json.load(f)
        except (json.JSONDecodeError, OSError):
            custom_channels = []

    # 檢查是否已存在
    for ch in custom_channels:
        if ch.get("channel_id") == channel_id or ch.get("url") == channel_input:
            print(f"⚠️ 頻道已存在: {ch.get('name', channel_id)}")
            return

    # 新增頻道
    new_channel = {
        "channel_id": channel_id,
        "name": channel_name,
        "url": channel_input if channel_input.startswith("http") else "",
        "category": "general",
        "description": "使用者自訂追蹤頻道",
    }
    custom_channels.append(new_channel)

    # 儲存
    try:
        with open(CUSTOM_CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(custom_channels, f, ensure_ascii=False, indent=2)
        print(f"✅ 已新增自訂頻道: {channel_name}")
        print(f"💡 可編輯 {CUSTOM_CHANNELS_FILE} 修改頻道名稱和分類")
    except OSError as e:
        print(f"❌ 儲存失敗: {e}")


# =========================================================
# 列出暢銷書（快速預覽，不搜尋影片）
# =========================================================

async def _run_list_books():
    """列出各平台暢銷書排行榜"""
    logger.info("📊 爬取暢銷書排行榜...")
    scraper = BestsellerScraper()
    books = await scraper.scrape_all()

    utf8_out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace",
    )

    utf8_out.write("\n📚 本週暢銷書排行榜（跨平台合併）：\n")
    utf8_out.write("━" * 40 + "\n")

    for i, book in enumerate(books, 1):
        lang_icon = "🌐" if book.language == "en" else "🇹🇼"
        utf8_out.write(f"{i:2d}. {lang_icon} 《{book.title}》\n")
        if book.author:
            utf8_out.write(f"    👤 {book.author}\n")
        if book.sources:
            utf8_out.write(f"    📍 {' / '.join(book.sources)}\n")
        utf8_out.write("\n")
        utf8_out.flush()

    utf8_out.write(f"共 {len(books)} 本暢銷書\n")
    utf8_out.flush()


# =========================================================
# AI Weekly 獨立執行
# =========================================================

async def _run_ai_weekly(dry_run: bool = False):
    """獨立執行 AI Weekly 蒐集流程

    搜尋 AI 相關影片 → 字幕擷取 → Gemini 分析 → 發送 Telegram

    Args:
        dry_run: 若為 True，只蒐集不發送
    """
    start_time = datetime.now()
    logger.info("=" * 50)
    logger.info("🤖 AI Weekly 獨立執行模式")
    logger.info("Dry Run: %s", dry_run)
    logger.info("=" * 50)

    # 蒐集 AI 影片（包含固定頻道 + 關鍵字搜尋 + 字幕 + 分析）
    collector = AIWeeklyCollector()
    ai_videos = await collector.collect(days_back=7)

    if not ai_videos:
        logger.warning("⚠️ AI Weekly 未找到任何影片，流程中止")
        return

    # 儲存影片
    video_storage = VideoStorage()
    video_storage.save_videos(ai_videos)

    # 產生報告
    reporter = ReportGenerator()
    segments = reporter.generate_ai_weekly(ai_videos)

    # 預覽
    logger.info("📋 AI Weekly 報告預覽：")
    utf8_out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace",
    )
    for segment in segments:
        utf8_out.write("\n" + segment + "\n")
        utf8_out.flush()

    # 發送 Telegram
    if dry_run:
        logger.info("🔇 Dry Run 模式，跳過 Telegram 發送")
    else:
        logger.info("📨 發送 AI Weekly Telegram 報告...")
        try:
            sender = TelegramSender()
            success = await sender.send_segments(segments)
            if success:
                logger.info("✅ AI Weekly 發送成功！")
            else:
                logger.error("❌ AI Weekly 部分發送失敗")
        except ValueError as e:
            logger.error("❌ Telegram 設定錯誤: %s", e)
        except Exception as e:
            logger.error("❌ 發送失敗: %s", e)

    elapsed = datetime.now() - start_time
    analyzed_count = sum(1 for v in ai_videos if v.key_points_zh)
    logger.info("=" * 50)
    logger.info("✅ AI Weekly 完成")
    logger.info(
        "🤖 影片: %d | 🧠 已整理: %d | 耗時: %s",
        len(ai_videos), analyzed_count, elapsed,
    )
    logger.info("=" * 50)


# =========================================================
# 舊版相容（保留 v1 蒐集功能）
# =========================================================

async def _run_v1_collect(mode: str, dry_run: bool = False):
    """舊版 v1 蒐集流程（頻道 RSS → Gemini 摘要）

    保留供向下相容，使用 --legacy 旗標觸發。
    """
    from .summarizer import summarize_videos

    start_time = datetime.now()
    logger.info("📚 讀書 Agent v1（舊版）啟動")

    days_back = 30 if mode == "initial" else 7

    async with YouTubeClient() as client:
        videos = await client.fetch_all_channels(days_back=days_back)

    logger.info("擷取完成：共 %d 部影片", len(videos))

    if videos:
        video_storage = VideoStorage()
        video_storage.save_videos(videos)

    from .models import ReadingReport
    report = ReadingReport(
        period_start=(datetime.now().replace(
            day=datetime.now().day
        )).strftime("%Y-%m-%d"),
        period_end=datetime.now().strftime("%Y-%m-%d"),
        videos=videos,
        mode=mode,
    )

    summary = None
    if videos:
        try:
            summary = await summarize_videos(videos)
        except Exception as e:
            logger.warning("Gemini 摘要失敗: %s", e)

    reporter = ReportGenerator()
    segments = reporter.generate(report, summary=summary)

    if not dry_run:
        # 使用舊版 Bot Token
        from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        sender = TelegramSender(
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID,
        )
        await sender.send_report(report, summary=summary)

    logger.info("✅ v1 流程完成")


# =========================================================
# 舊版保留功能
# =========================================================

async def _run_test_telegram():
    """測試 Telegram Bot 連線"""
    logger.info("🔧 測試 Telegram Bot 連線...")
    try:
        sender = TelegramSender()
        success = await sender.test_connection()
        if success:
            logger.info("✅ Telegram 連線測試通過！")
        else:
            logger.error("❌ Telegram 連線測試失敗")
            sys.exit(1)
    except ValueError as e:
        logger.error("❌ 設定錯誤: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("❌ 未預期錯誤: %s", e)
        sys.exit(1)


def _list_channels():
    """列出目前追蹤的頻道（預設 + 自訂）"""
    channels = load_channels()
    print("\n📚 預設說書頻道：")
    print("━" * 40)
    for i, ch in enumerate(channels, 1):
        cat = ch.get("category", "general")
        cat_info = BOOK_CATEGORIES.get(cat, {"icon": "📺", "name": cat})
        print(f"{i}. {cat_info['icon']} {ch['name']}")
        print(f"   分類: {cat_info['name']}")
        print(f"   URL: {ch.get('url', 'N/A')}")
        if ch.get("description"):
            print(f"   簡介: {ch['description']}")
        print()
    print(f"共 {len(channels)} 個預設頻道")

    # 顯示自訂頻道
    if CUSTOM_CHANNELS_FILE.exists():
        try:
            with open(CUSTOM_CHANNELS_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
            if custom:
                print(f"\n📌 自訂追蹤頻道：")
                print("━" * 40)
                for i, ch in enumerate(custom, 1):
                    print(f"{i}. 📺 {ch.get('name', ch.get('channel_id', '?'))}")
                    if ch.get("url"):
                        print(f"   URL: {ch['url']}")
                    print()
                print(f"共 {len(custom)} 個自訂頻道")
        except (json.JSONDecodeError, OSError):
            pass

    print(f"\n💡 用 --add-channel <url/id> 新增自訂追蹤頻道")


# =========================================================
# CLI 入口
# =========================================================

def main():
    """CLI 入口點"""
    parser = argparse.ArgumentParser(
        description="讀書 Agent v2 — 暢銷書說書影片蒐集與深度整理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python -m src.reading_agent --mode weekly            # 暢銷書→搜尋→整理→發送（含 AI Weekly）
  python -m src.reading_agent --mode weekly --dry-run   # 只整理不發送
  python -m src.reading_agent --ai-weekly               # 獨立執行 AI Weekly
  python -m src.reading_agent --ai-weekly --dry-run     # AI Weekly 不發送
  python -m src.reading_agent --analyze-url <url>       # 直接分析某個影片
  python -m src.reading_agent --list-books              # 列出暢銷書
  python -m src.reading_agent --add-channel <url>       # 新增自訂追蹤頻道
  python -m src.reading_agent --test-telegram           # 測試 Bot 連線
  python -m src.reading_agent --list-channels           # 列出追蹤頻道
  python -m src.reading_agent --mode weekly --legacy    # 使用舊版 v1 流程
  python -m src.reading_agent --bot                     # 啟動 Telegram Bot 互動模式
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["initial", "weekly"],
        help="蒐集模式：initial（首次大範圍）或 weekly（每週）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只蒐集和整理，不發送 Telegram",
    )
    parser.add_argument(
        "--analyze-url",
        metavar="URL",
        help="直接分析指定的 YouTube 影片 URL",
    )
    parser.add_argument(
        "--list-books",
        action="store_true",
        help="列出各平台暢銷書排行榜",
    )
    parser.add_argument(
        "--add-channel",
        metavar="CHANNEL",
        help="新增自訂追蹤頻道（URL 或 channel ID）",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="測試 Telegram Bot 連線",
    )
    parser.add_argument(
        "--list-channels",
        action="store_true",
        help="列出目前追蹤的頻道",
    )
    parser.add_argument(
        "--ai-weekly",
        action="store_true",
        help="獨立執行 AI Weekly 資訊蒐集與整理",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="使用舊版 v1 流程（頻道 RSS → Gemini 摘要）",
    )
    parser.add_argument(
        "--bot",
        action="store_true",
        help="啟動 Telegram Bot 互動模式（長駐 polling）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="顯示詳細日誌（DEBUG 等級）",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    # 不需要 async 的操作
    if args.list_channels:
        _list_channels()
        return

    if args.add_channel:
        _add_custom_channel(args.add_channel)
        return

    if args.bot:
        from .telegram_bot_handler import TelegramBotHandler
        bot = TelegramBotHandler()
        bot.run()
        return

    # 需要 async 的操作
    if args.list_books:
        asyncio.run(_run_list_books())
        return

    if args.test_telegram:
        asyncio.run(_run_test_telegram())
        return

    if args.ai_weekly:
        asyncio.run(_run_ai_weekly(args.dry_run))
        return

    if args.analyze_url:
        asyncio.run(_run_analyze_url(args.analyze_url, args.dry_run))
        return

    if args.mode:
        if args.legacy:
            asyncio.run(_run_v1_collect(args.mode, args.dry_run))
        else:
            asyncio.run(_run_v2_collect(args.mode, args.dry_run))
        return

    # 無有效動作時顯示說明
    parser.print_help()
    sys.exit(1)


# 支援 python -m src.reading_agent 呼叫
if __name__ == "__main__":
    main()
