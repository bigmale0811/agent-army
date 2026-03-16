"""LLM 步驟模組 — 呼叫大型語言模型並取得回應。

LLMStep 對應 YAML 中 action: llm 的步驟，
支援 prompt / input 模板替換，並透過 LLMRouter 路由到正確的 Provider。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

from agentforge.llm.router import LLMRouter
from agentforge.schema import StepDef
from agentforge.steps.base import BaseStep, StepOutput
from agentforge.utils.template import TemplateEngine


class LLMStep(BaseStep):
    """呼叫 LLM 取得回應的步驟。

    使用 TemplateEngine 渲染 prompt / input 欄位，
    再透過 LLMRouter 路由到對應的 Provider。
    """

    def __init__(
        self,
        step_def: StepDef,
        template_engine: TemplateEngine,
        router: LLMRouter,
        default_model: str,
    ) -> None:
        """初始化 LLM 步驟。

        Args:
            step_def: 步驟定義，需包含 prompt 欄位。
            template_engine: 模板引擎，用於渲染 prompt / input。
            router: LLM 路由器，負責選擇並呼叫 Provider。
            default_model: 當步驟未指定 model 時使用的預設模型。
        """
        super().__init__(step_def, template_engine)
        self._router = router
        self._default_model = default_model

    def _resolve_model(self) -> str:
        """決定此步驟使用的模型。

        步驟級別的 model 優先；若未設定則使用 Agent 級別的預設模型。

        Returns:
            model_ref 字串（格式：provider/model-name）。
        """
        return self._step_def.model or self._default_model

    def _render_prompt(self, context: dict[str, Any]) -> str:
        """渲染 prompt 模板。

        Args:
            context: 執行環境。

        Returns:
            渲染後的 prompt 字串。
        """
        prompt = self._step_def.prompt or ""
        return self._template_engine.render(prompt, context)

    def _render_input(self, context: dict[str, Any]) -> str:
        """渲染 input 模板（若存在）。

        Args:
            context: 執行環境。

        Returns:
            渲染後的 input 字串；若 input 欄位未設定則回傳空字串。
        """
        if not self._step_def.input:
            return ""
        return self._template_engine.render(self._step_def.input, context)

    def execute(self, context: dict[str, Any]) -> StepOutput:
        """呼叫 LLM 並回傳回應。

        1. 渲染 prompt 模板
        2. 渲染 input 模板（若有）
        3. 決定使用的模型
        4. 透過 router 呼叫 LLM
        5. 回傳 StepOutput

        Args:
            context: 執行環境，包含前面步驟的輸出。

        Returns:
            StepOutput，output 為模型回應文字。
        """
        try:
            rendered_prompt = self._render_prompt(context)
            rendered_input = self._render_input(context)
            model_ref = self._resolve_model()

            result = self._router.call(
                model_ref=model_ref,
                prompt=rendered_prompt,
                context=rendered_input,
            )

            return StepOutput(
                success=True,
                output=result.content,
                cost_usd=result.cost_usd,
                tokens=result.tokens_in + result.tokens_out,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM 步驟 '%s' 呼叫失敗", self._step_def.name)
            return StepOutput(
                success=False,
                error=f"LLM 呼叫失敗：{exc}",
            )

    def dry_run(self, context: dict[str, Any]) -> StepOutput:
        """模擬 LLM 呼叫（不實際呼叫 API）。

        Args:
            context: 執行環境。

        Returns:
            StepOutput，包含模擬執行的描述訊息。
        """
        try:
            rendered_prompt = self._render_prompt(context)
            model_ref = self._resolve_model()

            preview = rendered_prompt[:100]
            if len(rendered_prompt) > 100:
                preview += "..."

            return StepOutput(
                success=True,
                output=(
                    f"[DRY-RUN][LLM] Would call {model_ref} "
                    f"with prompt: {preview}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return StepOutput(
                success=False,
                error=f"模板渲染失敗：{exc}",
            )
