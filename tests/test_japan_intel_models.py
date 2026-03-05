# -*- coding: utf-8 -*-
"""models.py 單元測試 — Article 與 Report 資料模型"""

import pytest
from datetime import datetime
from src.japan_intel.models import Article, Report


class TestArticle:
    """Article dataclass 測試"""

    def test_create_article_with_required_fields(self):
        """建立只有必要欄位的 Article"""
        article = Article(
            title="大阪 IR 最新進展",
            url="https://example.com/osaka-ir",
            source="GGRAsia",
            published_at="2026-03-01T10:00:00",
        )
        assert article.title == "大阪 IR 最新進展"
        assert article.url == "https://example.com/osaka-ir"
        assert article.source == "GGRAsia"
        assert article.category == "other"
        assert article.language == "en"

    def test_create_article_with_all_fields(self):
        """建立包含所有欄位的 Article"""
        article = Article(
            title="Test",
            url="https://example.com/1",
            source="NHK",
            published_at="2026-03-01",
            summary="摘要內容",
            category="ir_casino",
            language="ja",
            collected_at="2026-03-01T12:00:00",
        )
        assert article.summary == "摘要內容"
        assert article.category == "ir_casino"
        assert article.language == "ja"

    def test_to_dict(self):
        """序列化為字典"""
        article = Article(
            title="Test", url="https://example.com/1",
            source="Test", published_at="2026-03-01",
        )
        d = article.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "Test"
        assert d["url"] == "https://example.com/1"
        assert "collected_at" in d

    def test_from_dict(self):
        """從字典反序列化"""
        data = {
            "title": "反序列化測試",
            "url": "https://example.com/2",
            "source": "Test",
            "published_at": "2026-03-01",
            "summary": "test summary",
            "category": "pachinko",
            "language": "ja",
            "collected_at": "2026-03-01T00:00:00",
        }
        article = Article.from_dict(data)
        assert article.title == "反序列化測試"
        assert article.category == "pachinko"

    def test_from_dict_ignores_extra_fields(self):
        """反序列化時忽略多餘欄位"""
        data = {
            "title": "Test", "url": "https://example.com/3",
            "source": "Test", "published_at": "2026-03-01",
            "extra_field": "should be ignored",
        }
        article = Article.from_dict(data)
        assert article.title == "Test"
        assert not hasattr(article, "extra_field")

    def test_equality_by_url(self):
        """以 URL 作為唯一識別比較"""
        a1 = Article(title="A", url="https://example.com/same", source="S", published_at="2026-01-01")
        a2 = Article(title="B", url="https://example.com/same", source="S2", published_at="2026-01-02")
        a3 = Article(title="A", url="https://example.com/diff", source="S", published_at="2026-01-01")
        assert a1 == a2
        assert a1 != a3

    def test_hash_by_url(self):
        """URL 相同的 Article 可用 set 去重"""
        a1 = Article(title="A", url="https://example.com/same", source="S", published_at="2026-01-01")
        a2 = Article(title="B", url="https://example.com/same", source="S2", published_at="2026-01-02")
        article_set = {a1, a2}
        assert len(article_set) == 1

    def test_roundtrip_serialization(self):
        """序列化後反序列化應還原"""
        original = Article(
            title="來回測試", url="https://example.com/rt",
            source="Test", published_at="2026-03-01",
            summary="摘要", category="gaming", language="en",
        )
        restored = Article.from_dict(original.to_dict())
        assert original == restored
        assert restored.title == "來回測試"
        assert restored.category == "gaming"


class TestReport:
    """Report dataclass 測試"""

    def _make_articles(self, count: int = 3) -> list[Article]:
        """建立測試用文章列表"""
        categories = ["ir_casino", "online_gambling", "pachinko"]
        return [
            Article(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                source="Test",
                published_at="2026-03-01",
                category=categories[i % len(categories)],
            )
            for i in range(count)
        ]

    def test_create_empty_report(self):
        """建立空報告"""
        report = Report(
            period_start="2026-02-24",
            period_end="2026-03-03",
        )
        assert report.total_count == 0
        assert report.category_counts == {}
        assert report.mode == "weekly"

    def test_report_auto_stats(self):
        """建立帶文章的報告，自動計算統計"""
        articles = self._make_articles(6)
        report = Report(
            period_start="2026-02-24",
            period_end="2026-03-03",
            articles=articles,
        )
        assert report.total_count == 6
        assert report.category_counts["ir_casino"] == 2
        assert report.category_counts["online_gambling"] == 2
        assert report.category_counts["pachinko"] == 2

    def test_add_articles(self):
        """批次新增文章並更新統計"""
        report = Report(period_start="2026-02-24", period_end="2026-03-03")
        assert report.total_count == 0

        report.add_articles(self._make_articles(3))
        assert report.total_count == 3

    def test_get_articles_by_category(self):
        """取得特定分類的文章"""
        articles = self._make_articles(6)
        report = Report(
            period_start="2026-02-24", period_end="2026-03-03",
            articles=articles,
        )
        ir_articles = report.get_articles_by_category("ir_casino")
        assert len(ir_articles) == 2
        assert all(a.category == "ir_casino" for a in ir_articles)

    def test_to_dict(self):
        """序列化為字典"""
        report = Report(
            period_start="2026-02-24", period_end="2026-03-03",
            articles=self._make_articles(2),
        )
        d = report.to_dict()
        assert d["total_count"] == 2
        assert len(d["articles"]) == 2
        assert isinstance(d["articles"][0], dict)

    def test_from_dict(self):
        """從字典反序列化"""
        original = Report(
            period_start="2026-02-24", period_end="2026-03-03",
            articles=self._make_articles(3), mode="initial",
        )
        restored = Report.from_dict(original.to_dict())
        assert restored.total_count == 3
        assert restored.mode == "initial"
        assert restored.period_start == "2026-02-24"
