# -*- coding: utf-8 -*-
"""讀書 Agent v2 — AI Weekly 資訊蒐集模組

功能：每週自動蒐集國內外 AI 最新資訊，包含固定頻道 RSS 追蹤
與 YouTube 關鍵字搜尋兩個資料來源，經 Gemini 深度重點整理後發送。

資料流程：
  固定 AI 頻道 (RSS)  +  YouTube 關鍵字搜尋 (AI 全領域)
              ↓                        ↓
         合併影片清單（去重、篩選 > 5 分鐘）
              ↓
    字幕擷取 (transcript_extractor — 100% 複用)
              ↓
    Gemini 深度重點整理 (AI 專用 prompt)
              ↓ (英文 → 翻譯成中文)
    中英雙語重點內容
"""

import asyncio
import logging
from datetime import datetime

import httpx

# ------------------------------------------------------------------ #
# 相容性修補：youtube-search-python 1.6.x 使用已被 httpx 0.28+ 移除的
# proxies 參數，導致 post() got an unexpected keyword argument 'proxies'。
# 在匯入 youtubesearchpython 之前先 patch httpx.post 以忽略該參數。
# ------------------------------------------------------------------ #
if not hasattr(httpx.post, "_patched_for_proxies"):
    _original_httpx_post = httpx.post

    def _patched_httpx_post(*args, **kwargs):
        kwargs.pop("proxies", None)
        return _original_httpx_post(*args, **kwargs)

    _patched_httpx_post._patched_for_proxies = True  # type: ignore[attr-defined]
    httpx.post = _patched_httpx_post

from youtubesearchpython import VideosSearch  # noqa: E402

from .config import (
    AI_MAX_SEARCH_PER_TOPIC,
    AI_SEARCH_TOPICS,
    MIN_VIDEO_DURATION,
    REQUEST_DELAY,
    load_ai_channels,
)
from .content_analyzer import ContentAnalyzer
from .models import Video
from .transcript_extractor import TranscriptExtractor
from .youtube_client import YouTubeClient

logger = logging.getLogger(__name__)


