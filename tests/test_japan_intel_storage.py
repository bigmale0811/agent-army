# -*- coding: utf-8 -*-
"""storage.py 單元測試 — 文章與報告的 JSON 存取"""

import json
import pytest
from datetime import date
from pathlib import Path

from src.japan_intel.models import Article, Report
from src.japan_intel.storage import ArticleStorage, ReportStorage


@pytest.fixture
def tmp_articles_dir(tmp_path):
    """建立暫時的文章目錄"""
    d = tmp_path / "articles"
    d.mkdir()
    return d


@pytest.fixture
def tmp_reports_dir(tmp_path):
    """建立暫時的報告目錄"""
    d = tmp_path / "reports"
    d.mkdir()
    return d


@pytest.fixture
def sample_articles():
    """測試用文章列表"""
    return [
        Article(
            title=f"Article {i}",
            url=f"https://example.com/article-{i}",
            source="TestSource",
            published_at="2026-03-01",
            category="ir_casino",
        )
        for i in range(5)
    ]


class TestArticleStorage:
    """ArticleStorage 測試"""

    def test_save_and_load(self, tmp_articles_dir, sample_articles):
        """儲存後讀取應一致"""
        storage = ArticleStorage(tmp_articles_dir)
        target_date = date(2026, 3, 1)

        storage.save_articles(sample_articles, target_date)
        loaded = storage.load_articles(target_date)

        assert len(loaded) == 5
        assert loaded[0].title == "Article 0"
        assert loaded[0].url == "https://example.com/article-0"

    def test_save_creates_json_file(self, tmp_articles_dir, sample_articles):
        """儲存應建立 JSON 檔案"""
        storage = ArticleStorage(tmp_articles_dir)
        target_date = date(2026, 3, 1)

        path = storage.save_articles(sample_articles, target_date)
        expected = tmp_articles_dir / "2026-03-01.json"
        assert expected.exists()

    def test_load_nonexistent_date(self, tmp_articles_dir):
        """讀取不存在的日期回傳空列表"""
        storage = ArticleStorage(tmp_articles_dir)
        result = storage.load_articles(date(2099, 1, 1))
        assert result == []

    def test_save_empty_list(self, tmp_articles_dir):
        """儲存空列表不建立檔案"""
        storage = ArticleStorage(tmp_articles_dir)
        storage.save_articles([], date(2026, 3, 1))
        assert not (tmp_articles_dir / "2026-03-01.json").exists()

    def test_merge_on_same_date(self, tmp_articles_dir):
        """同一天多次儲存應合併去重"""
        storage = ArticleStorage(tmp_articles_dir)
        target_date = date(2026, 3, 1)

        batch1 = [
            Article(title="A", url="https://example.com/a", source="S", published_at="2026-03-01"),
            Article(title="B", url="https://example.com/b", source="S", published_at="2026-03-01"),
        ]
        batch2 = [
            Article(title="B-dup", url="https://example.com/b", source="S", published_at="2026-03-01"),
            Article(title="C", url="https://example.com/c", source="S", published_at="2026-03-01"),
        ]

        storage.save_articles(batch1, target_date)
        storage.save_articles(batch2, target_date)

        loaded = storage.load_articles(target_date)
        assert len(loaded) == 3  # a, b, c（b 不重複）

    def test_load_articles_range(self, tmp_articles_dir):
        """讀取日期範圍內的文章"""
        storage = ArticleStorage(tmp_articles_dir)

        for day in [1, 2, 3, 4, 5]:
            d = date(2026, 3, day)
            articles = [
                Article(
                    title=f"Day{day}", url=f"https://example.com/d{day}",
                    source="S", published_at=d.isoformat(),
                )
            ]
            storage.save_articles(articles, d)

        result = storage.load_articles_range(date(2026, 3, 2), date(2026, 3, 4))
        assert len(result) == 3

    def test_get_all_urls(self, tmp_articles_dir, sample_articles):
        """取得所有已知 URL"""
        storage = ArticleStorage(tmp_articles_dir)
        storage.save_articles(sample_articles, date(2026, 3, 1))

        urls = storage.get_all_urls()
        assert len(urls) == 5
        assert "https://example.com/article-0" in urls

    def test_corrupted_json_returns_empty(self, tmp_articles_dir):
        """損壞的 JSON 檔案應回傳空列表而非拋出例外"""
        bad_file = tmp_articles_dir / "2026-03-01.json"
        bad_file.write_text("this is not json", encoding="utf-8")

        storage = ArticleStorage(tmp_articles_dir)
        result = storage.load_articles(date(2026, 3, 1))
        assert result == []


class TestReportStorage:
    """ReportStorage 測試"""

    def test_save_and_load_report(self, tmp_reports_dir):
        """儲存報告後讀取應一致"""
        storage = ReportStorage(tmp_reports_dir)
        articles = [
            Article(title="A", url="https://example.com/a", source="S", published_at="2026-03-01"),
        ]
        report = Report(
            period_start="2026-02-24", period_end="2026-03-03",
            articles=articles, mode="weekly",
        )

        path = storage.save_report(report)
        assert path.exists()

        loaded = storage.load_report(path)
        assert loaded is not None
        assert loaded.total_count == 1
        assert loaded.mode == "weekly"

    def test_list_reports(self, tmp_reports_dir):
        """列出所有報告"""
        storage = ReportStorage(tmp_reports_dir)

        for i in range(3):
            report = Report(
                period_start=f"2026-0{i+1}-01",
                period_end=f"2026-0{i+1}-07",
                mode="weekly",
            )
            storage.save_report(report)

        reports = storage.list_reports()
        assert len(reports) == 3

    def test_load_nonexistent_report(self, tmp_reports_dir):
        """讀取不存在的報告回傳 None"""
        storage = ReportStorage(tmp_reports_dir)
        result = storage.load_report(tmp_reports_dir / "nonexistent.json")
        assert result is None
