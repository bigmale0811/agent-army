# -*- coding: utf-8 -*-
"""讀書 Agent v2 — YouTube 影片搜尋模組

根據書籍資訊在 YouTube 搜尋對應的說書／書評影片。
中文書籍使用「{書名} 說書」關鍵字，英文書籍使用「{書名} book summary review」。
"""

import asyncio
import logging
from datetime import datetime

import httpx

# ------------------------------------------------------------------ #
# 相容性修補：youtube-search-python 1.6.x 使用已被 httpx 0.28+ 移除的
# proxies 參數，導致 post() got an unexpected keyword argument 'proxies'。
# ------------------------------------------------------------------ #
if not hasattr(httpx.post, "_patched_for_proxies"):
    _original_httpx_post = httpx.post

    def _patched_httpx_post(*args, **kwargs):
        kwargs.pop("proxies", None)
        return _original_httpx_post(*args, **kwargs)

    _patched_httpx_post._patched_for_proxies = True  # type: ignore[attr-defined]
    httpx.post = _patched_httpx_post

from youtubesearchpython import VideosSearch  # noqa: E402

from src.reading_agent.config import (
    MAX_SEARCH_RESULTS,
    MIN_VIDEO_DURATION,
    REQUEST_DELAY,
    SEARCH_KEYWORDS_EN,
    SEARCH_KEYWORDS_ZH,
)
from src.reading_agent.models import Book, Video

logger = logging.getLogger(__name__)


