"""ATG 遊戲商適配器"""
from __future__ import annotations
from slot_cloner.plugins.base import BaseAdapter
from slot_cloner.models.game import GameFingerprint, GameModel, GameConfig
from slot_cloner.models.asset import AssetBundle
from slot_cloner.models.enums import GameType


class ATGAdapter(BaseAdapter):
    """ATG (Agile Titan Games) 適配器

    處理 ATG 旗下遊戲（如戰神賽特 Storm of Seth）。
    特徵：godeebxp.com 網域、PixiJS 引擎、WebSocket 通訊。
    """

    @staticmethod
    def can_handle(url: str, fingerprint: GameFingerprint | None = None) -> bool:
        """ATG 遊戲判定：URL 包含 godeebxp.com"""
        return "godeebxp.com" in url.lower()

    @property
    def name(self) -> str:
        return "atg"

    async def recon(self, url: str, **kwargs) -> GameFingerprint:
        """ATG 偵察 — 使用 ReconEngine + ATG 特有邏輯"""
        from slot_cloner.recon.engine import ReconEngine
        engine = ReconEngine(**kwargs)
        fingerprint = await engine.recon(url)
        # ATG 額外資訊
        return fingerprint.model_copy(update={
            "provider": "atg",
            "extra": {"adapter": "atg", "platform": "godeebxp"},
        })

    async def scrape(self, fingerprint: GameFingerprint, **kwargs) -> AssetBundle:
        """ATG 資源擷取"""
        from slot_cloner.scraper.engine import ScraperEngine
        engine = ScraperEngine(**kwargs)
        return await engine.scrape(fingerprint)

    async def reverse(self, fingerprint: GameFingerprint, assets: AssetBundle, **kwargs) -> GameModel:
        """ATG 逆向分析"""
        from slot_cloner.reverse.engine import ReverseEngine
        engine = ReverseEngine()
        return await engine.reverse(fingerprint, assets)
