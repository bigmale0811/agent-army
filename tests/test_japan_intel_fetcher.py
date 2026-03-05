# -*- coding: utf-8 -*-
"""fetcher.py 單元測試 — HTTP 客戶端限速與重試"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from src.japan_intel.fetcher import RateLimitedFetcher


@pytest.mark.asyncio
class TestRateLimitedFetcher:
    """RateLimitedFetcher 測試"""

    async def test_context_manager(self):
        """async context manager 正確初始化和關閉"""
        async with RateLimitedFetcher(delay=0) as fetcher:
            assert fetcher._client is not None
        assert fetcher._client is None

    async def test_fetch_without_init_raises(self):
        """未初始化直接呼叫 fetch 應拋出 RuntimeError"""
        fetcher = RateLimitedFetcher(delay=0)
        with pytest.raises(RuntimeError, match="未初始化"):
            await fetcher.fetch("https://example.com")

    @patch("src.japan_intel.fetcher.asyncio.sleep", new_callable=AsyncMock)
    async def test_fetch_success(self, mock_sleep):
        """成功取得 HTML"""
        async with RateLimitedFetcher(delay=0) as fetcher:
            mock_response = MagicMock()
            mock_response.text = "<html>test</html>"
            mock_response.raise_for_status = MagicMock()

            with patch.object(fetcher._client, "get", new_callable=AsyncMock, return_value=mock_response):
                result = await fetcher.fetch("https://example.com")

        assert result == "<html>test</html>"
        assert fetcher.stats["total_requests"] == 1
        assert fetcher.stats["errors"] == 0

    @patch("src.japan_intel.fetcher.asyncio.sleep", new_callable=AsyncMock)
    async def test_fetch_404_returns_none(self, mock_sleep):
        """404 錯誤不重試，直接回傳 None"""
        async with RateLimitedFetcher(delay=0, max_retries=3) as fetcher:
            mock_response = MagicMock()
            mock_response.status_code = 404
            error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)

            async def raise_404(*args, **kwargs):
                raise error

            with patch.object(fetcher._client, "get", side_effect=raise_404):
                result = await fetcher.fetch("https://example.com/404")

        assert result is None
        assert fetcher.stats["errors"] == 1

    @patch("src.japan_intel.fetcher.asyncio.sleep", new_callable=AsyncMock)
    async def test_fetch_timeout_retries(self, mock_sleep):
        """逾時會重試直到達最大次數"""
        async with RateLimitedFetcher(delay=0, max_retries=2) as fetcher:
            async def raise_timeout(*args, **kwargs):
                raise httpx.TimeoutException("timeout")

            with patch.object(fetcher._client, "get", side_effect=raise_timeout):
                result = await fetcher.fetch("https://example.com/slow")

        assert result is None
        assert fetcher.stats["total_requests"] == 2
        assert fetcher.stats["errors"] == 1

    async def test_stats_initial(self):
        """初始統計為零"""
        async with RateLimitedFetcher(delay=0) as fetcher:
            assert fetcher.stats == {
                "total_requests": 0,
                "errors": 0,
                "success": 0,
            }
