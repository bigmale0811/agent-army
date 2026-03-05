# -*- coding: utf-8 -*-
"""讀書 Agent v2 — 暢銷書排行榜爬蟲

從四個平台爬取暢銷書排行榜：
- 博客來 (books.com.tw)
- 誠品 (eslite.com)
- 金石堂 (kingstone.com.tw)
- Amazon (amazon.com)

各平台爬蟲彼此獨立，單一平台失敗不影響其他平台。
結果依正規化書名去重，跨平台同一書籍合併來源並保留最佳排名。
"""

import asyncio
import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .config import (
    BESTSELLER_SOURCES,
    BESTSELLER_TOP_N,
    MAX_RETRIES,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
)
from .models import Book

logger = logging.getLogger(__name__)

# 模擬真實瀏覽器的 User-Agent，降低被封鎖的機率
_USER_AGENTS = {
    "zh": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "en": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}

# 通用請求標頭，包含語言偏好設定
_HEADERS_ZH = {
    "User-Agent": _USER_AGENTS["zh"],
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

_HEADERS_EN = {
    "User-Agent": _USER_AGENTS["en"],
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _normalize_title(title: str) -> str:
    """正規化書名：去除前後空格、轉小寫、移除所有空格（含全形）

    用於跨平台書籍去重比對，確保同一本書在不同平台的書名差異不影響比對結果。
    """
    return title.strip().lower().replace(" ", "").replace("\u3000", "")


class BestsellerScraper:
    """暢銷書排行榜爬蟲

    從博客來、誠品、金石堂、Amazon 四個平台抓取暢銷書排行榜。
    使用 httpx 進行非同步 HTTP 請求，BeautifulSoup 解析 HTML。

    使用方式：
        scraper = BestsellerScraper()
        books = await scraper.scrape_all()
    """

    def __init__(self, top_n: int = BESTSELLER_TOP_N):
        """初始化爬蟲

        Args:
            top_n: 每個平台抓取前 N 名，預設由 config.BESTSELLER_TOP_N 決定
        """
        self.top_n = top_n
        # httpx 非同步客戶端：設定超時與重新導向追蹤
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """取得（或建立）共用的 httpx 非同步客戶端

        採用懶惰初始化，避免在非非同步環境中建立客戶端。
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                # 允許重新使用連線，提升效能
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def _fetch(self, url: str, headers: dict, retries: int = MAX_RETRIES) -> Optional[str]:
        """帶重試邏輯的 HTTP GET 請求

        每次失敗後等待遞增的時間再重試（指數退避），最終仍失敗則回傳 None。

        Args:
            url: 目標 URL
            headers: HTTP 請求標頭
            retries: 最大重試次數

        Returns:
            成功時回傳 HTML 字串，失敗時回傳 None
        """
        client = await self._get_client()
        for attempt in range(1, retries + 1):
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                logger.debug("成功取得 %s（第 %d 次嘗試）", url, attempt)
                return response.text
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "HTTP 錯誤 %d：%s（第 %d/%d 次）",
                    e.response.status_code, url, attempt, retries
                )
            except httpx.RequestError as e:
                logger.warning("請求失敗：%s（第 %d/%d 次）：%s", url, attempt, retries, e)

            # 指數退避：避免短時間內連續發送大量請求
            if attempt < retries:
                wait_time = REQUEST_DELAY * (2 ** (attempt - 1))
                logger.debug("等待 %.1f 秒後重試...", wait_time)
                await asyncio.sleep(wait_time)

        logger.error("無法取得頁面（已重試 %d 次）：%s", retries, url)
        return None

    async def scrape_all(self) -> list[Book]:
        """從所有平台爬取暢銷書，去重後回傳合併結果

        四個平台並發爬取，任一平台失敗不影響其他平台的結果。
        同一本書出現在多個平台時，合併來源列表並保留最佳（最低）排名。

        Returns:
            去重後的暢銷書列表，依排名排序
        """
        logger.info("開始爬取所有平台暢銷書排行榜（前 %d 名）", self.top_n)

        # 並發爬取四個平台，縮短總等待時間
        results = await asyncio.gather(
            self._scrape_books_com_tw(),
            self._scrape_eslite(),
            self._scrape_kingstone(),
            self._scrape_amazon(),
            return_exceptions=False,  # 各平台已有自己的 try/except，不應拋出例外
        )

        # 合併所有平台的書籍列表
        all_books: list[Book] = []
        platform_names = ["博客來", "誠品", "金石堂", "Amazon"]
        for platform_name, books in zip(platform_names, results):
            logger.info("%s 取得 %d 本書", platform_name, len(books))
            all_books.extend(books)

        # 去重並合併跨平台重複書籍
        merged_books = self._deduplicate(all_books)
        logger.info("去重後共 %d 本暢銷書", len(merged_books))

        # 依排名排序（排名 0 表示未知，放到最後）
        merged_books.sort(key=lambda b: b.rank if b.rank > 0 else 9999)

        # 關閉 HTTP 客戶端，釋放連線資源
        if self._client and not self._client.is_closed:
            await self._client.aclose()

        return merged_books

    async def _scrape_books_com_tw(self) -> list[Book]:
        """爬取博客來暢銷書排行榜

        博客來排行榜頁面結構（實際選擇器可能隨網站改版而需調整）：
        - 書籍區塊：.type02_bd-a（排行榜條目）
        - 書名：h4 > a（連結文字為書名）
        - 作者：ul.msg > li:first-child（作者行）
        - 封面：img.cover（封面圖片）

        Returns:
            博客來暢銷書列表，失敗時回傳空列表
        """
        source_key = "books_com_tw"
        source_config = BESTSELLER_SOURCES[source_key]
        url = source_config["url"]
        source_name = source_config["name"]

        try:
            logger.info("開始爬取 %s：%s", source_name, url)
            html = await self._fetch(url, headers=_HEADERS_ZH)
            if not html:
                return []

            soup = BeautifulSoup(html, "html.parser")
            books: list[Book] = []

            # 博客來排行榜：每個書籍項目為 .type02_bd-a 區塊
            # 注意：實際選擇器可能因博客來改版而需要調整
            items = soup.select(".type02_bd-a")
            if not items:
                # 備用選擇器：嘗試其他可能的 DOM 結構
                items = soup.select(".item")
                logger.debug("博客來：使用備用選擇器 .item，找到 %d 個項目", len(items))

            for rank, item in enumerate(items[: self.top_n], start=1):
                try:
                    # 解析書名：h4 連結或 strong 標籤內的文字
                    title_tag = item.select_one("h4 a") or item.select_one("strong a")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    if not title:
                        continue

                    # 解析作者：通常在 ul.msg 的第一個 li 中
                    author = ""
                    author_candidates = item.select("ul.msg li")
                    if author_candidates:
                        # 第一個 li 通常為「作者」欄位，格式：「作者：王小明」
                        author_text = author_candidates[0].get_text(strip=True)
                        # 去除「作者：」前綴
                        if "：" in author_text:
                            author = author_text.split("：", 1)[1].strip()
                        elif ":" in author_text:
                            author = author_text.split(":", 1)[1].strip()
                        else:
                            author = author_text

                    # 解析封面圖 URL
                    cover_url = ""
                    img_tag = item.select_one("img")
                    if img_tag:
                        cover_url = img_tag.get("data-src") or img_tag.get("src", "")

                    book = Book(
                        title=title,
                        author=author,
                        language="zh",
                        sources=[source_name],
                        rank=rank,
                        cover_url=cover_url,
                    )
                    books.append(book)
                    logger.debug("博客來 #%d：%s / %s", rank, title, author)

                except Exception as e:
                    logger.warning("博客來：解析第 %d 個書籍項目失敗：%s", rank, e)
                    continue

            logger.info("博客來：成功解析 %d 本書", len(books))
            return books

        except Exception as e:
            # 單一平台失敗不中斷整體流程，記錄錯誤後回傳空列表
            logger.error("博客來爬蟲失敗：%s", e, exc_info=True)
            return []

    async def _scrape_eslite(self) -> list[Book]:
        """爬取誠品暢銷書排行榜

        誠品排行榜頁面結構（實際選擇器可能隨網站改版而需調整）：
        - 書籍區塊：.product-item 或 .book-item（列表中的每個書籍卡片）
        - 書名：.product-name 或 .title（書名文字）
        - 作者：.product-author 或 .author（作者文字）
        - 封面：.product-image img 或 .cover img

        Returns:
            誠品暢銷書列表，失敗時回傳空列表
        """
        source_key = "eslite"
        source_config = BESTSELLER_SOURCES[source_key]
        url = source_config["url"]
        source_name = source_config["name"]

        try:
            logger.info("開始爬取 %s：%s", source_name, url)
            html = await self._fetch(url, headers=_HEADERS_ZH)
            if not html:
                return []

            soup = BeautifulSoup(html, "html.parser")
            books: list[Book] = []

            # 誠品暢銷榜：嘗試多種可能的選擇器
            # 注意：實際選擇器可能因誠品改版而需要調整
            items = (
                soup.select(".product-item")
                or soup.select(".book-item")
                or soup.select("[class*='ProductItem']")
                or soup.select("[class*='bookItem']")
            )

            if not items:
                logger.warning("誠品：找不到書籍列表，頁面結構可能已改變")
                return []

            for rank, item in enumerate(items[: self.top_n], start=1):
                try:
                    # 解析書名
                    title_tag = (
                        item.select_one(".product-name")
                        or item.select_one(".title")
                        or item.select_one("[class*='productName']")
                        or item.select_one("[class*='bookTitle']")
                        or item.select_one("h3")
                        or item.select_one("h4")
                    )
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    if not title:
                        continue

                    # 解析作者
                    author = ""
                    author_tag = (
                        item.select_one(".product-author")
                        or item.select_one(".author")
                        or item.select_one("[class*='author']")
                    )
                    if author_tag:
                        author_text = author_tag.get_text(strip=True)
                        # 去除「作者：」等前綴標籤
                        if "：" in author_text:
                            author = author_text.split("：", 1)[1].strip()
                        else:
                            author = author_text

                    # 解析封面圖 URL
                    cover_url = ""
                    img_tag = item.select_one("img")
                    if img_tag:
                        cover_url = img_tag.get("data-src") or img_tag.get("src", "")

                    book = Book(
                        title=title,
                        author=author,
                        language="zh",
                        sources=[source_name],
                        rank=rank,
                        cover_url=cover_url,
                    )
                    books.append(book)
                    logger.debug("誠品 #%d：%s / %s", rank, title, author)

                except Exception as e:
                    logger.warning("誠品：解析第 %d 個書籍項目失敗：%s", rank, e)
                    continue

            logger.info("誠品：成功解析 %d 本書", len(books))
            return books

        except Exception as e:
            logger.error("誠品爬蟲失敗：%s", e, exc_info=True)
            return []

    async def _scrape_kingstone(self) -> list[Book]:
        """爬取金石堂暢銷書排行榜

        金石堂排行榜頁面結構（實際選擇器可能隨網站改版而需調整）：
        - 書籍區塊：.table-td 或 .hot-list-item（排行榜條目）
        - 書名：.title 或 .bookname（書名文字）
        - 作者：.author（作者文字）
        - 排名標記：.rank-number 或排行榜序號

        Returns:
            金石堂暢銷書列表，失敗時回傳空列表
        """
        source_key = "kingstone"
        source_config = BESTSELLER_SOURCES[source_key]
        url = source_config["url"]
        source_name = source_config["name"]

        try:
            logger.info("開始爬取 %s：%s", source_name, url)
            html = await self._fetch(url, headers=_HEADERS_ZH)
            if not html:
                return []

            soup = BeautifulSoup(html, "html.parser")
            books: list[Book] = []

            # 金石堂暢銷榜：嘗試多種可能的選擇器
            # 注意：實際選擇器可能因金石堂改版而需要調整
            items = (
                soup.select(".table-td")
                or soup.select(".hot-list-item")
                or soup.select(".rankList li")
                or soup.select("[class*='rankItem']")
                or soup.select(".product-box")
            )

            if not items:
                logger.warning("金石堂：找不到書籍列表，頁面結構可能已改變")
                return []

            for rank, item in enumerate(items[: self.top_n], start=1):
                try:
                    # 解析書名：金石堂通常使用 .title 或 .bookname 類別
                    title_tag = (
                        item.select_one(".title a")
                        or item.select_one(".bookname a")
                        or item.select_one(".title")
                        or item.select_one("h4 a")
                        or item.select_one("a[title]")
                    )
                    if not title_tag:
                        continue

                    # 優先使用 title 屬性（通常為完整書名，不受截斷影響）
                    title = (
                        title_tag.get("title")
                        or title_tag.get_text(strip=True)
                    )
                    if not title:
                        continue

                    # 解析作者：金石堂通常在 .author 或同層的文字節點中
                    author = ""
                    author_tag = (
                        item.select_one(".author")
                        or item.select_one("[class*='author']")
                        or item.select_one(".writer")
                    )
                    if author_tag:
                        author_text = author_tag.get_text(strip=True)
                        if "：" in author_text:
                            author = author_text.split("：", 1)[1].strip()
                        elif "/" in author_text:
                            # 格式：「作者/出版社」，取第一個斜線前的部分
                            author = author_text.split("/")[0].strip()
                        else:
                            author = author_text

                    # 解析封面圖 URL
                    cover_url = ""
                    img_tag = item.select_one("img")
                    if img_tag:
                        cover_url = img_tag.get("data-src") or img_tag.get("src", "")

                    book = Book(
                        title=title,
                        author=author,
                        language="zh",
                        sources=[source_name],
                        rank=rank,
                        cover_url=cover_url,
                    )
                    books.append(book)
                    logger.debug("金石堂 #%d：%s / %s", rank, title, author)

                except Exception as e:
                    logger.warning("金石堂：解析第 %d 個書籍項目失敗：%s", rank, e)
                    continue

            logger.info("金石堂：成功解析 %d 本書", len(books))
            return books

        except Exception as e:
            logger.error("金石堂爬蟲失敗：%s", e, exc_info=True)
            return []

    async def _scrape_amazon(self) -> list[Book]:
        """爬取 Amazon 暢銷書排行榜

        Amazon Best Sellers 頁面結構（實際選擇器可能隨網站改版而需調整）：
        - 書籍區塊：.zg-grid-general-faceout 或 .p13n-gridRow .p13n-sc-uncoverable-faceout
        - 書名：.p13n-sc-truncate-desktop-type2 或 ._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y
        - 作者：.a-size-small.a-link-child 或 .a-row .a-size-small（作者名稱行）
        - 排名標記：.zg-bdg-text（排行榜數字）

        Amazon 為英文平台，書籍語言設定為 "en"。

        Returns:
            Amazon 暢銷書列表，失敗時回傳空列表
        """
        source_key = "amazon"
        source_config = BESTSELLER_SOURCES[source_key]
        url = source_config["url"]
        source_name = source_config["name"]

        try:
            logger.info("開始爬取 %s：%s", source_name, url)
            # Amazon 需要英文 User-Agent 與語言標頭，降低被偵測為機器人的機率
            html = await self._fetch(url, headers=_HEADERS_EN)
            if not html:
                return []

            soup = BeautifulSoup(html, "html.parser")
            books: list[Book] = []

            # Amazon Best Sellers：嘗試多種可能的選擇器
            # 注意：Amazon 頻繁更改 DOM 結構，選擇器可能需要定期更新
            items = (
                soup.select(".zg-grid-general-faceout")
                or soup.select(".p13n-sc-uncoverable-faceout")
                or soup.select("[class*='zg-item']")
                or soup.select(".a-section.a-spacing-none.aok-relative")
            )

            if not items:
                logger.warning("Amazon：找不到書籍列表，頁面結構可能已改變")
                return []

            for rank, item in enumerate(items[: self.top_n], start=1):
                try:
                    # 解析書名：Amazon 使用多種 CSS 類別，取第一個非空結果
                    title_tag = (
                        item.select_one("._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y")
                        or item.select_one(".p13n-sc-truncate-desktop-type2")
                        or item.select_one(".p13n-sc-truncated")
                        or item.select_one("[class*='p13n-sc-truncate']")
                        or item.select_one(".a-size-base-plus.a-color-base")
                        or item.select_one(".a-link-normal .a-text-normal")
                    )
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    if not title:
                        continue

                    # 解析作者：Amazon 作者通常在書名下方的小字連結中
                    author = ""
                    author_tag = (
                        item.select_one(".a-size-small.a-link-child")
                        or item.select_one(".a-row .a-size-small a")
                        or item.select_one(".a-color-secondary.a-size-small")
                        or item.select_one("[class*='a-color-secondary'] span")
                    )
                    if author_tag:
                        author = author_tag.get_text(strip=True)
                        # 去除 "by " 前綴（Amazon 英文格式）
                        if author.lower().startswith("by "):
                            author = author[3:].strip()

                    # 解析封面圖 URL
                    cover_url = ""
                    img_tag = item.select_one("img")
                    if img_tag:
                        # Amazon 圖片可能使用 data-a-dynamic-image 屬性（JSON 格式）
                        dynamic_src = img_tag.get("data-a-dynamic-image")
                        if dynamic_src:
                            # 取 JSON 中的第一個 URL 鍵值（最高解析度）
                            import json as _json
                            try:
                                src_dict = _json.loads(dynamic_src)
                                cover_url = next(iter(src_dict.keys()), "")
                            except (_json.JSONDecodeError, StopIteration):
                                cover_url = img_tag.get("src", "")
                        else:
                            cover_url = img_tag.get("src", "")

                    # Amazon 書籍語言為英文
                    book = Book(
                        title=title,
                        author=author,
                        language="en",
                        sources=[source_name],
                        rank=rank,
                        cover_url=cover_url,
                    )
                    books.append(book)
                    logger.debug("Amazon #%d：%s / %s", rank, title, author)

                except Exception as e:
                    logger.warning("Amazon：解析第 %d 個書籍項目失敗：%s", rank, e)
                    continue

            logger.info("Amazon：成功解析 %d 本書", len(books))
            return books

        except Exception as e:
            logger.error("Amazon 爬蟲失敗：%s", e, exc_info=True)
            return []

    def _deduplicate(self, books: list[Book]) -> list[Book]:
        """跨平台書籍去重與合併

        去重邏輯：
        1. 以正規化書名（去空格、轉小寫）作為唯一識別鍵
        2. 同一本書出現在多個平台時，合併 sources 列表（去重）
        3. 保留最佳（最低數字）排名
        4. 其他欄位（作者、封面等）以最先出現的資料為準

        Args:
            books: 所有平台書籍的合併列表（可能包含重複項目）

        Returns:
            去重後的書籍列表
        """
        # 以正規化書名為 key，儲存已處理的書籍
        merged: dict[str, Book] = {}

        for book in books:
            key = _normalize_title(book.title)
            if not key:
                # 書名為空則略過
                continue

            if key not in merged:
                # 第一次出現：直接加入，確保 sources 為獨立列表副本
                merged[key] = Book(
                    title=book.title,
                    author=book.author,
                    language=book.language,
                    sources=list(book.sources),
                    rank=book.rank,
                    isbn=book.isbn,
                    cover_url=book.cover_url,
                    category=book.category,
                    collected_at=book.collected_at,
                )
            else:
                existing = merged[key]

                # 合併來源列表：使用集合去重，再轉回列表保持穩定順序
                combined_sources = list(dict.fromkeys(existing.sources + book.sources))
                existing.sources = combined_sources

                # 保留最佳（最低）排名：排名 0 視為「未知」，不覆蓋已知排名
                if book.rank > 0:
                    if existing.rank == 0 or book.rank < existing.rank:
                        existing.rank = book.rank

                # 若原有書籍缺少作者資訊，使用當前書籍的作者補充
                if not existing.author and book.author:
                    existing.author = book.author

                # 若原有書籍缺少封面圖，使用當前書籍的封面補充
                if not existing.cover_url and book.cover_url:
                    existing.cover_url = book.cover_url

        result = list(merged.values())
        logger.debug(
            "去重：輸入 %d 本書 → 輸出 %d 本書（移除 %d 個重複項目）",
            len(books), len(result), len(books) - len(result)
        )
        return result
