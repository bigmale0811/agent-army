"""Plugin 基礎類別 — 所有遊戲商 Adapter 的抽象介面"""
from __future__ import annotations
from abc import ABC, abstractmethod
from slot_cloner.models.game import GameFingerprint, GameModel
from slot_cloner.models.asset import AssetBundle


class BaseAdapter(ABC):
    """遊戲商適配器基礎類別

    每個遊戲商（ATG、PG Soft 等）需實作此介面。
    Pipeline 透過 PluginRegistry 自動選擇合適的 Adapter。
    """

    @staticmethod
    @abstractmethod
    def can_handle(url: str, fingerprint: GameFingerprint | None = None) -> bool:
        """判斷此 Adapter 是否能處理該遊戲 URL"""

    @abstractmethod
    async def recon(self, url: str, **kwargs) -> GameFingerprint:
        """偵察遊戲技術指紋"""

    @abstractmethod
    async def scrape(self, fingerprint: GameFingerprint, **kwargs) -> AssetBundle:
        """擷取遊戲資源"""

    @abstractmethod
    async def reverse(self, fingerprint: GameFingerprint, assets: AssetBundle, **kwargs) -> GameModel:
        """逆向分析遊戲邏輯"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter 名稱"""
