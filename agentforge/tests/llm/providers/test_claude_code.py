# -*- coding: utf-8 -*-
"""ClaudeCodeProvider 單元測試。

所有 subprocess 呼叫均使用 mock，不實際呼叫 claude CLI。
測試覆蓋：初始化、generate、agenerate、chat、achat、test_connection、
JSON 解析、fallback、錯誤處理、費用計算等。
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentforge.llm.providers.base import LLMResponse
from agentforge.llm.providers.claude_code import ClaudeCodeProvider


class TestClaudeCodeProviderInit:
    """ClaudeCodeProvider 初始化測試。"""

    def test_default_model(self) -> None:
        """預設模型應為 claude-sonnet-4-20250514。"""
        p = ClaudeCodeProvider()
        assert p.model == "claude-sonnet-4-20250514"

    def test_custom_model(self) -> None:
        """可自訂模型名稱。"""
        p = ClaudeCodeProvider(model="claude-opus-4-20250514")
        assert p.model == "claude-opus-4-20250514"

    def test_api_key_is_subscription(self) -> None:
        """api_key 應固定為 'subscription'。"""
        p = ClaudeCodeProvider()
        assert p.api_key == "subscription"

    def test_provider_name(self) -> None:
        """provider_name 應回傳 'claude-code'。"""
        p = ClaudeCodeProvider()
        assert p.provider_name == "claude-code"


class TestClaudeCodeGenerate:
    """generate() 方法測試。"""

    def test_generate_success(self) -> None:
        """mock subprocess 回傳有效 JSON，應正確解析 content。"""
        p = ClaudeCodeProvider()
        cli_output = json.dumps({
            "type": "result",
            "result": "Hello from Claude CLI",
            "cost_usd": 0.003,
            "is_error": False,
        })
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = cli_output

        with patch("subprocess.run", return_value=mock_result):
            response = p.generate("Say hello")

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello from Claude CLI"
        assert response.provider == "claude-code"
        assert response.model == "claude-sonnet-4-20250514"
        # token 估算：len("Hello from Claude CLI") // 4
        assert response.usage is not None
        assert response.usage["total_tokens"] > 0

    def test_generate_json_fallback(self) -> None:
        """mock 回傳非 JSON 文字，應 fallback 到純文字。"""
        p = ClaudeCodeProvider()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "This is plain text output"

        with patch("subprocess.run", return_value=mock_result):
            response = p.generate("Say hello")

        assert response.content == "This is plain text output"
        assert response.provider == "claude-code"

    def test_generate_cli_not_found(self) -> None:
        """mock FileNotFoundError，應拋出含安裝提示的 RuntimeError。"""
        p = ClaudeCodeProvider()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="claude CLI"):
                p.generate("Say hello")

    def test_generate_timeout(self) -> None:
        """mock TimeoutExpired，應拋出含超時提示的 RuntimeError。"""
        p = ClaudeCodeProvider()

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120),
        ):
            with pytest.raises(RuntimeError, match="超時"):
                p.generate("Say hello")

    def test_generate_nonzero_exit(self) -> None:
        """mock returncode=1，應拋出含錯誤訊息的 RuntimeError。"""
        p = ClaudeCodeProvider()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "CLI error occurred"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="錯誤"):
                p.generate("Say hello")

    def test_generate_is_error_true(self) -> None:
        """JSON 中 is_error=true，應拋出 RuntimeError。"""
        p = ClaudeCodeProvider()
        cli_output = json.dumps({
            "type": "result",
            "result": "Something went wrong",
            "cost_usd": 0.0,
            "is_error": True,
        })
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = cli_output

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Something went wrong"):
                p.generate("Say hello")

    def test_generate_model_override(self) -> None:
        """kwargs 中指定 model 應覆蓋預設模型。"""
        p = ClaudeCodeProvider()
        cli_output = json.dumps({
            "type": "result",
            "result": "ok",
            "cost_usd": 0.0,
            "is_error": False,
        })
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = cli_output

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            response = p.generate("test", model="claude-opus-4-20250514")

        # 確認呼叫時傳入了指定模型
        call_args = mock_run.call_args[0][0]
        assert "claude-opus-4-20250514" in call_args
        assert response.model == "claude-opus-4-20250514"

    def test_generate_token_estimation(self) -> None:
        """token 估算應為 len(content) // 4。"""
        p = ClaudeCodeProvider()
        content_text = "A" * 100  # 100 字元 → 估算 25 tokens
        cli_output = json.dumps({
            "type": "result",
            "result": content_text,
            "cost_usd": 0.0,
            "is_error": False,
        })
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = cli_output

        with patch("subprocess.run", return_value=mock_result):
            response = p.generate("test")

        assert response.usage is not None
        assert response.usage["completion_tokens"] == 25


