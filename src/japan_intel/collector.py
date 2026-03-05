# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — 蒐集協調器

負責協調所有資訊來源、執行去重、自動分類，
是整個蒐集流程的核心調度中心。
"""

import logging
from datetime import date, timedelta
from typing import Optional

from .config import (
    CATEGORY_KEYWORDS,
    INITIAL_DAYS,
    SEARCH_KEYWORDS_EN,
    SEARCH_KEYWORDS_JA,
    WEEKLY_DAYS,
)
from .fetcher import RateLimitedFetcher
from .models import Article, Report
from .sources.google_news import fetch_google_news
from .sources.industry_sites import fetch_industry_sites
from .sources.japan_media import fetch_japan_media
from .storage import ArticleStorage

logger = logging.getLogger(__name__)


class JapanIntelCollector:
    """日本博弈資訊蒐集協調器

    負責：
    1. 依模式（initial/weekly）決定蒐集範圍
    2. 呼叫各來源爬蟲蒐集文章
    3. URL 去重與標題相似度去重
    4. 自動分類文章
    5. 儲存蒐集結果
    6. 產生 Report 物件
    """

    def __init__(self, storage: Optional[ArticleStorage] = None):
        self._storage = storage or ArticleStorage()

    async def collect(self, mode: str = "weekly") -> Report:
        """執行完整的蒐集流程

        Args:
            mode: 蒐集模式
                - "initial": 蒐集過去一年的資料
                - "weekly": 蒐集過去一週的資料

        Returns:
            包含所有蒐集結果的 Report 物件
        """
        # 決定蒐集範圍
        today = date.today()
        if mode == "initial":
            days_back = INITIAL_DAYS
            start_date = today - timedelta(days=INITIAL_DAYS)
        else:
            days_back = WEEKLY_DAYS
            start_date = today - timedelta(days=WEEKLY_DAYS)

        logger.info(
            "開始蒐集 [%s 模式]：%s ~ %s（%d 天）",
            mode, start_date.isoformat(), today.isoformat(), days_back,
        )

        # 取得已知 URL，用於全域去重
        known_urls = self._storage.get_all_urls()
        logger.info("已知 %d 個歷史文章 URL", len(known_urls))

        all_articles: list[Article] = []

        # 使用 async context manager 管理 HTTP 客戶端
        async with RateLimitedFetcher() as fetcher:
            # === 來源 1: Google News（日文） ===
            try:
                logger.info("=== 開始蒐集 Google News（日文） ===")
                ja_articles = await fetch_google_news(
                    fetcher, SEARCH_KEYWORDS_JA, language="ja", days_back=days_back,
                )
                all_articles.extend(ja_articles)
            except Exception as e:
                logger.error("Google News（日文）蒐集失敗: %s", e)

            # === 來源 2: Google News（英文） ===
            try:
                logger.info("=== 開始蒐集 Google News（英文） ===")
                en_articles = await fetch_google_news(
                    fetcher, SEARCH_KEYWORDS_EN, language="en", days_back=days_back,
                )
                all_articles.extend(en_articles)
            except Exception as e:
                logger.error("Google News（英文）蒐集失敗: %s", e)

            # === 來源 3: 產業網站 ===
            try:
                logger.info("=== 開始蒐集產業網站 ===")
                # initial 模式多翻幾頁
                max_pages = 10 if mode == "initial" else 3
                industry_articles = await fetch_industry_sites(fetcher, max_pages)
                all_articles.extend(industry_articles)
            except Exception as e:
                logger.error("產業網站蒐集失敗: %s", e)

            # === 來源 4: 日本媒體 ===
            try:
                logger.info("=== 開始蒐集日本媒體 ===")
                japan_articles = await fetch_japan_media(
                    fetcher, SEARCH_KEYWORDS_JA,
                )
                all_articles.extend(japan_articles)
            except Exception as e:
                logger.error("日本媒體蒐集失敗: %s", e)

            logger.info("HTTP 客戶端統計: %s", fetcher.stats)

        # === 後處理 ===
        logger.info("蒐集完成，共 %d 篇（去重前）", len(all_articles))

        # 去重（URL 基準 + 排除已知）
        unique_articles = self._deduplicate(all_articles, known_urls)
        logger.info("去重後剩餘 %d 篇", len(unique_articles))

        # 自動分類
        for article in unique_articles:
            if article.category == "other":
                article.category = self._categorize(article)

        # 儲存文章
        if unique_articles:
            self._storage.save_articles(unique_articles)

        # 建構報告
        report = Report(
            period_start=start_date.isoformat(),
            period_end=today.isoformat(),
            articles=unique_articles,
            mode=mode,
        )

        logger.info(
            "報告產生完成：%s ~ %s，共 %d 篇，分類統計: %s",
            report.period_start, report.period_end,
            report.total_count, report.category_counts,
        )

        return report

    def _deduplicate(
        self,
        articles: list[Article],
        known_urls: set[str],
    ) -> list[Article]:
        """去除重複文章

        策略：
        1. URL 完全相同的視為重複
        2. 排除已在歷史資料中出現過的 URL

        Args:
            articles: 待去重的文章列表
            known_urls: 已知的歷史 URL 集合

        Returns:
            去重後的文章列表
        """
        seen_urls: set[str] = set()
        unique: list[Article] = []

        for article in articles:
            url = article.url.strip()
            if not url:
                continue
            if url in seen_urls or url in known_urls:
                continue
            seen_urls.add(url)
            unique.append(article)

        removed = len(articles) - len(unique)
        if removed > 0:
            logger.info("去重移除 %d 篇重複文章", removed)

        return unique

    def _categorize(self, article: Article) -> str:
        """根據標題和摘要中的關鍵字自動分類

        以關鍵字匹配計數決定分類，匹配最多的分類勝出。
        若無任何匹配則歸類為 "other"。

        Args:
            article: 要分類的文章

        Returns:
            分類代碼（如 "ir_casino", "online_gambling" 等）
        """
        # 合併標題和摘要作為匹配文字（轉小寫）
        text = f"{article.title} {article.summary}".lower()

        best_category = "other"
        best_score = 0

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > best_score:
                best_score = score
                best_category = category

        return best_category
