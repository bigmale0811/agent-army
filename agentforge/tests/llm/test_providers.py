# -*- coding: utf-8 -*-
"""LLM Provider 基礎測試。

測試 BaseProvider 抽象行為、OpenAICompatProvider 與 GeminiProvider
的初始化、參數組合、回應解析等邏輯。
所有實際 API 呼叫均使用 mock。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.llm.providers.base import BaseProvider, LLMResponse
from agentforge.llm.providers.openai_compat import OpenAICompatProvider
from agentforge.llm.providers.gemini import GeminiProvider


class TestBaseProvider:
    """BaseProvider 初始化驗證測試。"""

    def test_base_provider_requires_api_key(self) -> None:
        """缺少 api_key 應拋出 ValueError。"""
        # 透過子類別測試抽象類別的驗證
        class ConcreteProvider(BaseProvider):
            @property
            def provider_name(self) -> str:
                return "test"

            def generate(self, prompt, **kwargs):
                pass

            async def agenerate(self, prompt, **kwargs):
                pass

            def chat(self, messages, **kwargs):
                pass

            async def achat(self, messages, **kwargs):
                pass

            def test_connection(self) -> bool:
                return True

        with pytest.raises(ValueError, match="API key"):
            ConcreteProvider(api_key="", model="test-model")

    def test_base_provider_requires_model(self) -> None:
        """缺少 model 應拋出 ValueError。"""
        class ConcreteProvider(BaseProvider):
            @property
            def provider_name(self) -> str:
                return "test"

            def generate(self, prompt, **kwargs):
                pass

            async def agenerate(self, prompt, **kwargs):
                pass

            def chat(self, messages, **kwargs):
                pass

            async def achat(self, messages, **kwargs):
                pass

            def test_connection(self) -> bool:
                return True

        with pytest.raises(ValueError, match="模型名稱"):
            ConcreteProvider(api_key="test-key", model="")


class TestOpenAICompatProvider:
    """OpenAICompatProvider 測試。"""

    def test_provider_name_openai(self) -> None:
        """OpenAI base_url 應回傳 openai。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")
        assert p.provider_name == "openai"

    def test_provider_name_ollama(self) -> None:
        """localhost URL 應回傳 ollama。"""
        p = OpenAICompatProvider(
            api_key="ollama",
            model="qwen3:14b",
            base_url="http://localhost:11434/v1",
        )
        assert p.provider_name == "ollama"

    def test_provider_name_deepseek(self) -> None:
        """DeepSeek base_url 應回傳 deepseek。"""
        p = OpenAICompatProvider(
            api_key="key",
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
        )
        assert p.provider_name == "deepseek"

    def test_provider_name_groq(self) -> None:
        """Groq base_url 應回傳 groq。"""
        p = OpenAICompatProvider(
            api_key="key",
            model="llama3",
            base_url="https://api.groq.com/openai/v1",
        )
        assert p.provider_name == "groq"

    def test_provider_name_together(self) -> None:
        """Together base_url 應回傳 together。"""
        p = OpenAICompatProvider(
            api_key="key",
            model="llama3",
            base_url="https://api.together.xyz/v1",
        )
        assert p.provider_name == "together"

    def test_provider_name_generic(self) -> None:
        """未知 URL 應回傳 openai-compat。"""
        p = OpenAICompatProvider(
            api_key="key",
            model="custom",
            base_url="https://my-custom-api.example.com/v1",
        )
        assert p.provider_name == "openai-compat"

    def test_build_params_basic(self) -> None:
        """_build_params 應包含 model 和 messages。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")
        messages = [{"role": "user", "content": "hello"}]
        params = p._build_params(messages)

        assert params["model"] == "gpt-4o"
        assert params["messages"] == messages

    def test_build_params_with_temperature(self) -> None:
        """_build_params 應正確處理 temperature 參數。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")
        messages = [{"role": "user", "content": "hello"}]
        params = p._build_params(messages, temperature=0.7)

        assert params["temperature"] == 0.7

    def test_build_params_with_max_tokens(self) -> None:
        """_build_params 應正確處理 max_tokens 參數。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")
        messages = [{"role": "user", "content": "hello"}]
        params = p._build_params(messages, max_tokens=100)

        assert params["max_tokens"] == 100

    def test_build_params_model_override(self) -> None:
        """_build_params 中指定 model 應覆蓋預設模型。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")
        messages = [{"role": "user", "content": "hello"}]
        params = p._build_params(messages, model="gpt-4o-mini")

        assert params["model"] == "gpt-4o-mini"

    def test_build_response_with_usage(self) -> None:
        """_build_response 應正確解析 usage 資訊。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")

        mock_raw = MagicMock()
        mock_raw.choices[0].message.content = "Hello!"
        mock_raw.model = "gpt-4o"
        mock_raw.usage.prompt_tokens = 10
        mock_raw.usage.completion_tokens = 20
        mock_raw.usage.total_tokens = 30

        response = p._build_response(mock_raw)

        assert response.content == "Hello!"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 20

    def test_build_response_without_usage(self) -> None:
        """_build_response 應處理無 usage 的回應。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")

        mock_raw = MagicMock()
        mock_raw.choices[0].message.content = "Hello!"
        mock_raw.model = "gpt-4o"
        mock_raw.usage = None

        response = p._build_response(mock_raw)

        assert response.content == "Hello!"
        assert response.usage is None

    def test_generate_calls_chat(self) -> None:
        """generate() 應將 prompt 轉為 chat messages 後呼叫 chat()。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")

        with patch.object(p, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content="ok", model="gpt-4o", provider="openai"
            )
            p.generate("hello")

        mock_chat.assert_called_once()
        messages = mock_chat.call_args[0][0]
        assert messages[0]["content"] == "hello"
        assert messages[0]["role"] == "user"

    def test_get_sync_client_raises_on_missing_openai(self) -> None:
        """缺少 openai 套件時應拋出 ImportError。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")

        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises((ImportError, Exception)):
                p._get_sync_client()

    def test_test_connection_returns_false_on_exception(self) -> None:
        """test_connection 遇到例外應回傳 False。"""
        p = OpenAICompatProvider(api_key="key", model="gpt-4o")

        with patch.object(p, "generate", side_effect=ConnectionError("no network")):
            result = p.test_connection()

        assert result is False


