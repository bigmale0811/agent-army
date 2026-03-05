# -*- coding: utf-8 -*-
"""讀書 Agent v2 — BestsellerScraper 測試

測試暢銷書爬蟲的核心功能：
- scrape_all 並發爬取與去重整合
- 各平台 HTML 解析邏輯
- 去重邏輯（相同書名跨平台合併）
- 錯誤處理（單一平台失敗不影響其他平台）
- Amazon 書籍 language 欄位必須為 "en"
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reading_agent.bestseller_scraper import BestsellerScraper, _normalize_title
from src.reading_agent.models import Book


# ─────────────────────────────────────────────
# 共用 HTML 片段（模擬各平台真實頁面結構）
# ─────────────────────────────────────────────

# 博客來：兩本書的排行榜 HTML 片段
_BOOKS_COM_TW_HTML = """
<html><body>
  <div class="type02_bd-a">
    <h4><a href="/product/item/201234">原子習慣</a></h4>
    <ul class="msg">
      <li>作者：詹姆斯．克利爾</li>
      <li>出版社：方智</li>
    </ul>
    <img src="https://im1.book.com.tw/image/getImage?i=123.jpg" />
  </div>
  <div class="type02_bd-a">
    <h4><a href="/product/item/205678">學習如何學習</a></h4>
    <ul class="msg">
      <li>作者：芭芭拉．歐克莉</li>
    </ul>
    <img src="https://im1.book.com.tw/image/getImage?i=456.jpg" />
  </div>
</body></html>
"""

# 誠品：兩本書的排行榜 HTML 片段，其中一本與博客來重複
_ESLITE_HTML = """
<html><body>
  <div class="product-item">
    <div class="product-name">原子習慣</div>
    <div class="product-author">作者：詹姆斯．克利爾</div>
    <img src="https://cdn.eslite.com/cover/abc.jpg" />
  </div>
  <div class="product-item">
    <div class="product-name">被討厭的勇氣</div>
    <div class="product-author">作者：岸見一郎</div>
    <img src="https://cdn.eslite.com/cover/def.jpg" />
  </div>
</body></html>
"""

# 金石堂：一本書的排行榜 HTML 片段
_KINGSTONE_HTML = """
<html><body>
  <div class="table-td">
    <a class="title" title="刻意練習">刻意練習</a>
    <span class="author">作者：安德斯．艾瑞克森</span>
    <img src="https://www.kingstone.com.tw/img/k123.jpg" />
  </div>
</body></html>
"""

# Amazon：兩本書的排行榜 HTML 片段（英文書）
_AMAZON_HTML = """
<html><body>
  <div class="zg-grid-general-faceout">
    <span class="_cDEzb_p13n-sc-css-line-clamp-1_1Fn1y">Atomic Habits</span>
    <span class="a-size-small a-link-child">James Clear</span>
    <img src="https://images-na.ssl-images-amazon.com/atomic.jpg" />
  </div>
  <div class="zg-grid-general-faceout">
    <span class="_cDEzb_p13n-sc-css-line-clamp-1_1Fn1y">The Psychology of Money</span>
    <span class="a-size-small a-link-child">by Morgan Housel</span>
    <img src="https://images-na.ssl-images-amazon.com/psych.jpg" />
  </div>
