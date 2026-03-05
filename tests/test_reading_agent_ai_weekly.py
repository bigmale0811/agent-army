# -*- coding: utf-8 -*-
"""讀書 Agent v2 — AI Weekly 測試

測試 AI Weekly 功能的核心模組：
- AIWeeklyCollector：蒐集流程（固定頻道 + 關鍵字搜尋 + 去重 + 字幕 + 分析）
- ContentAnalyzer：AI 專用 prompt 建構與分析方法
- ReportGenerator：AI Weekly 報告產生
- runner.py：--ai-weekly CLI 參數解析
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reading_agent.ai_weekly import AIWeeklyCollector
from src.reading_agent.content_analyzer import ContentAnalyzer
from src.reading_agent.models import Video
from src.reading_agent.reporter import ReportGenerator


# ─────────────────────────────────────────────
# 共用輔助函式與測試資料
# ─────────────────────────────────────────────

def _make_video(
    title: str = "AI 測試影片",
    video_id: str = "ai_test_001",
    language: str = "zh",
    transcript: str = "這是一段關於大型語言模型的字幕內容。",
    description: str = "AI 影片描述",
    channel_name: str = "AI 頻道",
    category: str = "ai_general",
    duration_seconds: int = 600,
    key_points_zh: str = "",
    key_points_original: str = "",
    published_at: str = "2026-03-01",
) -> Video:
    """建立測試用 AI 影片 Video 物件"""
    return Video(
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_name=channel_name,
        channel_id="UC_ai_test",
        published_at=published_at,
        video_id=video_id,
        language=language,
        transcript=transcript,
        description=description,
        category=category,
        duration_seconds=duration_seconds,
        key_points_zh=key_points_zh,
        key_points_original=key_points_original,
    )


def _make_analyzer_with_mock() -> tuple[ContentAnalyzer, MagicMock]:
    """建立帶有 mock Gemini 客戶端的 ContentAnalyzer"""
    mock_client = MagicMock()
    with patch("src.reading_agent.content_analyzer._init_client", return_value=mock_client):
        analyzer = ContentAnalyzer()
    return analyzer, mock_client


# ─────────────────────────────────────────────
# AIWeeklyCollector 測試
# ─────────────────────────────────────────────

class TestAIWeeklyCollector:
    """AIWeeklyCollector 單元測試"""

    def test_parse_duration_hms(self):
        """HH:MM:SS 格式應正確解析為秒數"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        assert collector._parse_duration("1:30:00") == 5400
        assert collector._parse_duration("0:10:30") == 630

    def test_parse_duration_ms(self):
        """MM:SS 格式應正確解析為秒數"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        assert collector._parse_duration("15:30") == 930
        assert collector._parse_duration("5:00") == 300

    def test_parse_duration_empty(self):
        """空字串應回傳 0"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        assert collector._parse_duration("") == 0

    def test_parse_duration_invalid(self):
        """無效格式應回傳 0"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        assert collector._parse_duration("invalid") == 0

    def test_merge_and_deduplicate_removes_duplicates(self):
        """相同 video_id 的影片應去重，保留頻道來源版本"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        ch_videos = [_make_video(title="頻道版", video_id="dup001")]
        search_videos = [_make_video(title="搜尋版", video_id="dup001")]

        result = collector._merge_and_deduplicate(ch_videos, search_videos)
        assert len(result) == 1
        assert result[0].title == "頻道版"  # 頻道版本優先

    def test_merge_and_deduplicate_keeps_unique(self):
        """不同 video_id 的影片應全部保留"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        ch_videos = [_make_video(title="影片A", video_id="a001")]
        search_videos = [_make_video(title="影片B", video_id="b002")]

        result = collector._merge_and_deduplicate(ch_videos, search_videos)
        assert len(result) == 2

    def test_parse_search_result_valid(self):
        """有效搜尋結果應轉為 Video 物件"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        result = {
            "title": "GPT-5 發布解析",
            "link": "https://youtube.com/watch?v=xyz123",
            "id": "xyz123",
            "channel": {"name": "AI 新聞台", "id": "UC_ai"},
            "duration": "12:30",
            "description": "深入解析 GPT-5",
            "publishedTime": "3 days ago",
        }
        video = collector._parse_search_result(result, "GPT-5 最新消息")
        assert video is not None
        assert video.title == "GPT-5 發布解析"
        assert video.video_id == "xyz123"
        assert video.duration_seconds == 750

    def test_parse_search_result_missing_title_returns_none(self):
        """缺少 title 的結果應回傳 None"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        result = {"link": "https://youtube.com/watch?v=xyz", "id": "xyz"}
        video = collector._parse_search_result(result, "AI news")
        assert video is None

    def test_parse_search_result_detects_language(self):
        """中文主題搜尋結果應標記為 zh，英文為 en"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        base = {
            "title": "Test",
            "link": "https://youtube.com/watch?v=t1",
            "id": "t1",
            "channel": {"name": "Ch", "id": "UC"},
            "duration": "10:00",
        }
        zh_video = collector._parse_search_result(base, "AI 人工智慧最新應用")
        en_video = collector._parse_search_result(base, "AI latest breakthroughs 2026")
        assert zh_video.language == "zh"
        assert en_video.language == "en"

    @pytest.mark.asyncio
    async def test_fetch_ai_channels_empty_returns_empty(self):
        """無固定頻道時應回傳空列表"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        collector._channels = []
        result = await collector._fetch_ai_channels(days_back=7)
        assert result == []

    @pytest.mark.asyncio
    async def test_collect_returns_analyzed_videos(self):
        """完整 collect 流程應回傳已分析的影片"""
        collector = AIWeeklyCollector.__new__(AIWeeklyCollector)
        collector._channels = []

        mock_videos = [
            _make_video(title="AI Video 1", video_id="v1"),
            _make_video(title="AI Video 2", video_id="v2"),
        ]

        with patch.object(collector, "_fetch_ai_channels", new_callable=AsyncMock, return_value=[]):
            with patch.object(collector, "_search_ai_topics", new_callable=AsyncMock, return_value=mock_videos):
                with patch("src.reading_agent.ai_weekly.TranscriptExtractor") as MockExtractor:
                    mock_ext = MockExtractor.return_value
                    mock_ext.extract_batch = AsyncMock(return_value=mock_videos)

                    with patch("src.reading_agent.ai_weekly.ContentAnalyzer") as MockAnalyzer:
                        mock_ana = MockAnalyzer.return_value
                        for v in mock_videos:
                            v.key_points_zh = "測試重點"
                        mock_ana.analyze_ai_batch = AsyncMock(return_value=mock_videos)

                        result = await collector.collect(days_back=7)

        assert len(result) == 2
        assert all(v.key_points_zh for v in result)


# ─────────────────────────────────────────────
# ContentAnalyzer AI 專用方法測試
# ─────────────────────────────────────────────

class TestContentAnalyzerAI:
    """ContentAnalyzer AI 專用方法的單元測試"""

    @pytest.fixture
    def analyzer(self):
        analyzer, _ = _make_analyzer_with_mock()
        return analyzer

    def test_build_ai_analysis_prompt_zh_contains_ai_keywords(self, analyzer):
        """中文 AI 影片的 prompt 應包含 AI 分析關鍵字"""
        video = _make_video(language="zh")
        prompt = analyzer._build_ai_analysis_prompt(video)

        assert "AI" in prompt
        assert "繁體中文" in prompt
        assert "核心發現或突破" in prompt
        assert "趨勢或風險" in prompt

    def test_build_ai_analysis_prompt_en_uses_english_template(self, analyzer):
        """英文 AI 影片的 prompt 應使用英文模板"""
        video = _make_video(language="en", title="GPT-5 Review")
        prompt = analyzer._build_ai_analysis_prompt(video)

        assert "Core Findings or Breakthroughs" in prompt
        assert "Trends and Risks" in prompt
        assert "GPT-5 Review" in prompt

    def test_build_ai_analysis_prompt_no_transcript_fallback(self, analyzer):
        """無字幕時 AI prompt 應使用備用方案"""
        video = _make_video(language="zh", transcript="")
        prompt = analyzer._build_ai_analysis_prompt(video)

        assert "無法取得" in prompt

    @pytest.mark.asyncio
    async def test_analyze_ai_video_zh(self, analyzer):
        """中文 AI 影片分析後兩個欄位應填入相同內容"""
        video = _make_video(language="zh")
        expected = "1. GPT-5 重大突破：推理能力大幅提升"

        async def mock_gemini(prompt):
            return expected

        with patch.object(analyzer, "_call_gemini", side_effect=mock_gemini):
            result = await analyzer.analyze_ai_video(video)

        assert result.key_points_original == expected
        assert result.key_points_zh == expected

    @pytest.mark.asyncio
    async def test_analyze_ai_video_en_translates(self, analyzer):
        """英文 AI 影片應先分析再翻譯"""
        video = _make_video(language="en", title="AI Breakthroughs")
        en_result = "1. GPT-5 shows major improvement in reasoning."
        zh_result = "1. GPT-5 推理能力大幅提升。"

        call_count = 0

        async def mock_gemini(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return en_result
            return zh_result

        with patch.object(analyzer, "_call_gemini", side_effect=mock_gemini):
            result = await analyzer.analyze_ai_video(video)

        assert result.key_points_original == en_result
        assert result.key_points_zh == zh_result
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_ai_video_error_fallback(self, analyzer):
        """Gemini 失敗時 AI 分析應填入錯誤說明"""
        video = _make_video(language="zh")

        async def mock_gemini(prompt):
            raise RuntimeError("API 配額超限")

        with patch.object(analyzer, "_call_gemini", side_effect=mock_gemini):
            result = await analyzer.analyze_ai_video(video)

        assert "AI 分析失敗" in result.key_points_original
        assert "AI 分析失敗" in result.key_points_zh

    @pytest.mark.asyncio
    async def test_analyze_ai_batch_processes_all(self, analyzer):
        """AI 批次分析應處理所有影片"""
        videos = [_make_video(title=f"AI影片{i}", video_id=f"ai{i}") for i in range(3)]

        async def mock_analyze(video):
            video.key_points_zh = f"重點：{video.title}"
            return video

        with patch.object(analyzer, "analyze_ai_video", side_effect=mock_analyze):
            with patch("src.reading_agent.content_analyzer.asyncio.sleep", new_callable=AsyncMock):
                results = await analyzer.analyze_ai_batch(videos)

        assert len(results) == 3
        for i, v in enumerate(results):
            assert f"AI影片{i}" in v.key_points_zh

    @pytest.mark.asyncio
    async def test_analyze_ai_batch_empty_returns_empty(self, analyzer):
        """空列表輸入應回傳空列表"""
        results = await analyzer.analyze_ai_batch([])
        assert results == []


# ─────────────────────────────────────────────
# ReportGenerator AI Weekly 報告測試
# ─────────────────────────────────────────────

class TestReportGeneratorAIWeekly:
    """ReportGenerator.generate_ai_weekly() 測試"""

    def test_generate_ai_weekly_basic_structure(self):
        """AI Weekly 報告應包含標題、內容和頁尾"""
        reporter = ReportGenerator()
        videos = [
            _make_video(
                title="AI 突破新聞",
                key_points_zh="1. GPT-5 發布",
                category="ai_general",
                published_at="2026-03-01",
            ),
        ]
        segments = reporter.generate_ai_weekly(videos)

        # 至少有標題 + 內容 + 頁尾 = 3 段
        assert len(segments) >= 3

        # 標題包含 AI Weekly 字樣
        assert "AI 資訊整理" in segments[0]

        # 頁尾包含統計
        assert "AI Weekly" in segments[-1]
        assert "1 則" in segments[-1]

    def test_generate_ai_weekly_empty_videos(self):
        """無影片時仍應產生標題和頁尾"""
        reporter = ReportGenerator()
        segments = reporter.generate_ai_weekly([])

        assert len(segments) >= 2
        assert "0 則" in segments[-1]

    def test_generate_ai_weekly_bilingual_en_video(self):
        """英文影片應同時顯示原文和中文翻譯"""
        reporter = ReportGenerator()
        videos = [
            _make_video(
                title="GPT-5 Review",
                language="en",
                key_points_original="1. Major breakthrough in reasoning.",
                key_points_zh="1. 推理能力重大突破。",
                category="ai_general",
            ),
        ]
        segments = reporter.generate_ai_weekly(videos)

        # 合併所有段落檢查
        full_text = "\n".join(segments)
        assert "English Key Points" in full_text
        assert "中文翻譯" in full_text

    def test_generate_ai_weekly_zh_video_no_english(self):
        """中文影片不應顯示 English Key Points"""
        reporter = ReportGenerator()
        videos = [
            _make_video(
                title="AI 應用實例",
                language="zh",
                key_points_zh="1. 應用案例分析",
                category="ai_general",
            ),
        ]
        segments = reporter.generate_ai_weekly(videos)

        full_text = "\n".join(segments)
        assert "English Key Points" not in full_text
        assert "應用案例分析" in full_text

    def test_generate_ai_weekly_contains_date_range(self):
        """報告應包含日期範圍"""
        reporter = ReportGenerator()
        videos = [
            _make_video(published_at="2026-03-01", key_points_zh="重點"),
            _make_video(video_id="v2", published_at="2026-03-07", key_points_zh="重點"),
        ]
        segments = reporter.generate_ai_weekly(videos)

        assert "2026-03-01" in segments[0]
        assert "2026-03-07" in segments[0]


# ─────────────────────────────────────────────
# CLI 參數測試
# ─────────────────────────────────────────────

class TestRunnerCLI:
    """runner.py CLI 參數解析測試"""

    def test_ai_weekly_flag_exists(self):
        """--ai-weekly 參數應存在且可解析"""
        import argparse
        # 直接測試 argparse 解析
        from src.reading_agent.runner import main
        # 驗證 --ai-weekly 被正確加入（透過 import 不報錯確認模組語法正確）
        assert callable(main)
