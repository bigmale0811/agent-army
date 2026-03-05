"""統一 LLM Client — 工廠模式建立 Provider 並提供統一呼叫介面。

使用方式：
    # 基本用法
    client = LLMClient(provider="deepseek")
    result = client.generate("寫一個排序演算法")

    # 指定模型
    client = LLMClient(provider="openai", model="gpt-4o")
    result = client.chat([{"role": "user", "content": "你好"}])

    # 使用預設 Provider
    client = LLMClient()  # 讀取 DEFAULT_LLM_PROVIDER 環境變數
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    ProviderConfig,
    get_available_providers,
    get_default_provider,
    get_provider_config,
)
from .providers.base import BaseProvider, LLMResponse


class LLMClient:
    """統一 LLM Client — 封裝多家 Provider 的共用介面。"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        config_path: Optional[Path] = None,
        **kwargs: Any,
    ) -> None:
        """初始化 LLM Client。

        Args:
            provider: Provider 名稱（openai, deepseek, groq, together, gemini）
                      None 則使用預設 Provider
            model: 模型名稱，None 則使用 Provider 的預設模型
            api_key: API key，None 則從環境變數讀取
            config_path: 設定檔路徑，None 則使用預設路徑
            **kwargs: 傳給 Provider 的額外參數
        """
        # 決定 Provider
        provider_name = provider or get_default_provider(config_path)
        provider_config = get_provider_config(provider_name, config_path)

        if provider_config is None:
            available = [p.name for p in get_available_providers(config_path)]
            raise ValueError(
                f"未知的 Provider: {provider_name}。"
                f"可用的 Provider: {available or '無（請設定 API key）'}"
            )

        # 決定 API key
        resolved_api_key = api_key or provider_config.api_key
        if not resolved_api_key:
            raise ValueError(
                f"Provider '{provider_name}' 需要 API key。"
                f"請設定環境變數 {provider_config.api_key_env} "
                f"或在 .env 檔案中加入 {provider_config.api_key_env}=your-key"
            )

        # 決定模型
        resolved_model = model or provider_config.default_model

        # 建立 Provider 實例
        self._provider = self._create_provider(
            config=provider_config,
            api_key=resolved_api_key,
            model=resolved_model,
            **kwargs,
        )
        self._config = provider_config

    @staticmethod
    def _create_provider(
        config: ProviderConfig,
        api_key: str,
        model: str,
        **kwargs: Any,
    ) -> BaseProvider:
        """工廠方法 — 根據設定建立對應的 Provider。"""
        if config.is_gemini:
            from .providers.gemini import GeminiProvider

            return GeminiProvider(api_key=api_key, model=model, **kwargs)

        from .providers.openai_compat import OpenAICompatProvider

        # 所有非 Gemini 的 Provider 都用 OpenAI 相容介面
        return OpenAICompatProvider(
            api_key=api_key,
            model=model,
            base_url=config.base_url or "https://api.openai.com/v1",
            **kwargs,
        )

    @property
    def provider_name(self) -> str:
        """目前使用的 Provider 名稱。"""
        return self._provider.provider_name

    @property
    def model(self) -> str:
        """目前使用的模型名稱。"""
        return self._provider.model

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """產生文字回應（同步）。"""
        return self._provider.generate(prompt, **kwargs)

    async def agenerate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """產生文字回應（非同步）。"""
        return await self._provider.agenerate(prompt, **kwargs)

    def chat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """對話模式（同步）。"""
        return self._provider.chat(messages, **kwargs)

    async def achat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """對話模式（非同步）。"""
        return await self._provider.achat(messages, **kwargs)

    def test_connection(self) -> bool:
        """測試目前 Provider 的 API 連線。"""
        return self._provider.test_connection()

    @staticmethod
    def list_available(config_path: Optional[Path] = None) -> List[Dict[str, str]]:
        """列出所有可用的 Provider（已設定 API key）。

        Returns:
            Provider 資訊列表
        """
        available = get_available_providers(config_path)
        return [
            {
                "name": p.name,
                "model": p.default_model,
                "description": p.description,
            }
            for p in available
        ]

    @staticmethod
    def list_all(config_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """列出所有已設定的 Provider（含可用狀態）。

        Returns:
            Provider 資訊列表（含 available 欄位）
        """
        from .config import get_provider_configs

        configs = get_provider_configs(config_path)
        return [
            {
                "name": p.name,
                "model": p.default_model,
                "description": p.description,
                "available": p.is_available,
                "api_key_env": p.api_key_env,
            }
            for p in configs
        ]
