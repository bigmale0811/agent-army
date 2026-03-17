# -*- coding: utf-8 -*-
"""LLMRouter claude-code 整合測試。

驗證 Router 能正確路由 claude-code/ 前綴的模型到 ClaudeCodeProvider。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.llm.providers.base import LLMResponse
from agentforge.llm.providers.claude_code import ClaudeCodeProvider
from agentforge.llm.router import LLMCallResult, LLMRouter
from agentforge.schema import GlobalConfig


@pytest.fixture
def config() -> GlobalConfig:
    """最小化的 GlobalConfig。"""
    return GlobalConfig(default_model="ollama/qwen3:14b")


class TestRouterClaudeCode:
    """Router 對 claude-code provider 的路由測試。"""

    def test_route_to_claude_code_provider(self, config: GlobalConfig) -> None:
        """'claude-code/sonnet' 應路由到 ClaudeCodeProvider。"""
        router = LLMRouter(config)

        mock_response = LLMResponse(
            content="Hello from claude-code",
            model="sonnet",
            provider="claude-code",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        )

        with patch.object(
            ClaudeCodeProvider, "generate", return_value=mock_response
        ):
            result = router.call("claude-code/sonnet", "Say hi")

        assert isinstance(result, LLMCallResult)
        assert result.content == "Hello from claude-code"
        assert result.model == "sonnet"

        # 驗證快取的 Provider 是 ClaudeCodeProvider
        provider = router._providers["claude-code"]
        assert isinstance(provider, ClaudeCodeProvider)

    def test_claude_code_provider_cached(self, config: GlobalConfig) -> None:
        """同一 claude-code provider 第二次呼叫應使用快取。"""
        router = LLMRouter(config)

        mock_response = LLMResponse(
            content="ok",
            model="sonnet",
            provider="claude-code",
            usage={"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        )

        with patch.object(
            ClaudeCodeProvider, "generate", return_value=mock_response
        ):
            router.call("claude-code/sonnet", "first")
            router.call("claude-code/opus", "second")

        # 只有一個 claude-code provider 實例
        assert "claude-code" in router._providers
        assert len([k for k in router._providers if k == "claude-code"]) == 1
