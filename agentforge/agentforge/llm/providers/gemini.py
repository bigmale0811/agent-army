# -*- coding: utf-8 -*-
"""Google Gemini Provider — 使用 google-genai SDK。

支援模型：gemini-2.0-flash、gemini-2.0-pro、gemini-1.5-flash 等。
"""

from typing import Any, Dict, List, Optional

from agentforge.llm.providers.base import BaseProvider, LLMResponse


class GeminiProvider(BaseProvider):
    """Google Gemini API Provider。

    使用新版 google-genai SDK（非已棄用的 google-generativeai）。
    """

    def __init__(self, api_key: str, model: str, **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._client: Optional[Any] = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_client(self) -> Any:
        """取得 Gemini client（延遲初始化）。"""
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:
                raise ImportError(
                    "需要安裝 google-genai 套件：pip install google-genai"
                ) from e
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _build_response(
        self, raw_response: Any, model: str
    ) -> LLMResponse:
        """將 Gemini API 回應轉換為統一格式。"""
        content = raw_response.text or ""

        usage = None
        if hasattr(raw_response, "usage_metadata") and raw_response.usage_metadata:
            meta = raw_response.usage_metadata
            usage = {
                "prompt_tokens": getattr(meta, "prompt_token_count", 0),
                "completion_tokens": getattr(
                    meta, "candidates_token_count", 0
                ),
                "total_tokens": getattr(meta, "total_token_count", 0),
            }

        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            usage=usage,
            raw=raw_response,
        )

    def _convert_messages_to_contents(
        self, messages: List[Dict[str, str]]
    ) -> tuple:  # type: ignore[type-arg]
        """將 OpenAI 格式的 messages 轉換為 Gemini 格式。

        Returns:
            (system_instruction, contents) 元組
        """
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                # Gemini 使用 system_instruction 而非 system role
                system_instruction = content
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        return system_instruction, contents

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """同步產生文字回應。"""
        client = self._get_client()
        model = kwargs.pop("model", self.model)

        config = {}
        if "temperature" in kwargs:
            config["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            config["max_output_tokens"] = kwargs.pop("max_tokens")

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config if config else None,
        )
        return self._build_response(response, model)

    async def agenerate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """非同步產生文字回應。"""
        client = self._get_client()
        model = kwargs.pop("model", self.model)

        config = {}
        if "temperature" in kwargs:
            config["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            config["max_output_tokens"] = kwargs.pop("max_tokens")

        response = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=config if config else None,
        )
        return self._build_response(response, model)

    def chat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """同步對話模式。"""
        client = self._get_client()
        model = kwargs.pop("model", self.model)
        system_instruction, contents = self._convert_messages_to_contents(
            messages
        )

        config = {}
        if system_instruction:
            config["system_instruction"] = system_instruction
        if "temperature" in kwargs:
            config["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            config["max_output_tokens"] = kwargs.pop("max_tokens")

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config if config else None,
        )
        return self._build_response(response, model)

    async def achat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """非同步對話模式。"""
        client = self._get_client()
        model = kwargs.pop("model", self.model)
        system_instruction, contents = self._convert_messages_to_contents(
            messages
        )

        config = {}
        if system_instruction:
            config["system_instruction"] = system_instruction
        if "temperature" in kwargs:
            config["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            config["max_output_tokens"] = kwargs.pop("max_tokens")

        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config if config else None,
        )
        return self._build_response(response, model)

    def test_connection(self) -> bool:
        """測試 API 連線。"""
        try:
            response = self.generate(
                "Hi", max_tokens=5, temperature=0
            )
            return bool(response.content)
        except Exception:  # noqa: BLE001
            return False
