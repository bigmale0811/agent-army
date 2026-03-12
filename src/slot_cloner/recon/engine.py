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
        """執行偵察，回傳遊戲技術指紋

        注意：使用 init_script 阻擋遊戲 WS 連線，
        避免消耗一次性 Token（如 ATG 的 Demo Token）。
        只攔截 URL 資訊，不建立真正的 WS 連線。
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self._headless)
            try:
                context = await browser.new_context()

                # 阻擋遊戲 WS 連線，避免消耗一次性 Token
                await context.add_init_script("""
                    (() => {
                        const OrigWS = window.WebSocket;
                        const blocked = [];
                        window.WebSocket = function(url, ...args) {
                            blocked.push(url);
                            window.__blocked_ws_urls = blocked;
                            return {
                                send: ()=>{}, close: ()=>{},
                                addEventListener: ()=>{},
                                onopen: null, onmessage: null,
                                onclose: null, onerror: null,
                                readyState: 0,
                                CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3,
                            };
                        };
                        window.WebSocket.prototype = OrigWS.prototype;
                        window.WebSocket.CONNECTING = 0;
                        window.WebSocket.OPEN = 1;
                        window.WebSocket.CLOSING = 2;
                        window.WebSocket.CLOSED = 3;
                    })();
                """)

                page = await context.new_page()
                # 收集被攔截的 WebSocket URL
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

                # 從被阻擋的 WS 中取得 URL
                blocked_ws = await page.evaluate(
                    "window.__blocked_ws_urls || []"
                )
                if blocked_ws:
                    logger.info("偵測到 %d 個 WS 連線（已阻擋以保護 Token）", len(blocked_ws))

                # 從 URL 參數推斷遊戲類型
                game_type = self._detect_game_type(url)

                return GameFingerprint(
                    url=url,
                    framework=fingerprint_data.get("framework", "unknown"),
                    provider=self._detect_provider(url),
                    game_type=game_type,
                    canvas_detected=fingerprint_data.get("has_canvas", False),
                    webgl_detected=fingerprint_data.get("has_webgl", False),
                    websocket_urls=tuple(ws_urls or blocked_ws),
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
