"""逆向分析引擎 — 多層策略逆向遊戲邏輯"""
from __future__ import annotations
import json
import logging
from typing import Any
from playwright.async_api import async_playwright, Page
from slot_cloner.models.game import GameFingerprint, GameModel, GameConfig
from slot_cloner.models.asset import AssetBundle
from slot_cloner.models.enums import GameType, ConfidenceLevel
from slot_cloner.reverse.ws_analyzer import WSAnalyzer
from slot_cloner.reverse.js_analyzer import JSAnalyzer
from slot_cloner.reverse.paytable_parser import PaytableParser

logger = logging.getLogger(__name__)


class ReverseEngine:
    """逆向分析引擎

    4 層遞降策略：
    1. 設定檔直接解析（從已擷取的 JSON config）
    2. WebSocket 攔截（瀏覽器 JS context 中攔截解密後明文）
    3. JS 靜態分析（美化 + 正則搜尋）
    4. 視覺 OCR 分析（Sprint 4 實作）
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 60000) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms

    async def reverse(
        self,
        fingerprint: GameFingerprint,
        assets: AssetBundle,
    ) -> GameModel:
        """執行多層逆向分析"""
        ws_analyzer = WSAnalyzer()
        js_analyzer = JSAnalyzer()
        pt_parser = PaytableParser()

        # === Layer 1: 設定檔直接解析 ===
        logger.info("Layer 1: 分析已擷取的設定檔...")
        layer1_result = self._analyze_configs(assets.raw_configs, pt_parser)

        # === Layer 2: WebSocket 攔截 ===
        logger.info("Layer 2: WebSocket 攔截分析...")
        layer2_result = await self._analyze_websocket(
            fingerprint.url, ws_analyzer, pt_parser
        )

        # === Layer 3: JS 靜態分析 ===
        logger.info("Layer 3: JS 靜態分析...")
        layer3_result = self._analyze_js(fingerprint.js_bundle_urls, js_analyzer)

        # 合併結果（優先使用高可信度的資料）
        return self._merge_results(
            fingerprint, assets,
            layer1_result, layer2_result, layer3_result,
        )

    def _analyze_configs(
        self,
        raw_configs: dict[str, object],
        parser: PaytableParser,
    ) -> dict[str, Any]:
        """Layer 1: 從已擷取的 JSON 設定檔中搜尋遊戲配置"""
        result: dict[str, Any] = {"symbols": (), "paytable": None, "confidence": ConfidenceLevel.HIGH}

        for name, config in raw_configs.items():
            if not isinstance(config, dict):
                continue

            config_text = json.dumps(config, default=str).lower()
            # 搜尋包含賠率資訊的設定檔
            if any(kw in config_text for kw in ("paytable", "symbol", "payout")):
                try:
                    symbols, paytable = parser.parse_from_ws_config(config)
                    if symbols:
                        result["symbols"] = symbols
                        result["paytable"] = paytable
                        logger.info("Layer 1: 從 %s 找到遊戲配置", name)
                        return result
                except Exception as e:
                    logger.warning("Layer 1: 解析 %s 失敗: %s", name, e)

        result["confidence"] = ConfidenceLevel.LOW
        return result

    async def _analyze_websocket(
        self,
        url: str,
        ws_analyzer: WSAnalyzer,
        parser: PaytableParser,
    ) -> dict[str, Any]:
        """Layer 2: 用 Playwright 攔截 WebSocket 訊息"""
        result: dict[str, Any] = {
            "symbols": (),
            "paytable": None,
            "ws_messages": (),
            "confidence": ConfidenceLevel.MEDIUM,
        }

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self._headless)
                try:
                    page = await browser.new_page()

                    # 攔截 WebSocket 訊息
                    def on_ws(ws):
                        ws.on("framereceived", lambda data: ws_analyzer.add_message(data, "received"))
                        ws.on("framesent", lambda data: ws_analyzer.add_message(data, "sent"))

                    page.on("websocket", on_ws)

                    await page.goto(url, wait_until="networkidle", timeout=self._timeout_ms)
                    await page.wait_for_selector("canvas", timeout=self._timeout_ms)

                    # 等待一段時間收集 WS 訊息
                    await page.wait_for_timeout(5000)

                    # 分析 WS 訊息
                    ws_config = ws_analyzer.find_game_config()
                    if ws_config:
                        symbols, paytable = parser.parse_from_ws_config(ws_config)
                        result["symbols"] = symbols
                        result["paytable"] = paytable

                    result["ws_messages"] = tuple(
                        msg.get("parsed", {}) for msg in ws_analyzer.messages
                        if isinstance(msg.get("parsed"), dict)
                    )

                finally:
                    await browser.close()

        except Exception as e:
            logger.warning("Layer 2 WebSocket 分析失敗: %s", e)
            result["confidence"] = ConfidenceLevel.LOW

        return result

    def _analyze_js(
        self,
        js_urls: tuple[str, ...],
        analyzer: JSAnalyzer,
    ) -> dict[str, Any]:
        """Layer 3: JS 靜態分析（簡化版 — 不下載，用已有資料）"""
        # Sprint 2 簡化版：僅回傳空結果
        # 完整版需要下載 JS bundle 再分析
        return {
            "symbols": [],
            "grid_size": None,
            "rtp": [],
            "confidence": ConfidenceLevel.LOW,
        }

    def _merge_results(
        self,
        fingerprint: GameFingerprint,
        assets: AssetBundle,
        layer1: dict,
        layer2: dict,
        layer3: dict,
    ) -> GameModel:
        """合併各 Layer 的分析結果（高可信度優先）"""
        # 優先使用 Layer 1（設定檔），其次 Layer 2（WS），最後 Layer 3（JS）
        symbols = layer1.get("symbols") or layer2.get("symbols") or ()
        paytable = layer1.get("paytable") or layer2.get("paytable")

        from slot_cloner.models.symbol import PaytableConfig
        from slot_cloner.models.feature import FeaturesConfig

        config = GameConfig(
            name=fingerprint.url.split("gn=")[-1].split("&")[0] if "gn=" in fingerprint.url else "unknown",
            game_type=fingerprint.game_type,
            symbols=tuple(symbols) if symbols else (),
            paytable=paytable or PaytableConfig(),
            features=FeaturesConfig(),
        )

        # 判定總體可信度
        best_confidence = ConfidenceLevel.LOW
        if layer1.get("symbols"):
            best_confidence = ConfidenceLevel.HIGH
        elif layer2.get("symbols"):
            best_confidence = ConfidenceLevel.MEDIUM

        confidence_map = {
            "paytable": layer1.get("confidence", ConfidenceLevel.LOW),
            "symbols": best_confidence,
            "websocket": layer2.get("confidence", ConfidenceLevel.LOW),
        }

        return GameModel(
            config=config,
            fingerprint=fingerprint,
            assets=assets,
            confidence_map=confidence_map,
            raw_ws_messages=layer2.get("ws_messages", ()),
        )
