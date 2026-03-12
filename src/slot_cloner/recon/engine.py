"""偵察引擎 — 分析目標遊戲的技術指紋"""
from __future__ import annotations
import logging
from playwright.async_api import async_playwright, Page, Browser
from slot_cloner.models.game import GameFingerprint
from slot_cloner.models.enums import GameType

logger = logging.getLogger(__name__)


class ReconEngine:
    """偵察引擎 — 用 Playwright 開啟目標 URL 並收集技術指紋"""

    def __init__(self, headless: bool = True, timeout_ms: int = 60000) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms

    async def recon(self, url: str) -> GameFingerprint:
        """執行偵察，回傳遊戲技術指紋"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self._headless)
            try:
                page = await browser.new_page()
                # 收集 WebSocket URL
                ws_urls: list[str] = []
                page.on("websocket", lambda ws: ws_urls.append(ws.url))

                # 收集 JS bundle URL
                js_urls: list[str] = []

                async def handle_response(response):
                    content_type = response.headers.get("content-type", "")
                    if "javascript" in content_type and len(await response.body()) > 50000:
                        js_urls.append(response.url)

                page.on("response", handle_response)

                logger.info("正在載入: %s", url)
                await page.goto(url, wait_until="networkidle", timeout=self._timeout_ms)

                # 等待 Canvas 出現（遊戲載入完成的指標）
                await page.wait_for_selector("canvas", timeout=self._timeout_ms)
                logger.info("Canvas 偵測到，遊戲已載入")

                # 在瀏覽器中偵測框架
                fingerprint_data = await page.evaluate("""() => {
                    const result = {
                        has_canvas: !!document.querySelector('canvas'),
                        has_webgl: false,
                        framework: 'unknown',
                    };

                    // 偵測 WebGL
                    const canvas = document.querySelector('canvas');
                    if (canvas) {
                        try {
                            result.has_webgl = !!(canvas.getContext('webgl') || canvas.getContext('webgl2'));
                        } catch(e) {}
                    }

                    // 偵測遊戲框架
                    if (window.PIXI) result.framework = 'pixi';
                    else if (window.Phaser) result.framework = 'phaser';
                    else if (window.cc) result.framework = 'cocos';

                    return result;
                }""")

                # 從 URL 參數推斷遊戲類型
                game_type = self._detect_game_type(url)

                return GameFingerprint(
                    url=url,
                    framework=fingerprint_data.get("framework", "unknown"),
                    provider=self._detect_provider(url),
                    game_type=game_type,
                    canvas_detected=fingerprint_data.get("has_canvas", False),
                    webgl_detected=fingerprint_data.get("has_webgl", False),
                    websocket_urls=tuple(ws_urls),
                    js_bundle_urls=tuple(js_urls),
                )
            finally:
                await browser.close()

    @staticmethod
    def _detect_provider(url: str) -> str:
        """從 URL 推斷遊戲供應商"""
        url_lower = url.lower()
        if "godeebxp.com" in url_lower or "atg" in url_lower:
            return "atg"
        if "pgsoft" in url_lower:
            return "pg_soft"
        if "pragmatic" in url_lower:
            return "pragmatic"
        return "unknown"

    @staticmethod
    def _detect_game_type(url: str) -> GameType:
        """從 URL 參數推斷遊戲類型"""
        url_lower = url.lower()
        if "erase" in url_lower or "cascade" in url_lower or "cluster" in url_lower:
            return GameType.CASCADE
        if "ways" in url_lower:
            return GameType.WAYS
        return GameType.CASCADE  # 預設消除型
