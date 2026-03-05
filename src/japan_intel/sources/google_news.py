# -*- coding: utf-8 -*-
"""Google News RSS 爬蟲

透過 Google News 的 RSS feed 搜尋日本博弈相關新聞。
支援日文與英文關鍵字，解析 RSS XML 取得文章標題、連結、發佈日期。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# RSS 是 XML 格式，使用 html.parser 也能解析，抑制警告
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from ..fetcher import RateLimitedFetcher
from ..models import Article

logger = logging.getLogger(__name__)

# Google News RSS 基礎 URL
_RSS_BASE = "https://news.google.com/rss/search"


def _build_rss_url(keyword: str, language: str = "ja", days_back: int = 7) -> str:
    """建構 Google News RSS 搜尋 URL

    Args:
        keyword: 搜尋關鍵字
        language: 語言代碼（ja / en）
        days_back: 往回搜尋天數，用於 when 參數

    Returns:
        完整的 RSS URL
    """
    encoded = quote_plus(keyword)
    # Google News 的 when 參數：7d = 7天, 30d = 30天, 1y = 1年
    if days_back <= 7:
        when = "7d"
    elif days_back <= 30:
        when = "30d"
    elif days_back <= 365:
        when = "1y"
    else:
        when = "1y"

    if language == "ja":
        return f"{_RSS_BASE}?q={encoded}&hl=ja&gl=JP&ceid=JP:ja&when={when}"
    else:
        return f"{_RSS_BASE}?q={encoded}&hl=en&gl=US&ceid=US:en&when={when}"


def _parse_rss_date(date_str: str) -> str:
    """解析 RSS 中的日期格式（RFC 2822）

    Args:
        date_str: RSS 日期字串，如 "Mon, 03 Mar 2026 08:00:00 GMT"

    Returns:
        ISO 格式日期字串
    """
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.isoformat()
        except ValueError:
            continue

    # 解析失敗，回傳原始字串
    logger.warning("無法解析日期格式: %s", date_str)
    return date_str


async def fetch_google_news(
    fetcher: RateLimitedFetcher,
    keywords: list[str],
    language: str = "ja",
    days_back: int = 7,
) -> list[Article]:
    """從 Google News RSS 蒐集文章

    Args:
        fetcher: HTTP 客戶端實例
        keywords: 搜尋關鍵字列表
        language: 語言代碼（ja / en）
        days_back: 往回搜尋天數

    Returns:
        蒐集到的文章列表
    """
    articles: list[Article] = []
    source_name = f"Google News ({'日本語' if language == 'ja' else 'English'})"

    for keyword in keywords:
        url = _build_rss_url(keyword, language, days_back)
        logger.info("搜尋 Google News [%s]: %s", language, keyword)

        html = await fetcher.fetch(url)
        if not html:
            logger.warning("Google News RSS 無回應: %s", keyword)
            continue

        try:
            # 解析 RSS XML
            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all("item")

            for item in items:
                title_tag = item.find("title")
                link_tag = item.find("link")
                pub_date_tag = item.find("pubdate")
                desc_tag = item.find("description")

                if not title_tag or not link_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = link_tag.get_text(strip=True)
                # Google News 的 link 有時在 next sibling 文字節點中
                if not link and link_tag.next_sibling:
                    link = str(link_tag.next_sibling).strip()

                published_at = ""
                if pub_date_tag:
                    published_at = _parse_rss_date(pub_date_tag.get_text(strip=True))

                summary = ""
                if desc_tag:
                    # description 通常包含 HTML，清除標籤
                    desc_soup = BeautifulSoup(desc_tag.get_text(), "html.parser")
                    summary = desc_soup.get_text(strip=True)[:300]

                article = Article(
                    title=title,
                    url=link,
                    source=source_name,
                    published_at=published_at,
                    summary=summary,
                    language=language,
                )
                articles.append(article)

            logger.info(
                "Google News [%s] '%s': 取得 %d 篇",
                language, keyword, len(items),
            )

        except Exception as e:
            logger.error("解析 Google News RSS 失敗 [%s]: %s", keyword, e)
            continue

    logger.info("Google News [%s] 共蒐集 %d 篇（去重前）", language, len(articles))
    return articles
