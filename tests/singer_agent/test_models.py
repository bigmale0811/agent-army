# -*- coding: utf-8 -*-
"""
DEV-1: models.py 單元測試
測試所有核心 dataclass 的建立、序列化與不可變性。
"""
import pytest
from dataclasses import FrozenInstanceError
from pathlib import Path
from datetime import datetime


# ─────────────────────────────────────────────────
# SongResearch 測試
# ─────────────────────────────────────────────────

class TestSongResearch:
    """測試 SongResearch frozen dataclass。"""

    def test_create_with_all_fields(self, sample_song_research_data):
        """SongResearch 可用所有 8 個欄位成功建立。"""
        from src.singer_agent.models import SongResearch
        r = SongResearch(**sample_song_research_data)
        assert r.genre == "ballad"
        assert r.mood == "romantic, nostalgic"
        assert r.visual_style == "Pastel Watercolor"
        assert r.color_palette == ["soft_pink", "light_blue", "cream"]
        assert r.background_prompt == "pastel watercolor dreamy landscape, soft clouds"
        assert r.outfit_prompt == "white flowing dress, elegant"
        assert r.scene_description == "溫柔的粉彩水彩風格，夢幻背景"
        assert r.research_summary == "這首情歌帶有懷舊感，適合柔和的視覺風格"

    def test_is_frozen(self, sample_song_research_data):
        """SongResearch 為 frozen=True，不允許修改欄位。"""
        from src.singer_agent.models import SongResearch
        r = SongResearch(**sample_song_research_data)
        with pytest.raises(FrozenInstanceError):
            r.genre = "pop"  # type: ignore

    def test_all_eight_fields_required(self):
        """SongResearch 缺少任何欄位應拋出 TypeError。"""
        from src.singer_agent.models import SongResearch
        with pytest.raises(TypeError):
            SongResearch(genre="ballad")  # type: ignore

    def test_genre_is_non_empty(self, sample_song_research_data):
        """genre 欄位非空字串。"""
        from src.singer_agent.models import SongResearch
        r = SongResearch(**sample_song_research_data)
        assert isinstance(r.genre, str)
        assert len(r.genre) > 0

    def test_color_palette_is_list(self, sample_song_research_data):
        """color_palette 為 list 型別。"""
        from src.singer_agent.models import SongResearch
        r = SongResearch(**sample_song_research_data)
        assert isinstance(r.color_palette, list)

    def test_color_palette_non_empty(self, sample_song_research_data):
        """color_palette 至少包含一個元素。"""
        from src.singer_agent.models import SongResearch
        r = SongResearch(**sample_song_research_data)
        assert len(r.color_palette) > 0

    def test_equality(self, sample_song_research_data):
        """相同資料的兩個 SongResearch 應相等。"""
        from src.singer_agent.models import SongResearch
        r1 = SongResearch(**sample_song_research_data)
        r2 = SongResearch(**sample_song_research_data)
        assert r1 == r2

    def test_empty_color_palette_allowed(self, sample_song_research_data):
        """空的 color_palette list 在型別上合法（業務層決定是否允許）。"""
        from src.singer_agent.models import SongResearch
        data = {**sample_song_research_data, "color_palette": []}
        r = SongResearch(**data)
        assert r.color_palette == []


# ─────────────────────────────────────────────────
# SongSpec 測試
# ─────────────────────────────────────────────────

