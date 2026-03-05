"""測試 LLM Client。"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.llm.client import LLMClient

_TEST_CONFIG = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"


class TestLLMClient:
    """LLMClient 測試。"""

    def test_create_with_valid_provider(self):
        """使用有效的 Provider 和 API key 建立 Client。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            client = LLMClient(
                provider="openai",
                config_path=_TEST_CONFIG,
            )
            assert client.provider_name == "openai"
            assert client.model == "gpt-4o-mini"

    def test_create_with_custom_model(self):
        """指定自訂模型名稱。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            client = LLMClient(
                provider="openai",
                model="gpt-4o",
                config_path=_TEST_CONFIG,
            )
            assert client.model == "gpt-4o"

    def test_create_with_explicit_api_key(self):
        """直接傳入 API key。"""
        client = LLMClient(
            provider="deepseek",
            api_key="sk-explicit-key",
            config_path=_TEST_CONFIG,
        )
        assert client.provider_name == "deepseek"

    def test_unknown_provider_raises(self):
        """不存在的 Provider 拋出 ValueError。"""
        with pytest.raises(ValueError, match="未知的 Provider"):
            LLMClient(provider="nonexistent", config_path=_TEST_CONFIG)

    def test_missing_api_key_raises(self):
        """缺少 API key 拋出 ValueError。"""
        # 確保環境變數不存在
        os.environ.pop("OPENAI_API_KEY", None)
        with pytest.raises(ValueError, match="需要 API key"):
            LLMClient(provider="openai", config_path=_TEST_CONFIG)

    def test_gemini_provider_creation(self):
        """Gemini Provider 正確建立。"""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            client = LLMClient(
                provider="gemini",
                config_path=_TEST_CONFIG,
            )
            assert client.provider_name == "gemini"

    def test_list_all(self):
        """列出所有 Provider。"""
        providers = LLMClient.list_all(_TEST_CONFIG)
        assert len(providers) >= 5
        names = [p["name"] for p in providers]
        assert "openai" in names
        assert "deepseek" in names
        assert "gemini" in names
        # 每個 provider 都有 available 欄位
        for p in providers:
            assert "available" in p

    def test_list_available_no_keys(self):
        """未設定 API key 時沒有可用 Provider。"""
        # 清除所有可能的 key
        keys_to_clear = [
            "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
            "GROQ_API_KEY", "TOGETHER_API_KEY", "GOOGLE_API_KEY",
        ]
        env = {k: "" for k in keys_to_clear}
        with patch.dict(os.environ, env, clear=False):
            for k in keys_to_clear:
                os.environ.pop(k, None)
            available = LLMClient.list_available(_TEST_CONFIG)
            assert len(available) == 0
