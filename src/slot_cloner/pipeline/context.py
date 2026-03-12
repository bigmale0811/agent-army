"""Pipeline 上下文 — 各 Phase 間傳遞的不可變資料"""
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from slot_cloner.models.enums import PipelinePhase
from slot_cloner.models.game import GameFingerprint, GameModel
from slot_cloner.models.asset import AssetBundle


class PipelineContext(BaseModel):
    """Pipeline 各 Phase 間傳遞的不可變上下文"""
    model_config = ConfigDict(frozen=True)

    url: str
    game_name: str
    output_dir: Path
    dry_run: bool = False
    fingerprint: GameFingerprint | None = None
    assets: AssetBundle | None = None
    game_model: GameModel | None = None
    checkpoint: PipelinePhase = PipelinePhase.INIT
