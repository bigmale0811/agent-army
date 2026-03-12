"""PipelineContext 測試"""
import pytest
from pathlib import Path
from pydantic import ValidationError
from slot_cloner.pipeline.context import PipelineContext
from slot_cloner.models.enums import PipelinePhase


class TestPipelineContext:
    def test_create(self, tmp_path):
        ctx = PipelineContext(url="https://example.com", game_name="test", output_dir=tmp_path)
        assert ctx.url == "https://example.com"
        assert ctx.checkpoint == PipelinePhase.INIT

    def test_frozen(self, tmp_path):
        ctx = PipelineContext(url="https://example.com", game_name="test", output_dir=tmp_path)
        with pytest.raises(ValidationError):
            ctx.url = "changed"

    def test_model_copy_update(self, tmp_path):
        ctx = PipelineContext(url="https://example.com", game_name="test", output_dir=tmp_path)
        new_ctx = ctx.model_copy(update={"checkpoint": PipelinePhase.RECON})
        assert ctx.checkpoint == PipelinePhase.INIT  # 原始不變
        assert new_ctx.checkpoint == PipelinePhase.RECON  # 新的已更新

    def test_dry_run_default(self, tmp_path):
        ctx = PipelineContext(url="https://example.com", game_name="test", output_dir=tmp_path)
        assert ctx.dry_run is False
