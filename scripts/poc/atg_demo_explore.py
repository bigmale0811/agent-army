"""ATG 官網 Demo 探索腳本

從 ATG 官方網站 (atg-games.com) 出發，
嘗試進入戰神賽特 (Storm of Seth) 的 Demo 模式。
捕獲遊戲 URL、WS 訊息、截圖。
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


OUTPUT_DIR = Path("output/atg_demo")


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ws_messages: list[dict] = []
    all_urls: list[str] = []
    popup_urls: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="zh-TW",
        )

        # === 監控所有新頁面（彈出視窗、新分頁） ===
        def on_page(new_page):
            url = new_page.url
            print(f"[NEW PAGE] {url}")
            popup_urls.append(url)

        context.on("page", on_page)

        page = await context.new_page()

        # === 攔截所有請求 URL ===
        def on_request(req):
            url = req.url
            if "godeebxp" in url or "token" in url.lower() or "game" in url:
                all_urls.append(url)
                print(f"[REQ] {url[:150]}")

        page.on("request", on_request)

        # === WS 攔截 ===
        def on_ws(ws):
            print(f"[WS OPEN] {ws.url}")
            ws_messages.append({"type": "open", "url": ws.url})

            def on_msg(msg):
                direction = "sent" if msg.startswith("4") or msg.startswith("0") else "received"
                ws_messages.append({
                    "direction": direction,
                    "raw": str(msg)[:500],
                })
                print(f"[WS {direction.upper()}] {str(msg)[:120]}")

            def on_close(ws_obj):
                print(f"[WS CLOSE] {ws_obj.url}")

            ws.on("framereceived", lambda payload: on_msg(payload))
            ws.on("framesent", lambda payload: on_msg(payload))
            ws.on("close", on_close)

        page.on("websocket", on_ws)

        # === Step 1: 前往 ATG 官網遊戲頁面 ===
        print("\n=== Step 1: 前往 ATG 戰神賽特頁面 ===")
        await page.goto(
            "https://www.atg-games.com/en/game/storm-of-seth/",
            wait_until="networkidle",
            timeout=30000,
        )
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(OUTPUT_DIR / "01_game_page.png"))
        print(f"  頁面標題: {await page.title()}")

        # === Step 2: 尋找 Demo Play 按鈕 ===
        print("\n=== Step 2: 尋找 Demo Play 按鈕 ===")

        # 嘗試多種選擇器
        demo_selectors = [
            "text=Demo Play",
            "text=demo play",
            "text=Demo",
            "text=DEMO",
            "text=試玩",
            "text=Play Now",
            "text=Play",
            "button:has-text('Demo')",
            "button:has-text('Play')",
            "a:has-text('Demo')",
            "a:has-text('Play')",
            ".demo-btn",
            ".play-btn",
            "[class*='demo']",
            "[class*='play']",
            "[data-action='demo']",
        ]

        clicked = False
        for sel in demo_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    is_visible = await el.is_visible()
                    text = await el.inner_text() if is_visible else ""
                    print(f"  找到元素: {sel} → '{text}' (visible={is_visible})")
                    if is_visible:
                        await el.click()
                        clicked = True
                        print(f"  ✅ 點擊: {sel}")
                        break
            except Exception as e:
                pass

        if not clicked:
            # 列出頁面上所有按鈕和連結
            print("  ⚠️ 未找到 Demo 按鈕，列出頁面上的可點擊元素：")
            buttons = await page.query_selector_all("button, a[href], [role='button']")
            for btn in buttons[:20]:
                try:
                    text = (await btn.inner_text()).strip()
                    href = await btn.get_attribute("href") or ""
                    cls = await btn.get_attribute("class") or ""
                    if text or href:
                        print(f"    [{await btn.evaluate('e => e.tagName')}] text='{text[:50]}' href='{href[:80]}' class='{cls[:50]}'")
                except:
                    pass

        await page.wait_for_timeout(5000)
        await page.screenshot(path=str(OUTPUT_DIR / "02_after_demo_click.png"))

        # === Step 3: 檢查是否有新頁面/iframe 載入遊戲 ===
        print("\n=== Step 3: 檢查遊戲載入狀態 ===")

        # 檢查 iframe
        iframes = await page.query_selector_all("iframe")
        print(f"  iframe 數量: {len(iframes)}")
        for i, iframe in enumerate(iframes):
            src = await iframe.get_attribute("src") or ""
            print(f"  iframe[{i}]: {src[:200]}")

        # 檢查當前 URL
        print(f"  當前 URL: {page.url}")

        # 如果有新頁面打開
        if len(context.pages) > 1:
            game_page = context.pages[-1]
            print(f"  新頁面 URL: {game_page.url}")
            await game_page.wait_for_timeout(5000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "03_game_window.png"))

            # 在新頁面也攔截 WS
            game_page.on("websocket", on_ws)
            await game_page.wait_for_timeout(10000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "04_game_loaded.png"))

        # === Step 4: 嘗試直接呼叫 ATG API 取得 Demo Token ===
        print("\n=== Step 4: 嘗試 ATG API 取得 Demo Token ===")

        # 根據之前發現的 API 端點嘗試
        api_urls = [
            "https://api.godeebxp.com/api/v1/games/storm-of-seth/demo",
            "https://api.godeebxp.com/api/v1/demo/storm-of-seth",
            "https://api.godeebxp.com/api/games/demo?gn=egyptian-mythology",
            "https://api.godeebxp.com/api/v1/game/launch?game=storm-of-seth&mode=demo",
        ]

        for api_url in api_urls:
            try:
                resp = await page.request.get(api_url, timeout=5000)
                status = resp.status
                body = await resp.text()
                print(f"  [{status}] {api_url}")
                if status < 400 and body:
                    print(f"    Response: {body[:300]}")
                    # 保存成功的回應
                    with open(OUTPUT_DIR / "api_response.json", "w", encoding="utf-8") as f:
                        f.write(body)
            except Exception as e:
                print(f"  [ERR] {api_url} → {e}")

        # === Step 5: 嘗試用 JavaScript 觸發遊戲 ===
        print("\n=== Step 5: 探索頁面 JavaScript ===")
        try:
            # 檢查 Nuxt/Vue 應用的數據
            nuxt_data = await page.evaluate("""() => {
                const data = {};
                // Nuxt 3 payload
                if (window.__NUXT__) data.nuxt = JSON.stringify(window.__NUXT__).substring(0, 1000);
                // Vue app data
                if (window.__vue_app__) data.vue = 'found';
                // 全域變數
                const globals = Object.keys(window).filter(k =>
                    k.toLowerCase().includes('game') ||
                    k.toLowerCase().includes('config') ||
                    k.toLowerCase().includes('api') ||
                    k.toLowerCase().includes('demo')
                );
                data.gameGlobals = globals;
                return data;
            }""")
            print(f"  Nuxt/Vue data: {json.dumps(nuxt_data, indent=2)[:500]}")
        except Exception as e:
            print(f"  JS 探索失敗: {e}")

        # === 結果彙整 ===
        print("\n" + "=" * 60)
        print("=== 結果彙整 ===")
        print("=" * 60)
        print(f"攔截到的 godeebxp URLs: {len(all_urls)}")
        for u in all_urls[:10]:
            print(f"  {u[:200]}")
        print(f"新頁面 URLs: {len(popup_urls)}")
        for u in popup_urls:
            print(f"  {u[:200]}")
        print(f"WS 訊息: {len(ws_messages)}")
        for m in ws_messages[:10]:
            print(f"  {m}")

        # 保存結果
        results = {
            "intercepted_urls": all_urls,
            "popup_urls": popup_urls,
            "ws_messages": ws_messages,
        }
        with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n截圖和結果已保存到: {OUTPUT_DIR}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
