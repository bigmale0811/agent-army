"""Pipeline 協調器 — 依序執行 5 個 Phase 的狀態機，支援持久化 checkpoint"""
from __future__ import annotations
import logging
from typing import Callable, Awaitable
from slot_cloner.models.enums import PipelinePhase
from slot_cloner.pipeline.context import PipelineContext
from slot_cloner.pipeline.checkpoint import CheckpointManager

logger = logging.getLogger(__name__)

# Phase 處理函數的型別：接收 context，回傳新的 context
PhaseHandler = Callable[[PipelineContext], Awaitable[PipelineContext]]

# Phase 執行順序
PHASE_ORDER: tuple[PipelinePhase, ...] = (
    PipelinePhase.RECON,
    PipelinePhase.SCRAPE,
    PipelinePhase.REVERSE,
    PipelinePhase.REPORT,
    PipelinePhase.BUILD,
)


class PipelineOrchestrator:
    """Pipeline 主控 — 狀態機驅動，依序執行各 Phase"""

    def __init__(self, checkpoint_manager: CheckpointManager | None = None) -> None:
        self._handlers: dict[PipelinePhase, PhaseHandler] = {}
        self._checkpoint_mgr = checkpoint_manager

    def register(self, phase: PipelinePhase, handler: PhaseHandler) -> None:
        """註冊 Phase 處理函數"""
        self._handlers[phase] = handler

    async def run(
        self,
        context: PipelineContext,
        phases: tuple[PipelinePhase, ...] | None = None,
    ) -> PipelineContext:
        """
        執行 Pipeline。

        Args:
            context: 初始上下文
            phases: 要執行的 Phase（None 表示全部）

        Returns:
            更新後的上下文（不可變，回傳新物件）
        """
        target_phases = phases or PHASE_ORDER
        current = context

        # 如果啟用持久化 checkpoint 且有 resume 請求，載入上次進度
        if self._checkpoint_mgr and current.checkpoint == PipelinePhase.INIT:
            saved_phase = self._checkpoint_mgr.load()
            if saved_phase and saved_phase != PipelinePhase.INIT:
                logger.info("從持久化 Checkpoint 恢復: %s", saved_phase.value)
                current = current.model_copy(update={"checkpoint": saved_phase})

        for phase in PHASE_ORDER:
            if phase not in target_phases:
                logger.info("跳過 Phase: %s", phase.value)
                continue

            # 檢查是否需要從 checkpoint 恢復（跳過已完成的 Phase）
            if self._should_skip(current.checkpoint, phase):
                logger.info("Checkpoint 跳過已完成: %s", phase.value)
                continue

            handler = self._handlers.get(phase)
            if handler is None:
                logger.warning("Phase %s 無處理函數，跳過", phase.value)
                continue

            logger.info("開始 Phase: %s", phase.value)

            if current.dry_run:
                logger.info("[dry-run] 跳過 Phase: %s", phase.value)
                current = current.model_copy(
                    update={"checkpoint": phase}
                )
                continue

            # 執行 Phase，取得新的 context
            current = await handler(current)
            # 更新 checkpoint
            current = current.model_copy(
                update={"checkpoint": phase}
            )

            # 持久化 checkpoint 到磁碟
            if self._checkpoint_mgr:
                self._checkpoint_mgr.save(current, phase)

            logger.info("完成 Phase: %s", phase.value)

        # 標記完成，清除持久化 checkpoint
        current = current.model_copy(
            update={"checkpoint": PipelinePhase.DONE}
        )
        if self._checkpoint_mgr:
            self._checkpoint_mgr.clear()

        return current

    @staticmethod
    def _should_skip(checkpoint: PipelinePhase, current: PipelinePhase) -> bool:
        """判斷是否應跳過（checkpoint 機制）"""
        if checkpoint == PipelinePhase.INIT:
            return False
        phase_list = list(PHASE_ORDER)
        if checkpoint not in phase_list or current not in phase_list:
            return False
        return phase_list.index(current) <= phase_list.index(checkpoint)
