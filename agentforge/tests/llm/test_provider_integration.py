# -*- coding: utf-8 -*-
"""Provider 整合驗證測試。

確認路由器正確將各 provider 的 model_ref 導向對應 Provider 實例，
以及 Provider 實例化時的參數設定是否正確。
所有測試均使用 mock，不進行真實 API 呼叫。

測試範圍：
- Ollama 路由到 OpenAICompatProvider（base_url = localhost:11434）
- OpenAI 路由到 OpenAICompatProvider（base_url = openai.com）
- Gemini 路由到 GeminiProvider
- 未知 provider 拋出 ValueError 並給出清楚說明
- 自訂 base_url 與 api_key_env 設定被正確套用
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.llm.providers.base import LLMResponse
from agentforge.llm.providers.gemini import GeminiProvider
from agentforge.llm.providers.openai_compat import OpenAICompatProvider
from agentforge.llm.router import LLMCallResult, LLMRouter
from agentforge.schema import GlobalConfig, LLMProviderConfig


# ─────────────────────────────────────────────
# 測試輔助函式
# ─────────────────────────────────────────────

def _make_response(content: str = "ok") -> LLMResponse:
    """建立標準測試用 LLMResponse。"""
    return LLMResponse(
        content=content,
        model="test-model",
        provider="test",
        usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    )


def _minimal_config(**provider_overrides: LLMProviderConfig) -> GlobalConfig:
    """建立含 provider 設定的 GlobalConfig。"""
    return GlobalConfig(
        default_model="ollama/qwen3:14b",
        providers=provider_overrides,
    )


# ─────────────────────────────────────────────
# Ollama 路由測試
# ─────────────────────────────────────────────

class TestOllamaRouting:
    """Ollama provider 路由到 OpenAICompatProvider 的測試。"""

    def test_ollama_routes_to_openai_compat_provider(self) -> None:
        """ollama/* 應路由到 OpenAICompatProvider 實例。"""
        router = LLMRouter(_minimal_config())

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("ollama/qwen3:14b", "test prompt")

        provider = router._providers["ollama"]
        assert isinstance(provider, OpenAICompatProvider)

    def test_ollama_default_base_url_is_localhost(self) -> None:
        """未指定 base_url 時，Ollama 應預設使用 localhost:11434/v1。"""
        router = LLMRouter(_minimal_config())

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("ollama/llama3", "hello")

        provider = router._providers["ollama"]
        assert isinstance(provider, OpenAICompatProvider)
        assert "localhost" in provider.base_url
        assert "11434" in provider.base_url

    def test_ollama_custom_base_url_is_applied(self) -> None:
        """自訂 base_url 應被正確傳入 OpenAICompatProvider。"""
        custom_url = "http://192.168.1.100:11434/v1"
        config = _minimal_config(
            ollama=LLMProviderConfig(base_url=custom_url)
        )
        router = LLMRouter(config)

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("ollama/qwen3:14b", "test")

        provider = router._providers["ollama"]
        assert provider.base_url == custom_url

    def test_ollama_uses_dummy_api_key(self) -> None:
        """Ollama 應使用 'ollama' 作為 api_key（不需要真實 key）。"""
        router = LLMRouter(_minimal_config())

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("ollama/qwen3:14b", "test")

        provider = router._providers["ollama"]
        assert provider.api_key == "ollama"

    def test_ollama_provider_name(self) -> None:
        """Ollama OpenAICompatProvider 的 provider_name 應返回 'ollama'。"""
        provider = OpenAICompatProvider(
            api_key="ollama",
            model="qwen3:14b",
            base_url="http://localhost:11434/v1",
        )
        assert provider.provider_name == "ollama"


# ─────────────────────────────────────────────
# OpenAI 路由測試
# ─────────────────────────────────────────────

class TestOpenAIRouting:
    """OpenAI provider 路由到 OpenAICompatProvider 的測試。"""

    def test_openai_routes_to_openai_compat_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """openai/* 應路由到 OpenAICompatProvider。"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        router = LLMRouter(_minimal_config())

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("openai/gpt-4o-mini", "test")

        provider = router._providers["openai"]
        assert isinstance(provider, OpenAICompatProvider)

    def test_openai_reads_api_key_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OpenAI provider 應從 OPENAI_API_KEY 環境變數讀取 api_key。"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-my-real-key")
        router = LLMRouter(_minimal_config())

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("openai/gpt-4o-mini", "test")

        provider = router._providers["openai"]
        assert provider.api_key == "sk-my-real-key"

    def test_openai_custom_api_key_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """自訂 api_key_env 應從指定環境變數讀取 key。"""
        monkeypatch.setenv("MY_CUSTOM_OPENAI_KEY", "sk-custom-key")
        config = _minimal_config(
            openai=LLMProviderConfig(api_key_env="MY_CUSTOM_OPENAI_KEY")
        )
        router = LLMRouter(config)

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("openai/gpt-4o-mini", "test")

        provider = router._providers["openai"]
        assert provider.api_key == "sk-custom-key"

    def test_openai_default_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """未指定 base_url 時，OpenAI 應預設使用 api.openai.com/v1。"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        router = LLMRouter(_minimal_config())

        with patch.object(OpenAICompatProvider, "generate", return_value=_make_response()):
            router.call("openai/gpt-4o", "test")

        provider = router._providers["openai"]
        assert "openai.com" in provider.base_url

    def test_openai_provider_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """指向 openai.com 的 OpenAICompatProvider 的 provider_name 應為 'openai'。"""
        provider = OpenAICompatProvider(
            api_key="sk-test",
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
        )
        assert provider.provider_name == "openai"


# ─────────────────────────────────────────────
# Gemini 路由測試
# ─────────────────────────────────────────────

class TestGeminiRouting:
    """Gemini provider 路由到 GeminiProvider 的測試。"""

    def test_gemini_routes_to_gemini_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """gemini/* 應路由到 GeminiProvider 實例。"""
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
        router = LLMRouter(_minimal_config())

        with patch.object(GeminiProvider, "generate", return_value=_make_response()):
            router.call("gemini/gemini-2.0-flash", "test")

        provider = router._providers["gemini"]
        assert isinstance(provider, GeminiProvider)

    def test_gemini_reads_api_key_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gemini provider 應從 GEMINI_API_KEY 環境變數讀取 api_key。"""
        monkeypatch.setenv("GEMINI_API_KEY", "my-gemini-secret")
        router = LLMRouter(_minimal_config())

        with patch.object(GeminiProvider, "generate", return_value=_make_response()):
            router.call("gemini/gemini-2.0-flash", "test")

        provider = router._providers["gemini"]
        assert provider.api_key == "my-gemini-secret"

    def test_gemini_can_be_instantiated_directly(self) -> None:
        """GeminiProvider 應能直接實例化（不呼叫真實 API）。"""
        provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")
        assert provider.api_key == "fake-key"
        assert provider.model == "gemini-2.0-flash"
        assert provider.provider_name == "gemini"

    def test_gemini_custom_api_key_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """自訂 api_key_env 應被正確使用。"""
        monkeypatch.setenv("MY_GEMINI_KEY", "custom-gemini-key")
        config = _minimal_config(
            gemini=LLMProviderConfig(api_key_env="MY_GEMINI_KEY")
        )
        router = LLMRouter(config)

        with patch.object(GeminiProvider, "generate", return_value=_make_response()):
            router.call("gemini/gemini-2.5-pro", "test")

        provider = router._providers["gemini"]
        assert provider.api_key == "custom-gemini-key"


# ─────────────────────────────────────────────
# 未知 Provider 錯誤測試
# ─────────────────────────────────────────────

class TestUnknownProviderError:
    """未知 provider 應拋出清楚錯誤訊息的測試。"""

    def test_unknown_provider_raises_value_error(self) -> None:
        """未知 provider 應拋出 ValueError。"""
        router = LLMRouter(_minimal_config())
        with pytest.raises(ValueError):
            router.call("foobar/some-model", "test")

    def test_unknown_provider_error_message_is_clear(self) -> None:
        """ValueError 訊息應說明不支援的 provider 及支援清單。"""
        router = LLMRouter(_minimal_config())
        with pytest.raises(ValueError, match="未知的 LLM Provider"):
            router.call("xyz/model-v1", "test")

    def test_unknown_provider_mentions_supported_list(self) -> None:
        """錯誤訊息應列出支援的 provider 名稱。"""
        router = LLMRouter(_minimal_config())
        with pytest.raises(ValueError) as exc_info:
            router.call("notreal/model", "test")
        msg = str(exc_info.value)
        # 錯誤訊息應提及支援的 provider
        assert "ollama" in msg or "openai" in msg or "gemini" in msg

    def test_invalid_format_raises_validation_error(self) -> None:
        """不含斜線的 model_ref 應拋出 AgentForgeValidationError。"""
        from agentforge.schema import AgentForgeValidationError

        router = LLMRouter(_minimal_config())
        with pytest.raises(AgentForgeValidationError):
            router.call("no-slash-model", "test")
