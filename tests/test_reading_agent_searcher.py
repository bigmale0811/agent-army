# -*- coding: utf-8 -*-
"""讀書 Agent v2 — YouTubeSearcher 測試

測試 YouTube 影片搜尋器的核心功能：
- search_for_book 搜尋單本書籍
- search_all_books 批次搜尋
- _build_search_query 依語言產生不同關鍵字
- _filter_by_duration 過濾長度不足的影片（>= 5 分鐘）
- 空結果與錯誤的容錯處理
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reading_agent.models import Book, Video
from src.reading_agent.youtube_searcher import YouTubeSearcher


# ─────────────────────────────────────────────
# 共用輔助函式與測試資料
# ─────────────────────────────────────────────

def _make_book(title: str, language: str = "zh") -> Book:
    """建立測試用 Book 物件"""
    return Book(title=title, language=language, sources=["博客來"])


def _make_raw_result(
    title: str = "說書影片",
    video_id: str = "abc123",
    duration: str = "15:00",
    channel_name: str = "測試頻道",
) -> dict:
    """建立模擬的 youtube-search-python 原始搜尋結果"""
    return {
        "title": title,
        "id": video_id,
        "link": f"https://www.youtube.com/watch?v={video_id}",
        "channel": {"name": channel_name, "id": "UC_test"},
        "duration": duration,
        "description": "這是一部說書影片",
        "publishedTime": "2 weeks ago",
        "thumbnails": [{"url": f"https://img.youtube.com/vi/{video_id}/0.jpg"}],
        "viewCount": {"text": "12,345 views"},
    }


def _make_video(
    title: str = "說書影片",
    video_id: str = "abc123",
    duration_seconds: int = 900,
    language: str = "zh",
) -> Video:
    """建立測試用 Video 物件"""
    return Video(
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_name="測試頻道",
        channel_id="UC_test",
        published_at="2 weeks ago",
        video_id=video_id,
        duration_seconds=duration_seconds,
        language=language,
        book_title="原子習慣",
    )


# ─────────────────────────────────────────────
# YouTubeSearcher 測試類別
# ─────────────────────────────────────────────

class TestYouTubeSearcher:
    """YouTubeSearcher 的單元測試"""

    @pytest.fixture
    def searcher(self):
        """每個測試使用全新的搜尋器實例"""
        return YouTubeSearcher()

    # ──────────────────────────────────────────
    # 1. _build_search_query：依語言產生不同關鍵字
    # ──────────────────────────────────────────

    def test_build_search_query_zh_book(self, searcher):
        """中文書籍應使用「說書」關鍵字模板"""
        book = _make_book("原子習慣", language="zh")
        query = searcher._build_search_query(book)

        # 中文書籍搜尋關鍵字應包含書名與「說書」
        assert "原子習慣" in query
        assert "說書" in query

    def test_build_search_query_en_book(self, searcher):
        """英文書籍應使用 'book summary review' 關鍵字模板"""
        book = _make_book("Atomic Habits", language="en")
        query = searcher._build_search_query(book)

        # 英文書籍搜尋關鍵字應包含書名與 "book summary review"
        assert "Atomic Habits" in query
        assert "book summary review" in query.lower()

    def test_build_search_query_non_en_defaults_to_zh_template(self, searcher):
        """'en' 以外的任何語言均使用中文說書模板（else 分支的預設行為）

        _build_search_query 只對 language == 'en' 使用英文模板，
        其餘語言（包括 'ko'、'ja' 等）均落入 else 分支套用中文模板。
        """
        book = _make_book("일상의 책", language="ko")
        query = searcher._build_search_query(book)

        # 非 'en' 語言應套用中文說書模板（含「說書」關鍵字）
        assert "說書" in query
        assert book.title in query

    # ──────────────────────────────────────────
    # 2. _parse_duration：時間字串解析
    # ──────────────────────────────────────────

    def test_parse_duration_mm_ss_format(self, searcher):
        """解析 MM:SS 格式（如 '12:34'）"""
        assert searcher._parse_duration("12:34") == 754

    def test_parse_duration_hh_mm_ss_format(self, searcher):
        """解析 HH:MM:SS 格式（如 '1:23:45'）"""
        assert searcher._parse_duration("1:23:45") == 5025

    def test_parse_duration_invalid_returns_zero(self, searcher):
        """無效格式應回傳 0"""
        assert searcher._parse_duration("invalid") == 0
        assert searcher._parse_duration("") == 0

    # ──────────────────────────────────────────
    # 3. duration filtering：過濾短影片
    # ──────────────────────────────────────────

    def test_filter_by_duration_excludes_short_videos(self, searcher):
        """長度不足 MIN_VIDEO_DURATION（300 秒 = 5 分鐘）的影片應被過濾"""
        videos = [
            _make_video("短影片A", video_id="s1", duration_seconds=120),  # 2 分鐘，應被過濾
            _make_video("短影片B", video_id="s2", duration_seconds=299),  # 不足 5 分鐘，應被過濾
            _make_video("合格影片", video_id="s3", duration_seconds=300), # 剛好 5 分鐘，通過
            _make_video("長影片", video_id="s4", duration_seconds=1800),  # 30 分鐘，通過
        ]
        # 使用 min_duration=300（與 config.MIN_VIDEO_DURATION 相同）
        filtered = searcher._filter_by_duration(videos, min_duration=300)

        assert len(filtered) == 2
        titles = [v.title for v in filtered]
        assert "合格影片" in titles
        assert "長影片" in titles
        assert "短影片A" not in titles
        assert "短影片B" not in titles

    def test_filter_by_duration_all_pass(self, searcher):
        """所有影片均符合長度門檻時，應回傳全部"""
        videos = [_make_video(f"影片{i}", video_id=f"v{i}", duration_seconds=600) for i in range(3)]
        filtered = searcher._filter_by_duration(videos, min_duration=300)
        assert len(filtered) == 3

    # ──────────────────────────────────────────
    # 4. search_for_book：單本書搜尋
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_for_book_returns_filtered_videos(self, searcher):
        """search_for_book 應回傳通過長度過濾的 Video 列表"""
        book = _make_book("原子習慣")

        # 準備兩筆搜尋結果：一長一短
        raw_results = [
            _make_raw_result(title="原子習慣完整說書", video_id="long1", duration="20:00"),
            _make_raw_result(title="原子習慣一分鐘", video_id="short1", duration="1:00"),
        ]

        # 以同步函式模擬 _run_videos_search（在 to_thread 中執行）
        with patch.object(searcher, "_run_videos_search", return_value=raw_results):
            videos = await searcher.search_for_book(book)

        # 只有長度 >= 300 秒的影片應通過過濾
        assert len(videos) == 1
        assert videos[0].title == "原子習慣完整說書"
        # 影片應與書籍建立關聯
        assert videos[0].book_title == "原子習慣"
        assert videos[0].language == "zh"

    @pytest.mark.asyncio
    async def test_search_for_book_returns_empty_when_no_results(self, searcher):
        """搜尋無結果時應回傳空列表（不拋出例外）"""
        book = _make_book("不存在的書")

        with patch.object(searcher, "_run_videos_search", return_value=[]):
            videos = await searcher.search_for_book(book)

        assert videos == []

    @pytest.mark.asyncio
    async def test_search_for_book_handles_parse_error_gracefully(self, searcher):
        """搜尋結果缺少必要欄位時，應略過該筆並繼續處理其餘結果"""
        book = _make_book("原子習慣")

        raw_results = [
            # 缺少 title 的無效結果（應被略過）
            {"id": "bad1", "link": "https://youtube.com/watch?v=bad1", "duration": "10:00"},
            # 正常結果
            _make_raw_result(title="原子習慣說書", video_id="good1", duration="12:00"),
        ]

        with patch.object(searcher, "_run_videos_search", return_value=raw_results):
            videos = await searcher.search_for_book(book)

        # 無效結果被略過，有效結果正常處理
        valid = [v for v in videos if v.title == "原子習慣說書"]
        assert len(valid) == 1

    # ──────────────────────────────────────────
    # 5. search_all_books：批次搜尋
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_all_books_returns_dict_keyed_by_title(self, searcher):
        """search_all_books 應回傳以書名為鍵的字典"""
        books = [
            _make_book("原子習慣"),
            _make_book("Atomic Habits", language="en"),
        ]

        # 為每本書模擬不同的搜尋結果
        def mock_run_search(query, limit):
            if "原子習慣" in query:
                return [_make_raw_result(title="原子習慣說書", video_id="zh1", duration="15:00")]
            if "Atomic Habits" in query:
                return [_make_raw_result(title="Atomic Habits Summary", video_id="en1", duration="18:00")]
            return []

        with patch.object(searcher, "_run_videos_search", side_effect=mock_run_search):
            # 覆蓋 sleep 避免測試等待
            with patch("src.reading_agent.youtube_searcher.asyncio.sleep", new_callable=AsyncMock):
                result = await searcher.search_all_books(books)

        # 結果是字典，鍵為書名
        assert isinstance(result, dict)
        assert "原子習慣" in result
        assert "Atomic Habits" in result

        # 每本書都應有對應的影片列表
        assert isinstance(result["原子習慣"], list)
        assert isinstance(result["Atomic Habits"], list)

    @pytest.mark.asyncio
    async def test_search_all_books_continues_on_book_failure(self, searcher):
        """單本書搜尋失敗時，其他書籍的搜尋應繼續進行"""
        books = [
            _make_book("失敗書籍"),
            _make_book("正常書籍"),
        ]

        async def mock_search_for_book(book):
            if "失敗" in book.title:
                raise RuntimeError("模擬搜尋失敗")
            return [_make_video("正常影片", video_id="ok1", duration_seconds=600)]

        with patch.object(searcher, "search_for_book", side_effect=mock_search_for_book):
            with patch("src.reading_agent.youtube_searcher.asyncio.sleep", new_callable=AsyncMock):
                result = await searcher.search_all_books(books)

        # 失敗的書籍應有空列表（不中斷批次）
        assert result["失敗書籍"] == []
        # 正常書籍應有結果
        assert len(result["正常書籍"]) >= 1

    @pytest.mark.asyncio
    async def test_search_all_books_empty_input(self, searcher):
        """傳入空書籍列表時應回傳空字典"""
        result = await searcher.search_all_books([])
        assert result == {}
