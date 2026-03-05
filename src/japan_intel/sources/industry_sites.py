# -*- coding: utf-8 -*-
"""博弈產業網站爬蟲

蒐集國際博弈產業媒體的日本相關報導：
- GGRAsia（亞洲博弈新聞龍頭）
- Inside Asian Gaming（亞洲博弈專業媒體）
- CalvinAyre（全球博弈新聞）
- AGB（Asia Gaming Brief）
"""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..fetcher import RateLimitedFetcher
from ..models import Article

logger = logging.getLogger(__name__)


async def _scrape_ggr_asia(
    fetcher: RateLimitedFetcher,
    max_pages: int = 3,
) -> list[Article]:
    """蒐集 GGRAsia 的日本相關文章

    GGRAsia 是亞洲博弈新聞最具權威的媒體之一，
    提供 IR、賭場、博弈法規等深度報導。
    """
    articles: list[Article] = []
    base_url = "https://www.ggrasia.com"

    for page in range(1, max_pages + 1):
        # GGRAsia 搜尋頁面
        url = f"{base_url}/page/{page}/?s=japan"
        if page == 1:
            url = f"{base_url}/?s=japan"

        logger.info("蒐集 GGRAsia 第 %d 頁", page)
        html = await fetcher.fetch(url)
        if not html:
            break

        try:
            soup = BeautifulSoup(html, "html.parser")
            # 嘗試多種常見的文章列表選擇器
            post_items = (
                soup.select("article.post")
                or soup.select(".post-item")
                or soup.select("article")
            )

            if not post_items:
                logger.info("GGRAsia 第 %d 頁無文章，停止翻頁", page)
                break

            for post in post_items:
                title_tag = (
                    post.select_one("h2 a")
                    or post.select_one("h3 a")
                    or post.select_one(".entry-title a")
                )
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin(base_url, link)

                # 嘗試取得發佈日期
                date_tag = (
                    post.select_one("time")
                    or post.select_one(".entry-date")
                    or post.select_one(".post-date")
                )
                published_at = ""
                if date_tag:
                    datetime_attr = date_tag.get("datetime", "")
                    if datetime_attr:
                        published_at = datetime_attr
                    else:
                        published_at = date_tag.get_text(strip=True)

                # 嘗試取得摘要
                summary_tag = (
                    post.select_one(".entry-summary")
                    or post.select_one(".entry-content")
                    or post.select_one("p")
                )
                summary = ""
                if summary_tag:
                    summary = summary_tag.get_text(strip=True)[:300]

                articles.append(Article(
                    title=title,
                    url=link,
                    source="GGRAsia",
                    published_at=published_at,
                    summary=summary,
                    language="en",
                ))

        except Exception as e:
            logger.error("解析 GGRAsia 第 %d 頁失敗: %s", page, e)
            continue

    logger.info("GGRAsia 共蒐集 %d 篇", len(articles))
    return articles


async def _scrape_calvin_ayre(
    fetcher: RateLimitedFetcher,
    max_pages: int = 3,
) -> list[Article]:
    """蒐集 CalvinAyre 的日本標籤文章"""
    articles: list[Article] = []
    base_url = "https://calvinayre.com"

    for page in range(1, max_pages + 1):
        url = f"{base_url}/tag/japan/page/{page}/"
        if page == 1:
            url = f"{base_url}/tag/japan/"

        logger.info("蒐集 CalvinAyre 第 %d 頁", page)
        html = await fetcher.fetch(url)
        if not html:
            break

        try:
            soup = BeautifulSoup(html, "html.parser")
            post_items = (
                soup.select("article")
                or soup.select(".post-item")
                or soup.select(".entry")
            )

            if not post_items:
                break

            for post in post_items:
                title_tag = (
                    post.select_one("h2 a")
                    or post.select_one("h3 a")
                    or post.select_one(".entry-title a")
                )
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin(base_url, link)

                date_tag = post.select_one("time") or post.select_one(".entry-date")
                published_at = ""
                if date_tag:
                    published_at = date_tag.get("datetime", date_tag.get_text(strip=True))

                summary_tag = post.select_one(".entry-summary") or post.select_one("p")
                summary = summary_tag.get_text(strip=True)[:300] if summary_tag else ""

                articles.append(Article(
                    title=title,
                    url=link,
                    source="CalvinAyre",
                    published_at=published_at,
                    summary=summary,
                    language="en",
                ))

        except Exception as e:
            logger.error("解析 CalvinAyre 第 %d 頁失敗: %s", page, e)
            continue

    logger.info("CalvinAyre 共蒐集 %d 篇", len(articles))
    return articles


