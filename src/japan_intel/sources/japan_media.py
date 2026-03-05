# -*- coding: utf-8 -*-
"""日本媒體爬蟲

蒐集日本國內主流媒體的博弈相關報導：
- Yahoo Japan News（日本最大新聞聚合平台）
- NHK News Web（日本公共廣播）
透過搜尋功能取得相關文章。
"""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from ..fetcher import RateLimitedFetcher
from ..models import Article

logger = logging.getLogger(__name__)


async def _scrape_yahoo_japan(
    fetcher: RateLimitedFetcher,
    keywords: list[str],
) -> list[Article]:
    """蒐集 Yahoo Japan News 的博弈相關文章

    透過 Yahoo Japan 的新聞搜尋功能，
    使用日文關鍵字搜尋博弈、賭場、柏青哥等相關新聞。
    """
    articles: list[Article] = []
    base_url = "https://news.yahoo.co.jp"

    for keyword in keywords:
        encoded = quote_plus(keyword)
        # Yahoo Japan News 搜尋 URL
        url = f"https://search.yahoo.co.jp/news/search?p={encoded}&ei=UTF-8"

        logger.info("搜尋 Yahoo Japan: %s", keyword)
        html = await fetcher.fetch(url)
        if not html:
            continue

        try:
            soup = BeautifulSoup(html, "html.parser")
            # Yahoo Japan 搜尋結果的常見選擇器
            results = (
                soup.select(".newsFeed_item")
                or soup.select(".sw-CardBase")
                or soup.select("article")
                or soup.select(".NewsSearchItem")
            )

            for item in results:
                title_tag = (
                    item.select_one("a.newsFeed_item_link")
                    or item.select_one("h2 a")
                    or item.select_one("a")
                )
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")

                # 過濾非新聞連結
                if not link or "yahoo" not in link:
                    continue

                # 嘗試取得日期
                date_tag = (
                    item.select_one("time")
                    or item.select_one(".newsFeed_item_date")
                    or item.select_one("span[class*='date']")
                )
                published_at = ""
                if date_tag:
                    published_at = date_tag.get("datetime", date_tag.get_text(strip=True))

                # 嘗試取得摘要
                summary_tag = (
                    item.select_one(".newsFeed_item_text")
                    or item.select_one("p")
                )
                summary = summary_tag.get_text(strip=True)[:300] if summary_tag else ""

                articles.append(Article(
                    title=title,
                    url=link,
                    source="Yahoo Japan News",
                    published_at=published_at,
                    summary=summary,
                    language="ja",
                ))

            logger.info("Yahoo Japan '%s': 取得 %d 篇", keyword, len(results))

        except Exception as e:
            logger.error("解析 Yahoo Japan 搜尋結果失敗 [%s]: %s", keyword, e)
            continue

    logger.info("Yahoo Japan News 共蒐集 %d 篇", len(articles))
    return articles


async def _scrape_nhk(
    fetcher: RateLimitedFetcher,
    keywords: list[str],
) -> list[Article]:
    """蒐集 NHK News Web 的博弈相關文章

    NHK 是日本最具公信力的公共廣播，
    其報導通常涉及政策面和法規變動。
    """
    articles: list[Article] = []
    base_url = "https://www3.nhk.or.jp"

    for keyword in keywords:
        encoded = quote_plus(keyword)
        # NHK 搜尋 URL
        url = f"https://www3.nhk.or.jp/news/json/search/q={encoded}/new.json"

        logger.info("搜尋 NHK: %s", keyword)
        html = await fetcher.fetch(url)

        # NHK 搜尋 API 可能回傳 JSON，嘗試解析
        if not html:
            # 備用：嘗試 HTML 搜尋頁面
            fallback_url = f"https://cgi2.nhk.or.jp/nw/web-search/?q={encoded}"
            html = await fetcher.fetch(fallback_url)
            if not html:
                continue

        try:
            # 先嘗試當作 JSON 處理
            import json
            try:
                data = json.loads(html)
                items = data.get("result", {}).get("items", [])
                for item in items:
                    title = item.get("title", "")
                    link = item.get("url", "")
                    if link and not link.startswith("http"):
                        link = urljoin(base_url, link)
                    published_at = item.get("pubDate", "")
                    summary = item.get("description", "")[:300]

                    articles.append(Article(
                        title=title,
                        url=link,
                        source="NHK",
                        published_at=published_at,
                        summary=summary,
                        language="ja",
                    ))
                continue
            except (json.JSONDecodeError, TypeError):
                pass

            # JSON 解析失敗，當作 HTML 處理
            soup = BeautifulSoup(html, "html.parser")
            results = (
                soup.select(".content--list-item")
                or soup.select("article")
                or soup.select(".search-result-item")
            )

            for item in results:
                title_tag = item.select_one("a")
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin(base_url, link)

                date_tag = item.select_one("time") or item.select_one(".content--date")
                published_at = ""
                if date_tag:
                    published_at = date_tag.get("datetime", date_tag.get_text(strip=True))

                summary_tag = item.select_one("p")
                summary = summary_tag.get_text(strip=True)[:300] if summary_tag else ""

                articles.append(Article(
                    title=title,
                    url=link,
                    source="NHK",
                    published_at=published_at,
                    summary=summary,
                    language="ja",
                ))

            logger.info("NHK '%s': 取得 %d 篇", keyword, len(results))

        except Exception as e:
            logger.error("解析 NHK 搜尋結果失敗 [%s]: %s", keyword, e)
            continue

    logger.info("NHK 共蒐集 %d 篇", len(articles))
    return articles


async def fetch_japan_media(
    fetcher: RateLimitedFetcher,
    keywords: list[str],
) -> list[Article]:
    """蒐集所有日本媒體的文章

    依序蒐集 Yahoo Japan News 和 NHK，
    每個來源獨立處理錯誤，確保單一來源失敗不影響其他。

    Args:
        fetcher: HTTP 客戶端實例
        keywords: 日文搜尋關鍵字列表

    Returns:
        所有日本媒體蒐集到的文章列表
    """
    all_articles: list[Article] = []

    # Yahoo Japan News
    try:
        yahoo_articles = await _scrape_yahoo_japan(fetcher, keywords)
        all_articles.extend(yahoo_articles)
    except Exception as e:
        logger.error("蒐集 Yahoo Japan News 時發生未預期錯誤: %s", e)

    # NHK News Web
    try:
        nhk_articles = await _scrape_nhk(fetcher, keywords)
        all_articles.extend(nhk_articles)
    except Exception as e:
        logger.error("蒐集 NHK 時發生未預期錯誤: %s", e)

    logger.info("日本媒體共蒐集 %d 篇（去重前）", len(all_articles))
    return all_articles
