# -*- coding: utf-8 -*-
"""讀書 Agent v2 — ContentAnalyzer 測試

測試 Gemini 深度內容分析器的核心功能：
- analyze_video 分析單部影片並填入重點整理欄位
- analyze_batch 批次分析多部影片
- _build_analysis_prompt 建構 prompt 的結構
- translate_to_chinese 將英文重點翻譯為繁體中文
- 英文影片應同時填入 key_points_original 與 key_points_zh
- Gemini API 失敗時的容錯降級行為
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reading_agent.models import Video
from src.reading_agent.content_analyzer import ContentAnalyzer


# ─────────────────────────────────────────────
# 共用輔助函式與測試資料
# ─────────────────────────────────────────────

def _make_video(
    title: str = "說書影片",
    video_id: str = "abc123",
    language: str = "zh",
    transcript: str = "這是測試字幕內容，涵蓋書籍的核心概念與實用建議。",
    description: str = "測試影片描述",
    channel_name: str = "測試頻道",
) -> Video:
    """建立測試用 Video 物件"""
    return Video(
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_name=channel_name,
        channel_id="UC_test",
        published_at="2026-01-01",
        video_id=video_id,
        language=language,
        transcript=transcript,
        description=description,
    )


def _make_analyzer_with_mock_client() -> tuple[ContentAnalyzer, MagicMock]:
    """建立 ContentAnalyzer 並以 MagicMock 替換 Gemini 客戶端

    由於 ContentAnalyzer.__init__ 會直接呼叫 _init_client()，
    需要在 patch 環境中建立實例以避免實際網路呼叫。

    Returns:
        (analyzer, mock_client) 元組
    """
    mock_client = MagicMock()
    with patch("src.reading_agent.content_analyzer._init_client", return_value=mock_client):
        analyzer = ContentAnalyzer()
    return analyzer, mock_client


# ─────────────────────────────────────────────
# ContentAnalyzer 測試類別
# ─────────────────────────────────────────────

class TestContentAnalyzer:
    """ContentAnalyzer 的單元測試"""

    @pytest.fixture
    def analyzer_and_client(self):
        """建立帶有 mock 客戶端的分析器"""
        return _make_analyzer_with_mock_client()

    @pytest.fixture
    def analyzer(self, analyzer_and_client):
        """單獨取出 analyzer 實例（不需要直接操作 client 的測試使用）"""
        return analyzer_and_client[0]

    # ──────────────────────────────────────────
    # 1. analyze_video：中文影片分析
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_analyze_video_zh_fills_both_fields(self, analyzer):
        """中文影片分析後，key_points_original 與 key_points_zh 應相同且非空"""
        video = _make_video(language="zh")
        expected_result = "1. 核心觀點：成長型思維\n2. 重要案例：芭芭拉歐克莉的學習實驗"

        async def mock_call_gemini(prompt):
            return expected_result

        with patch.object(analyzer, "_call_gemini", side_effect=mock_call_gemini):
            updated = await analyzer.analyze_video(video)

        # 中文影片的兩個欄位應填入相同的分析結果
        assert updated.key_points_original == expected_result
        assert updated.key_points_zh == expected_result
        # Gemini 只應被呼叫一次（中文不需要額外翻譯步驟）
        assert updated.key_points_original != ""

    # ──────────────────────────────────────────
    # 2. analyze_video：英文影片分析（需翻譯）
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_analyze_video_en_fills_original_and_zh_separately(self, analyzer):
        """英文影片應先分析（英文）再翻譯（中文），兩個欄位內容不同"""
        video = _make_video(language="en", title="Atomic Habits Summary")

        en_result = "1. Core Concept: Tiny changes compound over time."
        zh_result = "1. 核心概念：微小改變的複利效應。"

        call_count = 0

        async def mock_call_gemini(prompt):
            nonlocal call_count
            call_count += 1
            # 第一次呼叫是分析（英文 prompt），第二次是翻譯（中文 prompt）
            if call_count == 1:
                return en_result
            return zh_result

        with patch.object(analyzer, "_call_gemini", side_effect=mock_call_gemini):
            updated = await analyzer.analyze_video(video)

        # 原文欄位應為英文分析結果
        assert updated.key_points_original == en_result
        # 中文欄位應為翻譯結果
        assert updated.key_points_zh == zh_result
        # 兩個欄位內容應不相同（英文 vs 中文）
        assert updated.key_points_original != updated.key_points_zh
        # Gemini 應被呼叫兩次（分析 + 翻譯）
        assert call_count == 2

    # ──────────────────────────────────────────
    # 3. analyze_video：Gemini 失敗時的降級行為
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_analyze_video_fallback_when_gemini_fails(self, analyzer):
        """Gemini API 失敗時，兩個重點整理欄位應填入錯誤說明而不拋出例外"""
        video = _make_video(language="zh")

        async def mock_call_gemini(prompt):
            raise RuntimeError("Gemini API 配額超限")

        with patch.object(analyzer, "_call_gemini", side_effect=mock_call_gemini):
            updated = await analyzer.analyze_video(video)

        # 應填入錯誤說明字串，而非保持空白
        assert updated.key_points_original.startswith("（分析失敗"), (
            f"錯誤情境下 key_points_original 應為錯誤說明，實際：'{updated.key_points_original}'"
        )
        assert updated.key_points_zh.startswith("（分析失敗"), (
            f"錯誤情境下 key_points_zh 應為錯誤說明，實際：'{updated.key_points_zh}'"
        )

    # ──────────────────────────────────────────
    # 4. analyze_batch：批次分析
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_analyze_batch_processes_all_videos(self, analyzer):
        """analyze_batch 應處理所有影片並回傳相同數量的結果"""
        videos = [
            _make_video(title=f"影片{i}", video_id=f"v{i}") for i in range(3)
        ]

        async def mock_analyze_video(video):
            video.key_points_original = f"重點整理：{video.title}"
            video.key_points_zh = f"中文重點：{video.title}"
            return video

        with patch.object(analyzer, "analyze_video", side_effect=mock_analyze_video):
            with patch("src.reading_agent.content_analyzer.asyncio.sleep", new_callable=AsyncMock):
                results = await analyzer.analyze_batch(videos)

        assert len(results) == 3
        # 確認每部影片都有被分析
        for i, video in enumerate(results):
            assert f"影片{i}" in video.key_points_original

    @pytest.mark.asyncio
    async def test_analyze_batch_empty_input_returns_empty(self, analyzer):
        """傳入空列表時應直接回傳空列表（不呼叫任何 API）"""
        results = await analyzer.analyze_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_analyze_batch_maintains_order(self, analyzer):
        """批次分析後，結果順序應與輸入順序一致"""
        videos = [
            _make_video(title=f"影片_{ch}", video_id=ch)
            for ch in ["A", "B", "C"]
        ]

        async def mock_analyze_video(video):
            video.key_points_zh = f"分析：{video.title}"
            return video

        with patch.object(analyzer, "analyze_video", side_effect=mock_analyze_video):
            with patch("src.reading_agent.content_analyzer.asyncio.sleep", new_callable=AsyncMock):
                results = await analyzer.analyze_batch(videos)

        # 順序應與輸入相同
        assert results[0].title == "影片_A"
        assert results[1].title == "影片_B"
        assert results[2].title == "影片_C"

    # ──────────────────────────────────────────
    # 5. translate_to_chinese：翻譯功能
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_translate_to_chinese_returns_zh_text(self, analyzer):
        """translate_to_chinese 應呼叫 Gemini 並回傳翻譯結果"""
        en_text = "1. Core Concept: Small habits lead to big changes."
        expected_zh = "1. 核心概念：微小習慣帶來重大改變。"

        async def mock_call_gemini(prompt):
            # 確認 prompt 包含原始英文文字
            assert en_text in prompt
            return expected_zh

        with patch.object(analyzer, "_call_gemini", side_effect=mock_call_gemini):
            result = await analyzer.translate_to_chinese(en_text)

        assert result == expected_zh

    @pytest.mark.asyncio
    async def test_translate_to_chinese_empty_input_returns_empty(self, analyzer):
        """傳入空字串時應直接回傳空字串，不呼叫 Gemini API"""
        with patch.object(analyzer, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
            result = await analyzer.translate_to_chinese("")

        assert result == ""
        mock_gemini.assert_not_called()

    @pytest.mark.asyncio
    async def test_translate_to_chinese_fallback_on_error(self, analyzer):
        """翻譯失敗時應回傳包含錯誤說明與原文的字串"""
        en_text = "Core concept here."

        async def mock_call_gemini(prompt):
            raise ConnectionError("網路連線中斷")

        with patch.object(analyzer, "_call_gemini", side_effect=mock_call_gemini):
            result = await analyzer.translate_to_chinese(en_text)

        # 失敗時應包含錯誤說明
        assert "翻譯失敗" in result
        # 失敗時應保留原文
        assert en_text in result

    # ──────────────────────────────────────────
    # 6. _build_analysis_prompt：Prompt 結構驗證
    # ──────────────────────────────────────────

    def test_build_analysis_prompt_zh_contains_transcript(self, analyzer):
        """中文影片的 prompt 應包含完整字幕內容"""
        video = _make_video(
            language="zh",
            transcript="這是完整的字幕逐字稿內容。",
        )
        prompt = analyzer._build_analysis_prompt(video)

        # prompt 應包含字幕內容
        assert "這是完整的字幕逐字稿內容" in prompt
        # 中文 prompt 應要求繁體中文輸出
        assert "繁體中文" in prompt

    def test_build_analysis_prompt_en_uses_english_template(self, analyzer):
        """英文影片的 prompt 應使用英文模板"""
        video = _make_video(
            language="en",
            title="Atomic Habits Summary",
            transcript="In this video we discuss tiny habits.",
        )
        prompt = analyzer._build_analysis_prompt(video)

        # 英文 prompt 應包含英文指令
        assert "key points" in prompt.lower() or "Key Points" in prompt
        # 應包含影片標題
        assert "Atomic Habits Summary" in prompt

    def test_build_analysis_prompt_no_transcript_uses_fallback(self, analyzer):
        """無字幕時 prompt 應改用標題與描述作為備用資訊來源，並標注說明"""
        video = _make_video(
            language="zh",
            transcript="",   # 無字幕
            title="說書影片",
            description="這是影片的描述文字",
        )
        prompt = analyzer._build_analysis_prompt(video)

        # 應在 prompt 中標注字幕不可用
        assert "無法取得" in prompt or "unavailable" in prompt.lower()
        # 應包含標題作為備用資訊
        assert "說書影片" in prompt

    def test_build_analysis_prompt_includes_video_metadata(self, analyzer):
        """prompt 應包含影片標題與頻道名稱等基本 metadata"""
        video = _make_video(
            title="原子習慣深度解析",
            channel_name="文森說書",
            language="zh",
        )
        prompt = analyzer._build_analysis_prompt(video)

        assert "原子習慣深度解析" in prompt
        assert "文森說書" in prompt
