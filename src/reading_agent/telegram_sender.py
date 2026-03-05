# -*- coding: utf-8 -*-
"""讀書 Agent v2 — Telegram 發送模組

透過 python-telegram-bot 將讀書摘要報告傳送到指定的 Telegram 聊天室。
v2：預設使用新的讀書專用 Bot（READING_BOT_TOKEN），舊 Bot 保留相容。
"""

import asyncio
import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError, RetryAfter, TimedOut

from .config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_SEND_DELAY,
    READING_BOT_TOKEN,
    READING_CHAT_ID,
)
from .models import ReadingReport
from .reporter import ReportGenerator

logger = logging.getLogger(__name__)


class TelegramSender:
    """Telegram 訊息發送器

    功能：
    - 發送讀書摘要報告（自動分段）
    - 發送 v2 暢銷書報告（多段訊息）
    - 發送純文字訊息
    - 測試 Bot 連線
    - 發送失敗自動重試（最多 3 次）

    v2 預設使用 READING_BOT_TOKEN，若未設定則自動降級為舊 Bot。
    """

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
    ):
        # v2 優先使用讀書 Agent 專用 Bot，未設定時降級為舊 Bot
        resolved_token = bot_token or READING_BOT_TOKEN or TELEGRAM_BOT_TOKEN
        resolved_chat_id = chat_id or READING_CHAT_ID or TELEGRAM_CHAT_ID

        if not resolved_token:
            raise ValueError(
                "READING_BOT_TOKEN 或 TELEGRAM_BOT_TOKEN 未設定，請檢查 .env 檔案"
            )
        if not resolved_chat_id:
            raise ValueError(
                "READING_CHAT_ID 或 TELEGRAM_CHAT_ID 未設定，請檢查 .env 檔案"
            )

        self._bot = Bot(token=resolved_token)
        self._chat_id = resolved_chat_id
        self._reporter = ReportGenerator()

    async def send_report(
        self,
        report: ReadingReport,
        summary: Optional[str] = None,
    ) -> bool:
        """發送讀書摘要報告

        Args:
            report: 蒐集報告物件
            summary: Gemini 產生的智慧摘要（可選）

        Returns:
            是否全部發送成功
        """
        segments = self._reporter.generate(report, summary=summary)
        success = True

        for i, segment in enumerate(segments):
            logger.info("發送第 %d/%d 段...", i + 1, len(segments))
            if not await self.send_text(segment):
                success = False
            # 段落間間隔
            if i < len(segments) - 1:
                await asyncio.sleep(TELEGRAM_SEND_DELAY)

        return success

    async def send_segments(self, segments: list[str]) -> bool:
        """發送多段訊息（v2 暢銷書報告用）

        直接接收已分段好的訊息列表，依序發送。

        Args:
            segments: 已分段好的訊息文字列表

        Returns:
            是否全部發送成功
        """
        success = True
        for i, segment in enumerate(segments):
            logger.info("發送第 %d/%d 段...", i + 1, len(segments))
            if not await self.send_text(segment):
                success = False
            if i < len(segments) - 1:
                await asyncio.sleep(TELEGRAM_SEND_DELAY)
        return success

    async def send_text(self, text: str, max_retries: int = 3) -> bool:
        """發送單則文字訊息，帶重試機制"""
        for attempt in range(1, max_retries + 1):
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    disable_web_page_preview=True,
                )
                logger.debug("訊息發送成功（%d 字）", len(text))
                return True

            except RetryAfter as e:
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
        """測試 Bot 連線和 Chat ID 是否有效"""
        try:
            me = await self._bot.get_me()
            logger.info("Bot 連線成功: @%s (%s)", me.username, me.first_name)

            test_msg = (
                "🤖 Agent Army — 讀書 Agent v2 連線測試\n"
                "━" * 18 + "\n"
                "✅ Telegram Bot 連線正常\n"
                f"🆔 Bot: @{me.username}\n"
                f"📬 Chat ID: {self._chat_id}\n"
                "━" * 18 + "\n"
                "📚 讀書 Agent v2 已就緒！"
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
