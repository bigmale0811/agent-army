# -*- coding: utf-8 -*-
"""AgentForge LLM Providers 模組 — 多供應商 LLM Provider 實作。

公開 API：
- BaseProvider: Provider 抽象基底類別
- LLMResponse: 統一回應格式
- OpenAICompatProvider: OpenAI 相容 Provider（含 Ollama）
- GeminiProvider: Google Gemini Provider
"""

from agentforge.llm.providers.base import BaseProvider, LLMResponse
from agentforge.llm.providers.gemini import GeminiProvider
from agentforge.llm.providers.openai_compat import OpenAICompatProvider

__all__ = [
    "BaseProvider",
    "LLMResponse",
    "OpenAICompatProvider",
    "GeminiProvider",
]
