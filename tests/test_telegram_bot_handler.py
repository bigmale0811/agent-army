# -*- coding: utf-8 -*-
"""Telegram Bot 互動模式處理器的測試

測試 TelegramBotHandler 各指令 handler 的邏輯，
包含授權驗證、訊息格式、頻道管理、影片查詢等功能。
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reading_agent.telegram_bot_handler import (
    TelegramBotHandler,
    _split_message,
)


# =========================================================
# Fixtures
# =========================================================

@pytest.fixture
def handler():
    """建立帶有測試用 token 和 chat_id 的 handler"""
    return TelegramBotHandler(
        bot_token="test-token-123",
        chat_id="12345",
    )


@pytest.fixture
def authorized_update():
    """建立已授權的 Telegram Update mock"""
    update = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def unauthorized_update():
    """建立未授權的 Telegram Update mock"""
    update = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 99999  # 不同的 chat_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def context():
    """建立 Telegram context mock"""
    ctx = MagicMock()
    ctx.args = []
    return ctx


# =========================================================
# 測試 _split_message
# =========================================================

class TestSplitMessage:
    """訊息分段工具測試"""

    def test_short_message_no_split(self):
        """短訊息不需要分段"""
        text = "Hello World"
        result = _split_message(text)
        assert result == [text]

    def test_exact_limit_no_split(self):
        """剛好等於上限不需要分段"""
        text = "a" * 4096
        result = _split_message(text, max_length=4096)
        assert len(result) == 1

    def test_long_message_splits(self):
        """超過上限時會分段"""
        lines = ["Line " + str(i) for i in range(500)]
        text = "\n".join(lines)
        result = _split_message(text, max_length=500)
        assert len(result) > 1
        for segment in result:
            assert len(segment) <= 500

    def test_split_preserves_content(self):
        """分段後合併內容不丟失"""
        lines = ["Line " + str(i) for i in range(100)]
        text = "\n".join(lines)
        result = _split_message(text, max_length=200)
        # 合併分段後應包含所有原始行
        merged = "\n".join(result)
        for line in lines:
            assert line in merged

    def test_empty_message(self):
        """空訊息回傳單段空字串"""
        result = _split_message("")
        assert result == [""]


# =========================================================
# 測試授權驗證
# =========================================================

class TestAuthorization:
    """授權驗證測試"""

    def test_authorized_user(self, handler, authorized_update):
        """授權使用者通過驗證"""
        assert handler._is_authorized(authorized_update) is True

    def test_unauthorized_user(self, handler, unauthorized_update):
        """未授權使用者被拒絕"""
        assert handler._is_authorized(unauthorized_update) is False

    def test_no_effective_chat(self, handler):
        """沒有 effective_chat 時拒絕"""
        update = MagicMock()
        update.effective_chat = None
        assert handler._is_authorized(update) is False

    def test_chat_id_string_comparison(self):
        """chat_id 使用字串比對（數字也轉為字串）"""
        h = TelegramBotHandler(bot_token="tok", chat_id="67890")
        update = MagicMock()
        update.effective_chat = MagicMock()
        update.effective_chat.id = 67890
        assert h._is_authorized(update) is True


# =========================================================
# 測試初始化
# =========================================================

class TestInit:
    """初始化測試"""

    def test_missing_token_raises(self):
        """未提供 token 時拋出 ValueError"""
        with patch.multiple(
            "src.reading_agent.telegram_bot_handler",
            READING_BOT_TOKEN="",
            TELEGRAM_BOT_TOKEN="",
        ):
            with pytest.raises(ValueError, match="TOKEN"):
                TelegramBotHandler(bot_token="", chat_id="123")

    def test_missing_chat_id_raises(self):
        """未提供 chat_id 時拋出 ValueError"""
        with patch.multiple(
            "src.reading_agent.telegram_bot_handler",
            READING_CHAT_ID="",
            TELEGRAM_CHAT_ID="",
        ):
            with pytest.raises(ValueError, match="CHAT_ID"):
                TelegramBotHandler(bot_token="tok", chat_id="")


# =========================================================
# 測試 /start 指令
# =========================================================

class TestCmdStart:
    """測試 /start 和 /help 指令"""

    @pytest.mark.asyncio
    async def test_start_authorized(self, handler, authorized_update, context):
        """授權使用者收到歡迎訊息"""
        await handler.cmd_start(authorized_update, context)
        authorized_update.message.reply_text.assert_called_once()
        msg = authorized_update.message.reply_text.call_args[0][0]
        assert "讀書 Agent" in msg
        assert "/videos" in msg
        assert "/books" in msg

    @pytest.mark.asyncio
    async def test_start_unauthorized(self, handler, unauthorized_update, context):
        """未授權使用者收到拒絕訊息"""
        await handler.cmd_start(unauthorized_update, context)
        unauthorized_update.message.reply_text.assert_called_once_with(
            "未授權的存取。"
        )


# =========================================================
# 測試 /videos 指令
# =========================================================

class TestCmdVideos:
    """測試 /videos 指令"""

    @pytest.mark.asyncio
    async def test_videos_no_data(self, handler, authorized_update, context, tmp_path):
        """沒有影片資料時顯示提示"""
        with patch(
            "src.reading_agent.telegram_bot_handler.VIDEOS_DIR",
            tmp_path,
        ):
            await handler.cmd_videos(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "沒有蒐集到" in msg

    @pytest.mark.asyncio
    async def test_videos_with_data(self, handler, authorized_update, context, tmp_path):
        """有影片資料時正確顯示"""
        # 建立測試資料
        video_data = [
            {
                "title": "測試影片",
                "url": "https://youtube.com/watch?v=abc123",
                "channel_name": "文森說書",
                "channel_id": "UC123",
                "published_at": "2026-03-03",
                "category": "general",
                "book_title": "測試書名",
            },
            {
                "title": "AI News Update",
                "url": "https://youtube.com/watch?v=def456",
                "channel_name": "Fireship",
                "channel_id": "UC456",
                "published_at": "2026-03-03",
                "category": "ai_tech",
            },
        ]
        test_file = tmp_path / "2026-03-03.json"
        test_file.write_text(json.dumps(video_data, ensure_ascii=False), encoding="utf-8")

        with patch(
            "src.reading_agent.telegram_bot_handler.VIDEOS_DIR",
            tmp_path,
        ):
            await handler.cmd_videos(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "共 2 部影片" in msg
            assert "說書影片" in msg
            assert "AI Weekly" in msg

    @pytest.mark.asyncio
    async def test_videos_unauthorized(self, handler, unauthorized_update, context):
        """未授權使用者被拒絕"""
        await handler.cmd_videos(unauthorized_update, context)
        unauthorized_update.message.reply_text.assert_called_once_with(
            "未授權的存取。"
        )


# =========================================================
# 測試 /channels 指令
# =========================================================

class TestCmdChannels:
    """測試 /channels 指令"""

    @pytest.mark.asyncio
    async def test_channels_shows_list(self, handler, authorized_update, context):
        """顯示頻道列表"""
        mock_channels = [
            {"name": "文森說書", "category": "general"},
            {"name": "閱部客", "category": "business"},
        ]
        with patch(
            "src.reading_agent.telegram_bot_handler.load_channels",
            return_value=mock_channels,
        ):
            await handler.cmd_channels(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "共 2 個" in msg
            assert "文森說書" in msg
            assert "閱部客" in msg

    @pytest.mark.asyncio
    async def test_channels_empty(self, handler, authorized_update, context):
        """沒有頻道時顯示提示"""
        with patch(
            "src.reading_agent.telegram_bot_handler.load_channels",
            return_value=[],
        ):
            await handler.cmd_channels(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "沒有追蹤" in msg


# =========================================================
# 測試 /add 指令
# =========================================================

class TestCmdAdd:
    """測試 /add 指令"""

    @pytest.mark.asyncio
    async def test_add_no_args(self, handler, authorized_update, context):
        """沒有參數時顯示用法"""
        context.args = []
        await handler.cmd_add(authorized_update, context)
        msg = authorized_update.message.reply_text.call_args[0][0]
        assert "用法" in msg

    @pytest.mark.asyncio
    async def test_add_invalid_url(self, handler, authorized_update, context):
        """非 URL 格式被拒絕"""
        context.args = ["not-a-url"]
        await handler.cmd_add(authorized_update, context)
        msg = authorized_update.message.reply_text.call_args[0][0]
        assert "http" in msg

    @pytest.mark.asyncio
    async def test_add_success(self, handler, authorized_update, context, tmp_path):
        """成功新增頻道"""
        context.args = ["https://www.youtube.com/@TestChannel"]

        # 建立空的 channels.json
        channels_file = tmp_path / "channels.json"
        channels_file.write_text("[]", encoding="utf-8")

        with patch(
            "src.reading_agent.telegram_bot_handler.CHANNELS_FILE",
            channels_file,
        ):
            await handler.cmd_add(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "已新增" in msg
            assert "TestChannel" in msg

            # 驗證 channels.json 被更新
            data = json.loads(channels_file.read_text(encoding="utf-8"))
            assert len(data) == 1
            assert data[0]["name"] == "TestChannel"

    @pytest.mark.asyncio
    async def test_add_duplicate(self, handler, authorized_update, context, tmp_path):
        """重複 URL 不會新增"""
        url = "https://www.youtube.com/@TestChannel"
        context.args = [url]

        channels_file = tmp_path / "channels.json"
        existing = [{"name": "TestChannel", "url": url, "channel_id": "", "category": "general"}]
        channels_file.write_text(json.dumps(existing), encoding="utf-8")

        with patch(
            "src.reading_agent.telegram_bot_handler.CHANNELS_FILE",
            channels_file,
        ):
            await handler.cmd_add(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "已存在" in msg


# =========================================================
# 測試 /remove 指令
# =========================================================

class TestCmdRemove:
    """測試 /remove 指令"""

    @pytest.mark.asyncio
    async def test_remove_no_args(self, handler, authorized_update, context):
        """沒有參數時顯示用法"""
        context.args = []
        await handler.cmd_remove(authorized_update, context)
        msg = authorized_update.message.reply_text.call_args[0][0]
        assert "用法" in msg

    @pytest.mark.asyncio
    async def test_remove_success(self, handler, authorized_update, context, tmp_path):
        """成功移除頻道"""
        context.args = ["文森說書"]

        channels_file = tmp_path / "channels.json"
        existing = [
            {"name": "文森說書", "url": "https://www.youtube.com/@vincentshuoshu"},
            {"name": "閱部客", "url": "https://www.youtube.com/@yuehbuker"},
        ]
        channels_file.write_text(
            json.dumps(existing, ensure_ascii=False), encoding="utf-8"
        )

        with patch(
            "src.reading_agent.telegram_bot_handler.CHANNELS_FILE",
            channels_file,
        ):
            await handler.cmd_remove(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "已移除" in msg
            assert "文森說書" in msg

            # 驗證只剩一個頻道
            data = json.loads(channels_file.read_text(encoding="utf-8"))
            assert len(data) == 1
            assert data[0]["name"] == "閱部客"

    @pytest.mark.asyncio
    async def test_remove_not_found(self, handler, authorized_update, context, tmp_path):
        """移除不存在的頻道"""
        context.args = ["不存在的頻道"]

        channels_file = tmp_path / "channels.json"
        existing = [{"name": "文森說書", "url": "test"}]
        channels_file.write_text(
            json.dumps(existing, ensure_ascii=False), encoding="utf-8"
        )

        with patch(
            "src.reading_agent.telegram_bot_handler.CHANNELS_FILE",
            channels_file,
        ):
            await handler.cmd_remove(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "找不到" in msg


# =========================================================
# 測試 /analyze 指令
# =========================================================

class TestCmdAnalyze:
    """測試 /analyze 指令"""

    @pytest.mark.asyncio
    async def test_analyze_no_args(self, handler, authorized_update, context):
        """沒有參數時顯示用法"""
        context.args = []
        await handler.cmd_analyze(authorized_update, context)
        msg = authorized_update.message.reply_text.call_args[0][0]
        assert "用法" in msg

    @pytest.mark.asyncio
    async def test_analyze_invalid_url(self, handler, authorized_update, context):
        """非 YouTube URL 被拒絕"""
        context.args = ["https://www.google.com"]
        await handler.cmd_analyze(authorized_update, context)
        msg = authorized_update.message.reply_text.call_args[0][0]
        assert "有效的 YouTube URL" in msg

    @pytest.mark.asyncio
    async def test_analyze_valid_url(self, handler, authorized_update, context):
        """有效的 YouTube URL 開始分析"""
        context.args = ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
        await handler.cmd_analyze(authorized_update, context)
        # 第一次 reply 是「正在分析」
        first_msg = authorized_update.message.reply_text.call_args_list[0][0][0]
        assert "分析" in first_msg


# =========================================================
# 測試內部工具方法
# =========================================================

class TestUtilities:
    """測試內部工具方法"""

    def test_extract_channel_name_at_format(self):
        """從 @ 格式 URL 擷取頻道名稱"""
        url = "https://www.youtube.com/@vincentshuoshu"
        result = TelegramBotHandler._extract_channel_name_from_url(url)
        assert result == "vincentshuoshu"

    def test_extract_channel_name_channel_format(self):
        """從 /channel/ 格式 URL 擷取頻道名稱"""
        url = "https://www.youtube.com/channel/UCPgGtH2PxZ9xR0ehzQ27FHw"
        result = TelegramBotHandler._extract_channel_name_from_url(url)
        assert "UCPgGtH2PxZ9xR0ehzQ" in result

    def test_extract_channel_name_c_format(self):
        """從 /c/ 格式 URL 擷取頻道名稱"""
        url = "https://www.youtube.com/c/MyChannel"
        result = TelegramBotHandler._extract_channel_name_from_url(url)
        assert result == "MyChannel"

    def test_is_youtube_url_valid(self):
        """有效的 YouTube URL"""
        assert TelegramBotHandler._is_youtube_url(
            "https://www.youtube.com/watch?v=abc123"
        )
        assert TelegramBotHandler._is_youtube_url(
            "https://youtu.be/abc123"
        )
        assert TelegramBotHandler._is_youtube_url(
            "https://www.youtube.com/shorts/abc123"
        )

    def test_is_youtube_url_invalid(self):
        """無效的 YouTube URL"""
        assert not TelegramBotHandler._is_youtube_url("https://www.google.com")
        assert not TelegramBotHandler._is_youtube_url("not-a-url")

    def test_extract_video_id_standard(self):
        """標準 YouTube URL 擷取 video_id"""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert TelegramBotHandler._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_short(self):
        """短網址 URL 擷取 video_id"""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert TelegramBotHandler._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_shorts(self):
        """Shorts URL 擷取 video_id"""
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        assert TelegramBotHandler._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid(self):
        """無效 URL 回傳空字串"""
        assert TelegramBotHandler._extract_video_id("https://www.google.com") == ""


# =========================================================
# 測試 /books 指令
# =========================================================

class TestCmdBooks:
    """測試 /books 指令"""

    @pytest.mark.asyncio
    async def test_books_unauthorized(self, handler, unauthorized_update, context):
        """未授權使用者被拒絕"""
        await handler.cmd_books(unauthorized_update, context)
        unauthorized_update.message.reply_text.assert_called_once_with(
            "未授權的存取。"
        )

    @pytest.mark.asyncio
    async def test_books_empty_result(self, handler, authorized_update, context):
        """沒有暢銷書時的處理"""
        mock_scraper = AsyncMock()
        mock_scraper.scrape_all = AsyncMock(return_value=[])

        with patch(
            "src.reading_agent.bestseller_scraper.BestsellerScraper",
            return_value=mock_scraper,
        ) as mock_cls:
            # 同時 patch cmd_books 內部的延遲匯入
            with patch.dict(
                "sys.modules",
                {"src.reading_agent.bestseller_scraper": MagicMock(
                    BestsellerScraper=MagicMock(return_value=mock_scraper)
                )},
            ):
                await handler.cmd_books(authorized_update, context)
                # 第一次是「處理中」，第二次是「無法取得」
                calls = authorized_update.message.reply_text.call_args_list
                assert len(calls) == 2
                assert "無法取得" in calls[1][0][0]


# =========================================================
# 測試 /weekly 和 /ai 指令
# =========================================================

class TestCmdWeeklyAndAi:
    """測試 /weekly 和 /ai 指令"""

    @pytest.mark.asyncio
    async def test_weekly_unauthorized(self, handler, unauthorized_update, context):
        """未授權使用者被拒絕"""
        await handler.cmd_weekly(unauthorized_update, context)
        unauthorized_update.message.reply_text.assert_called_once_with(
            "未授權的存取。"
        )

    @pytest.mark.asyncio
    async def test_weekly_sends_processing_message(
        self, handler, authorized_update, context
    ):
        """每週蒐集先發送處理中訊息"""
        with patch(
            "src.reading_agent.telegram_bot_handler.asyncio.create_task"
        ):
            await handler.cmd_weekly(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "每週蒐集" in msg

    @pytest.mark.asyncio
    async def test_ai_unauthorized(self, handler, unauthorized_update, context):
        """未授權使用者被拒絕"""
        await handler.cmd_ai(unauthorized_update, context)
        unauthorized_update.message.reply_text.assert_called_once_with(
            "未授權的存取。"
        )

    @pytest.mark.asyncio
    async def test_ai_sends_processing_message(
        self, handler, authorized_update, context
    ):
        """AI Weekly 先發送處理中訊息"""
        with patch(
            "src.reading_agent.telegram_bot_handler.asyncio.create_task"
        ):
            await handler.cmd_ai(authorized_update, context)
            msg = authorized_update.message.reply_text.call_args[0][0]
            assert "AI Weekly" in msg


# =========================================================
# 測試 Bot 指令選單（Menu Button）
# =========================================================

class TestBotCommands:
    """測試 Telegram Bot 指令選單註冊"""

    def test_bot_commands_defined(self):
        """BOT_COMMANDS 類別屬性已定義且不為空"""
        assert hasattr(TelegramBotHandler, "BOT_COMMANDS")
        assert len(TelegramBotHandler.BOT_COMMANDS) > 0

    def test_bot_commands_are_botcommand_instances(self):
        """每個指令都是 BotCommand 實例"""
        from telegram import BotCommand
        for cmd in TelegramBotHandler.BOT_COMMANDS:
            assert isinstance(cmd, BotCommand)

    def test_bot_commands_have_descriptions(self):
        """每個指令都有說明文字"""
        for cmd in TelegramBotHandler.BOT_COMMANDS:
            assert cmd.command, "指令名稱不能為空"
            assert cmd.description, f"指令 /{cmd.command} 缺少說明"

    def test_bot_commands_cover_all_handlers(self):
        """指令選單涵蓋所有已註冊的指令 handler"""
        # 從 BOT_COMMANDS 取得所有已註冊的指令名稱
        menu_commands = {cmd.command for cmd in TelegramBotHandler.BOT_COMMANDS}

        # 所有在 run() 中註冊的指令（discover 是進階功能，可選）
        expected_commands = {
            "start", "help", "videos", "books", "channels",
            "weekly", "ai", "add", "remove", "analyze", "collect",
        }
        # 選單至少要涵蓋所有核心指令
        for cmd in expected_commands:
            assert cmd in menu_commands, f"/{cmd} 未加入指令選單"

    @pytest.mark.asyncio
    async def test_post_init_calls_set_my_commands(self):
        """_post_init 呼叫 set_my_commands 註冊指令選單"""
        mock_app = AsyncMock()
        mock_app.bot = AsyncMock()
        mock_app.bot.set_my_commands = AsyncMock()

        await TelegramBotHandler._post_init(mock_app)

        mock_app.bot.set_my_commands.assert_called_once_with(
            TelegramBotHandler.BOT_COMMANDS
        )