class AIWeeklyCollector:
    """AI Weekly 資訊蒐集器

    兩個資料來源：
    1. 固定 AI 頻道 RSS 追蹤（複用 youtube_client.py）
    2. YouTube 關鍵字搜尋（複用 youtubesearchpython）

    蒐集後自動去重、擷取字幕、Gemini 深度分析。
    """

    def __init__(self) -> None:
        """初始化蒐集器"""
        self._channels = load_ai_channels()

    async def collect(self, days_back: int = 7) -> list[Video]:
        """完整蒐集流程：搜尋 → 去重 → 字幕 → 分析

        Args:
            days_back: RSS 追蹤往回幾天

        Returns:
            經過完整處理的 AI 影片列表
        """
        start_time = datetime.now()
        logger.info("🤖 AI Weekly 蒐集開始")

        # 1. 固定頻道 RSS 追蹤
        channel_videos = await self._fetch_ai_channels(days_back)
        logger.info("📡 固定頻道找到 %d 部影片", len(channel_videos))

        # 2. 關鍵字搜尋
        search_videos = await self._search_ai_topics()
        logger.info("🔍 關鍵字搜尋找到 %d 部影片", len(search_videos))

        # 3. 合併去重
        all_videos = self._merge_and_deduplicate(channel_videos, search_videos)
        logger.info("📋 合併去重後共 %d 部影片", len(all_videos))

        if not all_videos:
            logger.warning("⚠️ AI Weekly 未找到任何影片")
            return []

        # 4. 字幕擷取
        logger.info("📝 開始擷取字幕...")
        extractor = TranscriptExtractor()
        all_videos = await extractor.extract_batch(all_videos)

        transcript_count = sum(1 for v in all_videos if v.transcript)
        logger.info("📝 字幕擷取完成：%d/%d 部取得字幕", transcript_count, len(all_videos))

        # 5. Gemini AI 專用分析
        logger.info("🧠 開始 AI 專用深度分析...")
        analyzer = ContentAnalyzer()
        all_videos = await analyzer.analyze_ai_batch(all_videos)

        analyzed_count = sum(1 for v in all_videos if v.key_points_zh)
        logger.info("🧠 分析完成：%d/%d 部已整理", analyzed_count, len(all_videos))

        elapsed = datetime.now() - start_time
        logger.info("🤖 AI Weekly 蒐集完成，耗時: %s", elapsed)
        return all_videos

    async def _fetch_ai_channels(self, days_back: int = 7) -> list[Video]:
        """透過 RSS 追蹤固定 AI 頻道的新影片

        Args:
            days_back: 往回幾天的影片

        Returns:
            固定頻道的新影片列表
        """
        if not self._channels:
            logger.info("📡 無固定 AI 頻道，跳過 RSS 追蹤")
            return []

        try:
            async with YouTubeClient(channels=self._channels) as client:
                videos = await client.fetch_all_channels(days_back=days_back)

            # 為每部影片標記語言（依頻道設定）
            channel_lang_map = {
                ch["channel_id"]: ch.get("language", "en")
                for ch in self._channels
            }
            for video in videos:
                if video.channel_id in channel_lang_map:
                    video.language = channel_lang_map[video.channel_id]

            return videos
        except Exception as e:
            logger.warning("📡 RSS 追蹤失敗: %s", e)
            return []

    async def _search_ai_topics(self) -> list[Video]:
        """透過 YouTube 關鍵字搜尋 AI 相關影片

        依序搜尋 AI_SEARCH_TOPICS 中的所有主題，
        每個主題取 AI_MAX_SEARCH_PER_TOPIC 個結果。

        Returns:
            搜尋到的 AI 影片列表
        """
        all_videos: list[Video] = []

        for idx, topic in enumerate(AI_SEARCH_TOPICS):
            logger.info("🔍 搜尋主題 %d/%d: %s", idx + 1, len(AI_SEARCH_TOPICS), topic)

            try:
                raw_results = await asyncio.to_thread(
                    self._run_search, topic, AI_MAX_SEARCH_PER_TOPIC
                )

                for result in raw_results:
                    video = self._parse_search_result(result, topic)
                    if video and video.duration_seconds >= MIN_VIDEO_DURATION:
                        all_videos.append(video)

            except Exception as e:
                logger.warning("搜尋主題 '%s' 失敗: %s", topic, e)

            # 搜尋間隔
            if idx < len(AI_SEARCH_TOPICS) - 1:
                await asyncio.sleep(REQUEST_DELAY)

        logger.info("🔍 關鍵字搜尋完成，共找到 %d 部影片", len(all_videos))
        return all_videos

    def _run_search(self, query: str, limit: int) -> list[dict]:
        """同步執行 YouTube 搜尋（在 asyncio.to_thread 中呼叫）

        Args:
            query: 搜尋關鍵字
            limit: 最多取得的結果數量

        Returns:
            搜尋結果字典列表
        """
        try:
            search = VideosSearch(query, limit=limit)
            result = search.result()
            return result.get("result", [])
        except Exception as e:
            logger.warning("YouTube 搜尋失敗，關鍵字 '%s': %s", query, e)
            return []

    def _parse_search_result(self, result: dict, topic: str) -> Video | None:
        """將 youtube-search-python 搜尋結果轉為 Video 物件

        Args:
            result: 單筆搜尋結果字典
            topic: 搜尋使用的主題關鍵字

        Returns:
            Video 物件，或 None（若必要欄位缺失）
        """
        try:
            title = result.get("title", "")
            url = result.get("link", "")
            video_id = result.get("id", "")

            if not title or not url:
                return None

            channel = result.get("channel", {})
            channel_name = channel.get("name", "")
            channel_id = channel.get("id", "")

            duration_str = result.get("duration", "") or ""
            duration_seconds = self._parse_duration(duration_str)

            description = result.get("description", "") or ""
            published_at = result.get("publishedTime", "") or ""

            # 依搜尋主題判斷語言
            is_chinese = any(
                "\u4e00" <= ch <= "\u9fff" for ch in topic
            )
            language = "zh" if is_chinese else "en"

            # 分類為 ai_general（後續可依頻道細分）
            category = "ai_general"

            return Video(
                title=title,
                url=url,
                channel_name=channel_name,
                channel_id=channel_id,
                published_at=published_at,
                description=description,
                category=category,
                video_id=video_id,
                collected_at=datetime.now().isoformat(),
                duration_seconds=duration_seconds,
                language=language,
            )
        except Exception as e:
            logger.warning("解析搜尋結果失敗: %s", e)
            return None

    @staticmethod
    def _parse_duration(duration_str: str) -> int:
        """將時間字串解析為秒數

        支援 "HH:MM:SS" 與 "MM:SS" 兩種格式。

        Args:
            duration_str: 時間字串

        Returns:
            總秒數
        """
        if not duration_str:
            return 0
        try:
            parts = duration_str.strip().split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            return 0
        except (ValueError, IndexError):
            return 0

    def _merge_and_deduplicate(
        self,
        channel_videos: list[Video],
        search_videos: list[Video],
    ) -> list[Video]:
        """合併兩個來源的影片並去重

        以 video_id 為主鍵去重，RSS 頻道影片優先保留。

        Args:
            channel_videos: 固定頻道 RSS 追蹤影片
            search_videos: 關鍵字搜尋影片

        Returns:
            去重後的影片列表
        """
        seen_ids: set[str] = set()
        merged: list[Video] = []

        # 固定頻道影片優先
        for video in channel_videos:
            vid = video.video_id or video.url
            if vid not in seen_ids:
                seen_ids.add(vid)
                merged.append(video)

        # 搜尋影片補充
        for video in search_videos:
            vid = video.video_id or video.url
            if vid not in seen_ids:
                seen_ids.add(vid)
                merged.append(video)

        removed = (len(channel_videos) + len(search_videos)) - len(merged)
        if removed > 0:
            logger.info("去重移除 %d 部重複影片", removed)

        return merged
