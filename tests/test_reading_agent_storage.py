# -*- coding: utf-8 -*-
"""讀書 Agent — 儲存模組測試"""

import json
import pytest
from pathlib import Path

from src.reading_agent.models import Video, ReadingReport
from src.reading_agent.storage import VideoStorage, ReportStorage


@pytest.fixture
def tmp_video_dir(tmp_path):
    return tmp_path / "videos"


@pytest.fixture
def tmp_report_dir(tmp_path):
    return tmp_path / "reports"


def _make_video(idx=0):
    return Video(
        title=f"測試影片{idx}",
        url=f"https://youtube.com/watch?v=test{idx}",
        channel_name="測試頻道",
        channel_id="UC_test",
        published_at="2026-03-01",
        video_id=f"test{idx}",
    )


class TestVideoStorage:
    def test_save_and_load(self, tmp_video_dir):
        storage = VideoStorage(base_dir=tmp_video_dir)
        videos = [_make_video(0), _make_video(1)]
        storage.save_videos(videos, date_str="2026-03-03")

        loaded = storage.load_videos("2026-03-03")
        assert len(loaded) == 2
        assert loaded[0].title == "測試影片0"

    def test_merge_no_duplicates(self, tmp_video_dir):
        storage = VideoStorage(base_dir=tmp_video_dir)
        storage.save_videos([_make_video(0)], date_str="2026-03-03")
        storage.save_videos([_make_video(0), _make_video(1)], date_str="2026-03-03")

        loaded = storage.load_videos("2026-03-03")
        assert len(loaded) == 2  # 不重複

    def test_get_all_urls(self, tmp_video_dir):
        storage = VideoStorage(base_dir=tmp_video_dir)
        storage.save_videos([_make_video(0)], date_str="2026-03-01")
        storage.save_videos([_make_video(1)], date_str="2026-03-02")

        urls = storage.get_all_urls()
        assert len(urls) == 2

    def test_load_nonexistent(self, tmp_video_dir):
        storage = VideoStorage(base_dir=tmp_video_dir)
        result = storage.load_videos("1999-01-01")
        assert result == []


class TestReportStorage:
    def test_save_and_load(self, tmp_report_dir):
        storage = ReportStorage(base_dir=tmp_report_dir)
        report = ReadingReport(
            period_start="2026-02-24",
            period_end="2026-03-03",
            videos=[_make_video(0)],
            mode="weekly",
        )
        path = storage.save_report(report)
        assert path.exists()

        loaded = storage.load_report(path)
        assert loaded.total_count == 1
        assert loaded.mode == "weekly"
