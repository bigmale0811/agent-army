# -*- coding: utf-8 -*-
"""讀書 Agent — Telegram 發送器測試"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.reading_agent.models import Video, ReadingReport
from src.reading_agent.telegram_sender import TelegramSender


def _make_report(n=3):
    videos = [
        Video(
            title=f"說書影片{i}",
            url=f"https://youtube.com/watch?v=vid{i}",
            channel_name="測試頻道",
            channel_id="UC_test",
            published_at="2026-03-01",
        )
        for i in range(n)
    ]
    return ReadingReport(
        period_start="2026-02-24",
        period_end="2026-03-03",
        videos=videos,
    )


class TestTelegramSender:
    def test_init_no_token(self):
        """v2: 清空所有 token 環境變數後，應拋出 ValueError"""
        with patch("src.reading_agent.telegram_sender.READING_BOT_TOKEN", ""), \
             patch("src.reading_agent.telegram_sender.TELEGRAM_BOT_TOKEN", ""):
            with pytest.raises(ValueError, match="BOT_TOKEN"):
                TelegramSender(bot_token="", chat_id="123")

    def test_init_no_chat_id(self):
        """v2: 清空所有 chat_id 環境變數後，應拋出 ValueError"""
        with patch("src.reading_agent.telegram_sender.READING_CHAT_ID", ""), \
             patch("src.reading_agent.telegram_sender.TELEGRAM_CHAT_ID", ""):
            with pytest.raises(ValueError, match="CHAT_ID"):
                TelegramSender(bot_token="fake:token", chat_id="")

    @pytest.mark.asyncio
    async def test_send_text_success(self):
        with patch("src.reading_agent.telegram_sender.Bot") as MockBot:
            mock_bot = AsyncMock()
            MockBot.return_value = mock_bot

            sender = TelegramSender(bot_token="fake:token", chat_id="123")
            result = await sender.send_text("測試訊息")
            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_report(self):
        with patch("src.reading_agent.telegram_sender.Bot") as MockBot:
            mock_bot = AsyncMock()
            MockBot.return_value = mock_bot

            sender = TelegramSender(bot_token="fake:token", chat_id="123")
            report = _make_report(3)
            result = await sender.send_report(report, summary="測試摘要")
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection(self):
        with patch("src.reading_agent.telegram_sender.Bot") as MockBot:
            mock_bot = AsyncMock()
            mock_me = MagicMock()
            mock_me.username = "test_bot"
            mock_me.first_name = "Test"
            mock_bot.get_me = AsyncMock(return_value=mock_me)
            MockBot.return_value = mock_bot

            sender = TelegramSender(bot_token="fake:token", chat_id="123")
            result = await sender.test_connection()
            assert result is True
