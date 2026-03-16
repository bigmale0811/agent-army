# -*- coding: utf-8 -*-
"""GlobalConfig / LLMProviderConfig / BudgetConfig 的單元測試。"""

import pytest
from pydantic import ValidationError

from agentforge.schema.config import (
    BudgetConfig,
    GlobalConfig,
    LLMProviderConfig,
)


class TestValidConfig:
    """合法設定應正確解析。"""

    def test_valid_config(self) -> None:
        """完整的全域設定應正確建立。"""
        config = GlobalConfig(
            default_model="openai/gpt-4o-mini",
            providers={
                "openai": LLMProviderConfig(
                    api_key_env="OPENAI_API_KEY",
                    base_url="https://api.openai.com/v1",
                ),
                "ollama": LLMProviderConfig(
                    base_url="http://localhost:11434/v1",
                ),
            },
            budget=BudgetConfig(
                daily_limit_usd=10.0,
                warn_at_percent=80.0,
            ),
        )
        assert config.default_model == "openai/gpt-4o-mini"
        assert len(config.providers) == 2
        assert config.budget.daily_limit_usd == 10.0


class TestDefaultValues:
    """預設值應正確套用。"""

    def test_default_values(self) -> None:
        """完全不傳參數時，預設值應正確。"""
        config = GlobalConfig()
        assert config.default_model == "openai/gpt-4o-mini"
        assert config.providers == {}
        assert config.budget.daily_limit_usd == 10.0
        assert config.budget.warn_at_percent == 80.0

    def test_budget_defaults(self) -> None:
        budget = BudgetConfig()
        assert budget.daily_limit_usd == 10.0
        assert budget.warn_at_percent == 80.0

    def test_provider_defaults(self) -> None:
        provider = LLMProviderConfig()
        assert provider.api_key_env == ""
        assert provider.base_url is None


class TestProviderConfig:
    """Provider 設定驗證。"""

    def test_provider_config(self) -> None:
        """完整 provider 設定應正確解析。"""
        provider = LLMProviderConfig(
            api_key_env="MY_KEY",
            base_url="https://api.example.com/v1",
        )
        assert provider.api_key_env == "MY_KEY"
        assert provider.base_url == "https://api.example.com/v1"

    def test_frozen_config(self) -> None:
        """GlobalConfig 應不可變。"""
        config = GlobalConfig()
        with pytest.raises(ValidationError):
            config.default_model = "changed"  # type: ignore[misc]

    def test_frozen_budget(self) -> None:
        """BudgetConfig 應不可變。"""
        budget = BudgetConfig()
        with pytest.raises(ValidationError):
            budget.daily_limit_usd = 999.0  # type: ignore[misc]

    def test_frozen_provider(self) -> None:
        """LLMProviderConfig 應不可變。"""
        provider = LLMProviderConfig()
        with pytest.raises(ValidationError):
            provider.api_key_env = "changed"  # type: ignore[misc]
