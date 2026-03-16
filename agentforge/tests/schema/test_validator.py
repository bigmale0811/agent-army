# -*- coding: utf-8 -*-
"""YAML 載入與驗證函式的單元測試。"""

from pathlib import Path

import pytest
import yaml

from agentforge.schema.agent_def import AgentDef
from agentforge.schema.config import GlobalConfig
from agentforge.schema.validator import (
    AgentForgeValidationError,
    load_agent_def,
    load_global_config,
    validate_model_string,
)


# ── fixtures ──────────────────────────────────────────────


@pytest.fixture
def valid_agent_yaml(tmp_path: Path) -> Path:
    """建立合法的 Agent YAML 檔案。"""
    data = {
        "name": "test-agent",
        "description": "測試用 Agent",
        "model": "openai/gpt-4o-mini",
        "max_retries": 3,
        "steps": [
            {"name": "greet", "action": "shell", "command": "echo hello"},
            {"name": "think", "action": "llm", "prompt": "分析一下"},
            {
                "name": "write",
                "action": "save",
                "path": "out.txt",
                "content": "{{ steps.think.output }}",
            },
        ],
    }
    p = tmp_path / "agent.yaml"
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


@pytest.fixture
def invalid_agent_yaml(tmp_path: Path) -> Path:
    """建立驗證會失敗的 Agent YAML（缺少 steps）。"""
    data = {"name": "bad-agent"}
    p = tmp_path / "bad_agent.yaml"
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


@pytest.fixture
def broken_yaml(tmp_path: Path) -> Path:
    """建立語法錯誤的 YAML 檔案。"""
    p = tmp_path / "broken.yaml"
    p.write_text("name: [unclosed bracket", encoding="utf-8")
    return p


@pytest.fixture
def valid_config_yaml(tmp_path: Path) -> Path:
    """建立合法的全域設定 YAML 檔案。"""
    data = {
        "default_model": "openai/gpt-4o-mini",
        "providers": {
            "openai": {
                "api_key_env": "OPENAI_API_KEY",
                "base_url": "https://api.openai.com/v1",
            },
        },
        "budget": {
            "daily_limit_usd": 5.0,
            "warn_at_percent": 90.0,
        },
    }
    p = tmp_path / "agentforge.yaml"
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


# ── load_agent_def ────────────────────────────────────────


class TestLoadAgentDef:
    """load_agent_def 函式測試。"""

    def test_load_agent_def_success(self, valid_agent_yaml: Path) -> None:
        """合法 YAML 應成功載入為 AgentDef。"""
        agent = load_agent_def(valid_agent_yaml)
        assert isinstance(agent, AgentDef)
        assert agent.name == "test-agent"
        assert len(agent.steps) == 3

    def test_load_agent_def_file_not_found(self, tmp_path: Path) -> None:
        """檔案不存在應 raise AgentForgeValidationError。"""
        with pytest.raises(AgentForgeValidationError, match="找不到"):
            load_agent_def(tmp_path / "nonexistent.yaml")

    def test_load_agent_def_invalid_yaml(self, broken_yaml: Path) -> None:
        """YAML 語法錯誤應 raise AgentForgeValidationError。"""
        with pytest.raises(AgentForgeValidationError, match="YAML"):
            load_agent_def(broken_yaml)

    def test_load_agent_def_validation_error(
        self, invalid_agent_yaml: Path
    ) -> None:
        """Pydantic 驗證失敗應 raise 友善的 AgentForgeValidationError。"""
        with pytest.raises(AgentForgeValidationError, match="驗證失敗"):
            load_agent_def(invalid_agent_yaml)


# ── load_global_config ────────────────────────────────────


class TestLoadGlobalConfig:
    """load_global_config 函式測試。"""

    def test_load_global_config_success(
        self, valid_config_yaml: Path
    ) -> None:
        """合法設定 YAML 應成功載入。"""
        config = load_global_config(valid_config_yaml)
        assert isinstance(config, GlobalConfig)
        assert config.default_model == "openai/gpt-4o-mini"
        assert "openai" in config.providers
        assert config.budget.daily_limit_usd == 5.0


# ── validate_model_string ─────────────────────────────────


class TestValidateModelString:
    """validate_model_string 函式測試。"""

    def test_validate_model_string(self) -> None:
        """標準格式應正確解析。"""
        provider, model_name = validate_model_string("openai/gpt-4o")
        assert provider == "openai"
        assert model_name == "gpt-4o"

    def test_validate_model_string_ollama(self) -> None:
        """Ollama 帶冒號的格式應正確解析。"""
        provider, model_name = validate_model_string("ollama/qwen3:14b")
        assert provider == "ollama"
        assert model_name == "qwen3:14b"

    def test_validate_model_string_invalid(self) -> None:
        """缺少 provider 的格式應報錯。"""
        with pytest.raises(AgentForgeValidationError, match="provider/model-name"):
            validate_model_string("gpt-4o")

    def test_validate_model_string_empty(self) -> None:
        """空字串應報錯。"""
        with pytest.raises(AgentForgeValidationError, match="provider/model-name"):
            validate_model_string("")
