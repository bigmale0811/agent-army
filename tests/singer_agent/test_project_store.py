# -*- coding: utf-8 -*-
"""
DEV-5: project_store.py 測試。

使用 tmp_path 隔離所有檔案操作，不污染真實資料目錄。
測試覆蓋：
- save() 建立 JSON 檔案，結構正確
- load() 還原 ProjectState，資料一致
- 中文 title 正確序列化（ensure_ascii=False）
- list_projects() 按 created_at 降冪排序
- load() 找不到 ID 時拋出清楚例外
"""
import json
from pathlib import Path

import pytest

from src.singer_agent.models import (
    CopySpec,
    PrecheckResult,
    ProjectState,
    SongResearch,
    SongSpec,
)


# ─────────────────────────────────────────────────
# 共用工廠函式（建立測試用 ProjectState）
# ─────────────────────────────────────────────────

def _make_project_state(
    project_id: str = "proj-001",
    title: str = "月亮代表我的心",
    status: str = "completed",
    created_at: str = "2026-03-06T12:00:00",
    completed_at: str = "2026-03-06T12:30:00",
) -> ProjectState:
    """建立測試用 ProjectState，含完整巢狀物件。"""
    research = SongResearch(
        genre="ballad",
        mood="romantic",
        visual_style="Pastel Watercolor",
        color_palette=["soft_pink", "light_blue"],
        background_prompt="pastel dreamy landscape",
        outfit_prompt="white elegant dress",
        scene_description="溫柔粉彩場景",
        research_summary="懷舊情歌研究摘要",
    )
    song_spec = SongSpec(
        title=title,
        artist="測試歌手",
        language="zh-TW",
        research=research,
        created_at=created_at,
    )
    copy_spec = CopySpec(
        title=f"【MV】{title}",
        description="感人情歌\n\n#MV",
        tags=["MV", "情歌", "AI"],
    )
    precheck = PrecheckResult(
        passed=True,
        checks={"image_exists": True, "audio_exists": True},
        warnings=[],
        gemini_score=85,
        gemini_feedback="搭配良好",
    )
    return ProjectState(
        project_id=project_id,
        source_audio=f"data/singer_agent/inbox/{project_id}.mp3",
        status=status,
        metadata={"duration": 180},
        song_spec=song_spec,
        copy_spec=copy_spec,
        background_image=f"data/singer_agent/backgrounds/{project_id}.png",
        composite_image=f"data/singer_agent/composites/{project_id}.png",
        precheck_result=precheck,
        final_video=f"data/singer_agent/videos/{project_id}.mp4",
        render_mode="sadtalker",
        error_message="",
        created_at=created_at,
        completed_at=completed_at,
    )


# ─────────────────────────────────────────────────
# ProjectStore 初始化測試
# ─────────────────────────────────────────────────

class TestProjectStoreInit:
    """測試 ProjectStore 建構子。"""

    def test_default_uses_config_projects_dir(self):
        """預設使用 config.PROJECTS_DIR 作為儲存目錄。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore()

        assert store.projects_dir is not None
        assert isinstance(store.projects_dir, Path)

    def test_custom_directory_is_stored(self, tmp_path):
        """自訂目錄正確儲存。"""
        from src.singer_agent.project_store import ProjectStore

        custom_dir = tmp_path / "custom_projects"
        store = ProjectStore(projects_dir=custom_dir)

        assert store.projects_dir == custom_dir


# ─────────────────────────────────────────────────
# save() 測試
# ─────────────────────────────────────────────────

class TestProjectStoreSave:
    """測試 save()：序列化 ProjectState 為 JSON 檔案。"""

    def test_save_creates_json_file(self, tmp_path):
        """save() 在指定目錄建立 JSON 檔案。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        state = _make_project_state(project_id="proj-001")

        result_path = store.save(state)

        assert result_path.exists()
        assert result_path.suffix == ".json"

    def test_save_returns_path(self, tmp_path):
        """save() 回傳 Path 物件。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        state = _make_project_state()

        result = store.save(state)

        assert isinstance(result, Path)

    def test_save_filename_contains_project_id(self, tmp_path):
        """JSON 檔名包含 project_id。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        state = _make_project_state(project_id="my-unique-proj-123")

        result_path = store.save(state)

        assert "my-unique-proj-123" in result_path.name

    def test_save_json_is_valid(self, tmp_path):
        """儲存的檔案是合法 JSON。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        state = _make_project_state()

        result_path = store.save(state)

        content = result_path.read_text(encoding="utf-8")
        data = json.loads(content)  # 若不合法 JSON 會拋例外
        assert isinstance(data, dict)

    def test_save_preserves_chinese_characters(self, tmp_path):
        """中文 title 在 JSON 中保持中文（ensure_ascii=False）。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        state = _make_project_state(title="月亮代表我的心")

        result_path = store.save(state)

        raw_content = result_path.read_text(encoding="utf-8")
        # 確認中文直接寫入，而非 \\uXXXX 跳脫
        assert "月亮代表我的心" in raw_content

    def test_save_creates_parent_dir_if_missing(self, tmp_path):
        """目標目錄不存在時自動建立。"""
        from src.singer_agent.project_store import ProjectStore

        projects_dir = tmp_path / "deep" / "nested" / "projects"
        assert not projects_dir.exists()

        store = ProjectStore(projects_dir=projects_dir)
        state = _make_project_state()

        result_path = store.save(state)

        assert result_path.exists()


