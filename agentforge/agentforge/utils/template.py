# -*- coding: utf-8 -*-
"""模板引擎模組 — 支援 {{ steps.<name>.output }} 樣式的變數替換。

提供 TemplateEngine 類別，用於渲染 Agent 步驟中的模板字串，
允許後續步驟引用前面步驟的輸出結果。
"""

from __future__ import annotations

import re
from typing import Any


# 匹配 {{ steps.<name>.output }} 或 {{ steps.<name>.error }} 模式
_PATTERN = re.compile(r"\{\{\s*steps\.(\w+)\.(output|error)\s*\}\}")


class TemplateEngine:
    """步驟輸出模板引擎。

    支援在 prompt / command / path / content 等欄位中使用
    {{ steps.<name>.output }} 或 {{ steps.<name>.error }} 語法，
    引用先前步驟的執行結果。
    """

    @staticmethod
    def render(template: str, context: dict[str, Any]) -> str:
        """渲染模板字串，替換所有步驟輸出佔位符。

        Args:
            template: 包含 {{ steps.<name>.output }} 佔位符的模板字串。
            context: 執行環境，頂層須含 "steps" 鍵，
                     格式為 {"steps": {"<name>": {"output": "...", "error": "..."}}}.

        Returns:
            替換後的完整字串。

        Raises:
            KeyError: 模板中引用了不存在的步驟名稱或欄位。
        """
        steps_context: dict[str, dict[str, str]] = context.get("steps", {})

        def _replace(match: re.Match) -> str:  # type: ignore[type-arg]
            step_name = match.group(1)
            field = match.group(2)  # "output" 或 "error"

            if step_name not in steps_context:
                raise KeyError(
                    f"模板引用了未知的步驟 '{step_name}'。"
                    f"可用步驟：{list(steps_context.keys())}"
                )

            step_data = steps_context[step_name]
            if field not in step_data:
                raise KeyError(
                    f"步驟 '{step_name}' 沒有欄位 '{field}'。"
                    f"可用欄位：{list(step_data.keys())}"
                )

            return step_data[field]

        return _PATTERN.sub(_replace, template)

    @staticmethod
    def has_placeholders(template: str) -> bool:
        """檢查模板字串是否包含佔位符。

        Args:
            template: 待檢查的字串。

        Returns:
            True 表示存在至少一個佔位符。
        """
        return bool(_PATTERN.search(template))