class TestClaudeCodeAgenerate:
    """agenerate() 非同步方法測試。"""

    def test_agenerate_success(self) -> None:
        """非同步呼叫 claude CLI 應正確回傳 LLMResponse。"""
        p = ClaudeCodeProvider()
        cli_output = json.dumps({
            "type": "result",
            "result": "Async hello",
            "cost_usd": 0.001,
            "is_error": False,
        })

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            cli_output.encode("utf-8"),
            b"",
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            response = asyncio.get_event_loop().run_until_complete(
                p.agenerate("Say hello async")
            )

        assert isinstance(response, LLMResponse)
        assert response.content == "Async hello"

    def test_agenerate_cli_not_found(self) -> None:
        """非同步 FileNotFoundError 應拋出 RuntimeError。"""
        p = ClaudeCodeProvider()

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(RuntimeError, match="claude CLI"):
                asyncio.get_event_loop().run_until_complete(
                    p.agenerate("test")
                )


class TestClaudeCodeChat:
    """chat() / achat() 方法測試。"""

    def test_chat_merges_messages(self) -> None:
        """多個 messages 應合併為單一 prompt 後呼叫 generate。"""
        p = ClaudeCodeProvider()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        mock_response = LLMResponse(
            content="I am fine",
            model="claude-sonnet-4-20250514",
            provider="claude-code",
        )

        with patch.object(p, "generate", return_value=mock_response) as mock_gen:
            result = p.chat(messages)

        # 驗證合併後的 prompt 包含所有訊息
        merged_prompt = mock_gen.call_args[0][0]
        assert "You are helpful." in merged_prompt
        assert "Hello" in merged_prompt
        assert "Hi there" in merged_prompt
        assert "How are you?" in merged_prompt
        assert result.content == "I am fine"

    def test_achat_calls_agenerate(self) -> None:
        """achat 應合併 messages 後呼叫 agenerate。"""
        p = ClaudeCodeProvider()
        messages = [
            {"role": "user", "content": "Hi"},
        ]

        mock_response = LLMResponse(
            content="Hello",
            model="claude-sonnet-4-20250514",
            provider="claude-code",
        )

        with patch.object(
            p, "agenerate", return_value=mock_response
        ) as mock_agen:
            result = asyncio.get_event_loop().run_until_complete(
                p.achat(messages)
            )

        assert mock_agen.called
        assert result.content == "Hello"


class TestClaudeCodeTestConnection:
    """test_connection() 方法測試。"""

    def test_test_connection_success(self) -> None:
        """claude --version 成功應回傳 True。"""
        p = ClaudeCodeProvider()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            assert p.test_connection() is True

    def test_test_connection_fail(self) -> None:
        """claude --version 失敗應回傳 False。"""
        p = ClaudeCodeProvider()
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            assert p.test_connection() is False

    def test_test_connection_exception(self) -> None:
        """subprocess 拋出例外應回傳 False。"""
        p = ClaudeCodeProvider()

        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert p.test_connection() is False


class TestClaudeCodeCost:
    """費用相關測試。"""

    def test_cost_is_zero(self) -> None:
        """claude-code provider 費用應為 $0（訂閱制）。"""
        from agentforge.llm.budget import BudgetTracker

        cost = BudgetTracker.calculate_cost(
            "claude-code/claude-sonnet-4-20250514", 10000, 5000
        )
        assert cost == 0.0
