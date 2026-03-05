# -*- coding: utf-8 -*-
"""reporter.py 單元測試 — 報告產生器格式化與分段"""

import pytest
from src.japan_intel.models import Article, Report
from src.japan_intel.reporter import ReportGenerator


@pytest.fixture
def reporter():
    return ReportGenerator()


@pytest.fixture
def sample_report():
    """建立包含多分類文章的測試報告"""
    articles = [
        Article(
            title="大阪 IR 開發進度更新",
            url="https://example.com/osaka-ir",
            source="GGRAsia",
            published_at="2026-03-01",
            summary="大阪 IR 最新進展報導",
            category="ir_casino",
        ),
        Article(
            title="Japan online casino crackdown",
            url="https://example.com/online",
            source="CalvinAyre",
            published_at="2026-03-02",
            summary="Online gambling enforcement",
            category="online_gambling",
        ),
        Article(
            title="パチンコ業界新規制",
            url="https://example.com/pachinko",
            source="NHK",
            published_at="2026-03-03",
            summary="柏青哥新規",
            category="pachinko",
        ),
    ]
    return Report(
        period_start="2026-02-24",
        period_end="2026-03-03",
        articles=articles,
        mode="weekly",
    )


class TestReportGenerator:
    """ReportGenerator 測試"""

    def test_generate_returns_list(self, reporter, sample_report):
        """generate 回傳字串列表"""
        result = reporter.generate(sample_report)
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)
        assert len(result) >= 1

    def test_report_contains_title(self, reporter, sample_report):
        """報告包含標題"""
        result = reporter.generate(sample_report)
        full_text = "\n".join(result)
        assert "日本博弈產業週報" in full_text

    def test_report_contains_date_range(self, reporter, sample_report):
        """報告包含日期範圍"""
        result = reporter.generate(sample_report)
        full_text = "\n".join(result)
        assert "2026-02-24" in full_text
        assert "2026-03-03" in full_text

    def test_report_contains_category_headers(self, reporter, sample_report):
        """報告包含各分類標題"""
        result = reporter.generate(sample_report)
        full_text = "\n".join(result)
        assert "IR 綜合度假村" in full_text
        assert "線上博弈" in full_text
        assert "柏青哥/角子機" in full_text

    def test_report_contains_article_titles(self, reporter, sample_report):
        """報告包含文章標題"""
        result = reporter.generate(sample_report)
        full_text = "\n".join(result)
        assert "大阪 IR 開發進度更新" in full_text
        assert "パチンコ業界新規制" in full_text

    def test_report_contains_total_count(self, reporter, sample_report):
        """報告包含文章總數"""
        result = reporter.generate(sample_report)
        full_text = "\n".join(result)
        assert "3" in full_text

    def test_report_contains_agent_army_footer(self, reporter, sample_report):
        """報告底部有 Agent Army 標記"""
        result = reporter.generate(sample_report)
        full_text = "\n".join(result)
        assert "Agent Army" in full_text

    def test_empty_report(self, reporter):
        """空報告應有適當提示"""
        report = Report(period_start="2026-02-24", period_end="2026-03-03")
        result = reporter.generate(report)
        full_text = "\n".join(result)
        assert "未蒐集到" in full_text

    def test_split_long_message(self, reporter):
        """超長訊息應自動分段"""
        # 建立足夠多的文章（分散到多個分類）使報告超過 4096 字
        categories = ["ir_casino", "online_gambling", "pachinko", "gaming"]
        articles = [
            Article(
                title=f"Very Long Article Title Number {i} About Japan Gambling Industry News",
                url=f"https://example.com/article-{i}",
                source="TestSource",
                published_at="2026-03-01",
                summary="A" * 200,
                category=categories[i % len(categories)],
            )
            for i in range(80)
        ]
        report = Report(
            period_start="2026-02-24", period_end="2026-03-03",
            articles=articles,
        )
        result = reporter.generate(report)
        assert len(result) >= 2
        for segment in result:
            assert len(segment) <= 4096

    def test_initial_mode_title(self, reporter):
        """initial 模式應顯示年度總覽標題"""
        report = Report(
            period_start="2025-03-03", period_end="2026-03-03",
            mode="initial",
        )
        result = reporter.generate(report)
        full_text = "\n".join(result)
        assert "年度總覽" in full_text
