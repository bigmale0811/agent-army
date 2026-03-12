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
        """執行多層逆向分析

        統一 Session 架構：
        - 如果 assets.ws_messages 已有資料（Scraper 同 session 預捕獲），
          Layer 2 直接分析這些資料，不另開瀏覽器。
        - 如果沒有預捕獲資料，才開新瀏覽器攔截 WS。
        """
        ws_analyzer = WSAnalyzer()
        js_analyzer = JSAnalyzer()
        pt_parser = PaytableParser()

        # === Layer 1: 設定檔直接解析 ===
        logger.info("Layer 1: 分析已擷取的設定檔...")
        layer1_result = self._analyze_configs(assets.raw_configs, pt_parser)

        # === Layer 2: WebSocket 分析 ===
        if assets.ws_messages:
            # 統一 Session 模式：使用 Scraper 預捕獲的 WS 訊息
            logger.info("Layer 2: 使用 Scraper 預捕獲的 %d 則 WS 訊息（統一 Session）", len(assets.ws_messages))
            layer2_result = self._analyze_precaptured_ws(assets.ws_messages, ws_analyzer, pt_parser)
        else:
            # 舊模式：開新瀏覽器攔截 WS（Token 可能已失效）
            logger.info("Layer 2: WebSocket 攔截分析（開新瀏覽器）...")
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

    def _analyze_precaptured_ws(
        self,
        ws_messages: tuple[dict, ...],
        ws_analyzer: WSAnalyzer,
        parser: PaytableParser,
    ) -> dict[str, Any]:
        """Layer 2（統一 Session 版）：分析 Scraper 預捕獲的 WS 訊息

        不需開瀏覽器，直接分析已收集的原始 WS frame。
        """
        result: dict[str, Any] = {
            "symbols": (),
            "paytable": None,
            "ws_messages": (),
            "spin_results": (),
            "confidence": ConfidenceLevel.MEDIUM,
        }

        # 將原始 WS 訊息灌入 WSAnalyzer
        for msg in ws_messages:
            raw = msg.get("raw", "")
            direction = msg.get("direction", "received")
            ws_analyzer.add_message(raw, direction)

        # 搜尋遊戲配置
        ws_config = ws_analyzer.find_game_config()
        if ws_config:
            logger.info("Layer 2 (預捕獲): 找到遊戲配置！")
            symbols, paytable = parser.parse_from_ws_config(ws_config)
            result["symbols"] = symbols
            result["paytable"] = paytable

        # 搜尋 Spin 結果
        spin_results = ws_analyzer.find_spin_results()
        result["spin_results"] = tuple(spin_results)

        # 事件摘要
        events = ws_analyzer.get_all_events()
        logger.info(
            "Layer 2 (預捕獲): %d 則訊息, %d 個事件, %d 個 spin 結果",
            len(ws_analyzer.messages), len(events), len(spin_results),
        )
        if events:
            logger.info("  事件列表: %s", [e["event"] for e in events[:20]])

        result["ws_messages"] = tuple(
            msg.get("parsed", {}) for msg in ws_analyzer.messages
            if isinstance(msg.get("parsed"), dict)
        )

        return result

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
        """Layer 2: 用 Playwright 攔截 WebSocket 訊息（含 Spin 觸發）

        策略：
        1. 載入遊戲頁面 → 收集初始 WS 訊息（可能包含 config）
        2. 嘗試觸發 Spin → 攔截遊戲資料 WS 回應
        3. 分析所有收集到的 WS 訊息
        """
        result: dict[str, Any] = {
            "symbols": (),
            "paytable": None,
            "ws_messages": (),
            "spin_results": (),
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

                    # 第一階段：等待初始 WS 訊息（遊戲載入後的 config/init）
                    logger.info("Layer 2: 等待初始 WS 訊息...")
                    await page.wait_for_timeout(5000)

                    # 檢查是否已收到遊戲配置
                    ws_config = ws_analyzer.find_game_config()
                    if ws_config:
                        logger.info("Layer 2: 初始階段已找到遊戲配置")
                    else:
                        # 第二階段：觸發 Spin 以取得遊戲資料
                        logger.info("Layer 2: 初始階段無配置，嘗試觸發 Spin...")
                        spin_success = await self._trigger_spin(page)
                        if spin_success:
                            # 等待 Spin 動畫 + WS 回應
                            await page.wait_for_timeout(8000)
                            ws_config = ws_analyzer.find_game_config()

                            # 再嘗試一次 Spin 以收集更多資料
                            if not ws_config:
                                logger.info("Layer 2: 第一次 Spin 未取得配置，再嘗試一次...")
                                await self._trigger_spin(page)
                                await page.wait_for_timeout(8000)
                                ws_config = ws_analyzer.find_game_config()

                    # 解析遊戲配置
                    if ws_config:
                        symbols, paytable = parser.parse_from_ws_config(ws_config)
                        result["symbols"] = symbols
                        result["paytable"] = paytable

                    # 收集 Spin 結果
                    spin_results = ws_analyzer.find_spin_results()
                    result["spin_results"] = tuple(spin_results)

                    # 收集所有事件（除錯用）
                    events = ws_analyzer.get_all_events()
                    if events:
                        logger.info(
                            "Layer 2: 收集到 %d 則 WS 訊息, %d 個事件: %s",
                            len(ws_analyzer.messages), len(events),
                            [e["event"] for e in events[:20]],
                        )

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

    async def _trigger_spin(self, page: Page) -> bool:
        """嘗試觸發一次 Spin 以攔截 WS 遊戲資料

        策略（依序嘗試）：
        1. 搜尋常見 Spin 按鈕選擇器
        2. 對 Canvas 遊戲：點擊底部中央區域（Spin 按鈕常見位置）
        3. 嘗試用鍵盤 Space 觸發
        """
        # 策略 1: DOM 按鈕選擇器
        spin_selectors = [
            "[class*='spin' i]", "[class*='Spin']",
            "[class*='play' i]", "[class*='Play']",
            "[class*='start' i]", "[class*='Start']",
            "[id*='spin' i]", "[id*='play' i]",
            "button[class*='bet' i]",
        ]

        for selector in spin_selectors:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    logger.info("Spin 觸發成功（DOM 按鈕）: %s", selector)
                    return True
            except Exception:
                continue

        # 策略 2: Canvas 點擊（大多數 Cocos/PixiJS 遊戲用 Canvas）
        try:
            canvas = await page.query_selector("canvas")
            if canvas:
                bbox = await canvas.bounding_box()
                if bbox:
                    # Spin 按鈕通常在 canvas 底部中央
                    x = bbox["x"] + bbox["width"] / 2
                    y = bbox["y"] + bbox["height"] * 0.88
                    await page.mouse.click(x, y)
                    logger.info("Spin 觸發嘗試（Canvas 底部中央）: (%.0f, %.0f)", x, y)
                    return True
        except Exception as e:
            logger.debug("Canvas 點擊失敗: %s", e)

        # 策略 3: 鍵盤 Space 鍵（部分遊戲支援）
        try:
            await page.keyboard.press("Space")
            logger.info("Spin 觸發嘗試（Space 鍵）")
            return True
        except Exception:
            pass

        logger.warning("無法觸發 Spin")
        return False

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