# ─────────────────────────────────────────────────
# load() 測試
# ─────────────────────────────────────────────────

class TestProjectStoreLoad:
    """測試 load()：從 JSON 還原 ProjectState。"""

    def test_load_restores_project_id(self, tmp_path):
        """load() 還原後 project_id 一致。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        original = _make_project_state(project_id="test-restore-001")
        store.save(original)

        restored = store.load("test-restore-001")

        assert restored.project_id == "test-restore-001"

    def test_load_restores_status(self, tmp_path):
        """load() 還原後 status 一致。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        original = _make_project_state(status="failed")
        store.save(original)

        restored = store.load(original.project_id)

        assert restored.status == "failed"

    def test_load_restores_chinese_title(self, tmp_path):
        """load() 還原後中文 title 一致。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        original = _make_project_state(title="月亮代表我的心")
        store.save(original)

        restored = store.load(original.project_id)

        assert restored.song_spec is not None
        assert restored.song_spec.title == "月亮代表我的心"

    def test_load_returns_project_state_instance(self, tmp_path):
        """load() 回傳 ProjectState 實例。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        original = _make_project_state()
        store.save(original)

        restored = store.load(original.project_id)

        assert isinstance(restored, ProjectState)

    def test_load_raises_on_nonexistent_id(self, tmp_path):
        """load() 找不到 ID 時拋出清楚例外（非 KeyError 或 AttributeError）。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)

        with pytest.raises((FileNotFoundError, ValueError, KeyError)):
            store.load("nonexistent-project-id-9999")

    def test_load_error_message_is_informative(self, tmp_path):
        """load() 例外訊息包含 project_id。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        missing_id = "missing-proj-xyz"

        try:
            store.load(missing_id)
            pytest.fail("Should have raised an exception")
        except (FileNotFoundError, ValueError, KeyError) as e:
            assert missing_id in str(e)

    def test_save_and_load_full_roundtrip(self, tmp_path):
        """save → load 完整往返，所有欄位一致。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        original = _make_project_state(
            project_id="roundtrip-001",
            title="夜空中最亮的星",
        )
        store.save(original)

        restored = store.load("roundtrip-001")

        assert restored.project_id == original.project_id
        assert restored.status == original.status
        assert restored.render_mode == original.render_mode
        assert restored.song_spec.title == original.song_spec.title
        assert restored.copy_spec.title == original.copy_spec.title
        assert restored.precheck_result.passed == original.precheck_result.passed


# ─────────────────────────────────────────────────
# list_projects() 測試
# ─────────────────────────────────────────────────

class TestProjectStoreListProjects:
    """測試 list_projects()：回傳所有專案，按建立時間降冪排序。"""

    def test_empty_directory_returns_empty_list(self, tmp_path):
        """空目錄回傳空 list。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)

        result = store.list_projects()

        assert result == []

    def test_returns_list_of_project_states(self, tmp_path):
        """回傳值是 list[ProjectState]。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        store.save(_make_project_state(project_id="a"))

        result = store.list_projects()

        assert isinstance(result, list)
        assert all(isinstance(p, ProjectState) for p in result)

    def test_returns_all_saved_projects(self, tmp_path):
        """回傳所有已儲存的專案。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        for i in range(3):
            store.save(_make_project_state(project_id=f"proj-{i:03d}"))

        result = store.list_projects()

        assert len(result) == 3

    def test_sorted_by_created_at_descending(self, tmp_path):
        """回傳列表按 created_at 降冪排序（最新在前）。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)

        # 儲存三個不同時間的專案（時間順序：oldest → middle → newest）
        store.save(_make_project_state(
            project_id="oldest",
            created_at="2026-01-01T00:00:00",
        ))
        store.save(_make_project_state(
            project_id="newest",
            created_at="2026-03-06T00:00:00",
        ))
        store.save(_make_project_state(
            project_id="middle",
            created_at="2026-02-15T00:00:00",
        ))

        result = store.list_projects()

        assert result[0].project_id == "newest"
        assert result[1].project_id == "middle"
        assert result[2].project_id == "oldest"

    def test_list_includes_project_with_chinese_title(self, tmp_path):
        """list_projects() 正確載入含中文 title 的專案。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)
        store.save(_make_project_state(title="月亮代表我的心"))

        result = store.list_projects()

        assert len(result) == 1
        assert result[0].song_spec.title == "月亮代表我的心"

    def test_non_json_files_are_ignored(self, tmp_path):
        """目錄中的非 JSON 檔案被忽略，不造成崩潰。"""
        from src.singer_agent.project_store import ProjectStore

        store = ProjectStore(projects_dir=tmp_path)

        # 建立一個非 JSON 檔案
        (tmp_path / "readme.txt").write_text("not a project")
        (tmp_path / "temp.log").write_text("log data")

        # 儲存一個正常專案
        store.save(_make_project_state(project_id="real-proj"))

        result = store.list_projects()

        assert len(result) == 1
        assert result[0].project_id == "real-proj"
