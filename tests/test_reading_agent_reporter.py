# -*- coding: utf-8 -*-
"""讀書 Agent — 報告產生器測試"""

import pytest
from src.reading_agent.models import Video, ReadingReport
from src.reading_agent.reporter import ReportGenerator


def _make_report(n=5):
    videos = [
        Video(
            title=f"第{i}本書的說書",
            url=f"https://youtube.com/watch?v=v{i}",
            channel_name=f"頻道{i % 2}",
            channel_id=f"UC_{i % 2}",
            published_at="2026-03-01",
            category=["business", "science"][i % 2],
        )
        for i in range(n)
    ]
    return ReadingReport(
        period_start="2026-02-24",
        period_end="2026-03-03",
        videos=videos,
        mode="weekly",
    )


class TestReportGenerator:
    def test_empty_report(self):
        gen = ReportGenerator()
        report = ReadingReport(
            period_start="2026-02-24",
            period_end="2026-03-03",
        )
        segments = gen.generate(report)
        assert len(segments) == 1
        assert "未有新影片" in segments[0]

    def test_basic_report(self):
        gen = ReportGenerator()
        report = _make_report(3)
        segments = gen.generate(report)
        assert len(segments) >= 1
        assert "讀書摘要" in segments[0]

    def test_smart_report_with_summary(self):
        gen = ReportGenerator()
        report = _make_report(3)
        summary = "本週推薦書單：\n1. 原子習慣\n2. 思考的藝術"
        segments = gen.generate(report, summary=summary)
        full_text = "\n".join(segments)
        assert "原子習慣" in full_text
        assert "Gemini 摘要" in full_text

    def test_split_long_message(self):
        gen = ReportGenerator()
        # 建立超長報告
        report = _make_report(100)
        segments = gen.generate(report)
        for seg in segments:
            assert len(seg) <= 4096

    def test_report_contains_channel_stats(self):
        gen = ReportGenerator()
        report = _make_report(6)
        summary = "本週測試摘要"
        segments = gen.generate(report, summary=summary)
        full_text = "\n".join(segments)
        assert "頻道" in full_text

    def test_report_has_footer(self):
        gen = ReportGenerator()
        report = _make_report(3)
        segments = gen.generate(report)
        last = segments[-1]
        assert "Agent Army" in last
