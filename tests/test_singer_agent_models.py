# -*- coding: utf-8 -*-
"""Singer Agent 資料模型測試"""

import pytest

from src.singer_agent.models import (
    MVProject,
    ProjectStatus,
    SongMetadata,
    SongSpec,
)


class TestSongMetadata:
    """SongMetadata 序列化測試"""

    def test_to_dict_and_back(self):
        """to_dict → from_dict 往返不丟失資料"""
        meta = SongMetadata(
            title="告白氣球",
            artist="周杰倫",
            language="zh",
            genre_hint="pop",
            mood_hint="romantic",
        )
        data = meta.to_dict()
        restored = SongMetadata.from_dict(data)
        assert restored.title == "告白氣球"
        assert restored.artist == "周杰倫"
        assert restored.language == "zh"

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict 忽略未知欄位"""
        data = {"title": "test", "unknown_field": "value"}
        meta = SongMetadata.from_dict(data)
        assert meta.title == "test"

    def test_defaults(self):
        """所有欄位都有預設值"""
        meta = SongMetadata()
        assert meta.title == ""
        assert meta.artist == ""


class TestSongSpec:
    """SongSpec 序列化測試"""

    def test_to_dict_and_back(self):
        """to_dict → from_dict 往返"""
        spec = SongSpec(
            title="告白氣球",
            artist="周杰倫",
            genre="pop",
            mood="romantic",
            visual_style="dreamy pastel anime style",
            background_prompt="cherry blossom park at sunset",
        )
        data = spec.to_dict()
        restored = SongSpec.from_dict(data)
        assert restored.genre == "pop"
        assert restored.mood == "romantic"
        assert restored.background_prompt == "cherry blossom park at sunset"

    def test_empty_spec(self):
        """空規格書不會出錯"""
        spec = SongSpec()
        data = spec.to_dict()
        assert isinstance(data, dict)
        restored = SongSpec.from_dict(data)
        assert restored.title == ""


class TestMVProject:
    """MVProject 序列化測試"""

    def test_to_dict_with_nested_objects(self):
        """巢狀物件正確序列化"""
        project = MVProject(
            project_id="20260304_test",
            status=ProjectStatus.COMPLETED.value,
            metadata=SongMetadata(title="告白氣球", artist="周杰倫"),
            song_spec=SongSpec(genre="pop", mood="romantic"),
            youtube_title="測試標題",
            youtube_tags=["pop", "cover"],
        )
        data = project.to_dict()
        assert data["metadata"]["title"] == "告白氣球"
        assert data["song_spec"]["genre"] == "pop"
        assert data["youtube_tags"] == ["pop", "cover"]

    def test_from_dict_with_nested_objects(self):
        """巢狀物件正確反序列化"""
        data = {
            "project_id": "20260304_test",
            "status": "completed",
            "metadata": {"title": "告白氣球", "artist": "周杰倫"},
            "song_spec": {"genre": "pop", "mood": "romantic"},
            "youtube_tags": ["tag1"],
        }
        project = MVProject.from_dict(data)
        assert project.metadata.title == "告白氣球"
        assert project.song_spec.genre == "pop"

    def test_from_dict_without_nested(self):
        """沒有巢狀物件時不出錯"""
        data = {"project_id": "test", "status": "pending"}
        project = MVProject.from_dict(data)
        assert project.metadata is None
        assert project.song_spec is None

    def test_project_status_enum(self):
        """狀態列舉值正確"""
        assert ProjectStatus.PENDING.value == "pending"
        assert ProjectStatus.COMPLETED.value == "completed"
        assert ProjectStatus.FAILED.value == "failed"