class TestSongSpec:
    """測試 SongSpec dataclass（可變）及其序列化方法。"""

    def test_create_with_all_fields(self, sample_song_research_data):
        """SongSpec 可用所有欄位成功建立。"""
        from src.singer_agent.models import SongSpec, SongResearch
        research = SongResearch(**sample_song_research_data)
        spec = SongSpec(
            title="愛我的人和我愛的人",
            artist="測試歌手",
            language="zh-TW",
            research=research,
            created_at="2026-03-06T12:00:00",
        )
        assert spec.title == "愛我的人和我愛的人"
        assert spec.artist == "測試歌手"
        assert spec.language == "zh-TW"
        assert spec.research == research
        assert spec.created_at == "2026-03-06T12:00:00"

    def test_is_mutable(self, sample_song_research_data):
        """SongSpec 為一般 dataclass，允許修改欄位。"""
        from src.singer_agent.models import SongSpec, SongResearch
        research = SongResearch(**sample_song_research_data)
        spec = SongSpec(
            title="original", artist="artist", language="zh",
            research=research, created_at="2026-03-06T00:00:00"
        )
        spec.title = "modified"
        assert spec.title == "modified"

    def test_to_dict_returns_dict(self, sample_song_spec_data):
        """to_dict() 必須回傳 dict 型別。"""
        from src.singer_agent.models import SongSpec, SongResearch
        research = SongResearch(**sample_song_spec_data["research"])
        spec = SongSpec(
            title=sample_song_spec_data["title"],
            artist=sample_song_spec_data["artist"],
            language=sample_song_spec_data["language"],
            research=research,
            created_at=sample_song_spec_data["created_at"],
        )
        result = spec.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self, sample_song_spec_data):
        """to_dict() 結果必須包含所有頂層欄位。"""
        from src.singer_agent.models import SongSpec, SongResearch
        research = SongResearch(**sample_song_spec_data["research"])
        spec = SongSpec(
            title=sample_song_spec_data["title"],
            artist=sample_song_spec_data["artist"],
            language=sample_song_spec_data["language"],
            research=research,
            created_at=sample_song_spec_data["created_at"],
        )
        result = spec.to_dict()
        assert "title" in result
        assert "artist" in result
        assert "language" in result
        assert "research" in result
        assert "created_at" in result

    def test_to_dict_research_is_dict(self, sample_song_spec_data):
        """to_dict() 中的 research 欄位也應序列化為 dict。"""
        from src.singer_agent.models import SongSpec, SongResearch
        research = SongResearch(**sample_song_spec_data["research"])
        spec = SongSpec(
            title=sample_song_spec_data["title"],
            artist=sample_song_spec_data["artist"],
            language=sample_song_spec_data["language"],
            research=research,
            created_at=sample_song_spec_data["created_at"],
        )
        result = spec.to_dict()
        assert isinstance(result["research"], dict)

    def test_from_dict_returns_song_spec(self, sample_song_spec_data):
        """from_dict() 必須回傳 SongSpec 實例。"""
        from src.singer_agent.models import SongSpec
        result = SongSpec.from_dict(sample_song_spec_data)
        assert isinstance(result, SongSpec)

    def test_from_dict_research_is_song_research(self, sample_song_spec_data):
        """from_dict() 中的 research 欄位應還原為 SongResearch 實例。"""
        from src.singer_agent.models import SongSpec, SongResearch
        result = SongSpec.from_dict(sample_song_spec_data)
        assert isinstance(result.research, SongResearch)

    def test_roundtrip_to_dict_from_dict(self, sample_song_spec_data):
        """to_dict() → from_dict() 往返後資料應完全一致。"""
        from src.singer_agent.models import SongSpec
        original = SongSpec.from_dict(sample_song_spec_data)
        serialized = original.to_dict()
        restored = SongSpec.from_dict(serialized)
        assert restored.title == original.title
        assert restored.artist == original.artist
        assert restored.language == original.language
        assert restored.created_at == original.created_at
        assert restored.research == original.research

    def test_from_dict_invalid_missing_title(self, sample_song_spec_data):
        """from_dict() 缺少必要欄位 title 應拋出 KeyError 或 TypeError。"""
        from src.singer_agent.models import SongSpec
        bad_data = {k: v for k, v in sample_song_spec_data.items() if k != "title"}
        with pytest.raises((KeyError, TypeError)):
            SongSpec.from_dict(bad_data)


# ─────────────────────────────────────────────────
# CopySpec 測試
# ─────────────────────────────────────────────────

