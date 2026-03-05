# -*- coding: utf-8 -*-
"""Singer Agent Telegram Bot 測試"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.singer_agent.telegram_bot_handler import (
    SingerBotHandler,
    _parse_caption,
    _split_message,
)


# =========================================================
# Fixtures
# =========================================================

@pytest.fixture
def handler():
    """建立測試用 handler"""
    return SingerBotHandler(bot_token="test-token", chat_id="12345")


@pytest.fixture
def authorized_update():
    """已授權的 Update mock"""
    update = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_video = AsyncMock()
    return update


@pytest.fixture
def unauthorized_update():
    """未授權的 Update mock"""
    update = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 99999
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.args = []
    return ctx


# =========================================================
# 測試 caption 解析
# =========================================================

class TestParseCaption:
    """測試 caption 解析邏輯"""

    def test_full_caption(self):
        """歌名 / 歌手 / 情緒"""
        title, artist, mood = _parse_caption("告白氣球 / 周杰倫 / romantic", "f.mp3")
        assert title == "告白氣球"
        assert artist == "周杰倫"
        assert mood == "romantic"

    def test_title_and_artist(self):
        """歌名 / 歌手"""
        title, artist, mood = _parse_caption("告白氣球 / 周杰倫", "f.mp3")
        assert title == "告白氣球"
        assert artist == "周杰倫"
        assert mood == ""

    def test_title_only(self):
        """只有歌名"""
        title, artist, mood = _parse_caption("告白氣球", "f.mp3")
        assert title == "告白氣球"
        assert artist == ""
        assert mood == ""

    def test_empty_caption_uses_filename(self):
        """空 caption 用檔名推斷"""
        title, artist, mood = _parse_caption("", "告白氣球.mp3")
        assert title == "告白氣球"

    def test_empty_caption_with_artist_filename(self):
        """從 '歌手 - 歌名.mp3' 格式檔名解析"""
        title, artist, mood = _parse_caption("", "周杰倫 - 告白氣球.mp3")
        assert title == "告白氣球"
        assert artist == "周杰倫"

    def test_whitespace_trimmed(self):
        """前後空白被去除"""
        title, artist, mood = _parse_caption("  告白氣球  /  周杰倫  ", "f.mp3")
        assert title == "告白氣球"
        assert artist == "周杰倫"


# =========================================================
# 測試訊息分段
# =========================================================

class TestSplitMessage:

    def test_short_no_split(self):
        assert _split_message("hi") == ["hi"]

    def test_long_splits(self):
        text = "\n".join([f"Line {i}" for i in range(200)])
        result = _split_message(text, max_length=500)
        assert len(result) > 1


# =========================================================
# 測試授權
# =========================================================

class TestAuthorization:

    def test_authorized(self, handler, authorized_update):
        assert handler._is_authorized(authorized_update) is True

    def test_unauthorized(self, handler, unauthorized_update):
        assert handler._is_authorized(unauthorized_update) is False


# =========================================================
# 測試 /start
# =========================================================

class TestCmdStart:

    @pytest.mark.asyncio
    async def test_start_authorized(self, handler, authorized_update, context):
        await handler.cmd_start(authorized_update, context)
        authorized_update.message.reply_text.assert_called_once()
        msg = authorized_update.message.reply_text.call_args[0][0]
        assert "Singer Agent" in msg
        assert "MP3" in msg

    @pytest.mark.asyncio
    async def test_start_unauthorized(self, handler, unauthorized_update, context):
        await handler.cmd_start(unauthorized_update, context)
        unauthorized_update.message.reply_text.assert_called_once_with("未授權的存取。")


# =========================================================
# 測試 /list
# =========================================================

class TestCmdList:

    @pytest.mark.asyncio
    async def test_list_empty(self, handler, authorized_update, context):
        with patch(
            "src.singer_agent.telegram_bot_handler.list_projects",
            return_value=[],
        ):
            await handler.cmd_list(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "沒有" in msg


# =========================================================
# 測試 Bot 指令選單
# =========================================================

class TestBotCommands:

    def test_commands_defined(self):
        assert len(SingerBotHandler.BOT_COMMANDS) > 0

    def test_commands_have_descriptions(self):
        for cmd in SingerBotHandler.BOT_COMMANDS:
            assert cmd.command
            assert cmd.description

    @pytest.mark.asyncio
    async def test_post_init_registers_commands(self):
        mock_app = AsyncMock()
        mock_app.bot = AsyncMock()
        mock_app.bot.set_my_commands = AsyncMock()

        await SingerBotHandler._post_init(mock_app)

        mock_app.bot.set_my_commands.assert_called_once_with(
            SingerBotHandler.BOT_COMMANDS
        )


# =========================================================
# 測試圖片接收
# =========================================================

class TestHandlePhoto:

    @pytest.mark.asyncio
    async def test_photo_unauthorized(self, handler, unauthorized_update, context):
        unauthorized_update.message.photo = [MagicMock()]
        await handler.handle_photo(unauthorized_update, context)
        unauthorized_update.message.reply_text.assert_called_once_with("未授權的存取。")

    @pytest.mark.asyncio
    async def test_photo_saves_character(self, handler, authorized_update, context, tmp_path):
        """成功儲存角色圖片"""
        mock_photo = AsyncMock()
        mock_file = AsyncMock()
        mock_photo.get_file = AsyncMock(return_value=mock_file)
        authorized_update.message.photo = [mock_photo]

        char_path = tmp_path / "character" / "avatar.png"

        with patch(
            "src.singer_agent.telegram_bot_handler.CHARACTER_IMAGE",
            char_path,
        ):
            await handler.handle_photo(authorized_update, context)
            # 確認有回覆成功訊息
            calls = authorized_update.message.reply_text.call_args_list
            last_msg = calls[-1][0][0]
            assert "已設定" in last_msg
