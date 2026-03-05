# -*- coding: utf-8 -*-
"""讀書 Agent v2 — TranscriptExtractor 測試

測試 YouTube 字幕擷取器的核心功能：
- extract 擷取單一影片字幕
- extract_batch 批次擷取多部影片
- 語言回退機制（zh-TW -> zh-Hant -> zh）
- 無字幕時的容錯處理（回傳空字串）
- _merge_transcript_segments 合併字幕片段
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reading_agent.models import Video
from src.reading_agent.transcript_extractor import (
    TranscriptExtractor,
    _fetch_transcript_sync,
)


# ─────────────────────────────────────────────
# 共用輔助函式與測試資料
# ─────────────────────────────────────────────

def _make_video(
    video_id: str = "abc123",
    title: str = "說書影片",
    language: str = "zh",
    transcript: str = "",
) -> Video:
    """建立測試用 Video 物件"""
    return Video(
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_name="測試頻道",
        channel_id="UC_test",
        published_at="2026-01-01",
        video_id=video_id,
        language=language,
        transcript=transcript,
    )


def _make_segments(*texts: str) -> list[dict]:
    """建立模擬的字幕片段列表"""
    return [
        {"text": t, "start": float(i * 2), "duration": 2.0}
        for i, t in enumerate(texts)
    ]


# ─────────────────────────────────────────────
# TranscriptExtractor 測試類別
# ─────────────────────────────────────────────

class TestTranscriptExtractor:
    """TranscriptExtractor 的單元測試"""

    @pytest.fixture
    def extractor(self):
        """每個測試使用全新的擷取器實例，request_delay 設為 0 加速測試"""
        return TranscriptExtractor(request_delay=0.0)

    # ──────────────────────────────────────────
    # 1. extract：擷取單一影片字幕
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_extract_returns_merged_text(self, extractor):
        """extract 應回傳合併後的字幕純文字字串"""
        segments = _make_segments("這是", "第一段字幕。", "這是第二段。")

        with patch(
            "src.reading_agent.transcript_extractor.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.return_value = segments
            result = await extractor.extract("abc123", language="zh")

        # 應回傳非空字串
        assert isinstance(result, str)
        assert len(result) > 0
        # 字幕內容應包含原始文字
        assert "第一段字幕" in result
        assert "第二段" in result

    @pytest.mark.asyncio
    async def test_extract_returns_empty_string_when_no_transcript(self, extractor):
        """無法取得字幕時應回傳空字串（不拋出例外）"""
        with patch(
            "src.reading_agent.transcript_extractor.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            # 模擬 youtube_transcript_api 拋出 NoTranscriptFound 例外
            mock_to_thread.side_effect = Exception("TranscriptsDisabled: 字幕已關閉")
            result = await extractor.extract("no_caption_vid", language="zh")

        assert result == "", "無法取得字幕時應回傳空字串"

    @pytest.mark.asyncio
    async def test_extract_uses_correct_language_priority_for_zh(self, extractor):
        """中文影片應依 zh-TW → zh-Hant → zh 優先順序搜尋字幕"""
        segments = _make_segments("繁體中文字幕")

        with patch(
            "src.reading_agent.transcript_extractor.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.return_value = segments
            await extractor.extract("zh_video", language="zh")

        # 確認 _fetch_transcript_sync 被呼叫，且傳入繁體中文優先的語言列表
        call_args = mock_to_thread.call_args
        # to_thread 的第二個位置參數是 video_id，第三個是 language_codes
        lang_codes = call_args.args[2] if len(call_args.args) >= 3 else call_args.kwargs.get("language_codes", [])
        assert "zh-TW" in lang_codes, "繁體中文 zh-TW 應在語言優先列表中"
        assert lang_codes.index("zh-TW") < lang_codes.index("zh"), "zh-TW 應優先於 zh"

    @pytest.mark.asyncio
    async def test_extract_uses_correct_language_priority_for_en(self, extractor):
        """英文影片應優先搜尋 en 語系字幕"""
        segments = _make_segments("English transcript content")

        with patch(
            "src.reading_agent.transcript_extractor.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.return_value = segments
            await extractor.extract("en_video", language="en")

        call_args = mock_to_thread.call_args
        lang_codes = call_args.args[2] if len(call_args.args) >= 3 else call_args.kwargs.get("language_codes", [])
        assert "en" in lang_codes, "英文 en 應在語言優先列表中"

    # ──────────────────────────────────────────
    # 2. extract_batch：批次擷取
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_extract_batch_updates_video_transcript_field(self, extractor):
        """extract_batch 應更新每部影片的 transcript 欄位"""
        videos = [
            _make_video(video_id="v1", title="影片一"),
            _make_video(video_id="v2", title="影片二"),
        ]

        async def mock_extract(video_id, language="zh"):
            return f"字幕內容：{video_id}"

        with patch.object(extractor, "extract", side_effect=mock_extract):
            result = await extractor.extract_batch(videos)

        # 回傳同一批 Video 物件（已更新 transcript）
        assert len(result) == 2
        assert result[0].transcript == "字幕內容：v1"
        assert result[1].transcript == "字幕內容：v2"

    @pytest.mark.asyncio
    async def test_extract_batch_skips_videos_without_video_id(self, extractor):
        """缺少 video_id 的影片應被跳過，transcript 保持為空字串"""
        videos = [
            _make_video(video_id="", title="無 ID 影片"),   # 缺少 ID，應跳過
            _make_video(video_id="valid1", title="正常影片"),
        ]

        async def mock_extract(video_id, language="zh"):
            return f"字幕：{video_id}"

        with patch.object(extractor, "extract", side_effect=mock_extract):
            result = await extractor.extract_batch(videos)

        # 無 ID 的影片 transcript 應維持原本的空字串
        no_id_video = next(v for v in result if v.title == "無 ID 影片")
        assert no_id_video.transcript == ""

        # 正常影片應有字幕
        valid_video = next(v for v in result if v.title == "正常影片")
        assert valid_video.transcript == "字幕：valid1"

    @pytest.mark.asyncio
    async def test_extract_batch_empty_input(self, extractor):
        """傳入空列表時應回傳空列表"""
        result = await extractor.extract_batch([])
        assert result == []

    # ──────────────────────────────────────────
    # 3. _merge_transcript_segments：合併字幕片段
    # ──────────────────────────────────────────

    def test_merge_transcript_segments_basic(self, extractor):
        """基本合併：多個片段以空格連接"""
        segments = _make_segments("Hello", "world", "this is a test.")
        result = extractor._merge_transcript_segments(segments)
        assert result == "Hello world this is a test."

    def test_merge_transcript_segments_removes_noise_tags(self, extractor):
        """應移除 [Music]、[Applause] 等雜訊標記"""
        segments = [
            {"text": "我們開始說書", "start": 0.0, "duration": 2.0},
            {"text": "[Music]", "start": 2.0, "duration": 3.0},
            {"text": "這本書的主要概念是", "start": 5.0, "duration": 2.5},
            {"text": "[音樂]", "start": 7.5, "duration": 2.0},
            {"text": "成長型思維。", "start": 9.5, "duration": 2.0},
        ]
        result = extractor._merge_transcript_segments(segments)

        # 雜訊標記應被移除
        assert "[Music]" not in result
        assert "[音樂]" not in result
        # 正常文字應保留
        assert "說書" in result
        assert "成長型思維" in result

    def test_merge_transcript_segments_handles_newlines(self, extractor):
        """片段中的換行符號應被替換為空格"""
        segments = [
            {"text": "第一行\n第二行", "start": 0.0, "duration": 2.0},
            {"text": "正常文字", "start": 2.0, "duration": 2.0},
        ]
        result = extractor._merge_transcript_segments(segments)

        # 換行應轉為空格，不應有多餘的連續空格
        assert "\n" not in result
        assert "  " not in result  # 無連續兩個空格

    def test_merge_transcript_segments_empty_input(self, extractor):
        """空片段列表應回傳空字串"""
        result = extractor._merge_transcript_segments([])
        assert result == ""

    def test_merge_transcript_segments_filters_empty_texts(self, extractor):
        """移除雜訊後若片段為空，該片段應被忽略"""
        segments = [
            {"text": "[Music]", "start": 0.0, "duration": 2.0},
            {"text": "  ", "start": 2.0, "duration": 2.0},         # 純空白
            {"text": "實質內容在這裡", "start": 4.0, "duration": 2.0},
        ]
        result = extractor._merge_transcript_segments(segments)
        # 只應保留有實質內容的片段
        assert result.strip() == "實質內容在這裡"