class TestCopySpec:
    """測試 CopySpec frozen dataclass。"""

    def test_create_with_all_fields(self, sample_copy_spec_data):
        """CopySpec 可用所有欄位成功建立。"""
        from src.singer_agent.models import CopySpec
        spec = CopySpec(**sample_copy_spec_data)
        assert spec.title == "【虛擬歌手】愛我的人和我愛的人 MV"
        assert "感人的情歌" in spec.description
        assert spec.tags == ["虛擬歌手", "情歌", "MV", "AI"]

    def test_is_frozen(self, sample_copy_spec_data):
        """CopySpec 為 frozen=True，不允許修改欄位。"""
        from src.singer_agent.models import CopySpec
        spec = CopySpec(**sample_copy_spec_data)
        with pytest.raises(FrozenInstanceError):
            spec.title = "new title"  # type: ignore

    def test_tags_is_list(self, sample_copy_spec_data):
        """tags 欄位必須為 list 型別。"""
        from src.singer_agent.models import CopySpec
        spec = CopySpec(**sample_copy_spec_data)
        assert isinstance(spec.tags, list)

    def test_tags_non_empty(self, sample_copy_spec_data):
        """tags 至少包含一個元素。"""
        from src.singer_agent.models import CopySpec
        spec = CopySpec(**sample_copy_spec_data)
        assert len(spec.tags) > 0

    def test_tags_elements_are_strings(self, sample_copy_spec_data):
        """tags 中的每個元素都是字串。"""
        from src.singer_agent.models import CopySpec
        spec = CopySpec(**sample_copy_spec_data)
        assert all(isinstance(tag, str) for tag in spec.tags)

    def test_title_is_string(self, sample_copy_spec_data):
        """title 欄位為非空字串。"""
        from src.singer_agent.models import CopySpec
        spec = CopySpec(**sample_copy_spec_data)
        assert isinstance(spec.title, str)
        assert len(spec.title) > 0

    def test_description_is_string(self, sample_copy_spec_data):
        """description 欄位為字串。"""
        from src.singer_agent.models import CopySpec
        spec = CopySpec(**sample_copy_spec_data)
        assert isinstance(spec.description, str)

    def test_equality(self, sample_copy_spec_data):
        """相同資料的兩個 CopySpec 應相等。"""
        from src.singer_agent.models import CopySpec
        c1 = CopySpec(**sample_copy_spec_data)
        c2 = CopySpec(**sample_copy_spec_data)
        assert c1 == c2


# ─────────────────────────────────────────────────
# PrecheckResult 測試
# ─────────────────────────────────────────────────

class TestPrecheckResult:
    """測試 PrecheckResult frozen dataclass。"""

    def test_create_passed_true(self, sample_precheck_result_data):
        """PrecheckResult passed=True 時可正常建立。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(**sample_precheck_result_data)
        assert result.passed is True

    def test_create_passed_false(self):
        """PrecheckResult passed=False 時可正常建立。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(
            passed=False,
            checks={"image_exists": False},
            warnings=["圖片不存在"],
            gemini_score=None,
            gemini_feedback="",
        )
        assert result.passed is False

    def test_passed_is_bool(self, sample_precheck_result_data):
        """passed 欄位必須為 bool 型別。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(**sample_precheck_result_data)
        assert isinstance(result.passed, bool)

    def test_checks_is_dict(self, sample_precheck_result_data):
        """checks 欄位必須為 dict 型別。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(**sample_precheck_result_data)
        assert isinstance(result.checks, dict)

    def test_warnings_is_list(self, sample_precheck_result_data):
        """warnings 欄位必須為 list 型別。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(**sample_precheck_result_data)
        assert isinstance(result.warnings, list)

    def test_gemini_score_can_be_none(self):
        """gemini_score 允許為 None（未使用 Gemini 時）。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(
            passed=True,
            checks={},
            warnings=[],
            gemini_score=None,
            gemini_feedback="",
        )
        assert result.gemini_score is None

    def test_gemini_score_can_be_int(self, sample_precheck_result_data):
        """gemini_score 允許為整數。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(**sample_precheck_result_data)
        assert isinstance(result.gemini_score, int)
        assert result.gemini_score == 85

    def test_is_frozen(self, sample_precheck_result_data):
        """PrecheckResult 為 frozen=True，不允許修改欄位。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(**sample_precheck_result_data)
        with pytest.raises(FrozenInstanceError):
            result.passed = False  # type: ignore

    def test_gemini_feedback_is_string(self, sample_precheck_result_data):
        """gemini_feedback 欄位為字串。"""
        from src.singer_agent.models import PrecheckResult
        result = PrecheckResult(**sample_precheck_result_data)
        assert isinstance(result.gemini_feedback, str)


# ─────────────────────────────────────────────────
# ProjectState 測試
# ─────────────────────────────────────────────────

