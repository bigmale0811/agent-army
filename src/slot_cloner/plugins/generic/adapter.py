"""通用 Adapter — 使用完整引擎組合處理未知遊戲商

與 ATGAdapter 不同，GenericAdapter 不做遊戲商特定的優化，
但仍使用完整的 Recon / Scrape / Reverse 引擎進行通用分析。
"""
from __future__ import annotations
import logging
from pathlib import Path
from slot_cloner.plugins.base import BaseAdapter
from slot_cloner.models.game import GameFingerprint, GameModel, GameConfig
from slot_cloner.models.asset import AssetBundle
from slot_cloner.models.enums import GameType
from slot_cloner.recon.engine import ReconEngine
from slot_cloner.scraper.engine import ScraperEngine
from slot_cloner.reverse.engine import ReverseEngine

logger = logging.getLogger(__name__)


class GenericAdapter(BaseAdapter):
    """通用適配器 — 使用完整引擎組合處理未知遊戲商"""

    def __init__(self, output_dir: Path | None = None, headless: bool = True) -> None:
        self._output_dir = output_dir or Path("./output")
        self._headless = headless

    @staticmethod
    def can_handle(url: str, fingerprint: GameFingerprint | None = None) -> bool:
        return True

    @property
    def name(self) -> str:
        return "generic"

    async def recon(self, url: str, **kwargs) -> GameFingerprint:
        """偵察遊戲技術指紋（使用 ReconEngine）"""
        try:
            engine = ReconEngine(headless=self._headless)
            return await engine.recon(url)
        except Exception as e:
            logger.warning("Generic recon 失敗: %s", e)
            return GameFingerprint(url=url)

    async def scrape(self, fingerprint: GameFingerprint, **kwargs) -> AssetBundle:
        """擷取遊戲資源（使用 ScraperEngine）"""
        try:
            engine = ScraperEngine(output_dir=self._output_dir, headless=self._headless)
            return await engine.scrape(fingerprint)
        except Exception as e:
            logger.warning("Generic scrape 失敗: %s", e)
            return AssetBundle()

    async def reverse(self, fingerprint: GameFingerprint, assets: AssetBundle, **kwargs) -> GameModel:
        """逆向分析遊戲邏輯（使用 ReverseEngine）"""
        try:
            engine = ReverseEngine()
            return await engine.reverse(fingerprint, assets)
        except Exception as e:
            logger.warning("Generic reverse 失敗: %s", e)
            config = GameConfig(
                name=fingerprint.url.split("/")[-1] or "unknown",
                game_type=GameType.CASCADE,
            )
            return GameModel(config=config, fingerprint=fingerprint, assets=assets)
