# -*- coding: utf-8 -*-
"""Pipeline 執行引擎模組 — 驅動 Agent 的步驟執行流程。

PipelineEngine 負責：
1. 按順序執行 AgentDef 中的每個步驟
2. 管理步驟間的輸出 context
3. 透過 ProgressCallback 回報進度
4. 彙整執行結果為 PipelineResult
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from agentforge.core.failure import FailureHandler, RepairLevel
from agentforge.core.task_tracker import TaskTracker
from agentforge.llm.router import LLMRouter
from agentforge.schema import AgentDef, StepDef
from agentforge.steps.base import BaseStep, StepOutput
from agentforge.steps.llm_step import LLMStep
from agentforge.steps.save_step import SaveStep
from agentforge.steps.shell_step import ShellStep
from agentforge.utils.template import TemplateEngine


@runtime_checkable
class ProgressCallback(Protocol):
    """進度回報協定介面。

    PipelineEngine 在執行過程中呼叫這些方法，
    實作類別可用於顯示進度條、寫入日誌等。
    """

    def on_step_start(
        self,
        step_index: int,
        total_steps: int,
        step_name: str,
    ) -> None:
        """步驟開始前呼叫。

        Args:
            step_index: 目前步驟索引（從 0 起算）。
            total_steps: 總步驟數。
            step_name: 步驟名稱。
        """
        ...

    def on_step_complete(
        self,
        step_index: int,
        step_name: str,
        output: StepOutput,
        elapsed_seconds: float,
    ) -> None:
        """步驟完成後呼叫。

        Args:
            step_index: 完成的步驟索引。
            step_name: 步驟名稱。
            output: 步驟執行結果。
            elapsed_seconds: 步驟耗時（秒）。
        """
        ...

    def on_pipeline_complete(self, result: "PipelineResult") -> None:
        """整個 Pipeline 完成後呼叫。

        Args:
            result: 完整的 Pipeline 執行結果。
        """
        ...


@dataclass(frozen=True)
class StepResult:
    """單一步驟的執行結果（不可變）。

    Attributes:
        step_name: 步驟名稱。
        output: 步驟輸出。
        elapsed_seconds: 執行耗時（秒）。
    """

    step_name: str
    output: StepOutput
    elapsed_seconds: float


@dataclass(frozen=True)
class PipelineResult:
    """整個 Pipeline 的執行結果（不可變）。

    Attributes:
        agent_name: Agent 名稱。
        success: 是否所有步驟皆成功執行。
        steps: 所有步驟的執行結果（有序 tuple）。
        total_cost_usd: 所有步驟的 API 費用總計（美元）。
        total_seconds: Pipeline 總耗時（秒）。
    """

    agent_name: str
    success: bool
    steps: tuple[StepResult, ...]
    total_cost_usd: float
    total_seconds: float


class PipelineEngine:
    """Agent Pipeline 執行引擎。

    按照 AgentDef 中定義的步驟順序依序執行，
    並管理步驟間的輸出 context（讓後續步驟可引用前面步驟的輸出）。
    """

    def __init__(
        self,
        router: LLMRouter,
        callback: ProgressCallback | None = None,
        tracker: TaskTracker | None = None,
    ) -> None:
        """初始化 Pipeline 執行引擎。

        Args:
            router: LLM 路由器，用於 llm 步驟。
            callback: 進度回報回呼（可選）。
            tracker: 執行記錄追蹤器（可選）。
        """
        self._router = router
        self._callback = callback
        self._tracker = tracker
        self._template_engine = TemplateEngine()

    def execute(
        self,
        agent_def: AgentDef,
        *,
        dry_run: bool = False,
    ) -> PipelineResult:
        """執行 Agent 定義中的所有步驟（含三級自動修復）。

        Args:
            agent_def: 要執行的 Agent 定義。
            dry_run: 若為 True，所有步驟使用 dry_run 模式執行。

        Returns:
            PipelineResult 包含所有步驟結果與彙整資訊。
        """
        # 初始化追蹤
        run_id = self._tracker.start_run(agent_def.name) if self._tracker else None
        failure_handler = FailureHandler(max_retries=agent_def.max_retries)

        context: dict[str, Any] = {"steps": {}}
        results: list[StepResult] = []
        pipeline_start = time.monotonic()
        pipeline_success = True
        total_steps = len(agent_def.steps)

        for idx, step_def in enumerate(agent_def.steps):
            step = self._create_step(
                step_def,
                agent_def.model or "ollama/qwen3:14b",
            )

            # 通知步驟開始
            if self._callback is not None:
                self._callback.on_step_start(idx, total_steps, step_def.name)

            # 執行步驟（含失敗重試邏輯）
            output, elapsed = self._execute_step_with_retry(
                step, step_def, context, dry_run, failure_handler,
            )

            # 更新 context 供後續步驟引用
            context["steps"][step_def.name] = {
                "output": output.output,
                "error": output.error,
            }

            step_result = StepResult(
                step_name=step_def.name,
                output=output,
                elapsed_seconds=elapsed,
            )
            results.append(step_result)

            # 記錄到 TaskTracker
            if self._tracker and run_id:
                self._tracker.record_step(
                    run_id, step_def.name, step_def.action,
                    output.success, output.output, output.error,
                    output.cost_usd, output.tokens, elapsed,
                )

            # 通知步驟完成
            if self._callback is not None:
                self._callback.on_step_complete(
                    idx, step_def.name, output, elapsed,
                )

            # 步驟最終失敗時中止
            if not output.success:
                pipeline_success = False
                break

        total_seconds = time.monotonic() - pipeline_start
        total_cost = sum(r.output.cost_usd for r in results)

        pipeline_result = PipelineResult(
            agent_name=agent_def.name,
            success=pipeline_success,
            steps=tuple(results),
            total_cost_usd=total_cost,
            total_seconds=total_seconds,
        )

        # 記錄 Pipeline 完成
        if self._tracker and run_id:
            self._tracker.finish_run(
                run_id, pipeline_success, total_cost, total_seconds,
            )

        if self._callback is not None:
            self._callback.on_pipeline_complete(pipeline_result)

        return pipeline_result

    def _execute_step_with_retry(
        self,
        step: BaseStep,
        step_def: StepDef,
        context: dict[str, Any],
        dry_run: bool,
        failure_handler: FailureHandler,
    ) -> tuple[StepOutput, float]:
        """執行步驟，失敗時觸發三級修復。

        Returns:
            (最終的 StepOutput, 總耗時秒數)
        """
        if dry_run:
            start = time.monotonic()
            output = step.dry_run(context)
            return output, time.monotonic() - start

        retry_count = 0
        total_elapsed = 0.0
        # 硬性上限：防止任何邏輯錯誤導致無限迴圈
        max_attempts = failure_handler.max_retries + 1

        for _ in range(max_attempts):
            start = time.monotonic()
            output = step.execute(context)
            elapsed = time.monotonic() - start
            total_elapsed += elapsed

            if output.success:
                return output, total_elapsed

            retry_count += 1
            record = failure_handler.record_failure(
                step_def.name, output.error, retry_count,
            )

            if record.repair_level == RepairLevel.HALT:
                return output, total_elapsed

            if record.repair_level == RepairLevel.RETRY_WITH_FIX:
                context["_fix_prompt"] = record.fix_prompt
                continue

            # 第 2 級：REPLAN — MVP 降級為再試一次
            continue

        # 安全保底：迴圈耗盡仍失敗
        return output, total_elapsed

    def _create_step(
        self,
        step_def: StepDef,
        default_model: str,
    ) -> BaseStep:
        """根據步驟定義建立對應的步驟物件（工廠方法）。

        Args:
            step_def: 步驟定義。
            default_model: Agent 級別的預設模型。

        Returns:
            對應的 BaseStep 子類別實例。

        Raises:
            ValueError: 未知的 action 類型。
        """
        action = step_def.action

        if action == "shell":
            return ShellStep(step_def, self._template_engine)
        elif action == "llm":
            return LLMStep(
                step_def,
                self._template_engine,
                self._router,
                default_model,
            )
        elif action == "save":
            return SaveStep(step_def, self._template_engine)
        else:
            raise ValueError(
                f"未知的步驟 action：'{action}'。"
                f"支援的 action：shell、llm、save。"
            )
