"""ATG Demo 啟動器 — 自動從官網取得新鮮 Demo Token URL

流程：
1. 前往 ATG 官網遊戲頁面
2. 注入 WS 阻擋（防止 Token 被彈窗消耗）
3. 點擊 DEMO PLAY 按鈕
4. 攔截彈出視窗的 URL（含新鮮 Token）
5. 回傳 URL 供 Pipeline 使用
"""

from __future__ import annotations

import logging

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# ATG 官網遊戲頁面 URL 對應表
ATG_GAME_PAGES: dict[str, str] = {
    "storm-of-seth": "https://www.atg-games.com/en/game/storm-of-seth/",
    "storm-of-seth-2": "https://www.atg-games.com/en/game/Storm-of-Seth-2-Awakening/",
    "wuxia": "https://www.atg-games.com/en/game/wuxia-caishen/",
    "son-go-ku": "https://www.atg-games.com/en/game/son-go-ku/",
    "scarlet-three-kingdoms": "https://www.atg-games.com/en/game/scarlet-three-kingdoms/",
}

# WebSocket 阻擋腳本 — 防止彈窗消耗 Token
_WS_BLOCK_SCRIPT = """
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
"""


async def get_demo_url(
    game: str = "storm-of-seth",
    locale: str = "zh-tw",
    timeout_ms: int = 30000,
) -> str:
    """從 ATG 官網取得新鮮 Demo URL

    Args:
        game: 遊戲名稱（見 ATG_GAME_PAGES）
        locale: 語系（zh-tw, en, zh-cn）
        timeout_ms: 超時時間（毫秒）

    Returns:
        完整的遊戲 URL（含新鮮 Token）

    Raises:
        RuntimeError: 無法取得 Demo URL
    """
    page_url = ATG_GAME_PAGES.get(game)
    if not page_url:
        available = ", ".join(ATG_GAME_PAGES.keys())
        raise RuntimeError(
            f"不支援的遊戲: {game}。可用遊戲: {available}"
        )

    logger.info("從 ATG 官網取得 Demo URL: %s", game)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale=locale,
            )

            # 注入 WS 阻擋 — 防止彈窗消耗 Token
            await context.add_init_script(_WS_BLOCK_SCRIPT)

            page = await context.new_page()
            await page.goto(page_url, wait_until="networkidle", timeout=timeout_ms)
            await page.wait_for_timeout(2000)

            # 點擊 DEMO PLAY 並攔截彈出視窗
            async with context.expect_page(timeout=timeout_ms) as popup_info:
                await page.click("text=DEMO PLAY", timeout=10000)

            game_page = await popup_info.value
            await game_page.wait_for_timeout(3000)
            url = game_page.url

            # 替換語系
            if f"&l=en&" in url:
                url = url.replace("&l=en&", f"&l={locale}&")

            logger.info("Demo URL 取得成功（Token 已保鮮）")
            return url

        finally:
            await browser.close()
