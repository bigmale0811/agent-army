"""ATG 遊戲商適配器 — ATG (Agile Titan Games) 專用"""
from __future__ import annotations
import logging
from slot_cloner.plugins.base import BaseAdapter
from slot_cloner.models.game import GameFingerprint, GameModel, GameConfig
from slot_cloner.models.asset import AssetBundle
from slot_cloner.models.enums import GameType

logger = logging.getLogger(__name__)


class ATGAdapter(BaseAdapter):
    """ATG (Agile Titan Games) 適配器

    處理 ATG 旗下遊戲（如戰神賽特 Storm of Seth）。
    特徵：godeebxp.com 網域、Cocos Creator 引擎、Socket.IO WebSocket 通訊。

    ATG 遊戲架構特點：
    - 使用 Cocos Creator 引擎（非 PixiJS）
    - 所有 JSON config 為 Cocos 內部場景序列化格式（UUID 引用）
    - 遊戲資料（符號/賠率表）透過 Socket.IO WebSocket 在 Spin 後發送
    - WS URL 格式：wss://socket.godeebxp.com/socket.io/?EIO=3&transport=websocket
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
        """ATG 逆向分析 — 強化版

        ATG 專用策略：
        1. 先嘗試 Cocos Creator 場景解析（從已抓取的 JSON 提取 symbol-image 映射）
        2. 標準 4 層逆向分析（含 Socket.IO Spin 觸發）
        3. 合併 Cocos Creator 解析結果
        """
        from slot_cloner.reverse.engine import ReverseEngine
        from slot_cloner.reverse.cocos_parser import CocosCreatorParser

        # ATG 額外分析：解析 Cocos Creator 場景檔案
        cocos_symbols = []
        if assets.raw_configs:
            logger.info("ATG: 嘗試 Cocos Creator 場景解析（%d 個 JSON 設定檔）...", len(assets.raw_configs))
            cocos_parser = CocosCreatorParser()
            cocos_symbols = cocos_parser.extract_symbols_from_configs(assets.raw_configs)
            if cocos_symbols:
                logger.info("ATG: Cocos Creator 解析到 %d 個符號映射", len(cocos_symbols))
            else:
                logger.info("ATG: Cocos Creator 場景中未找到符號定義")

        # 標準逆向分析（包含 Spin 觸發）
        engine = ReverseEngine(**kwargs)
        game_model = await engine.reverse(fingerprint, assets)

        # 如果標準逆向未取得符號，嘗試用 Cocos 解析結果補充
        if not game_model.config.symbols and cocos_symbols:
            logger.info("ATG: 使用 Cocos Creator 解析結果補充符號定義")
            from slot_cloner.models.symbol import SymbolConfig, PaytableConfig
            from slot_cloner.models.enums import ConfidenceLevel

            updated_config = game_model.config.model_copy(update={
                "symbols": tuple(cocos_symbols),
            })
            updated_confidence = dict(game_model.confidence_map)
            updated_confidence["symbols"] = ConfidenceLevel.LOW
            updated_confidence["source"] = "cocos_creator_scene"

            game_model = game_model.model_copy(update={
                "config": updated_config,
                "confidence_map": updated_confidence,
            })

        return game_model