</body></html>
"""

# 空白頁面：用於測試無資料時的容錯行為
_EMPTY_HTML = "<html><body></body></html>"


# ─────────────────────────────────────────────
# 輔助函式
# ─────────────────────────────────────────────

def _make_book(title: str, author: str = "", language: str = "zh",
               sources: list[str] | None = None, rank: int = 1) -> Book:
    """建立測試用 Book 物件"""
    return Book(
        title=title,
        author=author,
        language=language,
        sources=sources or [],
        rank=rank,
    )


def _make_mock_response(html: str) -> MagicMock:
    """建立模擬的 httpx 回應物件"""
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ─────────────────────────────────────────────
# BestsellerScraper 測試類別
# ─────────────────────────────────────────────

class TestBestsellerScraper:
    """BestsellerScraper 的單元與整合測試"""

    @pytest.fixture
    def scraper(self):
        """每個測試使用全新的爬蟲實例，避免客戶端狀態污染"""
        return BestsellerScraper(top_n=10)

    # ──────────────────────────────────────────
    # 1. scrape_all：整合測試（並發爬取 + 去重）
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_scrape_all_returns_deduplicated_books(self, scraper):
        """scrape_all 應並發爬取四個平台，並將重複書籍合併後回傳

        「原子習慣」同時出現在博客來與誠品，
        最終結果中應只有一筆，且 sources 包含兩個平台。
        """
        # 每個平台的 _fetch 依序回傳對應 HTML
        fetch_side_effects = [
            _BOOKS_COM_TW_HTML,  # 博客來
            _ESLITE_HTML,        # 誠品
            _KINGSTONE_HTML,     # 金石堂
            _AMAZON_HTML,        # Amazon
        ]

        with patch.object(scraper, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = fetch_side_effects
            books = await scraper.scrape_all()

        # 確認確實呼叫了四次（每個平台一次）
        assert mock_fetch.call_count == 4

        # 回傳值必須是 Book 列表
        assert isinstance(books, list)
        assert all(isinstance(b, Book) for b in books)

        # 去重後應至少有 3 本書（原子習慣、學習如何學習、被討厭的勇氣、刻意練習、英文書）
        assert len(books) >= 3

    @pytest.mark.asyncio
    async def test_scrape_all_deduplicates_cross_platform(self, scraper):
        """跨平台相同書名應合併 sources 並保留最低排名"""
        with patch.object(scraper, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [
                _BOOKS_COM_TW_HTML,
                _ESLITE_HTML,
                _EMPTY_HTML,
                _EMPTY_HTML,
            ]
            books = await scraper.scrape_all()

        # 尋找「原子習慣」（博客來 #1 與誠品 #1 都有）
        atom_books = [b for b in books if "原子習慣" in b.title]
        assert len(atom_books) == 1, "重複的『原子習慣』應被合併為一筆"

        atom = atom_books[0]
        # 合併後 sources 應包含博客來與誠品兩者
        assert len(atom.sources) == 2
        source_names = set(atom.sources)
        assert "博客來" in source_names
        assert "誠品" in source_names

    # ──────────────────────────────────────────
    # 2. 博客來 HTML 解析
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_scrape_books_com_tw_parses_title_and_author(self, scraper):
        """博客來爬蟲應正確解析書名與作者"""
        with patch.object(scraper, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = _BOOKS_COM_TW_HTML
            books = await scraper._scrape_books_com_tw()

        assert len(books) == 2
        assert books[0].title == "原子習慣"
        # 去除「作者：」前綴後應只剩作者名
        assert books[0].author == "詹姆斯．克利爾"
        assert books[0].language == "zh"
        assert books[0].rank == 1
        assert books[1].title == "學習如何學習"
        assert books[1].rank == 2

    @pytest.mark.asyncio
    async def test_scrape_books_com_tw_returns_empty_on_fetch_failure(self, scraper):
        """博客來爬蟲：_fetch 回傳 None 時應回傳空列表"""
        with patch.object(scraper, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            books = await scraper._scrape_books_com_tw()

        assert books == []

    # ──────────────────────────────────────────
    # 3. Amazon 書籍 language 欄位
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_scrape_amazon_sets_language_en(self, scraper):
        """Amazon 爬蟲產生的 Book 物件 language 必須為 'en'"""
        with patch.object(scraper, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = _AMAZON_HTML
            books = await scraper._scrape_amazon()

        assert len(books) >= 1
        # 所有 Amazon 書籍的語言欄位均為英文
        for book in books:
            assert book.language == "en", (
                f"Amazon 書籍 '{book.title}' 的 language 應為 'en'，實際為 '{book.language}'"
            )

    @pytest.mark.asyncio
    async def test_scrape_amazon_strips_by_prefix(self, scraper):
        """Amazon 作者欄位中的 'by ' 前綴應被移除"""
        with patch.object(scraper, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = _AMAZON_HTML
            books = await scraper._scrape_amazon()

        # "The Psychology of Money" 的作者原始值為 "by Morgan Housel"
        psych = next((b for b in books if "Psychology" in b.title), None)
        if psych and psych.author:
            assert not psych.author.lower().startswith("by "), (
                f"作者欄位不應包含 'by ' 前綴，實際值：'{psych.author}'"
            )

    # ──────────────────────────────────────────
    # 4. 錯誤處理：單一平台失敗不影響其他平台
    # ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_scrape_all_continues_when_one_platform_fails(self, scraper):
        """單一平台爬蟲引發例外時，其他平台的結果應仍正常回傳"""
        # 博客來正常，誠品拋出例外，金石堂與 Amazon 回傳空頁面
        async def fetch_side_effect(url, headers, retries=3):
            if "books.com.tw" in url:
                return _BOOKS_COM_TW_HTML
            if "eslite" in url:
                raise RuntimeError("誠品網站連線逾時")
            return _EMPTY_HTML

        with patch.object(scraper, "_fetch", side_effect=fetch_side_effect):
            # scrape_all 本身不應拋出例外
            books = await scraper.scrape_all()

        # 即使誠品失敗，博客來的書籍仍應出現在結果中
        assert len(books) >= 2
        titles = [b.title for b in books]
        assert "原子習慣" in titles

    # ──────────────────────────────────────────
    # 5. 去重邏輯細節
    # ──────────────────────────────────────────

    def test_deduplicate_merges_sources_and_keeps_best_rank(self, scraper):
        """_deduplicate 應合併 sources 並保留最低排名（數字越小越好）"""
        books_input = [
            _make_book("原子習慣", rank=3, sources=["博客來"]),
            _make_book("原子習慣", rank=1, sources=["誠品"]),   # 誠品排名更好
            _make_book("被討厭的勇氣", rank=5, sources=["金石堂"]),
        ]
        result = scraper._deduplicate(books_input)

        # 去重後只有兩本書
        assert len(result) == 2

        # 找到「原子習慣」並驗證合併結果
        atom = next(b for b in result if "原子習慣" in b.title)
        assert atom.rank == 1, "應保留最低（最佳）排名"
        assert set(atom.sources) == {"博客來", "誠品"}

    def test_deduplicate_fills_missing_author(self, scraper):
        """_deduplicate 應以後出現的書籍補充缺少的作者資訊"""
        books_input = [
            _make_book("原子習慣", author="", sources=["博客來"]),
            _make_book("原子習慣", author="詹姆斯．克利爾", sources=["誠品"]),
        ]
        result = scraper._deduplicate(books_input)

        assert len(result) == 1
        assert result[0].author == "詹姆斯．克利爾", "應從第二筆補充作者資訊"

    def test_deduplicate_ignores_case_and_spaces(self, scraper):
        """_deduplicate 去重時應忽略大小寫與空格差異"""
        books_input = [
            _make_book("Atomic Habits", sources=["Amazon"]),
            # 全小寫且包含多餘空格，正規化後應與上面相同
            _make_book("atomic habits", sources=["Goodreads"]),
        ]
        result = scraper._deduplicate(books_input)
        assert len(result) == 1, "忽略大小寫後應被視為同一本書"

    # ──────────────────────────────────────────
    # 6. _normalize_title 正規化函式
    # ──────────────────────────────────────────

    def test_normalize_title_removes_spaces_and_lowercases(self):
        """_normalize_title 應去除空格並轉小寫"""
        assert _normalize_title("  Atomic Habits  ") == "atomichabits"
        assert _normalize_title("原子習慣") == "原子習慣"
        # 全形空格（\u3000）也應被移除
        assert _normalize_title("原子\u3000習慣") == "原子習慣"