class YouTubeSearcher:
    """YouTube 影片搜尋器

    針對每本書建立搜尋關鍵字，透過 youtube-search-python 取得搜尋結果，
    並過濾掉長度不足的影片，最終轉換為 Video 資料物件。
    """

    def _build_search_query(self, book: Book) -> str:
        """依書籍語言建立搜尋關鍵字

        Args:
            book: 書籍資料物件

        Returns:
            用於 YouTube 搜尋的關鍵字字串
        """
        # 依語言選擇不同的搜尋模板
        if book.language == "en":
            return SEARCH_KEYWORDS_EN.format(book_title=book.title)
        else:
            # 預設為中文說書搜尋
            return SEARCH_KEYWORDS_ZH.format(book_title=book.title)

    def _parse_duration(self, duration_str: str) -> int:
        """將時間字串解析為秒數

        支援 "HH:MM:SS" 與 "MM:SS" 兩種格式。
        若格式不符合預期則回傳 0。

        Args:
            duration_str: 時間字串，例如 "1:23:45" 或 "12:34"

        Returns:
            總秒數，解析失敗時回傳 0
        """
        if not duration_str:
            return 0

        try:
            parts = duration_str.strip().split(":")
            if len(parts) == 3:
                # HH:MM:SS 格式
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:
                # MM:SS 格式
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60 + seconds
            else:
                logger.warning("無法解析時間字串: %s", duration_str)
                return 0
        except (ValueError, IndexError) as e:
            logger.warning("時間字串解析錯誤 '%s': %s", duration_str, e)
            return 0

    def _filter_by_duration(
        self, videos: list[Video], min_duration: int
    ) -> list[Video]:
        """過濾長度不足的影片

        Args:
            videos: 待過濾的影片列表
            min_duration: 最短長度（秒），低於此值的影片將被排除

        Returns:
            通過長度門檻的影片列表
        """
        filtered = [v for v in videos if v.duration_seconds >= min_duration]
        removed = len(videos) - len(filtered)
        if removed > 0:
            logger.debug(
                "過濾掉 %d 部長度不足 %d 秒的影片", removed, min_duration
            )
        return filtered

    def _parse_result_to_video(self, result: dict, book: Book) -> Video | None:
        """將 youtube-search-python 的單筆結果轉換為 Video 物件

        youtube-search-python 回傳的結構範例：
        {
            "title": "...",
            "id": "dQw4w9WgXcQ",
            "link": "https://www.youtube.com/watch?v=...",
            "channel": {"name": "...", "id": "..."},
            "duration": "12:34",
            "description": "...",
            "publishedTime": "3 weeks ago",
            "thumbnails": [{"url": "...", ...}],
            "viewCount": {"text": "1,234,567 views", ...},
        }

        Args:
            result: 單筆搜尋結果字典
            book: 對應的書籍物件

        Returns:
            Video 物件，若必要欄位缺失則回傳 None
        """
        try:
            title = result.get("title", "")
            url = result.get("link", "")
            video_id = result.get("id", "")

            # 必要欄位驗證：標題與 URL 不可為空
            if not title or not url:
                logger.debug("搜尋結果缺少標題或 URL，略過此筆")
                return None

            # 解析頻道資訊
            channel = result.get("channel", {})
            channel_name = channel.get("name", "")
            channel_id = channel.get("id", "")

            # 解析影片長度
            duration_str = result.get("duration", "") or ""
            duration_seconds = self._parse_duration(duration_str)

            # 取得最高解析度縮圖
            thumbnails = result.get("thumbnails", [])
            thumbnail = thumbnails[0].get("url", "") if thumbnails else ""

            # description 可能為 None，統一轉為字串
            description = result.get("description", "") or ""

            # publishedTime 為相對時間字串（如 "3 weeks ago"），
            # 無法轉換為 ISO 格式，直接保留原始字串
            published_at = result.get("publishedTime", "") or ""

            return Video(
                title=title,
                url=url,
                channel_name=channel_name,
                channel_id=channel_id,
                published_at=published_at,
                description=description,
                category="general",
                video_id=video_id,
                thumbnail=thumbnail,
                collected_at=datetime.now().isoformat(),
                duration_seconds=duration_seconds,
                language=book.language,
                book_title=book.title,
            )
        except Exception as e:
            logger.warning("轉換搜尋結果為 Video 時發生錯誤: %s", e)
            return None

    def _run_videos_search(self, query: str, limit: int) -> list[dict]:
        """同步執行 YouTube 搜尋並回傳原始結果列表

        此方法設計為在 asyncio.to_thread() 中執行，
        因為 youtubesearchpython 是同步阻塞式 API。

        Args:
            query: 搜尋關鍵字
            limit: 最多取得的結果數量

        Returns:
            搜尋結果字典列表，失敗時回傳空列表
        """
        try:
            search = VideosSearch(query, limit=limit)
            result = search.result()
            # result() 回傳 {"result": [...], "nextPage": ...} 結構
            return result.get("result", [])
        except Exception as e:
            logger.warning("YouTube 搜尋執行失敗，關鍵字 '%s': %s", query, e)
            return []

    async def search_for_book(self, book: Book) -> list[Video]:
        """搜尋指定書籍的相關 YouTube 影片

        依書籍語言建立搜尋關鍵字，呼叫 YouTube 搜尋 API，
        過濾長度不足的影片後回傳 Video 列表。

        Args:
            book: 目標書籍資料物件

        Returns:
            符合條件的 Video 列表（長度 >= MIN_VIDEO_DURATION）
        """
        query = self._build_search_query(book)
        logger.info("搜尋書籍《%s》，關鍵字: %s", book.title, query)

        # 使用 asyncio.to_thread 包裝同步的 YouTubeSearch 呼叫
        raw_results = await asyncio.to_thread(
            self._run_videos_search, query, MAX_SEARCH_RESULTS
        )

        if not raw_results:
            logger.warning("書籍《%s》搜尋無結果", book.title)
            return []

        # 將原始搜尋結果轉換為 Video 物件，過濾掉轉換失敗的筆數
        videos: list[Video] = []
        for result in raw_results:
            video = self._parse_result_to_video(result, book)
            if video is not None:
                videos.append(video)

        # 過濾長度不足的影片
        videos = self._filter_by_duration(videos, MIN_VIDEO_DURATION)

        logger.info(
            "書籍《%s》找到 %d 部符合條件的影片", book.title, len(videos)
        )
        return videos

    async def search_all_books(
        self, books: list[Book]
    ) -> dict[str, list[Video]]:
        """批次搜尋多本書籍的相關 YouTube 影片

        逐一處理每本書，搜尋之間插入延遲以避免請求過於頻繁。
        若單本書搜尋失敗，記錄警告並繼續處理其餘書籍。

        Args:
            books: 書籍列表

        Returns:
            以書名為鍵、影片列表為值的字典；
            搜尋失敗的書籍對應空列表
        """
        results: dict[str, list[Video]] = {}

        for index, book in enumerate(books):
            try:
                videos = await self.search_for_book(book)
                results[book.title] = videos
            except Exception as e:
                # 單本書搜尋失敗不應中斷整個批次作業
                logger.warning(
                    "批次搜尋中，書籍《%s》發生未預期錯誤，略過: %s",
                    book.title,
                    e,
                )
                results[book.title] = []

            # 在每次搜尋之間加入延遲，避免對 YouTube 造成過大請求壓力
            # 最後一本書不需要等待
            if index < len(books) - 1:
                await asyncio.sleep(REQUEST_DELAY)

        logger.info(
            "批次搜尋完成，共處理 %d 本書籍，找到 %d 部影片",
            len(books),
            sum(len(v) for v in results.values()),
        )
        return results
