"""測試 LLM Config 模組。"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.llm.config import (
    ProviderConfig,
    get_available_providers,
    get_default_provider,
    get_provider_config,
    get_provider_configs,
    load_config,
)

# 測試用的 YAML 設定檔路徑
_TEST_CONFIG = Path(__file__).parent.parent.parent / "config" / "llm_providers.yaml"


class TestProviderConfig:
    """ProviderConfig 資料類別測試。"""

    def test_create_provider_config(self):
        """建立 ProviderConfig 實例。"""
        config = ProviderConfig(
            name="test",
            api_key_env="TEST_API_KEY",
            default_model="test-model",
            description="測試用",
            base_url="https://api.test.com/v1",
        )
        assert config.name == "test"
        assert config.api_key_env == "TEST_API_KEY"
        assert config.default_model == "test-model"
        assert config.base_url == "https://api.test.com/v1"

    def test_api_key_from_env(self):
        """從環境變數讀取 API key。"""
        config = ProviderConfig(
            name="test",
            api_key_env="TEST_LLM_KEY",
            default_model="test-model",
        )
        with patch.dict(os.environ, {"TEST_LLM_KEY": "sk-test-123"}):
            assert config.api_key == "sk-test-123"
            assert config.is_available is True

    def test_api_key_missing(self):
        """環境變數不存在時 API key 為 None。"""
        config = ProviderConfig(
            name="test",
            api_key_env="NONEXISTENT_KEY_12345",
            default_model="test-model",
        )
        # 確保環境變數不存在
        os.environ.pop("NONEXISTENT_KEY_12345", None)
        assert config.api_key is None
        assert config.is_available is False

    def test_is_gemini(self):
        """Gemini Provider 識別。"""
        gemini = ProviderConfig(name="gemini", api_key_env="X", default_model="x")
        other = ProviderConfig(name="openai", api_key_env="X", default_model="x")
        assert gemini.is_gemini is True
        assert other.is_gemini is False

    def test_frozen(self):
        """ProviderConfig 是不可變的。"""
        config = ProviderConfig(name="test", api_key_env="X", default_model="x")
        with pytest.raises(AttributeError):
            config.name = "changed"  # type: ignore[misc]


class TestLoadConfig:
    """設定檔載入測試。"""

    def test_load_existing_config(self):
        """載入現有的設定檔。"""
        config = load_config(_TEST_CONFIG)
        assert "providers" in config
        assert "openai" in config["providers"]
        assert "deepseek" in config["providers"]
        assert "gemini" in config["providers"]

    def test_load_missing_config(self, tmp_path):
        """設定檔不存在時回傳空設定。"""
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config == {"providers": {}, "default_provider": "openai"}

    def test_get_provider_configs(self):
        """取得所有 Provider 設定。"""
        configs = get_provider_configs(_TEST_CONFIG)
        assert len(configs) >= 5
        names = [c.name for c in configs]
        assert "openai" in names
        assert "deepseek" in names
        assert "gemini" in names

    def test_get_provider_config(self):
        """取得指定 Provider 設定。"""
        config = get_provider_config("openai", _TEST_CONFIG)
        assert config is not None
        assert config.name == "openai"
        assert config.default_model == "gpt-4o-mini"
        assert config.base_url == "https://api.openai.com/v1"

    def test_get_nonexistent_provider(self):
        """查詢不存在的 Provider 回傳 None。"""
        config = get_provider_config("nonexistent", _TEST_CONFIG)
        assert config is None


class TestDefaultProvider:
    """預設 Provider 測試。"""

    def test_default_from_config(self):
        """從設定檔讀取預設 Provider。"""
        default = get_default_provider(_TEST_CONFIG)
        assert default == "openai"

    def test_default_from_env(self):
        """環境變數覆蓋設定檔的預設值。"""
        with patch.dict(os.environ, {"DEFAULT_LLM_PROVIDER": "deepseek"}):
            default = get_default_provider(_TEST_CONFIG)
            assert default == "deepseek"


class TestAvailableProviders:
    """可用 Provider 測試。"""

    def test_no_keys_set(self):
        """未設定任何 API key 時沒有可用 Provider。"""
        # 清除所有可能的 API key 環境變數
        env_cleanup = {
            "OPENAI_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "GROQ_API_KEY": "",
            "TOGETHER_API_KEY": "",
            "GOOGLE_API_KEY": "",
        }
        with patch.dict(os.environ, env_cleanup, clear=False):
            # 需要額外移除這些 key
            for key in env_cleanup:
                os.environ.pop(key, None)
            available = get_available_providers(_TEST_CONFIG)
            assert len(available) == 0

    def test_with_one_key(self):
        """設定一個 API key 後有一個可用 Provider。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            available = get_available_providers(_TEST_CONFIG)
            names = [p.name for p in available]
            assert "openai" in names
