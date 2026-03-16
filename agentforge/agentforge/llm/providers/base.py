# -*- coding: utf-8 -*-
"""LLM Provider 抽象基底類別。

所有 Provider 必須繼承此類別，實作 generate / chat / test_connection 方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class LLMResponse:
    """統一的 LLM 回應格式（不可變）。

    Attributes:
        content: 模型產生的文字內容
        model: 使用的模型名稱
        provider: Provider 名稱
        usage: token 使用量（prompt_tokens, completion_tokens, total_tokens）
        raw: 原始 API 回應（除錯用）
    """

    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    raw: Optional[Any] = field(default=None, repr=False)


class BaseProvider(ABC):
    """所有 LLM Provider 的抽象基底類別。

    子類別需實作：generate, agenerate, chat, achat, test_connection
    """

    def __init__(self, api_key: str, model: str, **kwargs: Any) -> None:
        if not api_key:
            raise ValueError(f"{self.provider_name} 需要 API key")
        if not model:
            raise ValueError(f"{self.provider_name} 需要指定模型名稱")
        self.api_key = api_key
        self.model = model
        self.extra_config = kwargs

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名稱，用於識別和日誌。"""
        ...

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """同步產生文字回應。

        Args:
            prompt: 使用者提示詞
            **kwargs: 額外參數（temperature, max_tokens 等）

        Returns:
            LLMResponse 統一回應格式
        """
        ...

    @abstractmethod
    async def agenerate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """非同步產生文字回應。"""
        ...

    @abstractmethod
    def chat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """同步對話模式。

        Args:
            messages: 對話訊息列表，格式 [{"role": "user", "content": "..."}]
            **kwargs: 額外參數

        Returns:
            LLMResponse 統一回應格式
        """
        ...

    @abstractmethod
    async def achat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> LLMResponse:
        """非同步對話模式。"""
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """測試 API 連線是否正常。

        Returns:
            True 表示連線成功
        """
        ...
