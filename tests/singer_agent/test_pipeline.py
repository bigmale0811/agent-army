# -*- coding: utf-8 -*-
"""
DEV-12: pipeline.py 測試。

測試覆蓋：
- Pipeline 初始化
- dry_run 完整 8 步走完
- progress_callback 被正確呼叫
- 步驟失敗時 status=failed 不閃退
- 各步驟正確串接
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import datetime

import pytest

from src.singer_agent.models import (
    PipelineRequest, ProjectState, SongResearch, SongSpec,
    CopySpec, PrecheckResult,
)


def _make_request(tmp_path: Path) -> PipelineRequest:
    """建立測試用 PipelineRequest。"""
    audio = tmp_path / "test.mp3"
    audio.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    return PipelineRequest(
        audio_path=audio,
        title="測試歌曲",
        artist="測試歌手",
        language="zh-TW",
    )


def _make_song_research() -> SongResearch:
    return SongResearch(
        genre="pop", mood="happy",
        visual_style="Modern", color_palette=["blue"],
        background_prompt="blue sky", outfit_prompt="casual",
        scene_description="現代風格", research_summary="流行樂",
    )


def _make_song_spec() -> SongSpec:
    return SongSpec(
        title="測試歌曲", artist="測試歌手", language="zh-TW",
        research=_make_song_research(),
        created_at=datetime.now().isoformat(),
    )


class TestPipelineInit:
    def test_can_create_pipeline(self, tmp_path):
        """可建立 Pipeline 實例。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img)
        assert p is not None

    def test_dry_run_flag_stored(self, tmp_path):
        """dry_run 參數被儲存。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (10, 10), (0, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=True)
        assert p.dry_run is True

    def test_progress_callback_stored(self, tmp_path):
        """progress_callback 參數被儲存。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (10, 10), (0, 0, 0)).save(char_img)
        cb = MagicMock()
        p = Pipeline(character_image=char_img, progress_callback=cb)
        assert p.progress_callback is cb


class TestPipelineDryRun:
    def test_dry_run_returns_project_state(self, tmp_path):
        """dry_run 回傳 ProjectState。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=True)
        req = _make_request(tmp_path)
        result = p.run(req)
        assert isinstance(result, ProjectState)

    def test_dry_run_status_is_completed(self, tmp_path):
        """dry_run 完成後 status=completed。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=True)
        req = _make_request(tmp_path)
        result = p.run(req)
        assert result.status == "completed"

    def test_dry_run_has_song_spec(self, tmp_path):
        """dry_run 完成後有 song_spec。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=True)
        req = _make_request(tmp_path)
        result = p.run(req)
        assert result.song_spec is not None

    def test_dry_run_has_copy_spec(self, tmp_path):
        """dry_run 完成後有 copy_spec。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=True)
        req = _make_request(tmp_path)
        result = p.run(req)
        assert result.copy_spec is not None

    def test_dry_run_has_precheck_result(self, tmp_path):
        """dry_run 完成後有 precheck_result。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=True)
        req = _make_request(tmp_path)
        result = p.run(req)
        assert result.precheck_result is not None
        assert result.precheck_result.passed is True


class TestPipelineProgressCallback:
    def test_callback_called_for_each_step(self, tmp_path):
        """progress_callback 在每步被呼叫。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        cb = MagicMock()
        p = Pipeline(character_image=char_img, dry_run=True,
                     progress_callback=cb)
        req = _make_request(tmp_path)
        p.run(req)
        # 至少呼叫 8 次（8 個步驟）
        assert cb.call_count >= 8

    def test_callback_receives_step_number(self, tmp_path):
        """callback 第一個參數是步驟編號。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        cb = MagicMock()
        p = Pipeline(character_image=char_img, dry_run=True,
                     progress_callback=cb)
        req = _make_request(tmp_path)
        p.run(req)
        first_call_step = cb.call_args_list[0][0][0]
        assert isinstance(first_call_step, int)
        assert first_call_step == 1


class TestPipelineErrorHandling:
    def test_step_failure_sets_status_failed(self, tmp_path):
        """步驟失敗時 status=failed，不閃退。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=False)
        req = _make_request(tmp_path)

        # Mock researcher 拋出例外
        with patch("src.singer_agent.pipeline.SongResearcher") as MockRes:
            MockRes.return_value.research.side_effect = RuntimeError("LLM 離線")
            result = p.run(req)

        assert result.status == "failed"
        assert "LLM 離線" in result.error_message

    def test_step_failure_does_not_raise(self, tmp_path):
        """步驟失敗不拋出例外到呼叫方。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=False)
        req = _make_request(tmp_path)

        with patch("src.singer_agent.pipeline.SongResearcher") as MockRes:
            MockRes.return_value.research.side_effect = RuntimeError("boom")
            # 不應拋出
            result = p.run(req)
        assert result is not None

    def test_project_id_is_generated(self, tmp_path):
        """每次執行會產生 project_id。"""
        from src.singer_agent.pipeline import Pipeline
        char_img = tmp_path / "avatar.png"
        from PIL import Image as _Img; _Img.new("RGBA", (200, 300), (255, 0, 0)).save(char_img)
        p = Pipeline(character_image=char_img, dry_run=True)
        req = _make_request(tmp_path)
        result = p.run(req)
        assert result.project_id != ""
        assert len(result.project_id) > 0
