# -*- coding: utf-8 -*-
"""sources/ 單元測試 — 各資訊來源爬蟲解析邏輯"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.japan_intel.sources.google_news import (
    _build_rss_url,
    _parse_rss_date,
    fetch_google_news,
)
from src.japan_intel.sources.industry_sites import fetch_industry_sites
from src.japan_intel.sources.japan_media import fetch_japan_media


class TestGoogleNewsRssUrl:
    """RSS URL 建構測試"""

    def test_japanese_url(self):
        url = _build_rss_url("カジノ", language="ja", days_back=7)
        assert "news.google.com/rss/search" in url
        assert "hl=ja" in url
        assert "gl=JP" in url
        assert "when=7d" in url

    def test_english_url(self):
        url = _build_rss_url("Japan casino", language="en", days_back=30)
        assert "hl=en" in url
        assert "when=30d" in url

    def test_yearly_url(self):
        url = _build_rss_url("test", language="ja", days_back=365)
        assert "when=1y" in url

    def test_keyword_encoding(self):
        url = _build_rss_url("日本 カジノ IR", language="ja")
        # 空格應被編碼
        assert "%E6" in url or "+" in url


class TestGoogleNewsDateParse:
    """RSS 日期解析測試"""

    def test_rfc2822_format(self):
        result = _parse_rss_date("Mon, 03 Mar 2026 08:00:00 GMT")
        assert "2026-03-03" in result

    def test_iso_format(self):
        result = _parse_rss_date("2026-03-03T08:00:00Z")
        assert "2026-03-03" in result

    def test_unparseable_returns_original(self):
        result = _parse_rss_date("invalid date format")
        assert result == "invalid date format"


@pytest.mark.asyncio
class TestGoogleNewsFetch:
    """Google News 蒐集整合測試（mock HTTP）"""

    async def test_returns_articles_from_rss(self):
        """成功解析 RSS 應回傳文章列表"""
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value="""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>大阪 IR 最新消息</title>
      <link>https://example.com/osaka-ir</link>
      <pubDate>Mon, 03 Mar 2026 08:00:00 GMT</pubDate>
      <description>大阪統合型リゾートの進捗</description>
    </item>
    <item>
      <title>日本カジノ法規</title>
      <link>https://example.com/japan-law</link>
      <pubDate>Sun, 02 Mar 2026 10:00:00 GMT</pubDate>
      <description>カジノ規制の最新動向</description>
    </item>
  </channel>
</rss>""")

        articles = await fetch_google_news(
            mock_fetcher, ["テスト"], language="ja", days_back=7,
        )
        assert len(articles) == 2
        assert articles[0].title == "大阪 IR 最新消息"
        assert articles[0].source == "Google News (日本語)"

    async def test_empty_response_returns_empty(self):
        """HTTP 回傳 None 時回傳空列表"""
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value=None)

        articles = await fetch_google_news(
            mock_fetcher, ["テスト"], language="ja",
        )
        assert articles == []


@pytest.mark.asyncio
class TestIndustrySitesFetch:
    """產業網站蒐集測試（mock HTTP）"""

    async def test_handles_all_fetch_failures_gracefully(self):
        """所有來源都失敗時不拋出例外，回傳空列表"""
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value=None)

        articles = await fetch_industry_sites(mock_fetcher, max_pages=1)
        assert articles == []

    async def test_parses_article_elements(self):
        """能解析 WordPress 風格 HTML"""
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value="""
<html><body>
<article class="post">
    <h2><a href="https://ggrasia.com/osaka-ir">Osaka IR Update</a></h2>
    <time datetime="2026-03-01">March 1, 2026</time>
    <p>The latest on Osaka integrated resort development.</p>
</article>
</body></html>""")

        articles = await fetch_industry_sites(mock_fetcher, max_pages=1)
        assert len(articles) >= 1


@pytest.mark.asyncio
class TestJapanMediaFetch:
    """日本媒體蒐集測試（mock HTTP）"""

    async def test_handles_all_fetch_failures_gracefully(self):
        """所有來源都失敗時不拋出例外"""
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch = AsyncMock(return_value=None)

        articles = await fetch_japan_media(mock_fetcher, ["テスト"])
        assert articles == []
