"""CheckpointManager 單元測試"""
import json
import pytest
from pathlib import Path
from slot_cloner.pipeline.checkpoint import CheckpointManager, CHECKPOINT_FILENAME
from slot_cloner.pipeline.context import PipelineContext
from slot_cloner.models.enums import PipelinePhase


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "output"


@pytest.fixture
def checkpoint_mgr(output_dir: Path) -> CheckpointManager:
    return CheckpointManager(output_dir)


@pytest.fixture
def sample_context(output_dir: Path) -> PipelineContext:
    return PipelineContext(
        url="https://example.com/game",
        game_name="test-game",
        output_dir=output_dir,
    )


def test_checkpoint_initially_none(checkpoint_mgr: CheckpointManager):
    """無 checkpoint 時回傳 None"""
    assert checkpoint_mgr.load() is None
    assert not checkpoint_mgr.exists()


def test_save_and_load(checkpoint_mgr: CheckpointManager, sample_context: PipelineContext):
    """存儲後可正確載入"""
    checkpoint_mgr.save(sample_context, PipelinePhase.RECON)
    assert checkpoint_mgr.exists()
    loaded = checkpoint_mgr.load()
    assert loaded == PipelinePhase.RECON


def test_save_updates_phase(checkpoint_mgr: CheckpointManager, sample_context: PipelineContext):
    """後續存儲會覆蓋前一個"""
    checkpoint_mgr.save(sample_context, PipelinePhase.RECON)
    checkpoint_mgr.save(sample_context, PipelinePhase.SCRAPE)
    loaded = checkpoint_mgr.load()
    assert loaded == PipelinePhase.SCRAPE


def test_clear_removes_checkpoint(checkpoint_mgr: CheckpointManager, sample_context: PipelineContext):
    """清除後無 checkpoint"""
    checkpoint_mgr.save(sample_context, PipelinePhase.REVERSE)
    checkpoint_mgr.clear()
    assert not checkpoint_mgr.exists()
    assert checkpoint_mgr.load() is None


def test_get_info(checkpoint_mgr: CheckpointManager, sample_context: PipelineContext):
    """get_info 回傳完整 checkpoint 資料"""
    checkpoint_mgr.save(sample_context, PipelinePhase.REPORT)
    info = checkpoint_mgr.get_info()
    assert info is not None
    assert info["completed_phase"] == "report"
    assert info["game_name"] == "test-game"
    assert info["version"] == 1


def test_corrupted_checkpoint_returns_none(checkpoint_mgr: CheckpointManager, output_dir: Path):
    """損壞的 checkpoint 檔案回傳 None"""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / CHECKPOINT_FILENAME).write_text("not json!", encoding="utf-8")
    assert checkpoint_mgr.load() is None
