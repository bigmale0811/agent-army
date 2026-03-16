# -*- coding: utf-8 -*-
"""YAML 檔案載入與驗證。

提供從 YAML 檔案載入 AgentDef 和 GlobalConfig 的函式，
並將 Pydantic 驗證錯誤包裝為友善的中文錯誤訊息。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agentforge.schema.agent_def import AgentDef
from agentforge.schema.config import GlobalConfig


class AgentForgeValidationError(Exception):
    """驗證失敗時的自訂例外。

    包含友善的中文錯誤訊息與建議修正方式。
    """


def _read_yaml(path: Path) -> dict:
    """讀取並解析 YAML 檔案。

    Args:
        path: YAML 檔案路徑。

    Returns:
        解析後的 dict。

    Raises:
        AgentForgeValidationError: 檔案不存在或 YAML 語法錯誤。
    """
    if not path.exists():
        raise AgentForgeValidationError(
            f"找不到檔案：{path}\n"
            f"建議修正：請確認檔案路徑是否正確，或使用 'agentforge init' 產生範本。"
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AgentForgeValidationError(
            f"無法讀取檔案 {path}：{exc}\n"
            f"建議修正：請檢查檔案權限或磁碟狀態。"
        ) from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise AgentForgeValidationError(
            f"YAML 語法錯誤（{path}）：{exc}\n"
            f"建議修正：請使用 YAML lint 工具檢查語法，確認縮排和特殊字元正確。"
        ) from exc

    if not isinstance(data, dict):
        raise AgentForgeValidationError(
            f"YAML 檔案 {path} 的頂層結構必須是 mapping（key: value 格式），"
            f"但得到 {type(data).__name__}。\n"
            f"建議修正：請確認 YAML 檔案以 key: value 格式開頭。"
        )

    return data


def load_agent_def(path: Path) -> AgentDef:
    """載入並驗證 Agent YAML 定義。

    Args:
        path: Agent YAML 檔案路徑。

    Returns:
        驗證通過的 AgentDef 實例。

    Raises:
        AgentForgeValidationError: 檔案不存在、YAML 語法錯誤、或驗證失敗。
    """
    data = _read_yaml(path)

    try:
        return AgentDef(**data)
    except ValidationError as exc:
        # 將 Pydantic 錯誤包裝為友善訊息
        errors = exc.errors()
        messages: list[str] = []
        for err in errors:
            loc = " → ".join(str(x) for x in err["loc"])
            messages.append(f"  - {loc}: {err['msg']}")

        error_detail = "\n".join(messages)
        raise AgentForgeValidationError(
            f"Agent 定義驗證失敗（{path}）：\n"
            f"{error_detail}\n"
            f"建議修正：請參考 agentforge/templates/example.yaml 的範例格式。"
        ) from exc


def load_global_config(path: Path) -> GlobalConfig:
    """載入並驗證全域設定 YAML。

    Args:
        path: 全域設定 YAML 檔案路徑。

    Returns:
        驗證通過的 GlobalConfig 實例。

    Raises:
        AgentForgeValidationError: 檔案不存在、YAML 語法錯誤、或驗證失敗。
    """
    data = _read_yaml(path)

    try:
        return GlobalConfig(**data)
    except ValidationError as exc:
        errors = exc.errors()
        messages: list[str] = []
        for err in errors:
            loc = " → ".join(str(x) for x in err["loc"])
            messages.append(f"  - {loc}: {err['msg']}")

        error_detail = "\n".join(messages)
        raise AgentForgeValidationError(
            f"全域設定驗證失敗（{path}）：\n"
            f"{error_detail}\n"
            f"建議修正：請參考 agentforge/templates/agentforge.yaml 的範例格式。"
        ) from exc


def validate_model_string(model: str) -> tuple[str, str]:
    """驗證並解析 model 字串。

    格式必須為 provider/model-name（例如 openai/gpt-4o、ollama/qwen3:14b）。

    Args:
        model: 待驗證的 model 字串。

    Returns:
        (provider, model_name) 元組。

    Raises:
        AgentForgeValidationError: 格式不符。
    """
    if not model or "/" not in model:
        raise AgentForgeValidationError(
            f"model 格式錯誤：'{model}'。"
            f"正確格式為 provider/model-name（例如 openai/gpt-4o、ollama/qwen3:14b）。"
            f"建議修正：請在 model 名稱前加上 provider 前綴，用 '/' 分隔。"
        )

    provider, model_name = model.split("/", 1)

    if not provider or not model_name:
        raise AgentForgeValidationError(
            f"model 格式錯誤：'{model}'。"
            f"provider 和 model-name 都不可為空。"
            f"建議修正：確認格式為 provider/model-name。"
        )

    return provider, model_name
