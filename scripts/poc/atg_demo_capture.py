"""ATG Demo 完整擷取腳本

從 ATG 官網點擊 Demo Play，攔截彈出的遊戲視窗，
在遊戲視窗中擷取所有 WS 訊息、截圖、遊戲資料。
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, Page


OUTPUT_DIR = Path("output/atg_demo_capture")


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ws_messages: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="zh-TW",
        )
        page = await context.new_page()

        # === Step 1: 前往 ATG 戰神賽特頁面 ===
        print("=== Step 1: 前往 ATG 官網 Storm of Seth 頁面 ===")
        await page.goto(
            "https://www.atg-games.com/en/game/storm-of-seth/",
            wait_until="networkidle",
            timeout=30000,
        )
        await page.wait_for_timeout(2000)
        print(f"  頁面: {await page.title()}")

        # === Step 2: 點擊 Demo Play，攔截彈出視窗 ===
        print("\n=== Step 2: 點擊 DEMO PLAY，攔截彈出視窗 ===")

        # 等待彈出視窗事件 + 點擊 Demo Play
        async with context.expect_page() as popup_info:
            await page.click("text=DEMO PLAY", timeout=10000)

        game_page: Page = await popup_info.value
        game_url = game_page.url
        print(f"  ✅ 攔截到遊戲 URL: {game_url[:150]}")

        # 提取 Token
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(game_url)
        params = parse_qs(parsed.query)
        token = params.get("t", [""])[0]
        print(f"  🔑 Token: {token}")

        # === Step 3: 在遊戲頁面設置 WS 攔截 ===
        print("\n=== Step 3: 設置 WS 攔截並等待遊戲載入 ===")

        def on_ws(ws):
            print(f"  [WS OPEN] {ws.url}")
            ws_messages.append({"type": "open", "url": ws.url})

            def on_received(payload):
                ws_messages.append({
                    "direction": "received",
                    "raw": str(payload)[:2000],
                })
                preview = str(payload)[:120]
                print(f"  [WS ←] {preview}")

            def on_sent(payload):
                ws_messages.append({
                    "direction": "sent",
                    "raw": str(payload)[:2000],
                })
                preview = str(payload)[:120]
                print(f"  [WS →] {preview}")

            ws.on("framereceived", on_received)
            ws.on("framesent", on_sent)

        game_page.on("websocket", on_ws)

        # 等待遊戲載入
        print("  等待遊戲載入（15 秒）...")
        await game_page.wait_for_timeout(15000)
        await game_page.screenshot(path=str(OUTPUT_DIR / "01_game_loaded.png"))
        print(f"  截圖已保存: 01_game_loaded.png")
        print(f"  目前 WS 訊息: {len(ws_messages)} 則")

        # === Step 4: 檢查是否有 Canvas ===
        print("\n=== Step 4: 檢查遊戲狀態 ===")
        canvas = await game_page.query_selector("canvas")
        if canvas:
            bbox = await canvas.bounding_box()
            print(f"  ✅ Canvas 存在: {bbox}")
        else:
            print("  ⚠️ 無 Canvas")

        # 檢查是否有錯誤對話框
        page_text = await game_page.inner_text("body")
        if "找不到" in page_text or "token" in page_text.lower():
            print(f"  ⚠️ 可能有 Token 錯誤: {page_text[:200]}")
        elif "已離開" in page_text:
            print(f"  ⚠️ 遊戲已關閉: {page_text[:200]}")
        else:
            print(f"  頁面文字（前100字）: {page_text[:100]}")

        # === Step 5: 嘗試觸發 Spin ===
        print("\n=== Step 5: 嘗試觸發 Spin ===")

        # 策略 1: 按空白鍵
        print("  嘗試按空白鍵...")
        await game_page.keyboard.press("Space")
        await game_page.wait_for_timeout(5000)
        await game_page.screenshot(path=str(OUTPUT_DIR / "02_after_space.png"))
        print(f"  WS 訊息: {len(ws_messages)} 則")

        # 策略 2: 點擊 Canvas 底部中間（Spin 按鈕通常在那）
        if canvas and bbox:
            spin_x = bbox["x"] + bbox["width"] * 0.5
            spin_y = bbox["y"] + bbox["height"] * 0.85
            print(f"  嘗試點擊 Canvas Spin 位置 ({spin_x:.0f}, {spin_y:.0f})...")
            await game_page.mouse.click(spin_x, spin_y)
            await game_page.wait_for_timeout(5000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "03_after_spin_click.png"))
            print(f"  WS 訊息: {len(ws_messages)} 則")

            # 第二次 Spin
            print("  嘗試第二次 Spin...")
            await game_page.keyboard.press("Space")
            await game_page.wait_for_timeout(5000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "04_after_second_spin.png"))
            print(f"  WS 訊息: {len(ws_messages)} 則")

        # === Step 6: 結果彙整 ===
        print("\n" + "=" * 60)
        print("=== 結果彙整 ===")
        print("=" * 60)
        print(f"遊戲 URL: {game_url}")
        print(f"Token: {token}")
        print(f"WS 訊息總數: {len(ws_messages)}")

        # 分類 WS 訊息
        sent = [m for m in ws_messages if m.get("direction") == "sent"]
        recv = [m for m in ws_messages if m.get("direction") == "received"]
        opens = [m for m in ws_messages if m.get("type") == "open"]
        print(f"  - WS 連線: {len(opens)}")
        print(f"  - 發送: {len(sent)}")
        print(f"  - 接收: {len(recv)}")

        # 檢查是否有 401 錯誤
        has_401 = any("401" in m.get("raw", "") for m in ws_messages)
        has_token_error = any("找不到" in m.get("raw", "") for m in ws_messages)
        print(f"  - 401 錯誤: {'是' if has_401 else '否'}")
        print(f"  - Token 錯誤: {'是' if has_token_error else '否'}")

        # 找出關鍵 WS 事件
        print("\n--- 關鍵 WS 訊息 ---")
        for m in ws_messages:
            raw = m.get("raw", "")
            if any(kw in raw.lower() for kw in [
                "initial", "spin", "result", "config", "game",
                "401", "token", "status", "balance", "bet",
                "paytable", "symbol", "win", "free"
            ]):
                direction = m.get("direction", m.get("type", "?"))
                print(f"  [{direction}] {raw[:300]}")

        # 保存完整結果
        results = {
            "game_url": game_url,
            "token": token,
            "ws_messages": ws_messages,
            "has_401": has_401,
            "has_token_error": has_token_error,
            "total_messages": len(ws_messages),
        }
        with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n截圖和結果已保存到: {OUTPUT_DIR}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
