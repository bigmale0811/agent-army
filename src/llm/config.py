"""LLM Provider 設定管理 — 從 YAML 和環境變數載入設定。"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class ProviderConfig:
    """單一 Provider 的設定（不可變）。

    Attributes:
        name: Provider 識別名稱
        api_key_env: API key 的環境變數名稱
        base_url: API 端點 URL（OpenAI 相容用）
        default_model: 預設模型名稱
        description: Provider 描述
    """

    name: str
    api_key_env: str
    default_model: str
    description: str = ""
    base_url: Optional[str] = None

    @property
    def api_key(self) -> Optional[str]:
        """從環境變數取得 API key。"""
        return os.environ.get(self.api_key_env)

    @property
    def is_available(self) -> bool:
        """檢查此 Provider 是否可用（有 API key）。"""
        key = self.api_key
        return key is not None and len(key) > 0

    @property
    def is_gemini(self) -> bool:
        """是否為 Gemini Provider（使用不同的 SDK）。"""
        return self.name == "gemini"


# 預設設定檔路徑
_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"


def load_config(
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """載入 YAML 設定檔。

    Args:
        config_path: 設定檔路徑，None 則使用預設路徑

    Returns:
        解析後的設定字典
    """
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        return {"providers": {}, "default_provider": "openai"}

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_provider_configs(
    config_path: Optional[Path] = None,
) -> List[ProviderConfig]:
    """取得所有 Provider 設定。

    Returns:
        ProviderConfig 列表
    """
    config = load_config(config_path)
    providers = config.get("providers", {})

    result = []
    for name, settings in providers.items():
        result.append(
            ProviderConfig(
                name=name,
                api_key_env=settings.get("api_key_env", ""),
                base_url=settings.get("base_url"),
                default_model=settings.get("default_model", ""),
                description=settings.get("description", ""),
            )
        )
    return result


def get_provider_config(
    provider_name: str,
    config_path: Optional[Path] = None,
) -> Optional[ProviderConfig]:
    """取得指定 Provider 的設定。

    Args:
        provider_name: Provider 名稱
        config_path: 設定檔路徑

    Returns:
        ProviderConfig 或 None
    """
    configs = get_provider_configs(config_path)
    for cfg in configs:
        if cfg.name == provider_name:
            return cfg
    return None


def get_default_provider(
    config_path: Optional[Path] = None,
) -> str:
    """取得預設 Provider 名稱。

    優先順序：環境變數 > YAML 設定 > "openai"
    """
    env_default = os.environ.get("DEFAULT_LLM_PROVIDER")
    if env_default:
        return env_default

    config = load_config(config_path)
    return config.get("default_provider", "openai")


def get_available_providers(
    config_path: Optional[Path] = None,
) -> List[ProviderConfig]:
    """取得所有可用的 Provider（有 API key 的）。"""
    return [p for p in get_provider_configs(config_path) if p.is_available]
