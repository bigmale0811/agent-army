# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — HTTP 客戶端

基於 httpx 的 async HTTP 客戶端，內建限速、重試、錯誤處理機制，
確保對來源網站友善且穩定地取得資料。
"""

import asyncio
import logging
from typing import Optional

import httpx

from .config import (
    MAX_RETRIES,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


class RateLimitedFetcher:
    """限速 HTTP 客戶端

    功能：
    - 請求間隔限速（預設 1.5 秒）
    - 失敗自動重試（指數退避，最多 3 次）
    - 統一 User-Agent 與超時設定
    - 錯誤記錄但不中斷整體流程
    """

    def __init__(
        self,
        delay: float = REQUEST_DELAY,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        user_agent: str = USER_AGENT,
    ):
        self._delay = delay
        self._timeout = timeout
        self._max_retries = max_retries
        self._user_agent = user_agent
        self._client: Optional[httpx.AsyncClient] = None
        # 計數器，用於統計與日誌
        self._request_count = 0
        self._error_count = 0

    async def __aenter__(self) -> "RateLimitedFetcher":
        """進入 async context manager，建立 httpx 客戶端"""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            headers={
                "User-Agent": self._user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja,en;q=0.9,zh-TW;q=0.8",
            },
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """離開 async context manager，關閉 httpx 客戶端"""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info(
            "HTTP 客戶端關閉：共發送 %d 次請求，%d 次失敗",
            self._request_count, self._error_count,
        )

    async def fetch(self, url: str) -> Optional[str]:
        """取得指定 URL 的 HTML 內容

        帶有限速和自動重試機制。失敗時回傳 None 而非拋出例外，
        讓上層邏輯可以跳過該來源繼續處理其他來源。

        Args:
            url: 要請求的 URL

        Returns:
            HTML 文字內容，失敗時回傳 None
        """
        if not self._client:
            raise RuntimeError("Fetcher 未初始化，請使用 async with 語法")

        # 限速：等待指定間隔
        await asyncio.sleep(self._delay)

        for attempt in range(1, self._max_retries + 1):
            try:
                self._request_count += 1
                response = await self._client.get(url)
                response.raise_for_status()

                logger.debug("成功取得 %s（%d bytes）", url, len(response.text))
                return response.text

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # 4xx 錯誤不重試（除了 429 Too Many Requests）
                if 400 <= status < 500 and status != 429:
                    logger.warning(
                        "HTTP %d 錯誤，跳過 %s: %s", status, url, e
                    )
                    self._error_count += 1
                    return None

                # 429 或 5xx 錯誤：指數退避後重試
                wait_time = self._delay * (2 ** attempt)
                logger.warning(
                    "HTTP %d 錯誤（第 %d/%d 次），%s 秒後重試: %s",
                    status, attempt, self._max_retries, wait_time, url,
                )
                await asyncio.sleep(wait_time)

            except httpx.TimeoutException:
                wait_time = self._delay * (2 ** attempt)
                logger.warning(
                    "請求逾時（第 %d/%d 次），%s 秒後重試: %s",
                    attempt, self._max_retries, wait_time, url,
                )
                await asyncio.sleep(wait_time)

            except httpx.RequestError as e:
                logger.warning(
                    "連線錯誤（第 %d/%d 次），跳過 %s: %s",
                    attempt, self._max_retries, url, e,
                )
                if attempt == self._max_retries:
                    self._error_count += 1
                    return None
                await asyncio.sleep(self._delay * (2 ** attempt))

        # 所有重試都失敗
        self._error_count += 1
        logger.error("已達最大重試次數，放棄請求: %s", url)
        return None

    @property
    def stats(self) -> dict[str, int]:
        """回傳請求統計資訊"""
        return {
            "total_requests": self._request_count,
            "errors": self._error_count,
            "success": self._request_count - self._error_count,
        }