class TestGeminiProvider:
    """GeminiProvider 測試。"""

    def test_provider_name(self) -> None:
        """provider_name 應回傳 gemini。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")
        assert p.provider_name == "gemini"

    def test_convert_messages_user_role(self) -> None:
        """user role 應轉換為 Gemini 格式。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")
        messages = [{"role": "user", "content": "hello"}]
        sys_instr, contents = p._convert_messages_to_contents(messages)

        assert sys_instr is None
        assert len(contents) == 1
        assert contents[0]["role"] == "user"
        assert contents[0]["parts"][0]["text"] == "hello"

    def test_convert_messages_assistant_role(self) -> None:
        """assistant role 應轉換為 model role。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")
        messages = [{"role": "assistant", "content": "I can help"}]
        _, contents = p._convert_messages_to_contents(messages)

        assert contents[0]["role"] == "model"

    def test_convert_messages_system_role(self) -> None:
        """system role 應轉換為 system_instruction。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "hello"},
        ]
        sys_instr, contents = p._convert_messages_to_contents(messages)

        assert sys_instr == "You are helpful"
        assert len(contents) == 1

    def test_build_response_with_usage(self) -> None:
        """_build_response 應正確解析 Gemini usage 資訊。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")

        mock_raw = MagicMock()
        mock_raw.text = "Gemini response"
        mock_raw.usage_metadata.prompt_token_count = 5
        mock_raw.usage_metadata.candidates_token_count = 15
        mock_raw.usage_metadata.total_token_count = 20

        response = p._build_response(mock_raw, "gemini-2.0-flash")

        assert response.content == "Gemini response"
        assert response.provider == "gemini"
        assert response.usage["prompt_tokens"] == 5

    def test_build_response_without_usage_metadata(self) -> None:
        """_build_response 應處理無 usage_metadata 的回應。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")

        mock_raw = MagicMock(spec=["text"])
        mock_raw.text = "no usage"

        response = p._build_response(mock_raw, "gemini-2.0-flash")

        assert response.content == "no usage"
        assert response.usage is None

    def test_get_client_raises_on_missing_package(self) -> None:
        """缺少 google-genai 套件時應拋出 ImportError。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")

        with patch.dict("sys.modules", {"google": None, "google.genai": None}):
            with pytest.raises((ImportError, Exception)):
                p._get_client()

    def test_test_connection_returns_false_on_exception(self) -> None:
        """test_connection 遇到例外應回傳 False。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")

        with patch.object(p, "generate", side_effect=ConnectionError("no network")):
            result = p.test_connection()

        assert result is False

    def test_generate_calls_client(self) -> None:
        """generate() 應呼叫 Gemini client 的 generate_content。"""
        p = GeminiProvider(api_key="key", model="gemini-2.0-flash")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "generated text"
        mock_response.usage_metadata = None
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(p, "_get_client", return_value=mock_client):
            result = p.generate("Tell me a joke")

        assert result.content == "generated text"
        mock_client.models.generate_content.assert_called_once()
