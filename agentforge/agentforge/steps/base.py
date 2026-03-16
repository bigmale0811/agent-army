# -*- coding: utf-8 -*-
"""步驟基底模組 — 定義 StepOutput 資料類別與 BaseStep 抽象類別。

所有步驟類型（ShellStep / LLMStep / SaveStep）皆繼承自 BaseStep，
並必須實作 execute() 與 dry_run() 方法。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentforge.schema import StepDef
    from agentforge.utils.template import TemplateEngine


@dataclass(frozen=True)
class StepOutput:
    """單一步驟的執行結果（不可變）。

    Attributes:
        success: 執行是否成功。
        output: 標準輸出或模型回應內容。
        error: 錯誤訊息（失敗時有值）。
        cost_usd: 本次執行花費的 API 費用（美元），shell/save 步驟為 0。
        tokens: 本次執行消耗的 token 總數，shell/save 步驟為 0。
    """

    success: bool
    output: str = ""
    error: str = ""
    cost_usd: float = 0.0
    tokens: int = 0


class BaseStep(ABC):
    """所有步驟類型的抽象基底類別。

    子類別需實作：
    - execute(context): 真實執行步驟
    - dry_run(context): 模擬執行，不產生實際副作用
    """

    def __init__(
        self,
        step_def: "StepDef",
        template_engine: "TemplateEngine",
    ) -> None:
        """初始化步驟。

        Args:
            step_def: 步驟定義（來自 YAML）。
            template_engine: 模板引擎，用於渲染含佔位符的欄位。
        """
        self._step_def = step_def
        self._template_engine = template_engine

    @property
    def name(self) -> str:
        """步驟名稱。"""
        return self._step_def.name

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> StepOutput:
        """真實執行步驟。

        Args:
            context: 執行環境，包含前面步驟的輸出。

        Returns:
            StepOutput 執行結果。
        """
        ...

    @abstractmethod
    def dry_run(self, context: dict[str, Any]) -> StepOutput:
        """模擬執行步驟（不產生副作用）。

        Args:
            context: 執行環境。

        Returns:
            StepOutput，包含描述性訊息但不實際執行操作。
        """
        ...
