# -*- coding: utf-8 -*-
"""Agent YAML 定義的 Pydantic v2 模型。

此模組定義了 Agent 的資料結構，包括：
- StepDef：單一步驟定義（shell / llm / save）
- AgentDef：完整 Agent 定義（含步驟列表與驗證規則）

所有模型皆為 frozen（不可變），確保建立後不會被意外修改。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _validate_model_format(model: str) -> str:
    """驗證 model 字串格式必須為 provider/model-name。

    Args:
        model: 待驗證的 model 字串。

    Returns:
        通過驗證的原始字串。

    Raises:
        ValueError: 格式不符時拋出。
    """
    if "/" not in model:
        raise ValueError(
            f"model 格式錯誤：'{model}'。"
            f"正確格式為 provider/model-name（例如 openai/gpt-4o、ollama/qwen3:14b）。"
            f"建議修正：請在 model 名稱前加上 provider 前綴，用 '/' 分隔。"
        )
    provider, model_name = model.split("/", 1)
    if not provider or not model_name:
        raise ValueError(
            f"model 格式錯誤：'{model}'。"
            f"provider 和 model-name 都不可為空。"
            f"建議修正：確認格式為 provider/model-name。"
        )
    return model


class StepDef(BaseModel):
    """單一步驟定義。

    支援三種 action 類型：
    - shell：執行 shell 命令，需提供 command
    - llm：呼叫 LLM，需提供 prompt
    - save：儲存檔案，需提供 path 和 content
    """

    model_config = ConfigDict(frozen=True)

    name: str  # 步驟名稱（同一 Agent 內不可重複）
    action: Literal["shell", "llm", "save"]  # 動作類型
    command: str | None = None  # shell 用：要執行的命令
    prompt: str | None = None  # llm 用：提示詞模板
    input: str | None = None  # llm 用：額外輸入模板變數
    path: str | None = None  # save 用：輸出檔案路徑
    content: str | None = None  # save 用：輸出內容模板
    model: str | None = None  # 可覆蓋 Agent 級別的 model

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        """驗證 model 格式（如果有值）。"""
        if v is not None:
            return _validate_model_format(v)
        return v

    @model_validator(mode="after")
    def validate_action_fields(self) -> StepDef:
        """根據 action 類型驗證必要欄位是否存在。"""
        action = self.action

        if action == "shell" and not self.command:
            raise ValueError(
                f"步驟 '{self.name}' 的 action 為 'shell'，但缺少 command 欄位。"
                f"建議修正：請為 shell 步驟提供要執行的命令，例如 command: 'ls -la'。"
            )

        if action == "llm" and not self.prompt:
            raise ValueError(
                f"步驟 '{self.name}' 的 action 為 'llm'，但缺少 prompt 欄位。"
                f"建議修正：請為 llm 步驟提供提示詞，例如 prompt: '請分析以下內容...'。"
            )

        if action == "save":
            if not self.path:
                raise ValueError(
                    f"步驟 '{self.name}' 的 action 為 'save'，但缺少 path 欄位。"
                    f"建議修正：請為 save 步驟提供輸出路徑，例如 path: 'output.md'。"
                )
            if not self.content:
                raise ValueError(
                    f"步驟 '{self.name}' 的 action 為 'save'，但缺少 content 欄位。"
                    f"建議修正：請為 save 步驟提供輸出內容模板，"
                    f"例如 content: '{{{{ steps.analyze.output }}}}'。"
                )

        return self


class AgentDef(BaseModel):
    """完整的 Agent 定義。

    包含 Agent 的名稱、描述、預設 model、重試次數，以及步驟列表。
    所有欄位建立後不可變（frozen）。
    """

    model_config = ConfigDict(frozen=True)

    name: str  # Agent 名稱
    description: str = ""  # Agent 描述
    model: str = ""  # 格式：provider/model-name（可選）
    max_retries: int = 3  # 最大重試次數（1-10）
    steps: list[StepDef]  # 步驟列表（至少一個）

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """驗證 model 格式（如果有值）。"""
        if v:
            return _validate_model_format(v)
        return v

    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """驗證 max_retries 必須在 1-10 之間。"""
        if v < 1 or v > 10:
            raise ValueError(
                f"max_retries 值為 {v}，但必須在 1 到 10 之間。"
                f"建議修正：請將 max_retries 設為 1 到 10 之間的整數。"
            )
        return v

    @model_validator(mode="after")
    def validate_steps(self) -> AgentDef:
        """驗證步驟列表不為空，且 step name 不可重複。"""
        # 檢查 steps 是否為空
        if not self.steps:
            raise ValueError(
                "steps 列表不可為空。每個 Agent 至少需要一個步驟。"
                "建議修正：請在 steps 中定義至少一個 shell、llm 或 save 步驟。"
            )

        # 檢查 step name 是否重複
        names = [step.name for step in self.steps]
        seen: set[str] = set()
        duplicates: list[str] = []
        for n in names:
            if n in seen:
                duplicates.append(n)
            seen.add(n)

        if duplicates:
            dup_str = ", ".join(f"'{d}'" for d in duplicates)
            raise ValueError(
                f"steps 中有重複的名稱：{dup_str}。"
                f"每個步驟的 name 必須唯一，因為後續步驟會透過名稱引用前面步驟的輸出。"
                f"建議修正：請為重複的步驟取不同的名稱。"
            )

        return self
