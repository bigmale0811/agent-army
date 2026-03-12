"""Plugin 註冊表 — 自動發現與路由 Adapter"""
from __future__ import annotations
import logging
from slot_cloner.plugins.base import BaseAdapter
from slot_cloner.models.game import GameFingerprint

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Adapter 註冊表 — 管理所有遊戲商適配器"""

    def __init__(self) -> None:
        self._adapters: list[type[BaseAdapter]] = []

    def register(self, adapter_cls: type[BaseAdapter]) -> None:
        """註冊一個 Adapter 類別"""
        if adapter_cls in self._adapters:
            logger.warning("Adapter %s 已註冊，跳過重複註冊", adapter_cls.__name__)
            return
        self._adapters.append(adapter_cls)
        logger.info("已註冊 Adapter: %s", adapter_cls.__name__)

    def find_adapter(
        self,
        url: str,
        fingerprint: GameFingerprint | None = None,
    ) -> BaseAdapter:
        """根據 URL 和指紋找到合適的 Adapter

        遍歷所有已註冊的 Adapter，回傳第一個 can_handle 為 True 的。
        如果都不匹配，回傳 GenericAdapter（兜底）。
        """
        for adapter_cls in self._adapters:
            if adapter_cls.can_handle(url, fingerprint):
                logger.info("選用 Adapter: %s", adapter_cls.__name__)
                return adapter_cls()

        # 兜底：使用 GenericAdapter
        from slot_cloner.plugins.generic.adapter import GenericAdapter
        logger.info("無匹配 Adapter，使用 GenericAdapter")
        return GenericAdapter()

    @property
    def adapters(self) -> list[type[BaseAdapter]]:
        """已註冊的 Adapter 列表"""
        return list(self._adapters)
