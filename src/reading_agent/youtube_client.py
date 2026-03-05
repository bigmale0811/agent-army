# -*- coding: utf-8 -*-
"""讀書 Agent — YouTube RSS 客戶端

從 YouTube 說書頻道的 Atom RSS feed 擷取最新影片資訊。
使用 feedparser 解析 Atom XML，httpx 進行非同步 HTTP 請求。
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from time import mktime

import feedparser
import httpx

from .config import (
    YOUTUBE_RSS_BASE,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    load_channels,
)
from .models import Video

logger = logging.getLogger(__name__)


class YouTubeClient:
    """YouTube RSS 客戶端

    功能：
    - 從單一頻道的 RSS feed 擷取最新影片
    - 批次擷取所有設定頻道的影片
    - 自動限速、重試、錯誤處理
    - 支援日期範圍過濾
    """

    def __init__(self, channels: Optional[list[dict]] = None):
        """初始化 YouTube 客戶端

        Args:
            channels: 頻道列表（若為 None 則從設定載入）
        """
        self._client: Optional[httpx.AsyncClient] = None
        self._channels = channels or load_channels()

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "AgentArmy-ReadingAgent/1.0"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    def channels(self) -> list[dict]:
        return self._channels

    async def fetch_channel_videos(
        self,
        channel_config: dict,
        days_back: int = 7,
    ) -> list[Video]:
        """擷取指定頻道的最新影片

        透過 YouTube RSS feed 取得頻道的近期影片，
        並依照 days_back 過濾日期範圍。

        Args:
            channel_config: 頻道設定（需包含 channel_id, name）
            days_back: 往回蒐集的天數

        Returns:
            符合日期範圍的影片列表
        """
        if not self._client:
            raise RuntimeError("請使用 async with 進入 context manager")

        channel_id = channel_config["channel_id"]
        channel_name = channel_config.get("name", channel_id)
        rss_url = f"{YOUTUBE_RSS_BASE}?channel_id={channel_id}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.get(rss_url)
                response.raise_for_status()

                # 使用 feedparser 解析 Atom XML
                feed = feedparser.parse(response.text)

                if not feed.entries:
                    logger.warning("[%s] RSS feed 無任何項目", channel_name)
                    return []

                videos = []
                cutoff = datetime.now() - timedelta(days=days_back)

                for entry in feed.entries:
                    # 解析發布日期
                    published = self._parse_date(entry)
                    if published and published < cutoff:
                        continue

                    # 擷取影片 ID（從 entry.id 或 link 中提取）
                    video_id = self._extract_video_id(entry)

                    # 擷取描述（YouTube RSS 使用 media_group）
                    description = self._extract_description(entry)

                    video = Video(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        channel_name=channel_name,
                        channel_id=channel_id,
                        published_at=published.isoformat() if published else "",
                        description=description[:500],
                        category=channel_config.get("category", "general"),
                        video_id=video_id,
                        thumbnail=(
                            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                            if video_id else ""
                        ),
                    )
                    videos.append(video)

                logger.info(
                    "從 [%s] 擷取到 %d 部影片（%d 天內）",
                    channel_name, len(videos), days_back,
                )
                return videos

            except httpx.HTTPStatusError as e:
                logger.warning(
                    "[%s] HTTP %d（第 %d/%d 次）",
                    channel_name, e.response.status_code,
                    attempt, MAX_RETRIES,
                )
            except httpx.TimeoutException:
                logger.warning(
                    "[%s] 請求逾時（第 %d/%d 次）",
                    channel_name, attempt, MAX_RETRIES,
                )
            except Exception as e:
                logger.warning(
                    "[%s] 擷取失敗（第 %d/%d 次）: %s",
                    channel_name, attempt, MAX_RETRIES, e,
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(REQUEST_DELAY * attempt)

        logger.error("[%s] 擷取失敗，已達重試上限", channel_name)
        return []

    async def fetch_all_channels(self, days_back: int = 7) -> list[Video]:
        """擷取所有頻道的最新影片

        依序對每個頻道發送 RSS 請求，並彙整結果。
        請求間有延遲以避免被限速。

        Args:
            days_back: 往回蒐集的天數（預設 7 天）

        Returns:
            所有影片列表（按發布日期降序排列）
        """
        all_videos: list[Video] = []

        for channel_config in self._channels:
            videos = await self.fetch_channel_videos(channel_config, days_back)
            all_videos.extend(videos)
            # 請求間隔，避免觸發限速
            await asyncio.sleep(REQUEST_DELAY)

        # 按發布日期降序排列
        all_videos.sort(key=lambda v: v.published_at, reverse=True)

        # URL 去重
        seen_urls: set[str] = set()
        unique_videos: list[Video] = []
        for video in all_videos:
            if video.url not in seen_urls:
                seen_urls.add(video.url)
                unique_videos.append(video)

        logger.info(
            "共擷取 %d 部影片（去重後 %d 部），來自 %d 個頻道",
            len(all_videos), len(unique_videos), len(self._channels),
        )
        return unique_videos

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """解析 feedparser entry 的發布日期"""
        # 嘗試 published_parsed
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime.fromtimestamp(mktime(entry.published_parsed))
            except (ValueError, OverflowError, OSError):
                pass

        # 嘗試 updated_parsed
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime.fromtimestamp(mktime(entry.updated_parsed))
            except (ValueError, OverflowError, OSError):
                pass

        # 嘗試直接解析 published 字串
        published_str = entry.get("published", "")
        if published_str:
            for fmt in [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S+00:00",
                "%Y-%m-%d",
            ]:
                try:
                    return datetime.strptime(published_str, fmt).replace(tzinfo=None)
                except ValueError:
                    continue

        return datetime.now()

    @staticmethod
    def _extract_video_id(entry) -> str:
        """從 entry 中提取 YouTube 影片 ID

        YouTube Atom feed 的 entry.id 格式為 'yt:video:VIDEO_ID'
        """
        # 從 entry.id 提取
        entry_id = entry.get("id", "")
        if entry_id.startswith("yt:video:"):
            return entry_id[9:]

        # 從 yt_videoid 屬性提取（feedparser 可能解析為此）
        if hasattr(entry, "yt_videoid"):
            return entry.yt_videoid

        # 從 link URL 提取
        link = entry.get("link", "")
        match = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", link)
        if match:
            return match.group(1)

        return ""

    @staticmethod
    def _extract_description(entry) -> str:
        """從 entry 中提取影片描述

        YouTube Atom feed 的描述在 media:group > media:description 中，
        feedparser 可能將其解析為 media_description 或 summary。
        """
        # 嘗試 media_group 中的 description
        if hasattr(entry, "media_group"):
            for item in entry.media_group:
                if hasattr(item, "content"):
                    for content in item.get("content", []):
                        if "description" in str(content.get("type", "")):
                            return content.get("value", "")

        # feedparser 可能將 media:description 解析為 summary
        summary = entry.get("summary", "")
        if summary:
            return summary

        # 嘗試 media_description
        if hasattr(entry, "media_description"):
            return entry.media_description

        return ""
