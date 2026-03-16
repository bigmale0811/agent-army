# -*- coding: utf-8 -*-
"""LLMRouter 單元測試。

所有 Provider 呼叫均使用 mock，不實際連接外部 API。
測試 LLMRouter 的路由邏輯、Provider 建立、快取機制及結果映射。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.llm.providers.base import LLMResponse
from agentforge.llm.router import LLMCallResult, LLMRouter
from agentforge.schema import GlobalConfig, LLMProviderConfig


@pytest.fixture
def minimal_config() -> GlobalConfig:
    """最小化的 GlobalConfig（無自訂 provider 設定）。"""
    return GlobalConfig(default_model="ollama/qwen3:14b")


@pytest.fixture
def full_config() -> GlobalConfig:
    """含 provider 設定的 GlobalConfig。"""
    return GlobalConfig(
        default_model="openai/gpt-4o-mini",
        providers={
            "openai": LLMProviderConfig(api_key_env="MY_OPENAI_KEY"),
            "gemini": LLMProviderConfig(api_key_env="MY_GEMINI_KEY"),
            "ollama": LLMProviderConfig(base_url="http://localhost:11434/v1"),
        },
    )


def _make_llm_response(content: str = "test response") -> LLMResponse:
    """建立測試用 LLMResponse。"""
    return LLMResponse(
        content=content,
        model="test-model",
        provider="test",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    )


class TestLLMRouterCall:
    """call() 方法測試。"""

    def test_call_ollama_returns_result(self, minimal_config: GlobalConfig) -> None:
        """呼叫 ollama provider 應回傳 LLMCallResult。"""
        router = LLMRouter(minimal_config)
        mock_response = _make_llm_response("Hello from Ollama")

        with patch(
            "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
            return_value=mock_response,
        ):
            result = router.call("ollama/qwen3:14b", "Say hi")

        assert isinstance(result, LLMCallResult)
        assert result.content == "Hello from Ollama"
        assert result.model == "qwen3:14b"
        assert result.tokens_in == 10
        assert result.tokens_out == 20

    def test_call_with_context(self, minimal_config: GlobalConfig) -> None:
        """提供 context 時應將 prompt 和 context 合併傳入 Provider。"""
        router = LLMRouter(minimal_config)
        mock_response = _make_llm_response("combined response")

        with patch(
            "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
            return_value=mock_response,
        ) as mock_gen:
            router.call("ollama/qwen3:14b", "Analyze:", "some context data")

        # 驗證合併後的 prompt 被傳入
        call_args = mock_gen.call_args[0][0]
        assert "Analyze:" in call_args
        assert "some context data" in call_args

    def test_call_without_usage(self, minimal_config: GlobalConfig) -> None:
        """Provider 未回傳 usage 時，tokens 應為 0。"""
        router = LLMRouter(minimal_config)
        mock_response = LLMResponse(
            content="no usage info",
            model="test-model",
            provider="test",
            usage=None,
        )

        with patch(
            "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
            return_value=mock_response,
        ):
            result = router.call("ollama/test-model", "prompt")

        assert result.tokens_in == 0
        assert result.tokens_out == 0

    def test_call_invalid_model_raises(self, minimal_config: GlobalConfig) -> None:
        """格式錯誤的 model_ref 應拋出 AgentForgeValidationError。"""
        from agentforge.schema import AgentForgeValidationError

        router = LLMRouter(minimal_config)
        with pytest.raises(AgentForgeValidationError):
            router.call("invalid-model-no-slash", "prompt")

    def test_call_unknown_provider_raises(self, minimal_config: GlobalConfig) -> None:
        """未知的 provider 應拋出 ValueError。"""
        router = LLMRouter(minimal_config)
        with pytest.raises(ValueError, match="未知的 LLM Provider"):
            router.call("unknown_provider/model", "prompt")


class TestLLMRouterProviderCreation:
    """Provider 建立與快取測試。"""

    def test_ollama_provider_uses_localhost(
        self, minimal_config: GlobalConfig
    ) -> None:
        """Ollama provider 預設應使用 localhost:11434。"""
        from agentforge.llm.providers.openai_compat import OpenAICompatProvider

        router = LLMRouter(minimal_config)

        with patch(
            "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
            return_value=_make_llm_response(),
        ):
            router.call("ollama/qwen3:14b", "test")

        provider = router._providers["ollama"]
        assert isinstance(provider, OpenAICompatProvider)
        assert "11434" in provider.base_url or "localhost" in provider.base_url

    def test_provider_is_cached(self, minimal_config: GlobalConfig) -> None:
        """同一 provider 第二次呼叫時應使用快取實例。"""
        router = LLMRouter(minimal_config)

        with patch(
            "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
            return_value=_make_llm_response(),
        ):
            router.call("ollama/qwen3:14b", "first call")
            router.call("ollama/qwen3:14b", "second call")

        # 確認 _providers 中只有一個 ollama 實例
        assert len(router._providers) == 1

    def test_openai_provider_reads_env_var(
        self, full_config: GlobalConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OpenAI provider 應從環境變數讀取 API key。"""
        monkeypatch.setenv("MY_OPENAI_KEY", "sk-test-key")
        router = LLMRouter(full_config)

        with patch(
            "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
            return_value=_make_llm_response(),
        ):
            router.call("openai/gpt-4o-mini", "test")

        provider = router._providers["openai"]
        assert provider.api_key == "sk-test-key"

    def test_gemini_provider_reads_env_var(
        self, full_config: GlobalConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gemini provider 應從環境變數讀取 API key。"""
        monkeypatch.setenv("MY_GEMINI_KEY", "gemini-test-key")
        router = LLMRouter(full_config)

        with patch(
            "agentforge.llm.providers.gemini.GeminiProvider.generate",
            return_value=_make_llm_response(),
        ):
            router.call("gemini/gemini-2.0-flash", "test")

        provider = router._providers["gemini"]
        assert provider.api_key == "gemini-test-key"

    def test_custom_ollama_base_url(self, full_config: GlobalConfig) -> None:
        """自訂 Ollama base_url 應被正確傳入 Provider。"""
        router = LLMRouter(full_config)

        with patch(
            "agentforge.llm.providers.openai_compat.OpenAICompatProvider.generate",
            return_value=_make_llm_response(),
        ):
            router.call("ollama/qwen3:14b", "test")

        provider = router._providers["ollama"]
        assert provider.base_url == "http://localhost:11434/v1"
