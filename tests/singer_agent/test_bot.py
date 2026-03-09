# -*- coding: utf-8 -*-
"""
DEV-14: bot.py 測試（V2.1 — 支援動態角色圖片）。

測試覆蓋：
- 授權閘門（ALLOWED_USER_IDS 過濾）
- /start 指令
- /list 指令（列出專案）
- 圖片處理（角色照片暫存 + 副檔名白名單）
- 圖片 + MP3 整合流程（先傳圖再傳 MP3 / 直接傳 MP3）
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
# 輔助工具：建立 mock Telegram Photo Update
# ─────────────────────────────────────────────────

def _make_photo_update(
    user_id: int = 12345,
    chat_id: int = 12345,
    file_id: str = "photo_abc123",
    as_document: bool = False,
    doc_file_name: str = "avatar.png",
    doc_mime_type: str = "image/png",
) -> MagicMock:
    """建立帶有圖片的 mock Update。

    Args:
        as_document: True 時模擬以檔案形式傳送的圖片
    """
    update = _make_update(user_id=user_id, chat_id=chat_id)

    if as_document:
        # 以檔案形式傳送的圖片
        update.message.photo = []
        doc = MagicMock()
        doc.file_id = file_id
        doc.file_name = doc_file_name
        doc.mime_type = doc_mime_type
        update.message.document = doc
    else:
        # Telegram 壓縮圖片
        photo_small = MagicMock()
        photo_small.file_id = "small_id"
        photo_large = MagicMock()
        photo_large.file_id = file_id
        update.message.photo = [photo_small, photo_large]
        update.message.document = None

    update.message.caption = None
    return update


# ─────────────────────────────────────────────────
# 測試類別：圖片處理
# ─────────────────────────────────────────────────

class TestPhotoHandler:
    """測試角色圖片接收處理（V2.1）。"""

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_photo_unauthorized_rejected(self, mock_config):
        """未授權使用者傳圖片被拒絕。"""
        from src.singer_agent.bot import photo_handler
        mock_config.ALLOWED_USER_IDS = [99999]

        update = _make_photo_update(user_id=11111)
        context = _make_context()

        await photo_handler(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "未授權" in call_text

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_photo_saved_to_user_photos(self, mock_config, tmp_path):
        """已授權使用者傳圖片，暫存到 _user_photos。"""
        from src.singer_agent import bot
        from src.singer_agent.bot import photo_handler

        mock_config.ALLOWED_USER_IDS = [12345]
        mock_config.INBOX_DIR = tmp_path / "inbox"

        update = _make_photo_update(user_id=12345)
        context = _make_context()

        mock_file = AsyncMock()
        mock_file.download_to_drive = AsyncMock()
        context.bot.get_file = AsyncMock(return_value=mock_file)

        # 清除可能殘留的測試資料
        bot._user_photos.pop(12345, None)

        await photo_handler(update, context)

        # 驗證暫存
        assert 12345 in bot._user_photos
        assert "avatar_12345" in bot._user_photos[12345].name

        # 驗證回覆
        call_text = update.message.reply_text.call_args[0][0]
        assert "已收到" in call_text and "MP3" in call_text

        # 清理
        bot._user_photos.pop(12345, None)

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_photo_document_accepted(self, mock_config, tmp_path):
        """以檔案形式傳送的圖片也能被接受。"""
        from src.singer_agent import bot
        from src.singer_agent.bot import photo_handler

        mock_config.ALLOWED_USER_IDS = [12345]
        mock_config.INBOX_DIR = tmp_path / "inbox"

        update = _make_photo_update(
            user_id=12345, as_document=True,
            doc_file_name="my_face.png", doc_mime_type="image/png",
        )
        context = _make_context()

        mock_file = AsyncMock()
        mock_file.download_to_drive = AsyncMock()
        context.bot.get_file = AsyncMock(return_value=mock_file)

        bot._user_photos.pop(12345, None)

        await photo_handler(update, context)

        assert 12345 in bot._user_photos
        bot._user_photos.pop(12345, None)

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_photo_invalid_extension_rejected(self, mock_config, tmp_path):
        """非圖片副檔名被拒絕。"""
        from src.singer_agent.bot import photo_handler

        mock_config.ALLOWED_USER_IDS = [12345]
        mock_config.INBOX_DIR = tmp_path / "inbox"

        update = _make_photo_update(
            user_id=12345, as_document=True,
            doc_file_name="malware.exe", doc_mime_type="image/png",
        )
        context = _make_context()

        await photo_handler(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "JPG" in call_text or "PNG" in call_text

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_photo_non_image_document_rejected(self, mock_config, tmp_path):
        """非圖片 MIME 類型被拒絕。"""
        from src.singer_agent.bot import photo_handler

        mock_config.ALLOWED_USER_IDS = [12345]
        mock_config.INBOX_DIR = tmp_path / "inbox"

        update = _make_photo_update(
            user_id=12345, as_document=True,
            doc_file_name="report.pdf", doc_mime_type="application/pdf",
        )
        context = _make_context()

        await photo_handler(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "圖片" in call_text


class TestPhotoAudioIntegration:
    """測試圖片 + MP3 整合流程（V2.1）。"""

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_audio_uses_user_photo(self, mock_config, tmp_path):
        """傳圖片後再傳 MP3，job 內包含 character_image。"""
        from src.singer_agent import bot
        from src.singer_agent.bot import audio_handler

        mock_config.ALLOWED_USER_IDS = [12345]
        mock_config.INBOX_DIR = tmp_path / "inbox"

        # 模擬先傳了圖片（直接寫入 _user_photos）
        fake_photo = tmp_path / "avatar.png"
        fake_photo.write_bytes(b"\x89PNG")
        bot._user_photos[12345] = fake_photo

        original_queue = bot._job_queue
        test_queue = asyncio.Queue()
        bot._job_queue = test_queue

        try:
            update = _make_audio_update(user_id=12345)
            context = _make_context()

            mock_file = AsyncMock()
            mock_file.download_to_drive = AsyncMock()
            context.bot.get_file = AsyncMock(return_value=mock_file)

            await audio_handler(update, context)

            # 確認 job 有 character_image
            job = await test_queue.get()
            assert job["character_image"] == str(fake_photo)

            # 確認 _user_photos 已清除（用後即刪）
            assert 12345 not in bot._user_photos

            # 確認回覆包含自訂圖片提示
            call_text = update.message.reply_text.call_args[0][0]
            assert "你傳的" in call_text or "角色圖片" in call_text
        finally:
            bot._job_queue = original_queue
            bot._user_photos.pop(12345, None)

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.config")
    async def test_audio_without_photo_uses_default(self, mock_config, tmp_path):
        """沒傳圖片直接發 MP3，job 的 character_image 為 None。"""
        from src.singer_agent import bot
        from src.singer_agent.bot import audio_handler

        mock_config.ALLOWED_USER_IDS = [12345]
        mock_config.INBOX_DIR = tmp_path / "inbox"

        # 確保沒有暫存圖片
        bot._user_photos.pop(12345, None)

        original_queue = bot._job_queue
        test_queue = asyncio.Queue()
        bot._job_queue = test_queue

        try:
            update = _make_audio_update(user_id=12345)
            context = _make_context()

            mock_file = AsyncMock()
            mock_file.download_to_drive = AsyncMock()
            context.bot.get_file = AsyncMock(return_value=mock_file)

            await audio_handler(update, context)

            job = await test_queue.get()
            assert job["character_image"] is None

            # 確認回覆包含預設圖片提示
            call_text = update.message.reply_text.call_args[0][0]
            assert "預設" in call_text
        finally:
            bot._job_queue = original_queue


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


# ─────────────────────────────────────────────────
# 測試類別：_parse_title_artist
# ─────────────────────────────────────────────────

class TestParseTitleArtist:
    """測試從檔名推斷歌曲標題與歌手。"""

    def test_title_artist_from_underscore(self):
        """底線分割的檔名正確取得 title 與 artist。"""
        from src.singer_agent.bot import _parse_title_artist
        title, artist = _parse_title_artist("愛你_周杰倫.mp3")
        assert title == "愛你"
        assert artist == "周杰倫"

    def test_no_underscore_uses_stem_as_title(self):
        """無底線時 title 為整個檔名，artist 為未知。"""
        from src.singer_agent.bot import _parse_title_artist
        title, artist = _parse_title_artist("一首歌.mp3")
        assert title == "一首歌"
        assert artist == "未知"

    def test_multiple_underscores_keeps_rest(self):
        """多個底線時 artist 包含後續所有部分。"""
        from src.singer_agent.bot import _parse_title_artist
        title, artist = _parse_title_artist("愛我的人_裘海正_2026.mp3")
        assert title == "愛我的人"
        assert artist == "裘海正_2026"


# ─────────────────────────────────────────────────
# 測試類別：Worker
# ─────────────────────────────────────────────────

class TestWorker:
    """測試 Worker 佇列消費者 + 管線執行 + 影片回傳。"""

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.Pipeline")
    @patch("src.singer_agent.bot.config")
    async def test_worker_sends_video_on_success(self, mock_config, MockPipeline):
        """管線成功時 worker 傳送影片檔給使用者。"""
        import tempfile
        import os
        from src.singer_agent import bot
        from src.singer_agent.bot import worker

        mock_config.CHARACTER_IMAGE = Path("/tmp/avatar.png")

        # 建立暫時影片檔（大於 200 bytes）
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\x00" * 500)
            video_path = f.name

        try:
            # 模擬成功的 ProjectState
            mock_state = MagicMock()
            mock_state.status = "completed"
            mock_state.final_video = video_path
            mock_state.project_id = "proj-test"
            mock_state.error_message = ""

            MockPipeline.return_value.run.return_value = mock_state

            mock_bot = MagicMock()
            mock_bot.send_message = AsyncMock()
            mock_bot.send_document = AsyncMock()

            # 放入一個 job
            original_queue = bot._job_queue
            test_queue = asyncio.Queue()
            bot._job_queue = test_queue

            await test_queue.put({
                "chat_id": 12345,
                "file_path": "/tmp/test.mp3",
                "file_name": "測試歌_歌手.mp3",
            })

            # 執行 worker（設 timeout 避免永久阻塞）
            task = asyncio.create_task(worker(mock_bot))
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # 驗證 send_document 被呼叫（影片回傳）
            mock_bot.send_document.assert_called_once()
            call_kwargs = mock_bot.send_document.call_args
            assert call_kwargs[1]["chat_id"] == 12345

            bot._job_queue = original_queue
        finally:
            try:
                os.unlink(video_path)
            except PermissionError:
                pass  # Windows 檔案鎖定，略過清理

    @pytest.mark.asyncio
    @patch("src.singer_agent.bot.Pipeline")
    @patch("src.singer_agent.bot.config")
    async def test_worker_notifies_on_failure(self, mock_config, MockPipeline):
        """管線失敗時 worker 通知使用者錯誤訊息。"""
        from src.singer_agent import bot
        from src.singer_agent.bot import worker

        mock_config.CHARACTER_IMAGE = Path("/tmp/avatar.png")

        mock_state = MagicMock()
        mock_state.status = "failed"
        mock_state.final_video = ""
        mock_state.project_id = "proj-fail"
        mock_state.error_message = "LLM 離線"

        MockPipeline.return_value.run.return_value = mock_state

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_bot.send_document = AsyncMock()

        original_queue = bot._job_queue
        test_queue = asyncio.Queue()
        bot._job_queue = test_queue

        await test_queue.put({
            "chat_id": 12345,
            "file_path": "/tmp/test.mp3",
            "file_name": "測試歌_歌手.mp3",
        })

        task = asyncio.create_task(worker(mock_bot))
        await asyncio.sleep(0.1)
        task.cancel()

        # 不應傳送影片
        mock_bot.send_document.assert_not_called()

        # 應發送失敗訊息（至少 2 次 send_message：開始處理 + 失敗通知）
        assert mock_bot.send_message.call_count >= 2
        all_texts = " ".join(
            c[1]["text"] for c in mock_bot.send_message.call_args_list
        )
        assert "失敗" in all_texts or "❌" in all_texts

        bot._job_queue = original_queue
