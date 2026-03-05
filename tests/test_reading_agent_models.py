# -*- coding: utf-8 -*-
"""讀書 Agent — 資料模型測試"""

import pytest
from src.reading_agent.models import Video, ReadingReport


class TestVideo:
    """Video 資料模型測試"""

    def _make_video(self, **kwargs):
        defaults = {
            "title": "測試影片",
            "url": "https://youtube.com/watch?v=abc123",
            "channel_name": "測試頻道",
            "channel_id": "UC_test",
            "published_at": "2026-03-01T10:00:00",
            "description": "這是一部測試影片",
            "category": "general",
            "video_id": "abc123",
        }
        defaults.update(kwargs)
        return Video(**defaults)

    def test_create_video(self):
        v = self._make_video()
        assert v.title == "測試影片"
        assert v.url == "https://youtube.com/watch?v=abc123"
        assert v.channel_name == "測試頻道"
        assert v.collected_at  # 自動產生

    def test_equality_by_url(self):
        v1 = self._make_video(title="標題A")
        v2 = self._make_video(title="標題B")  # 同 URL
        assert v1 == v2

    def test_inequality_different_url(self):
        v1 = self._make_video(url="https://youtube.com/watch?v=aaa")
        v2 = self._make_video(url="https://youtube.com/watch?v=bbb")
        assert v1 != v2

    def test_hash_by_url(self):
        v1 = self._make_video()
        v2 = self._make_video()
        assert hash(v1) == hash(v2)
        assert len({v1, v2}) == 1  # set 去重

    def test_to_dict(self):
        v = self._make_video(description="a" * 1000)
        d = v.to_dict()
        assert d["title"] == "測試影片"
        assert len(d["description"]) <= 500  # 描述截斷

    def test_from_dict(self):
        d = {
            "title": "從字典建立",
            "url": "https://youtube.com/watch?v=xyz",
            "channel_name": "字典頻道",
            "channel_id": "UC_dict",
            "published_at": "2026-01-01",
        }
        v = Video.from_dict(d)
        assert v.title == "從字典建立"
        assert v.category == "general"  # 預設值

    def test_roundtrip(self):
        v = self._make_video()
        d = v.to_dict()
        v2 = Video.from_dict(d)
        assert v.title == v2.title
        assert v.url == v2.url


class TestReadingReport:
    """ReadingReport 資料模型測試"""

    def _make_report(self, n_videos=5):
        videos = [
            Video(
                title=f"影片{i}",
                url=f"https://youtube.com/watch?v=v{i}",
                channel_name=f"頻道{i % 3}",
                channel_id=f"UC_{i % 3}",
                published_at="2026-03-01",
                category=["business", "science", "general"][i % 3],
            )
            for i in range(n_videos)
        ]
        return ReadingReport(
            period_start="2026-02-24",
            period_end="2026-03-03",
            videos=videos,
            mode="weekly",
        )

    def test_total_count(self):
        r = self._make_report(5)
        assert r.total_count == 5

    def test_channel_counts(self):
        r = self._make_report(6)
        counts = r.channel_counts
        assert sum(counts.values()) == 6

    def test_category_counts(self):
        r = self._make_report(6)
        counts = r.category_counts
        assert "business" in counts
        assert "science" in counts

    def test_get_videos_by_channel(self):
        r = self._make_report(6)
        ch0 = r.get_videos_by_channel("頻道0")
        assert all(v.channel_name == "頻道0" for v in ch0)

    def test_get_videos_by_category(self):
        r = self._make_report(6)
        biz = r.get_videos_by_category("business")
        assert all(v.category == "business" for v in biz)

    def test_to_dict(self):
        r = self._make_report(3)
        d = r.to_dict()
        assert d["total_count"] == 3
        assert "videos" in d
        assert "channel_counts" in d

    def test_from_dict(self):
        r = self._make_report(3)
        d = r.to_dict()
        r2 = ReadingReport.from_dict(d)
        assert r2.total_count == 3
        assert r2.mode == "weekly"

    def test_empty_report(self):
        r = ReadingReport(
            period_start="2026-02-24",
            period_end="2026-03-03",
        )
        assert r.total_count == 0
        assert r.channel_counts == {}
