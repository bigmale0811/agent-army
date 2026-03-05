"""雲端 LLM 模組 — 統一介面串接多家雲端模型 API。

支援的 Provider：
- OpenAI 相容（OpenAI、DeepSeek、Groq、Together AI）
- Google Gemini

使用方式：
    from src.llm import LLMClient
    client = LLMClient(provider="deepseek")
    result = client.generate("你好")
"""

from .client import LLMClient
from .providers.base import BaseProvider, LLMResponse

__all__ = ["LLMClient", "BaseProvider", "LLMResponse"]
