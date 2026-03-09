# -*- coding: utf-8 -*-
"""讀書 Agent — YouTube 客戶端測試"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.reading_agent.youtube_client import YouTubeClient
from src.reading_agent.models import Video

# 模擬的 YouTube RSS Atom feed
_MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <title>文森說書</title>
  <entry>
    <id>yt:video:abc123</id>
    <yt:videoId>abc123</yt:videoId>
    <yt:channelId>UCPyR_jfaRH6KN2TOl4AM0uQ</yt:channelId>
    <title>《原子習慣》改變你人生的最小單位</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
    <published>{pub_date}</published>
    <media:group>
      <media:description>今天介紹一本改變無數人的好書</media:description>
    </media:group>
  </entry>
  <entry>
    <id>yt:video:def456</id>
    <yt:videoId>def456</yt:videoId>
    <title>《刻意練習》成為高手的秘密</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=def456"/>
    <published>{pub_date}</published>
    <media:group>
      <media:description>如何從新手變成專家</media:description>
    </media:group>
  </entry>
</feed>
"""

# 模組載入時的日期字串，供 replace 使用
_MOCK_PUB_DATE = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
_MOCK_RSS = _MOCK_RSS.format(pub_date=_MOCK_PUB_DATE)

_MOCK_CHANNEL = {
    "channel_id": "UCPyR_jfaRH6KN2TOl4AM0uQ",
    "name": "文森說書",
    "url": "https://www.youtube.com/@vincentshuoshu",
    "category": "general",
}


class TestYouTubeClient:
    @pytest.mark.asyncio
    async def test_fetch_channel_videos(self):
        """測試從單一頻道擷取影片"""
        mock_response = MagicMock()
        mock_response.text = _MOCK_RSS
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        client = YouTubeClient(channels=[_MOCK_CHANNEL])
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value=mock_response)

        videos = await client.fetch_channel_videos(_MOCK_CHANNEL, days_back=30)
        assert len(videos) == 2
        assert "原子習慣" in videos[0].title
        assert videos[0].channel_name == "文森說書"
        assert videos[0].category == "general"

    @pytest.mark.asyncio
    async def test_fetch_channel_date_filter(self):
        """測試日期過濾"""
        # 使用 30 天前的日期
        old_date = (datetime.now() - timedelta(days=60)).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00"
        )
        old_rss = _MOCK_RSS.replace(
            _MOCK_PUB_DATE,
            old_date,
        )
        mock_response = MagicMock()
        mock_response.text = old_rss
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        client = YouTubeClient(channels=[_MOCK_CHANNEL])
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value=mock_response)

        videos = await client.fetch_channel_videos(_MOCK_CHANNEL, days_back=7)
        assert len(videos) == 0  # 超過 7 天的影片被過濾

    @pytest.mark.asyncio
    async def test_fetch_channel_http_error(self):
        """測試 HTTP 錯誤處理"""
        import httpx

        client = YouTubeClient(channels=[_MOCK_CHANNEL])
        client._client = AsyncMock()

        error_response = MagicMock()
        error_response.status_code = 404
        client._client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=error_response
            )
        )

        videos = await client.fetch_channel_videos(_MOCK_CHANNEL, days_back=7)
        assert videos == []  # 錯誤時回傳空列表

    @pytest.mark.asyncio
    async def test_fetch_all_channels(self):
        """測試批次擷取所有頻道"""
        mock_response = MagicMock()
        mock_response.text = _MOCK_RSS
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        channels = [_MOCK_CHANNEL, {**_MOCK_CHANNEL, "name": "第二頻道"}]
        client = YouTubeClient(channels=channels)
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value=mock_response)

        videos = await client.fetch_all_channels(days_back=30)
        # 兩個頻道同樣的 RSS → 相同 URL → 去重後應為 2
        assert len(videos) == 2

    def test_extract_video_id(self):
        """測試影片 ID 提取"""
        # 從 yt:video:ID 格式
        entry = MagicMock()
        entry.get = lambda k, d="": {
            "id": "yt:video:abc123",
            "link": "",
        }.get(k, d)
        assert YouTubeClient._extract_video_id(entry) == "abc123"

    def test_extract_video_id_from_link(self):
        """測試從 URL 提取影片 ID"""
        entry = MagicMock(spec=[])
        entry.get = lambda k, d="": {
            "id": "",
            "link": "https://www.youtube.com/watch?v=xyz789tst01",
        }.get(k, d)
        assert YouTubeClient._extract_video_id(entry) == "xyz789tst01"
