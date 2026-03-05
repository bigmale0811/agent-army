# -*- coding: utf-8 -*-
"""telegram_sender.py 單元測試 — Telegram 發送模組"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.japan_intel.telegram_sender import TelegramSender
from src.japan_intel.models import Article, Report


class TestTelegramSenderInit:
    """TelegramSender 初始化測試"""

    def test_missing_token_raises(self):
        """缺少 Bot Token 應拋出 ValueError"""
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            TelegramSender(bot_token="", chat_id="12345")

    def test_missing_chat_id_raises(self):
        """缺少 Chat ID 應拋出 ValueError"""
        with pytest.raises(ValueError, match="TELEGRAM_CHAT_ID"):
            TelegramSender(bot_token="fake:token", chat_id="")


@pytest.mark.asyncio
class TestTelegramSenderSend:
    """TelegramSender 發送測試"""

    @patch("src.japan_intel.telegram_sender.Bot")
    async def test_send_text_success(self, MockBot):
        """成功發送文字訊息"""
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock()

        sender = TelegramSender(bot_token="fake:token", chat_id="12345")
        result = await sender.send_text("Hello test")

        assert result is True
        mock_bot.send_message.assert_called_once()

    @patch("src.japan_intel.telegram_sender.Bot")
    async def test_send_text_retry_on_timeout(self, MockBot):
        """逾時應重試"""
        from telegram.error import TimedOut

        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock(
            side_effect=[TimedOut(), None]
        )

        sender = TelegramSender(bot_token="fake:token", chat_id="12345")
        result = await sender.send_text("Hello retry")

        assert result is True
        assert mock_bot.send_message.call_count == 2

    @patch("src.japan_intel.telegram_sender.Bot")
    async def test_send_report_calls_send_text(self, MockBot):
        """send_report 應呼叫 send_text 發送各段"""
        mock_bot = MockBot.return_value
        mock_bot.send_message = AsyncMock()

        sender = TelegramSender(bot_token="fake:token", chat_id="12345")
        report = Report(
            period_start="2026-02-24", period_end="2026-03-03",
            articles=[
                Article(
                    title="Test", url="https://example.com/1",
                    source="S", published_at="2026-03-01",
                ),
            ],
        )
        result = await sender.send_report(report)
        assert result is True
        assert mock_bot.send_message.call_count >= 1

    @patch("src.japan_intel.telegram_sender.Bot")
    async def test_test_connection(self, MockBot):
        """test_connection 應呼叫 get_me 和 send_message"""
        mock_bot = MockBot.return_value
        mock_me = MagicMock()
        mock_me.username = "test_bot"
        mock_me.first_name = "Test Bot"
        mock_bot.get_me = AsyncMock(return_value=mock_me)
        mock_bot.send_message = AsyncMock()

        sender = TelegramSender(bot_token="fake:token", chat_id="12345")
        result = await sender.test_connection()

        assert result is True
        mock_bot.get_me.assert_called_once()