class TestProjectState:
    """測試 ProjectState dataclass 及其序列化方法。"""

    def _make_project_state(self, sample_project_state_data):
        """從完整資料字典建立 ProjectState 實例的輔助方法。"""
        from src.singer_agent.models import ProjectState
        return ProjectState.from_dict(sample_project_state_data)

    def test_create_from_dict(self, sample_project_state_data):
        """ProjectState 可由完整資料字典成功建立。"""
        state = self._make_project_state(sample_project_state_data)
        assert state.project_id == "test-project-001"
        assert state.status == "completed"

    def test_is_mutable(self, sample_project_state_data):
        """ProjectState 為一般 dataclass，允許修改欄位。"""
        state = self._make_project_state(sample_project_state_data)
        state.status = "running"
        assert state.status == "running"

    def test_song_spec_is_song_spec_instance(self, sample_project_state_data):
        """song_spec 欄位應還原為 SongSpec 實例。"""
        from src.singer_agent.models import SongSpec
        state = self._make_project_state(sample_project_state_data)
        assert isinstance(state.song_spec, SongSpec)

    def test_song_spec_can_be_none(self, sample_project_state_data):
        """song_spec 允許為 None（管線尚未完成研究步驟時）。"""
        from src.singer_agent.models import ProjectState
        data = {**sample_project_state_data, "song_spec": None}
        state = ProjectState.from_dict(data)
        assert state.song_spec is None

    def test_copy_spec_is_copy_spec_instance(self, sample_project_state_data):
        """copy_spec 欄位應還原為 CopySpec 實例。"""
        from src.singer_agent.models import CopySpec
        state = self._make_project_state(sample_project_state_data)
        assert isinstance(state.copy_spec, CopySpec)

    def test_copy_spec_can_be_none(self, sample_project_state_data):
        """copy_spec 允許為 None。"""
        from src.singer_agent.models import ProjectState
        data = {**sample_project_state_data, "copy_spec": None}
        state = ProjectState.from_dict(data)
        assert state.copy_spec is None

    def test_precheck_result_is_precheck_result_instance(self, sample_project_state_data):
        """precheck_result 欄位應還原為 PrecheckResult 實例。"""
        from src.singer_agent.models import PrecheckResult
        state = self._make_project_state(sample_project_state_data)
        assert isinstance(state.precheck_result, PrecheckResult)

    def test_precheck_result_can_be_none(self, sample_project_state_data):
        """precheck_result 允許為 None。"""
        from src.singer_agent.models import ProjectState
        data = {**sample_project_state_data, "precheck_result": None}
        state = ProjectState.from_dict(data)
        assert state.precheck_result is None

    def test_metadata_is_dict(self, sample_project_state_data):
        """metadata 欄位必須為 dict 型別。"""
        state = self._make_project_state(sample_project_state_data)
        assert isinstance(state.metadata, dict)

    def test_to_dict_contains_all_fields(self, sample_project_state_data):
        """to_dict() 結果必須包含所有頂層欄位。"""
        state = self._make_project_state(sample_project_state_data)
        result = state.to_dict()
        expected_keys = [
            "project_id", "source_audio", "status", "metadata",
            "song_spec", "copy_spec", "background_image", "composite_image",
            "precheck_result", "final_video", "render_mode", "error_message",
            "created_at", "completed_at",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_to_dict_returns_dict(self, sample_project_state_data):
        """to_dict() 必須回傳 dict 型別。"""
        state = self._make_project_state(sample_project_state_data)
        assert isinstance(state.to_dict(), dict)

    def test_to_dict_song_spec_is_dict(self, sample_project_state_data):
        """to_dict() 中的 song_spec 應序列化為 dict。"""
        state = self._make_project_state(sample_project_state_data)
        result = state.to_dict()
        assert isinstance(result["song_spec"], dict)

    def test_to_dict_copy_spec_is_dict(self, sample_project_state_data):
        """to_dict() 中的 copy_spec 應序列化為 dict。"""
        state = self._make_project_state(sample_project_state_data)
        result = state.to_dict()
        assert isinstance(result["copy_spec"], dict)

    def test_to_dict_precheck_result_is_dict(self, sample_project_state_data):
        """to_dict() 中的 precheck_result 應序列化為 dict。"""
        state = self._make_project_state(sample_project_state_data)
        result = state.to_dict()
        assert isinstance(result["precheck_result"], dict)

    def test_to_dict_none_fields_preserved(self, sample_project_state_data):
        """to_dict() 中的 None 欄位應保留為 None（不移除）。"""
        from src.singer_agent.models import ProjectState
        data = {**sample_project_state_data, "song_spec": None, "copy_spec": None}
        state = ProjectState.from_dict(data)
        result = state.to_dict()
        assert result["song_spec"] is None
        assert result["copy_spec"] is None

    def test_roundtrip_to_dict_from_dict(self, sample_project_state_data):
        """to_dict() → from_dict() 往返後資料應完全一致。"""
        from src.singer_agent.models import ProjectState
        original = ProjectState.from_dict(sample_project_state_data)
        serialized = original.to_dict()
        restored = ProjectState.from_dict(serialized)

        assert restored.project_id == original.project_id
        assert restored.status == original.status
        assert restored.source_audio == original.source_audio
        assert restored.render_mode == original.render_mode
        assert restored.error_message == original.error_message
        assert restored.created_at == original.created_at
        assert restored.completed_at == original.completed_at

    def test_roundtrip_nested_song_spec(self, sample_project_state_data):
        """往返後 song_spec 中的巢狀 SongResearch 資料應完全一致。"""
        from src.singer_agent.models import ProjectState
        original = ProjectState.from_dict(sample_project_state_data)
        serialized = original.to_dict()
        restored = ProjectState.from_dict(serialized)

        assert restored.song_spec.research.genre == original.song_spec.research.genre
        assert restored.song_spec.research.mood == original.song_spec.research.mood
        assert restored.song_spec.research.color_palette == original.song_spec.research.color_palette

    def test_status_values(self, sample_project_state_data):
        """status 欄位可接受 running、completed、failed 三種值。"""
        from src.singer_agent.models import ProjectState
        for status in ["running", "completed", "failed"]:
            data = {**sample_project_state_data, "status": status}
            state = ProjectState.from_dict(data)
            assert state.status == status

    def test_render_mode_values(self, sample_project_state_data):
        """render_mode 欄位可接受 sadtalker 和 ffmpeg_static 兩種值。"""
        from src.singer_agent.models import ProjectState
        for mode in ["sadtalker", "ffmpeg_static"]:
            data = {**sample_project_state_data, "render_mode": mode}
            state = ProjectState.from_dict(data)
            assert state.render_mode == mode


# ─────────────────────────────────────────────────
# PipelineRequest 測試
# ─────────────────────────────────────────────────

class TestPipelineRequest:
    """測試 PipelineRequest dataclass。"""

    def test_create_minimal(self, stub_mp3_path):
        """PipelineRequest 可用最少必要欄位建立。"""
        from src.singer_agent.models import PipelineRequest
        req = PipelineRequest(
            audio_path=stub_mp3_path,
            title="測試歌曲",
            artist="測試歌手",
        )
        assert req.title == "測試歌曲"
        assert req.artist == "測試歌手"

    def test_audio_path_is_path_type(self, stub_mp3_path):
        """audio_path 欄位必須為 Path 型別。"""
        from src.singer_agent.models import PipelineRequest
        req = PipelineRequest(
            audio_path=stub_mp3_path,
            title="test",
            artist="test",
        )
        assert isinstance(req.audio_path, Path)

    def test_audio_path_accepts_path_object(self, stub_mp3_path):
        """audio_path 接受 Path 物件。"""
        from src.singer_agent.models import PipelineRequest
        req = PipelineRequest(
            audio_path=stub_mp3_path,
            title="test",
            artist="test",
        )
        assert req.audio_path == stub_mp3_path

    def test_optional_fields_have_defaults(self, stub_mp3_path):
        """language, genre_hint, mood_hint, notes 有預設空字串。"""
        from src.singer_agent.models import PipelineRequest
        req = PipelineRequest(
            audio_path=stub_mp3_path,
            title="test",
            artist="test",
        )
        assert req.language == ""
        assert req.genre_hint == ""
        assert req.mood_hint == ""
        assert req.notes == ""

    def test_optional_fields_can_be_set(self, stub_mp3_path):
        """可覆寫選填欄位。"""
        from src.singer_agent.models import PipelineRequest
        req = PipelineRequest(
            audio_path=stub_mp3_path,
            title="test",
            artist="test",
            language="zh-TW",
            genre_hint="ballad",
            mood_hint="romantic",
            notes="特殊備註",
        )
        assert req.language == "zh-TW"
        assert req.genre_hint == "ballad"
        assert req.mood_hint == "romantic"
        assert req.notes == "特殊備註"

    def test_missing_required_fields_raises(self):
        """缺少必要欄位 audio_path 應拋出 TypeError。"""
        from src.singer_agent.models import PipelineRequest
        with pytest.raises(TypeError):
            PipelineRequest(title="test", artist="test")  # type: ignore

    def test_audio_path_with_unicode_filename(self, tmp_path):
        """audio_path 支援含中文的路徑（Path 物件）。"""
        from src.singer_agent.models import PipelineRequest
        unicode_path = tmp_path / "愛我的人.mp3"
        unicode_path.write_bytes(b"\x00")
        req = PipelineRequest(
            audio_path=unicode_path,
            title="愛我的人",
            artist="歌手",
        )
        assert req.audio_path == unicode_path
        assert "愛我的人" in str(req.audio_path)