async def _scrape_agb(
    fetcher: RateLimitedFetcher,
    max_pages: int = 3,
) -> list[Article]:
    """蒐集 AGB（Asia Gaming Brief）的日本市場文章"""
    articles: list[Article] = []
    base_url = "https://agbrief.com"

    for page in range(1, max_pages + 1):
        url = f"{base_url}/market/japan/page/{page}/"
        if page == 1:
            url = f"{base_url}/market/japan/"

        logger.info("蒐集 AGB 第 %d 頁", page)
        html = await fetcher.fetch(url)
        if not html:
            break

        try:
            soup = BeautifulSoup(html, "html.parser")
            post_items = (
                soup.select("article")
                or soup.select(".post-item")
                or soup.select(".entry")
            )

            if not post_items:
                break

            for post in post_items:
                title_tag = (
                    post.select_one("h2 a")
                    or post.select_one("h3 a")
                    or post.select_one(".entry-title a")
                )
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin(base_url, link)

                date_tag = post.select_one("time") or post.select_one(".entry-date")
                published_at = ""
                if date_tag:
                    published_at = date_tag.get("datetime", date_tag.get_text(strip=True))

                summary_tag = post.select_one(".entry-summary") or post.select_one("p")
                summary = summary_tag.get_text(strip=True)[:300] if summary_tag else ""

                articles.append(Article(
                    title=title,
                    url=link,
                    source="AGB",
                    published_at=published_at,
                    summary=summary,
                    language="en",
                ))

        except Exception as e:
            logger.error("解析 AGB 第 %d 頁失敗: %s", page, e)
            continue

    logger.info("AGB 共蒐集 %d 篇", len(articles))
    return articles


async def _scrape_inside_asian_gaming(
    fetcher: RateLimitedFetcher,
    max_pages: int = 3,
) -> list[Article]:
    """蒐集 Inside Asian Gaming 的日本相關文章"""
    articles: list[Article] = []
    base_url = "https://www.asgam.com"

    for page in range(1, max_pages + 1):
        url = f"{base_url}/page/{page}/?s=japan"
        if page == 1:
            url = f"{base_url}/?s=japan"

        logger.info("蒐集 Inside Asian Gaming 第 %d 頁", page)
        html = await fetcher.fetch(url)
        if not html:
            break

        try:
            soup = BeautifulSoup(html, "html.parser")
            post_items = (
                soup.select("article")
                or soup.select(".post-item")
                or soup.select(".entry")
            )

            if not post_items:
                break

            for post in post_items:
                title_tag = (
                    post.select_one("h2 a")
                    or post.select_one("h3 a")
                    or post.select_one(".entry-title a")
                )
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = title_tag.get("href", "")
                if link and not link.startswith("http"):
                    link = urljoin(base_url, link)

                date_tag = post.select_one("time") or post.select_one(".entry-date")
                published_at = ""
                if date_tag:
                    published_at = date_tag.get("datetime", date_tag.get_text(strip=True))

                summary_tag = post.select_one(".entry-summary") or post.select_one("p")
                summary = summary_tag.get_text(strip=True)[:300] if summary_tag else ""

                articles.append(Article(
                    title=title,
                    url=link,
                    source="Inside Asian Gaming",
                    published_at=published_at,
                    summary=summary,
                    language="en",
                ))

        except Exception as e:
            logger.error("解析 Inside Asian Gaming 第 %d 頁失敗: %s", page, e)
            continue

    logger.info("Inside Asian Gaming 共蒐集 %d 篇", len(articles))
    return articles


async def fetch_industry_sites(
    fetcher: RateLimitedFetcher,
    max_pages: int = 3,
) -> list[Article]:
    """蒐集所有產業網站的文章

    依序蒐集 GGRAsia、CalvinAyre、AGB、Inside Asian Gaming，
    每個來源獨立處理錯誤，確保單一來源失敗不影響其他來源。

    Args:
        fetcher: HTTP 客戶端實例
        max_pages: 每個來源最多翻幾頁

    Returns:
        所有產業網站蒐集到的文章列表
    """
    all_articles: list[Article] = []

    scrapers = [
        ("GGRAsia", _scrape_ggr_asia),
        ("CalvinAyre", _scrape_calvin_ayre),
        ("AGB", _scrape_agb),
        ("Inside Asian Gaming", _scrape_inside_asian_gaming),
    ]

    for name, scraper in scrapers:
        try:
            articles = await scraper(fetcher, max_pages)
            all_articles.extend(articles)
        except Exception as e:
            logger.error("蒐集 %s 時發生未預期錯誤: %s", name, e)
            continue

    logger.info("產業網站共蒐集 %d 篇（去重前）", len(all_articles))
    return all_articles
