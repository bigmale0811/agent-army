# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — 資料存取層

負責將蒐集到的文章和報告以 JSON 格式儲存到 data/japan_intel/ 目錄，
以及從既有檔案中讀取歷史資料，用於去重和報告產生。
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .config import ARTICLES_DIR, REPORTS_DIR
from .models import Article, Report

logger = logging.getLogger(__name__)


class ArticleStorage:
    """文章 JSON 檔案存取

    以日期為單位儲存文章，檔案格式：YYYY-MM-DD.json
    每個 JSON 檔案包含該日蒐集到的所有文章列表。
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or ARTICLES_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_articles(self, articles: list[Article], collect_date: Optional[date] = None) -> Path:
        """儲存文章列表到 JSON 檔案

        Args:
            articles: 要儲存的文章列表
            collect_date: 蒐集日期，預設為今天

        Returns:
            儲存的檔案路徑
        """
        if not articles:
            logger.warning("沒有文章需要儲存")
            return self._dir

        target_date = collect_date or date.today()
        file_path = self._dir / f"{target_date.isoformat()}.json"

        # 如果該日期已有檔案，合併去重
        existing = self.load_articles(target_date)
        existing_urls = {a.url for a in existing}
        new_articles = [a for a in articles if a.url not in existing_urls]

        all_articles = existing + new_articles
        data = [a.to_dict() for a in all_articles]

        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "儲存 %d 篇文章到 %s（新增 %d 篇）",
            len(all_articles), file_path.name, len(new_articles),
        )
        return file_path

    def load_articles(self, target_date: date) -> list[Article]:
        """讀取指定日期的文章

        Args:
            target_date: 要讀取的日期

        Returns:
            該日期的文章列表，檔案不存在則回傳空列表
        """
        file_path = self._dir / f"{target_date.isoformat()}.json"
        if not file_path.exists():
            return []

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return [Article.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("讀取 %s 失敗: %s", file_path.name, e)
            return []

    def load_articles_range(self, start_date: date, end_date: date) -> list[Article]:
        """讀取日期範圍內的所有文章

        Args:
            start_date: 起始日期（含）
            end_date: 結束日期（含）

        Returns:
            該範圍內的所有文章列表
        """
        articles = []
        # 掃描目錄中所有 JSON 檔案，篩選日期範圍
        for file_path in sorted(self._dir.glob("*.json")):
            try:
                file_date = date.fromisoformat(file_path.stem)
                if start_date <= file_date <= end_date:
                    articles.extend(self.load_articles(file_date))
            except ValueError:
                # 檔名不是有效日期格式，跳過
                continue
        return articles

    def get_all_urls(self) -> set[str]:
        """取得所有已儲存文章的 URL 集合，用於全域去重"""
        urls: set[str] = set()
        for file_path in self._dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                for item in data:
                    if "url" in item:
                        urls.add(item["url"])
            except (json.JSONDecodeError, KeyError):
                continue
        return urls


class ReportStorage:
    """報告 JSON 檔案存取

    檔案格式：report_YYYY-MM-DD_{mode}.json
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self._dir = base_dir or REPORTS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: Report) -> Path:
        """儲存報告到 JSON 檔案

        Args:
            report: 要儲存的報告

        Returns:
            儲存的檔案路徑
        """
        filename = f"report_{report.period_end}_{report.mode}.json"
        file_path = self._dir / filename

        file_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("報告已儲存: %s（共 %d 篇文章）", filename, report.total_count)
        return file_path

    def load_report(self, file_path: Path) -> Optional[Report]:
        """讀取指定報告檔案

        Args:
            file_path: 報告檔案路徑

        Returns:
            Report 實例，讀取失敗則回傳 None
        """
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return Report.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("讀取報告 %s 失敗: %s", file_path.name, e)
            return None

    def list_reports(self) -> list[Path]:
        """列出所有已儲存的報告檔案，按日期排序"""
        return sorted(self._dir.glob("report_*.json"))
