# -*- coding: utf-8 -*-
"""collector.py 單元測試 — 蒐集協調器的去重與分類邏輯"""

import pytest
from src.japan_intel.collector import JapanIntelCollector
from src.japan_intel.models import Article


class TestDeduplication:
    """去重邏輯測試"""

    def _make_collector(self):
        return JapanIntelCollector.__new__(JapanIntelCollector)

    def test_url_dedup(self):
        """URL 相同的文章只保留第一篇"""
        collector = self._make_collector()
        articles = [
            Article(title="A", url="https://example.com/1", source="S", published_at="2026-03-01"),
            Article(title="A-dup", url="https://example.com/1", source="S2", published_at="2026-03-02"),
            Article(title="B", url="https://example.com/2", source="S", published_at="2026-03-01"),
        ]
        result = collector._deduplicate(articles, set())
        assert len(result) == 2
        assert result[0].title == "A"

    def test_exclude_known_urls(self):
        """排除已知的歷史 URL"""
        collector = self._make_collector()
        articles = [
            Article(title="New", url="https://example.com/new", source="S", published_at="2026-03-01"),
            Article(title="Old", url="https://example.com/old", source="S", published_at="2026-03-01"),
        ]
        known = {"https://example.com/old"}
        result = collector._deduplicate(articles, known)
        assert len(result) == 1
        assert result[0].title == "New"

    def test_skip_empty_url(self):
        """跳過空 URL 的文章"""
        collector = self._make_collector()
        articles = [
            Article(title="Empty", url="", source="S", published_at="2026-03-01"),
            Article(title="Valid", url="https://example.com/valid", source="S", published_at="2026-03-01"),
        ]
        result = collector._deduplicate(articles, set())
        assert len(result) == 1

    def test_empty_input(self):
        """空列表去重回傳空列表"""
        collector = self._make_collector()
        result = collector._deduplicate([], set())
        assert result == []


class TestCategorization:
    """自動分類邏輯測試"""

    def _make_collector(self):
        return JapanIntelCollector.__new__(JapanIntelCollector)

    def test_ir_casino_category(self):
        """包含 IR/casino 關鍵字應分類為 ir_casino"""
        collector = self._make_collector()
        article = Article(
            title="Osaka IR integrated resort latest update",
            url="https://example.com/1", source="S", published_at="2026-03-01",
        )
        assert collector._categorize(article) == "ir_casino"

    def test_online_gambling_category(self):
        """包含 online gambling 關鍵字應分類為 online_gambling"""
        collector = self._make_collector()
        article = Article(
            title="Japan online gambling platform iGaming growth",
            url="https://example.com/2", source="S", published_at="2026-03-01",
            summary="オンラインカジノ internet gambling trends",
        )
        assert collector._categorize(article) == "online_gambling"

    def test_pachinko_category(self):
        """包含 pachinko 關鍵字應分類為 pachinko"""
        collector = self._make_collector()
        article = Article(
            title="パチンコ業界の最新動向",
            url="https://example.com/3", source="S", published_at="2026-03-01",
        )
        assert collector._categorize(article) == "pachinko"

    def test_gaming_category(self):
        """包含 sports betting 關鍵字應分類為 gaming"""
        collector = self._make_collector()
        article = Article(
            title="Japan sports betting and lottery market",
            url="https://example.com/4", source="S", published_at="2026-03-01",
        )
        assert collector._categorize(article) == "gaming"

    def test_regulation_category(self):
        """包含法規關鍵字應分類為 regulation"""
        collector = self._make_collector()
        article = Article(
            title="カジノ管理委員会 new regulation",
            url="https://example.com/5", source="S", published_at="2026-03-01",
            summary="日本 gambling law enforcement 取り締まり",
        )
        assert collector._categorize(article) == "regulation"

    def test_no_match_returns_other(self):
        """無匹配關鍵字應歸類為 other"""
        collector = self._make_collector()
        article = Article(
            title="Weather forecast for Tokyo",
            url="https://example.com/6", source="S", published_at="2026-03-01",
        )
        assert collector._categorize(article) == "other"

    def test_case_insensitive(self):
        """分類應不區分大小寫"""
        collector = self._make_collector()
        article = Article(
            title="OSAKA IR CASINO Development",
            url="https://example.com/7", source="S", published_at="2026-03-01",
        )
        assert collector._categorize(article) == "ir_casino"
