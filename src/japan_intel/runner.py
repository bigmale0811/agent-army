# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — CLI 入口

提供命令列介面來執行蒐集、產生報告、發送 Telegram。
支援多種執行模式和選項。

用法：
    python -m src.japan_intel.runner --mode weekly       # 每週蒐集
    python -m src.japan_intel.runner --mode initial      # 首次蒐集（近一年）
    python -m src.japan_intel.runner --test-telegram     # 測試 Telegram 連線
    python -m src.japan_intel.runner --mode weekly --dry-run  # 只蒐集不發送
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from .collector import JapanIntelCollector
from .reporter import ReportGenerator
from .storage import ArticleStorage, ReportStorage
from .summarizer import summarize_report
from .telegram_sender import TelegramSender

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False):
    """設定日誌格式與等級

    Windows 終端預設使用 cp950 編碼，無法顯示 emoji，
    因此強制使用 UTF-8 編碼輸出。
    """
    level = logging.DEBUG if verbose else logging.INFO
    # Windows 終端 cp950 不支援 emoji，強制 UTF-8
    handler = logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    )
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.basicConfig(level=level, handlers=[handler])


async def _run_collect(mode: str, dry_run: bool = False):
    """執行蒐集流程

    Args:
        mode: 蒐集模式（initial / weekly）
        dry_run: 若為 True，只蒐集和產生報告但不發送 Telegram
    """
    start_time = datetime.now()
    logger.info("=" * 50)
    logger.info("日本博弈資訊蒐集 Agent 啟動")
    logger.info("模式: %s | Dry Run: %s", mode, dry_run)
    logger.info("=" * 50)

    # === 1. 蒐集文章 ===
    logger.info("📡 開始蒐集資訊...")
    collector = JapanIntelCollector()
    report = await collector.collect(mode=mode)

    logger.info(
        "📊 蒐集完成：共 %d 篇文章，耗時 %s",
        report.total_count,
        datetime.now() - start_time,
    )

    # === 2. 儲存報告 ===
    report_storage = ReportStorage()
    report_path = report_storage.save_report(report)
    logger.info("💾 報告已儲存: %s", report_path)

    # === 3. Gemini 翻譯＋重點整理 ===
    summaries = None
    if report.total_count > 0:
        logger.info("🧠 使用 Gemini 進行翻譯與重點整理...")
        try:
            summaries = await summarize_report(report)
            logger.info("✅ Gemini 摘要完成：%d 個分類", len(summaries))
        except Exception as e:
            logger.warning("⚠️ Gemini 摘要失敗，將使用原文格式: %s", e)
            summaries = None

    # === 4. 預覽報告（輸出到終端） ===
    reporter = ReportGenerator()
    segments = reporter.generate(report, summaries=summaries)
    logger.info("📋 報告預覽：")
    for segment in segments:
        print("\n" + segment)

    # === 5. 發送 Telegram ===
    if dry_run:
        logger.info("🔇 Dry Run 模式，跳過 Telegram 發送")
    else:
        logger.info("📨 發送 Telegram 報告...")
        try:
            sender = TelegramSender()
            # 傳入 summaries 讓 sender 使用智慧摘要格式
            success = await sender.send_report(report, summaries=summaries)
            if success:
                logger.info("✅ Telegram 報告發送成功！")
            else:
                logger.error("❌ Telegram 報告發送部分失敗")
        except ValueError as e:
            logger.error("❌ Telegram 設定錯誤: %s", e)
        except Exception as e:
            logger.error("❌ Telegram 發送失敗: %s", e)

    # === 5. 完成統計 ===
    elapsed = datetime.now() - start_time
    logger.info("=" * 50)
    logger.info("✅ 蒐集流程完成")
    logger.info("📈 文章數: %d | 耗時: %s", report.total_count, elapsed)
    logger.info("=" * 50)


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


def main():
    """CLI 入口點"""
    parser = argparse.ArgumentParser(
        description="日本博弈資訊蒐集 Agent — 自動蒐集日本賭場、博弈、電子遊戲產業資訊",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python -m src.japan_intel.runner --mode weekly           # 蒐集本週資訊並發送
  python -m src.japan_intel.runner --mode initial          # 首次蒐集近一年資訊
  python -m src.japan_intel.runner --mode weekly --dry-run  # 只蒐集不發送
  python -m src.japan_intel.runner --test-telegram         # 測試 Telegram 連線
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["initial", "weekly"],
        help="蒐集模式：initial（近一年）或 weekly（近一週）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只蒐集和產生報告，不發送 Telegram",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="測試 Telegram Bot 連線",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="顯示詳細日誌（DEBUG 等級）",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    # 至少要指定一個動作
    if not args.mode and not args.test_telegram:
        parser.print_help()
        sys.exit(1)

    # 執行對應動作
    if args.test_telegram:
        asyncio.run(_run_test_telegram())
    elif args.mode:
        asyncio.run(_run_collect(args.mode, args.dry_run))


# 支援 python -m src.japan_intel.runner 呼叫
if __name__ == "__main__":
    main()
