"""OpenAI 相容 Provider — 支援所有 OpenAI API 格式的服務。

覆蓋的服務：OpenAI、DeepSeek、Groq、Together AI 等。
只要 API 相容 OpenAI 格式，都可以透過修改 base_url 使用。
"""

from typing import Any, Dict, List, Optional

from .base import BaseProvider, LLMResponse


class OpenAICompatProvider(BaseProvider):
    """OpenAI 相容 API Provider。

    透過 openai Python 套件（>=1.0），只需修改 base_url
    即可連接任何 OpenAI 相容的 API 服務。
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = base_url
        # 延遲匯入，只在實際使用時才需要 openai 套件
        self._sync_client: Optional[Any] = None
        self._async_client: Optional[Any] = None

    @property
    def provider_name(self) -> str:
        """根據 base_url 自動判斷 Provider 名稱。"""
        url = self.base_url.lower()
        if "deepseek" in url:
            return "deepseek"
        if "groq" in url:
            return "groq"
        if "together" in url:
            return "together"
        if "openai" in url:
            return "openai"
        return "openai-compat"

    def _get_sync_client(self) -> Any:
        """取得同步 OpenAI client（延遲初始化）。"""
        if self._sync_client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError(
                    "需要安裝 openai 套件：pip install openai>=1.0"
                ) from e
            self._sync_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._sync_client

    def _get_async_client(self) -> Any:
        """取得非同步 OpenAI client（延遲初始化）。"""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise ImportError(
                    "需要安裝 openai 套件：pip install openai>=1.0"
                ) from e
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._async_client

    def _build_response(self, raw_response: Any) -> LLMResponse:
        """將 OpenAI API 回應轉換為統一格式。"""
        choice = raw_response.choices[0]
        content = choice.message.content or ""

        usage = None
        if raw_response.usage:
            usage = {
                "prompt_tokens": raw_response.usage.prompt_tokens,
                "completion_tokens": raw_response.usage.completion_tokens,
                "total_tokens": raw_response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model=raw_response.model,
            provider=self.provider_name,
            usage=usage,
            raw=raw_response,
        )

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """同步產生文字回應。"""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)

    async def agenerate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """非同步產生文字回應。"""
        messages = [{"role": "user", "content": prompt}]
        return await self.achat(messages, **kwargs)

    def chat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """同步對話模式。"""
        client = self._get_sync_client()
        params = self._build_params(messages, **kwargs)
        response = client.chat.completions.create(**params)
        return self._build_response(response)

    async def achat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """非同步對話模式。"""
        client = self._get_async_client()
        params = self._build_params(messages, **kwargs)
        response = await client.chat.completions.create(**params)
        return self._build_response(response)

    def _build_params(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> Dict[str, Any]:
        """組合 API 請求參數。"""
        params: Dict[str, Any] = {
            "model": kwargs.pop("model", self.model),
            "messages": messages,
        }
        # 常用參數
        if "temperature" in kwargs:
            params["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs.pop("max_tokens")
        if "top_p" in kwargs:
            params["top_p"] = kwargs.pop("top_p")
        if "stream" in kwargs:
            params["stream"] = kwargs.pop("stream")
        # 剩餘的 kwargs 直接傳入
        params.update(kwargs)
        return params

    def test_connection(self) -> bool:
        """測試 API 連線 — 發送一個最小請求。"""
        try:
            response = self.generate(
                "Hi", max_tokens=5, temperature=0
            )
            return bool(response.content)
        except Exception:
            return False
