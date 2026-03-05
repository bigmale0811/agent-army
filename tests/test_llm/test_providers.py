"""測試 LLM Provider 實作。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.providers.base import BaseProvider, LLMResponse


class TestLLMResponse:
    """LLMResponse 資料類別測試。"""

    def test_create_response(self):
        """建立 LLMResponse 實例。"""
        response = LLMResponse(
            content="Hello",
            model="gpt-4o-mini",
            provider="openai",
            usage={"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        )
        assert response.content == "Hello"
        assert response.model == "gpt-4o-mini"
        assert response.provider == "openai"
        assert response.usage["total_tokens"] == 6

    def test_frozen(self):
        """LLMResponse 是不可變的。"""
        response = LLMResponse(content="Hi", model="m", provider="p")
        with pytest.raises(AttributeError):
            response.content = "changed"  # type: ignore[misc]


class TestBaseProvider:
    """BaseProvider 抽象類別測試。"""

    def test_cannot_instantiate(self):
        """無法直接實例化抽象類別。"""
        with pytest.raises(TypeError):
            BaseProvider(api_key="key", model="model")  # type: ignore[abstract]

    def test_requires_api_key(self):
        """API key 不能為空。"""
        # 建立一個具體子類別來測試
        class DummyProvider(BaseProvider):
            @property
            def provider_name(self):
                return "dummy"

            def generate(self, prompt, **kwargs):
                return LLMResponse(content="", model="", provider="")

            async def agenerate(self, prompt, **kwargs):
                return LLMResponse(content="", model="", provider="")

            def chat(self, messages, **kwargs):
                return LLMResponse(content="", model="", provider="")

            async def achat(self, messages, **kwargs):
                return LLMResponse(content="", model="", provider="")

            def test_connection(self):
                return True

        with pytest.raises(ValueError, match="需要 API key"):
            DummyProvider(api_key="", model="model")

    def test_requires_model(self):
        """模型名稱不能為空。"""

        class DummyProvider(BaseProvider):
            @property
            def provider_name(self):
                return "dummy"

            def generate(self, prompt, **kwargs):
                return LLMResponse(content="", model="", provider="")

            async def agenerate(self, prompt, **kwargs):
                return LLMResponse(content="", model="", provider="")

            def chat(self, messages, **kwargs):
                return LLMResponse(content="", model="", provider="")

            async def achat(self, messages, **kwargs):
                return LLMResponse(content="", model="", provider="")

            def test_connection(self):
                return True

        with pytest.raises(ValueError, match="需要指定模型"):
            DummyProvider(api_key="key", model="")


class TestOpenAICompatProvider:
    """OpenAI 相容 Provider 測試。"""

    def test_provider_name_detection(self):
        """根據 base_url 自動判斷 Provider 名稱。"""
        from src.llm.providers.openai_compat import OpenAICompatProvider

        cases = [
            ("https://api.openai.com/v1", "openai"),
            ("https://api.deepseek.com", "deepseek"),
            ("https://api.groq.com/openai/v1", "groq"),
            ("https://api.together.xyz/v1", "together"),
            ("https://custom-api.example.com/v1", "openai-compat"),
        ]
        for base_url, expected_name in cases:
            provider = OpenAICompatProvider(
                api_key="test-key",
                model="test-model",
                base_url=base_url,
            )
            assert provider.provider_name == expected_name, (
                f"base_url={base_url} should be {expected_name}"
            )

    def test_build_params(self):
        """組合 API 請求參數。"""
        from src.llm.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider(
            api_key="test-key",
            model="test-model",
            base_url="https://api.openai.com/v1",
        )
        messages = [{"role": "user", "content": "Hello"}]
        params = provider._build_params(messages, temperature=0.5, max_tokens=100)

        assert params["model"] == "test-model"
        assert params["messages"] == messages
        assert params["temperature"] == 0.5
        assert params["max_tokens"] == 100

    def test_build_response(self):
        """轉換 API 回應為統一格式。"""
        from src.llm.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider(
            api_key="test-key",
            model="test-model",
            base_url="https://api.openai.com/v1",
        )

        # 模擬 OpenAI API 回應
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello back!"
        mock_response.model = "gpt-4o-mini"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.usage.total_tokens = 8

        result = provider._build_response(mock_response)
        assert result.content == "Hello back!"
        assert result.model == "gpt-4o-mini"
        assert result.provider == "openai"
        assert result.usage["total_tokens"] == 8


class TestGeminiProvider:
    """Gemini Provider 測試。"""

    def test_provider_name(self):
        """Gemini Provider 名稱。"""
        from src.llm.providers.gemini import GeminiProvider

        provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
        assert provider.provider_name == "gemini"

    def test_convert_messages(self):
        """轉換 OpenAI 格式的 messages 為 Gemini 格式。"""
        from src.llm.providers.gemini import GeminiProvider

        provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")

        messages = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "嗨！"},
            {"role": "user", "content": "再見"},
        ]

        system, contents = provider._convert_messages_to_contents(messages)
        assert system == "你是助手"
        assert len(contents) == 3
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"  # assistant → model
        assert contents[2]["role"] == "user"
