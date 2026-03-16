# -*- coding: utf-8 -*-
"""三級自動修復模組 — 失敗時自動重試、重新規劃或停機。

修復等級：
- Level 1 (RETRY_WITH_FIX)：注入修復 prompt → 重跑該步驟
- Level 2 (REPLAN_PIPELINE)：LLM 重新規劃 → 全部重跑
- Level 3 (HALT)：停機 → 通知使用者
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RepairLevel(Enum):
    """修復等級枚舉。"""

    RETRY_WITH_FIX = "retry_with_fix"
    REPLAN_PIPELINE = "replan_pipeline"
    HALT = "halt"


@dataclass(frozen=True)
class FailureRecord:
    """單次失敗記錄（不可變）。

    Attributes:
        step_name: 失敗的步驟名稱。
        error: 錯誤訊息。
        retry_count: 第幾次重試。
        repair_level: 觸發的修復等級。
        fix_prompt: 修復 prompt（若適用）。
    """

    step_name: str
    error: str
    retry_count: int
    repair_level: RepairLevel
    fix_prompt: str = ""


class FailureHandler:
    """三級自動修復處理器。

    根據重試次數決定修復策略：
    - 第 1 次失敗 → RETRY_WITH_FIX（注入修復提示重跑）
    - 第 2 次失敗 → REPLAN_PIPELINE（重新規劃流程）
    - 第 3 次以上 → HALT（停機通知）
    """

    def __init__(self, max_retries: int = 3) -> None:
        """初始化修復處理器。

        Args:
            max_retries: 最大重試次數（預設 3）。
        """
        self._max_retries = max_retries
        self._failures: list[FailureRecord] = []

    @property
    def failure_count(self) -> int:
        """已記錄的失敗次數。"""
        return len(self._failures)

    @property
    def failures(self) -> tuple[FailureRecord, ...]:
        """所有失敗記錄（不可變 tuple）。"""
        return tuple(self._failures)

    @property
    def max_retries(self) -> int:
        """最大重試次數。"""
        return self._max_retries

    def get_repair_level(self, retry_count: int) -> RepairLevel:
        """根據重試次數與 max_retries 決定修復等級。

        修復策略依 max_retries 動態調整：
        - retry < max_retries - 1 → RETRY_WITH_FIX
        - retry == max_retries - 1 → REPLAN_PIPELINE
        - retry >= max_retries → HALT

        Args:
            retry_count: 目前是第幾次重試（從 1 開始）。

        Returns:
            對應的修復等級。
        """
        if retry_count < self._max_retries - 1:
            return RepairLevel.RETRY_WITH_FIX
        elif retry_count < self._max_retries:
            return RepairLevel.REPLAN_PIPELINE
        else:
            return RepairLevel.HALT

    def record_failure(
        self,
        step_name: str,
        error: str,
        retry_count: int,
    ) -> FailureRecord:
        """記錄一次失敗並回傳修復策略。

        Args:
            step_name: 失敗的步驟名稱。
            error: 錯誤訊息。
            retry_count: 目前是第幾次重試。

        Returns:
            包含修復等級和修復 prompt 的 FailureRecord。
        """
        level = self.get_repair_level(retry_count)
        fix_prompt = self.build_fix_prompt(step_name, error) if level == RepairLevel.RETRY_WITH_FIX else ""

        record = FailureRecord(
            step_name=step_name,
            error=error,
            retry_count=retry_count,
            repair_level=level,
            fix_prompt=fix_prompt,
        )
        self._failures.append(record)
        return record

    def build_fix_prompt(
        self,
        step_name: str,
        error: str,
    ) -> str:
        """建立修復 prompt（Level 1 專用）。

        Args:
            step_name: 失敗的步驟名稱。
            error: 錯誤訊息。

        Returns:
            注入到重試步驟的修復提示。
        """
        prev_errors = "\n".join(
            f"  - [{f.step_name}] {f.error}" for f in self._failures
        )
        return (
            f"[AUTO-REPAIR] 步驟 '{step_name}' 執行失敗。\n"
            f"錯誤訊息：{error}\n"
            f"歷史錯誤：\n{prev_errors}\n"
            f"請修正上述問題後重新執行。"
        )

    def should_halt(self) -> bool:
        """判斷是否應該停機。"""
        return self.failure_count >= self._max_retries

    def generate_report(self) -> str:
        """產出完整的錯誤報告。

        Returns:
            Markdown 格式的錯誤報告。
        """
        if not self._failures:
            return "## 錯誤報告\n\n無失敗記錄。"

        lines = ["## 錯誤報告", "", f"**總失敗次數**：{self.failure_count}", ""]
        for i, f in enumerate(self._failures, 1):
            lines.append(f"### 第 {i} 次失敗")
            lines.append(f"- **步驟**：{f.step_name}")
            lines.append(f"- **錯誤**：{f.error}")
            lines.append(f"- **修復等級**：{f.repair_level.value}")
            if f.fix_prompt:
                lines.append(f"- **修復 prompt**：{f.fix_prompt[:100]}...")
            lines.append("")

        return "\n".join(lines)

    def reset(self) -> None:
        """重置所有失敗記錄。"""
        self._failures.clear()
