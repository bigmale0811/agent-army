"""Shell 步驟模組 — 執行系統命令並回傳結果。

ShellStep 對應 YAML 中 action: shell 的步驟，
使用 subprocess 執行命令，並支援模板替換。

安全備註：使用 shell=True 是有意設計，因為 Agent YAML 由開發者撰寫（非終端使用者），
且需要支援 shell 語法（管道、重導向等）。模板替換的輸入來自前步驟的輸出。
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from agentforge.schema import StepDef
from agentforge.steps.base import BaseStep, StepOutput
from agentforge.utils.template import TemplateEngine

logger = logging.getLogger(__name__)

# 命令執行逾時時間（秒）
_TIMEOUT_SECONDS = 300


class ShellStep(BaseStep):
    """執行 Shell 命令的步驟。

    支援在 command 欄位中使用 {{ steps.<name>.output }} 模板語法，
    引用先前步驟的輸出結果。
    """

    def __init__(
        self,
        step_def: StepDef,
        template_engine: TemplateEngine,
    ) -> None:
        """初始化 Shell 步驟。

        Args:
            step_def: 步驟定義，需包含 command 欄位。
            template_engine: 模板引擎。
        """
        super().__init__(step_def, template_engine)

    def _render_command(self, context: dict[str, Any]) -> str:
        """渲染命令模板。

        Args:
            context: 執行環境。

        Returns:
            渲染後的命令字串。

        Raises:
            KeyError: 模板引用了不存在的步驟輸出。
        """
        command = self._step_def.command or ""
        return self._template_engine.render(command, context)

    def execute(self, context: dict[str, Any]) -> StepOutput:
        """執行 Shell 命令。

        Args:
            context: 執行環境，包含前面步驟的輸出。

        Returns:
            StepOutput，success 依回傳碼決定。
        """
        try:
            rendered_command = self._render_command(context)
        except KeyError as exc:
            logger.error("Shell 步驟 '%s' 模板渲染失敗：%s", self._step_def.name, exc)
            return StepOutput(
                success=False, error=f"模板變數不存在：{exc}",
            )

        try:
            # 使用 shell=True：Agent YAML 由開發者撰寫，需支援管道/重導向等語法
            result = subprocess.run(
                rendered_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
            )
            return StepOutput(
                success=(result.returncode == 0),
                output=result.stdout,
                error=result.stderr,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Shell 步驟 '%s' 逾時：%s", self._step_def.name, rendered_command)
            return StepOutput(
                success=False, output="",
                error=f"命令執行逾時（超過 {_TIMEOUT_SECONDS} 秒）：{rendered_command}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Shell 步驟 '%s' 執行異常", self._step_def.name)
            return StepOutput(
                success=False, output="",
                error=f"命令執行失敗：{exc}",
            )

    def dry_run(self, context: dict[str, Any]) -> StepOutput:
        """模擬執行 Shell 命令（不實際執行）。"""
        try:
            rendered_command = self._render_command(context)
        except KeyError as exc:
            return StepOutput(success=False, error=f"模板變數不存在：{exc}")
        return StepOutput(
            success=True,
            output=f"[DRY-RUN][SHELL] Would execute: {rendered_command}",
        )
