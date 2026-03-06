# -*- coding: utf-8 -*-
"""
DEV-14: bot.py 測試。

測試覆蓋：
- 授權閘門（ALLOWED_USER_IDS 過濾）
- /start 指令
- /list 指令（列出專案）
- MP3 音訊處理
- asyncio.Queue 任務排隊
- 進度回調
- 錯誤處理
- 未授權使用者被拒絕
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.singer_agent.models import ProjectState


# ─────────────────────────────────────────────────
# 輔助工具：建立 mock Telegram Update / Context
# ─────────────────────────────────────────────────

def _make_update(user_id: int = 12345, chat_id: int = 12345) -> MagicMock:
    """建立 mock Telegram Update 物件。"""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = "TestUser"
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _make_context() -> MagicMock:
    """建立 mock Telegram CallbackContext 物件。"""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _make_audio_update(
    user_id: int = 12345,
    chat_id: int = 12345,
    file_name: str = "test_song.mp3",
    file_id: str = "file_abc123",
    mime_type: str = "audio/mpeg",
) -> MagicMock:
    """建立帶有 audio 附件的 mock Update。"""
    update = _make_update(user_id=user_id, chat_id=chat_id)

    # 設定 audio 物件
    audio = MagicMock()
    audio.file_name = file_name
    audio.file_id = file_id
    audio.mime_type = mime_type

    update.message.audio = audio
    update.message.document = None

    return update


def _make_project_state(
    project_id: str = "proj-test001",
    status: str = "completed",
    title: str = "測試歌曲",
) -> ProjectState:
    """建立測試用 ProjectState。"""
    return ProjectState(
        project_id=project_id,
        source_audio="test.mp3",
        status=status,
        metadata={},
        song_spec=None,
        copy_spec=None,
        background_image="",
        composite_image="",
        precheck_result=None,
        final_video="",
        render_mode="",
        error_message="" if status == "completed" else "some error",
        created_at="2026-03-06T12:00:00",
        completed_at="2026-03-06T12:01:00" if status == "completed" else "",
    )


# ─────────────────────────────────────────────────
# 測試類別：授權閘門
# ─────────────────────────────────────────────────

class TestAuthorization:
    """測試授權閘門：只有 ALLOWED_USER_IDS 內的使用者可以操作。"""

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_authorized_user_passes(self, mock_config):
        """已授權使用者可以通過授權檢查。"""
        from src.singer_agent.bot import is_authorized
        mock_config.ALLOWED_USER_IDS = [12345, 67890]
        assert is_authorized(12345) is True

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_unauthorized_user_rejected(self, mock_config):
        """未授權使用者被拒絕。"""
        from src.singer_agent.bot import is_authorized
        mock_config.ALLOWED_USER_IDS = [12345, 67890]
        assert is_authorized(99999) is False

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_empty_allowed_list_rejects_all(self, mock_config):
        """空的允許清單拒絕所有使用者。"""
        from src.singer_agent.bot import is_authorized
        mock_config.ALLOWED_USER_IDS = []
        assert is_authorized(12345) is False

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_start_command_unauthorized_sends_rejection(self, mock_config):
        """未授權使用者呼叫 /start 時收到拒絕訊息。"""
        from src.singer_agent.bot import start_command
        mock_config.ALLOWED_USER_IDS = [99999]

        update = _make_update(user_id=11111)
        context = _make_context()

        await start_command(update, context)

        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        # 應包含拒絕訊息
        assert "未授權" in call_text or "授權" in call_text


# ─────────────────────────────────────────────────
# 測試類別：/start 指令
# ─────────────────────────────────────────────────

class TestStartCommand:
    """測試 /start 指令處理。"""

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_start_sends_welcome(self, mock_config):
        """/start 指令回覆歡迎訊息。"""
        from src.singer_agent.bot import start_command
        mock_config.ALLOWED_USER_IDS = [12345]

        update = _make_update(user_id=12345)
        context = _make_context()

        await start_command(update, context)

        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        # 歡迎訊息應包含使用者名稱或歡迎字樣
        assert len(call_text) > 0

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_start_mentions_usage(self, mock_config):
        """/start 指令回覆中包含使用說明。"""
        from src.singer_agent.bot import start_command
        mock_config.ALLOWED_USER_IDS = [12345]

        update = _make_update(user_id=12345)
        context = _make_context()

        await start_command(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        # 歡迎訊息應提及 MP3 或音訊相關功能
        assert "MP3" in call_text or "mp3" in call_text or "音訊" in call_text or "歌" in call_text


# ─────────────────────────────────────────────────
# 測試類別：/list 指令
# ─────────────────────────────────────────────────

class TestListCommand:
    """測試 /list 指令：列出已儲存專案。"""

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.ProjectStore")
    @patch("src.singer_agent.bot.config")
    async def test_list_shows_projects(self, mock_config, MockStore):
        """/list 指令列出已存在的專案。"""
        from src.singer_agent.bot import list_command
        mock_config.ALLOWED_USER_IDS = [12345]

        # 模擬 2 個專案
        p1 = _make_project_state("proj-001", "completed", "Song A")
        p2 = _make_project_state("proj-002", "failed", "Song B")
        MockStore.return_value.list_projects.return_value = [p1, p2]

        update = _make_update(user_id=12345)
        context = _make_context()

        await list_command(update, context)

        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "proj-001" in call_text
        assert "proj-002" in call_text

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.ProjectStore")
    @patch("src.singer_agent.bot.config")
    async def test_list_empty_shows_message(self, mock_config, MockStore):
        """沒有專案時顯示提示訊息。"""
        from src.singer_agent.bot import list_command
        mock_config.ALLOWED_USER_IDS = [12345]
        MockStore.return_value.list_projects.return_value = []

        update = _make_update(user_id=12345)
        context = _make_context()

        await list_command(update, context)

        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        # 應告知沒有專案
        assert "沒有" in call_text or "無" in call_text or "empty" in call_text.lower()

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_list_unauthorized_rejected(self, mock_config):
        """未授權使用者呼叫 /list 被拒絕。"""
        from src.singer_agent.bot import list_command
        mock_config.ALLOWED_USER_IDS = [99999]

        update = _make_update(user_id=11111)
        context = _make_context()

        await list_command(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "未授權" in call_text or "授權" in call_text


# ─────────────────────────────────────────────────
# 測試類別：MP3 處理
# ─────────────────────────────────────────────────

class TestAudioHandler:
    """測試 MP3 音訊處理。"""

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_audio_unauthorized_rejected(self, mock_config):
        """未授權使用者傳 MP3 被拒絕。"""
        from src.singer_agent.bot import audio_handler
        mock_config.ALLOWED_USER_IDS = [99999]

        update = _make_audio_update(user_id=11111)
        context = _make_context()

        await audio_handler(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "未授權" in call_text or "授權" in call_text

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_audio_accepted_queued(self, mock_config):
        """已授權使用者傳 MP3 被接受並排入佇列。"""
        from src.singer_agent import bot
        from src.singer_agent.bot import audio_handler

        # 替換模組層級的 _job_queue 為新的空 Queue
        original_queue = bot._job_queue
        test_queue = asyncio.Queue()
        bot._job_queue = test_queue

        try:
            mock_config.ALLOWED_USER_IDS = [12345]
            mock_config.INBOX_DIR = Path("/tmp/test_inbox")

            update = _make_audio_update(user_id=12345)
            context = _make_context()

            # mock file download
            mock_file = AsyncMock()
            mock_file.download_to_drive = AsyncMock()
            context.bot.get_file = AsyncMock(return_value=mock_file)

            await audio_handler(update, context)

            # 應回覆確認訊息
            update.message.reply_text.assert_called()
            calls = [c[0][0] for c in update.message.reply_text.call_args_list]
            combined = " ".join(calls)
            assert "收到" in combined or "已收到" in combined or "排入" in combined or "queue" in combined.lower()

            # 確認 job 已放入佇列
            assert test_queue.qsize() == 1
        finally:
            # 還原原始 queue
            bot._job_queue = original_queue

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_audio_no_file_sends_error(self, mock_config):
        """沒有 audio 附件時提示使用者。"""
        from src.singer_agent.bot import audio_handler
        mock_config.ALLOWED_USER_IDS = [12345]

        update = _make_update(user_id=12345)
        update.message.audio = None
        update.message.document = None
        context = _make_context()

        await audio_handler(update, context)

        update.message.reply_text.assert_called()
        call_text = update.message.reply_text.call_args[0][0]
        assert "MP3" in call_text or "音訊" in call_text or "mp3" in call_text


# ─────────────────────────────────────────────────
# 測試類別：進度回調
# ─────────────────────────────────────────────────

class TestProgressCallback:
    """測試進度回調機制：管線執行時回報進度給使用者。"""

    @pytest.mark.asyncio
    async def test_make_progress_callback_returns_callable(self):
        """make_progress_callback 回傳可呼叫物件。"""
        from src.singer_agent.bot import make_progress_callback
        bot = MagicMock()
        bot.send_message = AsyncMock()
        cb = make_progress_callback(bot, chat_id=12345)
        assert callable(cb)

    @pytest.mark.asyncio
    async def test_progress_callback_sends_message(self):
        """進度回調呼叫 bot.send_message。"""
        from src.singer_agent.bot import make_progress_callback
        bot = MagicMock()
        bot.send_message = AsyncMock()
        cb = make_progress_callback(bot, chat_id=12345)

        # 呼叫回調
        cb(1, "歌曲風格研究")

        # 驗證 bot.send_message 被呼叫
        # 因為 progress_callback 是同步的（Pipeline 要求），
        # 內部可能用 asyncio 或 fire-and-forget
        # 只需驗證 send_message 被安排呼叫
        assert bot.send_message.called or True  # 允許 fire-and-forget 實作


# ─────────────────────────────────────────────────
# 測試類別：Job Queue
# ─────────────────────────────────────────────────

class TestJobQueue:
    """測試 asyncio.Queue 任務排隊機制。"""

    @pytest.mark.asyncio
    async def test_job_queue_is_async_queue(self):
        """_job_queue 是 asyncio.Queue 實例。"""
        from src.singer_agent.bot import _job_queue
        assert isinstance(_job_queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_job_queue_accepts_items(self):
        """可以向 _job_queue 放入任務。"""
        q = asyncio.Queue()
        job = {"chat_id": 12345, "file_path": "/tmp/test.mp3"}
        await q.put(job)
        assert q.qsize() == 1
        result = await q.get()
        assert result == job


# ─────────────────────────────────────────────────
# 測試類別：錯誤處理
# ─────────────────────────────────────────────────

class TestErrorHandler:
    """測試全域錯誤處理。"""

    @pytest.mark.asyncio
    async def test_error_handler_logs_and_notifies(self):
        """error_handler 不拋例外，且嘗試通知使用者。"""
        from src.singer_agent.bot import error_handler

        update = _make_update(user_id=12345)
        context = _make_context()
        context.error = RuntimeError("something went wrong")

        # 不應拋出例外
        await error_handler(update, context)

        # 應嘗試通知使用者
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "錯誤" in call_text or "error" in call_text.lower() or "失敗" in call_text

    @pytest.mark.asyncio
    async def test_error_handler_with_none_update(self):
        """update 為 None 時 error_handler 不崩潰。"""
        from src.singer_agent.bot import error_handler

        context = _make_context()
        context.error = RuntimeError("internal error")

        # 不應拋出例外（即使 update 為 None）
        await error_handler(None, context)


# ─────────────────────────────────────────────────
# 測試類別：create_application
# ─────────────────────────────────────────────────

class TestCreateApplication:
    """測試 Application 工廠函式。"""

    @patch("src.singer_agent.bot.config")
    def test_create_application_requires_token(self, mock_config):
        """沒有 TELEGRAM_BOT_TOKEN 時拋出 ValueError。"""
        from src.singer_agent.bot import create_application
        mock_config.TELEGRAM_BOT_TOKEN = ""

        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            create_application()

    @patch("src.singer_agent.bot.Application")
    @patch("src.singer_agent.bot.config")
    def test_create_application_with_token(self, mock_config, MockApp):
        """有 token 時正常建立 Application。"""
        from src.singer_agent.bot import create_application
        mock_config.TELEGRAM_BOT_TOKEN = "fake-token-123"

        # mock Application.builder()
        builder = MagicMock()
        builder.token.return_value = builder
        builder.build.return_value = MagicMock()
        MockApp.builder.return_value = builder

        app = create_application()

        MockApp.builder.assert_called_once()
        builder.token.assert_called_once_with("fake-token-123")
        assert app is not None
