# -*- coding: utf-8 -*-
"""Claude Code CLI Provider — 透過 subprocess 呼叫 claude CLI。

使用 Claude Code 訂閱制 CLI，不需要 API key。
透過 `claude -p <prompt> --output-format json --model <model>` 執行推理。
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any, Dict, List, Optional

from agentforge.llm.providers.base import BaseProvider, LLMResponse

# 預設模型名稱
_DEFAULT_MODEL = "claude-sonnet-4-20250514"

# subprocess 超時秒數
_TIMEOUT_SECONDS = 120


class ClaudeCodeProvider(BaseProvider):
    """Claude Code CLI Provider。

    透過 subprocess 呼叫 `claude` CLI 執行推理。
    使用訂閱制（subscription），不需要真實的 API key。

    支援同步與非同步模式：
    - 同步：subprocess.run
    - 非同步：asyncio.create_subprocess_exec
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        **kwargs: Any,
    ) -> None:
        """初始化 ClaudeCodeProvider。

        Args:
            model: 模型名稱，預設為 claude-sonnet-4-20250514。
            **kwargs: 額外設定參數。
        """
        # 傳入 "subscription" 作為 api_key，通過父類別的非空檢查
        super().__init__(api_key="subscription", model=model, **kwargs)

    @property
    def provider_name(self) -> str:
        """Provider 名稱。"""
        return "claude-code"

    def _build_command(self, prompt: str, model: str) -> list[str]:
        """組合 claude CLI 指令。

        Args:
            prompt: 提示詞文字。
            model: 模型名稱。

        Returns:
            指令列表，供 subprocess 使用。
        """
        return [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            model,
        ]

    def _parse_output(self, stdout: str, model: str) -> LLMResponse:
        """解析 claude CLI 的 stdout 輸出。

        嘗試解析為 JSON 格式：
        {"type":"result","result":"...","cost_usd":0.0,"is_error":false}

        若 JSON 解析失敗，fallback 到純文字模式。

        Args:
            stdout: CLI 的標準輸出文字。
            model: 使用的模型名稱。

        Returns:
            LLMResponse 統一回應格式。

        Raises:
            RuntimeError: 當 JSON 中 is_error 為 True 時。
        """
        try:
            data = json.loads(stdout)
            # 檢查是否為錯誤回應
            if data.get("is_error", False):
                raise RuntimeError(
                    f"Claude CLI 回傳錯誤：{data.get('result', '未知錯誤')}"
                )
            content = data.get("result", "")
        except json.JSONDecodeError:
            # JSON 解析失敗，fallback 到純文字
            content = stdout

        # token 估算：約每 4 個字元為 1 個 token
        estimated_tokens = max(len(content) // 4, 1)

        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": estimated_tokens,
                "total_tokens": estimated_tokens,
            },
            raw=stdout,
        )

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """同步產生文字回應 — 透過 subprocess 呼叫 claude CLI。

        Args:
            prompt: 使用者提示詞。
            **kwargs: 額外參數（model 可覆蓋預設模型）。

        Returns:
            LLMResponse 統一回應格式。

        Raises:
            RuntimeError: CLI 找不到、超時、非零退出碼、或 is_error 為 True。
        """
        model = kwargs.pop("model", self.model)
        cmd = self._build_command(prompt, model)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "找不到 claude CLI。請先安裝：npm install -g @anthropic-ai/claude-code"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"claude CLI 執行超時（{_TIMEOUT_SECONDS} 秒）。"
                "請檢查網路連線或嘗試縮短提示詞。"
            )

        if result.returncode != 0:
            stderr_msg = result.stderr.strip() if result.stderr else "未知錯誤"
            raise RuntimeError(
                f"claude CLI 執行錯誤（exit code {result.returncode}）：{stderr_msg}"
            )

        return self._parse_output(result.stdout, model)

    async def agenerate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """非同步產生文字回應 — 透過 asyncio.create_subprocess_exec。

        Args:
            prompt: 使用者提示詞。
            **kwargs: 額外參數（model 可覆蓋預設模型）。

        Returns:
            LLMResponse 統一回應格式。

        Raises:
            RuntimeError: CLI 找不到、超時、非零退出碼、或 is_error 為 True。
        """
        model = kwargs.pop("model", self.model)
        cmd = self._build_command(prompt, model)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "找不到 claude CLI。請先安裝：npm install -g @anthropic-ai/claude-code"
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError(
                f"claude CLI 執行超時（{_TIMEOUT_SECONDS} 秒）。"
                "請檢查網路連線或嘗試縮短提示詞。"
            )

        stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""

        if process.returncode != 0:
            stderr_msg = stderr.strip() if stderr else "未知錯誤"
            raise RuntimeError(
                f"claude CLI 執行錯誤（exit code {process.returncode}）：{stderr_msg}"
            )

        return self._parse_output(stdout, model)

    def _merge_messages(self, messages: List[Dict[str, str]]) -> str:
        """將對話訊息列表合併為單一提示詞文字。

        格式：
        [system]: ...
        [user]: ...
        [assistant]: ...

        Args:
            messages: 對話訊息列表。

        Returns:
            合併後的提示詞字串。
        """
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"[{role}]: {content}")
        return "\n".join(parts)

    def chat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """同步對話模式 — 合併 messages 後呼叫 generate。

        Args:
            messages: 對話訊息列表。
            **kwargs: 額外參數。

        Returns:
            LLMResponse 統一回應格式。
        """
        merged_prompt = self._merge_messages(messages)
        return self.generate(merged_prompt, **kwargs)

    async def achat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """非同步對話模式 — 合併 messages 後呼叫 agenerate。

        Args:
            messages: 對話訊息列表。
            **kwargs: 額外參數。

        Returns:
            LLMResponse 統一回應格式。
        """
        merged_prompt = self._merge_messages(messages)
        return await self.agenerate(merged_prompt, **kwargs)

    def test_connection(self) -> bool:
        """測試 claude CLI 是否可用 — 執行 claude --version。

        Returns:
            True 表示 CLI 可用。
        """
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False
