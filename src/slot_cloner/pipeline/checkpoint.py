"""Checkpoint 持久化管理器 — 支援 Pipeline 中斷續跑"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from slot_cloner.models.enums import PipelinePhase
from slot_cloner.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)

CHECKPOINT_FILENAME = ".slot_cloner_checkpoint.json"


class CheckpointManager:
    """管理 Pipeline 執行狀態的持久化存儲

    功能：
    - 每完成一個 Phase 自動存檔到 JSON
    - 程序中斷後可從最後完成的 Phase 恢復
    - 儲存完整 PipelineContext（不含大型二進制資料）
    """

    def __init__(self, output_dir: Path) -> None:
        self._checkpoint_path = output_dir / CHECKPOINT_FILENAME
        self._output_dir = output_dir

    @property
    def checkpoint_path(self) -> Path:
        return self._checkpoint_path

    def save(self, context: PipelineContext, phase: PipelinePhase) -> None:
        """存儲 checkpoint

        Args:
            context: 當前上下文
            phase: 剛完成的 Phase
        """
        data = {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "completed_phase": phase.value,
            "url": context.url,
            "game_name": context.game_name,
            "output_dir": str(context.output_dir),
            "has_fingerprint": context.fingerprint is not None,
            "has_assets": context.assets is not None,
            "has_game_model": context.game_model is not None,
        }

        # 序列化 fingerprint（輕量資料）
        if context.fingerprint:
            data["fingerprint"] = context.fingerprint.model_dump(mode="json")

        # game_model 只存摘要（完整資料太大）
        if context.game_model and context.game_model.config:
            data["game_model_name"] = context.game_model.config.name

        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoint_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.info("Checkpoint 已儲存: Phase %s → %s", phase.value, self._checkpoint_path)

    def load(self) -> PipelinePhase | None:
        """讀取上次的 checkpoint

        Returns:
            上次完成的 PipelinePhase，或 None（無 checkpoint）
        """
        if not self._checkpoint_path.exists():
            return None

        try:
            data = json.loads(self._checkpoint_path.read_text(encoding="utf-8"))
            phase_str = data.get("completed_phase", "")
            phase = PipelinePhase(phase_str)
            logger.info("載入 Checkpoint: Phase %s (儲存於 %s)", phase.value, data.get("timestamp", "unknown"))
            return phase
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("Checkpoint 讀取失敗: %s", e)
            return None

    def clear(self) -> None:
        """清除 checkpoint（Pipeline 成功完成時呼叫）"""
        if self._checkpoint_path.exists():
            self._checkpoint_path.unlink()
            logger.info("Checkpoint 已清除")

    def exists(self) -> bool:
        """是否有未完成的 checkpoint"""
        return self._checkpoint_path.exists()

    def get_info(self) -> dict | None:
        """取得 checkpoint 的完整資訊（用於顯示狀態）"""
        if not self._checkpoint_path.exists():
            return None
        try:
            return json.loads(self._checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return None
