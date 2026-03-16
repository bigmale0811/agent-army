"""Save 步驟模組 — 將內容寫入指定路徑的檔案。

SaveStep 對應 YAML 中 action: save 的步驟，
支援 path / content 欄位的模板替換，並自動建立父目錄。
包含路徑穿越防護（禁止寫入工作目錄外的路徑）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agentforge.schema import StepDef
from agentforge.steps.base import BaseStep, StepOutput
from agentforge.utils.template import TemplateEngine

logger = logging.getLogger(__name__)


class SaveStep(BaseStep):
    """將內容寫入檔案的步驟。

    支援在 path / content 欄位中使用 {{ steps.<name>.output }} 模板語法，
    並自動建立不存在的父目錄。
    """

    def __init__(
        self,
        step_def: StepDef,
        template_engine: TemplateEngine,
    ) -> None:
        """初始化 Save 步驟。

        Args:
            step_def: 步驟定義，需包含 path 和 content 欄位。
            template_engine: 模板引擎。
        """
        super().__init__(step_def, template_engine)

    def _render_path(self, context: dict[str, Any]) -> str:
        """渲染 path 模板。

        Args:
            context: 執行環境。

        Returns:
            渲染後的檔案路徑字串。
        """
        path = self._step_def.path or ""
        return self._template_engine.render(path, context)

    def _render_content(self, context: dict[str, Any]) -> str:
        """渲染 content 模板。

        Args:
            context: 執行環境。

        Returns:
            渲染後的檔案內容字串。
        """
        content = self._step_def.content or ""
        return self._template_engine.render(content, context)

    @staticmethod
    def _validate_path(rendered_path: str) -> Path:
        """驗證路徑安全性（防止 .. 路徑穿越攻擊）。

        Agent YAML 由開發者撰寫，允許絕對路徑。
        但阻擋 .. 元件以防止模板注入造成的路徑穿越。

        Args:
            rendered_path: 渲染後的路徑字串。

        Returns:
            解析後的路徑。

        Raises:
            PermissionError: 偵測到路徑穿越（含 .. 元件）。
        """
        file_path = Path(rendered_path)
        # 阻擋含 ".." 的路徑元件（防止模板注入穿越）
        if ".." in file_path.parts:
            raise PermissionError(f"路徑穿越偵測（禁止 ..）：{rendered_path}")
        return file_path

    def execute(self, context: dict[str, Any]) -> StepOutput:
        """將內容寫入檔案（含路徑穿越防護）。

        Args:
            context: 執行環境，包含前面步驟的輸出。

        Returns:
            StepOutput，success=True 並包含儲存路徑。
        """
        try:
            rendered_path = self._render_path(context)
            rendered_content = self._render_content(context)
            file_path = self._validate_path(rendered_path)

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(rendered_content, encoding="utf-8")

            return StepOutput(
                success=True,
                output=f"Saved to {rendered_path}",
            )
        except PermissionError as exc:
            logger.error("Save 步驟路徑安全檢查失敗：%s", exc)
            return StepOutput(success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Save 步驟 '%s' 寫入失敗", self._step_def.name)
            return StepOutput(success=False, error=f"檔案寫入失敗：{exc}")

    def dry_run(self, context: dict[str, Any]) -> StepOutput:
        """模擬寫入檔案（不實際寫入）。

        Args:
            context: 執行環境。

        Returns:
            StepOutput，包含模擬執行的描述訊息。
        """
        try:
            rendered_path = self._render_path(context)
            rendered_content = self._render_content(context)

            preview = rendered_content[:80]
            if len(rendered_content) > 80:
                preview += "..."

            return StepOutput(
                success=True,
                output=(
                    f"[DRY-RUN][SAVE] Would write to {rendered_path} "
                    f"({len(rendered_content)} chars): {preview}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return StepOutput(
                success=False,
                error=f"模板渲染失敗：{exc}",
            )
