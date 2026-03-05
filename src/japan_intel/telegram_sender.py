# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — Telegram 發送模組

透過 python-telegram-bot 將報告傳送到指定的 Telegram 聊天室。
支援長訊息自動分段、重試機制、連線測試。
"""

import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_SEND_DELAY
from .models import Report
from .reporter import ReportGenerator

logger = logging.getLogger(__name__)


class TelegramSender:
    """Telegram 訊息發送器

    功能：
    - 發送報告（自動分段）
    - 發送純文字訊息
    - 測試 Bot 連線與 Chat ID 有效性
    - 發送失敗自動重試（最多 3 次）
    """

    def __init__(
        self,
        bot_token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
    ):
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN 未設定，請檢查 .env 檔案")
        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID 未設定，請檢查 .env 檔案")

        self._bot = Bot(token=bot_token)
        self._chat_id = chat_id
        self._reporter = ReportGenerator()

    async def send_report(
        self,
        report: Report,
        summaries: Optional[dict[str, str]] = None,
    ) -> bool:
        """發送蒐集報告

        將報告格式化為繁體中文文字，自動處理分段發送。
        若提供 summaries（Gemini 摘要），使用智慧摘要格式。

        Args:
            report: 蒐集報告物件
            summaries: Gemini 產生的各分類摘要（可選）

        Returns:
            是否全部發送成功
        """
        self._summaries = summaries
        if report.mode == "initial" and report.total_count > 50:
            return await self._send_initial_report(report)
        else:
            return await self._send_weekly_report(report)

    async def _send_weekly_report(self, report: Report) -> bool:
        """發送週報"""
        segments = self._reporter.generate(report, summaries=self._summaries)
        success = True

        for i, segment in enumerate(segments):
            logger.info("發送第 %d/%d 段...", i + 1, len(segments))
            if not await self.send_text(segment):
                success = False
            # 段落間間隔，避免觸發 Telegram 限速
            if i < len(segments) - 1:
                await asyncio.sleep(TELEGRAM_SEND_DELAY)

        return success

    async def _send_initial_report(self, report: Report) -> bool:
        """發送年度報告（按月分批）"""
        # 先發一則總覽訊息
        overview = (
            "📊 日本博弈產業年度總覽\n"
            f"📅 {report.period_start} ~ {report.period_end}\n"
            f"📈 共蒐集 {report.total_count} 則資訊\n"
            "━" * 18 + "\n"
            "以下按月份分批發送...\n"
        )
        await self.send_text(overview)
        await asyncio.sleep(TELEGRAM_SEND_DELAY)

        # 按月份分批
        batches = self._reporter.generate_monthly_reports(report)
        success = True

        for batch_idx, segments in enumerate(batches):
            for seg_idx, segment in enumerate(segments):
                if not await self.send_text(segment):
                    success = False
                await asyncio.sleep(TELEGRAM_SEND_DELAY)

        return success

    async def send_text(self, text: str, max_retries: int = 3) -> bool:
        """發送單則文字訊息，帶重試機制

        Args:
            text: 要發送的文字
            max_retries: 最大重試次數

        Returns:
            是否發送成功
        """
        for attempt in range(1, max_retries + 1):
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    # 不使用 Markdown 解析以避免特殊字元問題
                    disable_web_page_preview=True,
                )
                logger.debug("訊息發送成功（%d 字）", len(text))
                return True

            except RetryAfter as e:
                # Telegram 限速，等待指定時間後重試
                wait = e.retry_after
                logger.warning(
                    "Telegram 限速，等待 %d 秒後重試（第 %d/%d 次）",
                    wait, attempt, max_retries,
                )
                await asyncio.sleep(wait)

            except TimedOut:
                logger.warning(
                    "發送逾時（第 %d/%d 次）", attempt, max_retries,
                )
                await asyncio.sleep(2 * attempt)

            except TelegramError as e:
                logger.error(
                    "Telegram 錯誤（第 %d/%d 次）: %s",
                    attempt, max_retries, e,
                )
                if attempt == max_retries:
                    return False
                await asyncio.sleep(2 * attempt)

        return False

    async def test_connection(self) -> bool:
        """測試 Bot 連線和 Chat ID 是否有效

        發送一則測試訊息來驗證設定是否正確。

        Returns:
            連線是否成功
        """
        try:
            # 先測試 Bot Token 有效性
            me = await self._bot.get_me()
            logger.info("Bot 連線成功: @%s (%s)", me.username, me.first_name)

            # 發送測試訊息
            test_msg = (
                "🤖 Agent Army — 連線測試\n"
                "━" * 18 + "\n"
                "✅ Telegram Bot 連線正常\n"
                f"🆔 Bot: @{me.username}\n"
                f"📬 Chat ID: {self._chat_id}\n"
                "━" * 18 + "\n"
                "日本博弈資訊蒐集 Agent 已就緒！"
            )
            result = await self.send_text(test_msg)

            if result:
                logger.info("測試訊息發送成功")
            else:
                logger.error("測試訊息發送失敗")
            return result

        except TelegramError as e:
            logger.error("Bot 連線失敗: %s", e)
            return False
