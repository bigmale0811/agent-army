# -*- coding: utf-8 -*-
"""LLM 路由器模組 — 根據 model 字串自動選擇適合的 Provider。

LLMRouter 封裝了 Provider 的建立邏輯，提供統一的 call() 介面，
支援 ollama / openai / gemini 三大 provider，並快取已建立的 Provider 實例。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from agentforge.llm.providers.base import BaseProvider
from agentforge.llm.providers.claude_code import ClaudeCodeProvider
from agentforge.llm.providers.gemini import GeminiProvider
from agentforge.llm.providers.openai_compat import OpenAICompatProvider
from agentforge.schema import GlobalConfig, validate_model_string

# 每個 token 的估算費率（美元），用於本地或無 usage 資訊時的費用估算
_COST_PER_TOKEN_FALLBACK = 0.0


@dataclass(frozen=True)
class LLMCallResult:
    """LLM 呼叫結果（不可變）。

    Attributes:
        content: 模型回應的文字內容。
        model: 實際使用的模型名稱。
        tokens_in: 輸入 token 數量。
        tokens_out: 輸出 token 數量。
        cost_usd: 本次呼叫費用（美元）。
    """

    content: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class LLMRouter:
    """LLM 路由器 — 根據 model_ref 自動路由到對應的 Provider。

    支援的 provider：
    - ollama：本地 Ollama 服務（http://localhost:11434/v1）
    - openai：OpenAI API
    - gemini：Google Gemini API
    - claude-code：Claude Code CLI（訂閱制）

    Provider 實例採延遲建立並快取，避免重複初始化。
    """

    def __init__(self, config: GlobalConfig) -> None:
        """初始化 LLM 路由器。

        Args:
            config: 全域設定，包含各 Provider 的 API key 設定。
        """
        self._config = config
        # 快取已建立的 Provider 實例（key: provider_name）
        self._providers: dict[str, BaseProvider] = {}

    def call(
        self,
        model_ref: str,
        prompt: str,
        context: str = "",
    ) -> LLMCallResult:
        """呼叫指定模型生成文字回應。

        Args:
            model_ref: 模型參照字串，格式為 provider/model-name。
            prompt: 主要提示詞。
            context: 附加輸入文字（可選），若非空則合併到 prompt 後方。

        Returns:
            LLMCallResult 包含回應內容與 token 用量。

        Raises:
            AgentForgeValidationError: model_ref 格式錯誤。
            ValueError: 未知的 provider。
        """
        provider_name, model_name = validate_model_string(model_ref)
        provider = self._get_or_create_provider(provider_name, model_name)

        # 合併 prompt 與 context
        full_prompt = f"{prompt}\n\n{context}".strip() if context else prompt

        response = provider.generate(full_prompt, model=model_name)

        # 解析 token 用量
        tokens_in = 0
        tokens_out = 0
        if response.usage:
            tokens_in = response.usage.get("prompt_tokens", 0)
            tokens_out = response.usage.get("completion_tokens", 0)

        return LLMCallResult(
            content=response.content,
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=_COST_PER_TOKEN_FALLBACK,
        )

    def _get_or_create_provider(
        self, provider_name: str, model_name: str
    ) -> BaseProvider:
        """取得或建立 Provider 實例（延遲初始化並快取）。

        Args:
            provider_name: Provider 名稱（ollama / openai / gemini）。
            model_name: 模型名稱（傳入 Provider 作為預設模型）。

        Returns:
            對應的 BaseProvider 實例。

        Raises:
            ValueError: 未知的 provider 名稱。
        """
        if provider_name in self._providers:
            return self._providers[provider_name]

        provider = self._create_provider(provider_name, model_name)
        self._providers[provider_name] = provider
        return provider

    def _create_provider(
        self, provider_name: str, model_name: str
    ) -> BaseProvider:
        """根據 provider_name 建立對應的 Provider 實例。

        Args:
            provider_name: Provider 名稱。
            model_name: 模型名稱，作為 Provider 的預設模型。

        Returns:
            新建立的 BaseProvider 實例。

        Raises:
            ValueError: 未知的 provider 名稱。
        """
        provider_cfg = self._config.providers.get(provider_name)

        if provider_name == "ollama":
            # Ollama 使用 OpenAI 相容 API，無需真實 API key
            base_url = (
                provider_cfg.base_url
                if provider_cfg and provider_cfg.base_url
                else "http://localhost:11434/v1"
            )
            return OpenAICompatProvider(
                api_key="ollama",
                model=model_name,
                base_url=base_url,
            )

        elif provider_name == "openai":
            # 從環境變數讀取 API key
            env_var = (
                provider_cfg.api_key_env
                if provider_cfg and provider_cfg.api_key_env
                else "OPENAI_API_KEY"
            )
            api_key = os.environ.get(env_var, "")
            base_url = (
                provider_cfg.base_url
                if provider_cfg and provider_cfg.base_url
                else "https://api.openai.com/v1"
            )
            return OpenAICompatProvider(
                api_key=api_key,
                model=model_name,
                base_url=base_url,
            )

        elif provider_name == "gemini":
            env_var = (
                provider_cfg.api_key_env
                if provider_cfg and provider_cfg.api_key_env
                else "GEMINI_API_KEY"
            )
            api_key = os.environ.get(env_var, "")
            return GeminiProvider(
                api_key=api_key,
                model=model_name,
            )

        elif provider_name == "claude-code":
            # Claude Code CLI 訂閱制，不需要 API key
            return ClaudeCodeProvider(model=model_name)

        else:
            raise ValueError(
                f"未知的 LLM Provider：'{provider_name}'。"
                f"支援的 Provider：ollama、openai、gemini、claude-code。"
            )
