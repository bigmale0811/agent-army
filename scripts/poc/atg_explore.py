"""ATG 選機台流程探勘腳本 — 截圖分析 + 嘗試點擊進入遊戲"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else ""
OUT = Path("output/atg_explore")
OUT.mkdir(parents=True, exist_ok=True)


async def explore():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})

        ws_messages = []

        def on_ws(ws):
            def on_recv(data):
                ws_messages.append(("recv", data[:300] if isinstance(data, str) else data[:100].hex()))
            def on_sent(data):
                ws_messages.append(("sent", data[:300] if isinstance(data, str) else data[:100].hex()))
            ws.on("framereceived", on_recv)
            ws.on("framesent", on_sent)
            print(f"[WS] 連線: {ws.url[:80]}")

        page.on("websocket", on_ws)

        print(f"[1] 載入選機台頁面...")
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_selector("canvas", timeout=30000)
        await page.wait_for_timeout(3000)

        # 截圖 1: 選機台頁面
        await page.screenshot(path=str(OUT / "01_machine_select.png"), full_page=True)
        print(f"[2] 截圖已存: 01_machine_select.png")
        print(f"    WS 訊息數: {len(ws_messages)}")
        for i, (d, m) in enumerate(ws_messages[:10]):
            print(f"    WS[{i}] {d}: {m[:120]}")

        # 取得 canvas 尺寸
        canvas = await page.query_selector("canvas")
        bbox = await canvas.bounding_box()
        print(f"[3] Canvas 尺寸: {bbox}")

        # 嘗試點擊 canvas 中央（選機台）
        cx, cy = bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2
        print(f"[4] 點擊 Canvas 中央: ({cx:.0f}, {cy:.0f})")
        await page.mouse.click(cx, cy)
        await page.wait_for_timeout(5000)

        await page.screenshot(path=str(OUT / "02_after_center_click.png"), full_page=True)
        print(f"[5] 截圖已存: 02_after_center_click.png")
        print(f"    WS 訊息數: {len(ws_messages)}")
        for i, (d, m) in enumerate(ws_messages[4:15]):
            print(f"    WS[{i+4}] {d}: {m[:120]}")

        # 嘗試點擊偏左位置（第一台機器可能在這裡）
        lx = bbox["x"] + bbox["width"] * 0.25
        ly = bbox["y"] + bbox["height"] * 0.5
        print(f"[6] 點擊 Canvas 左側: ({lx:.0f}, {ly:.0f})")
        await page.mouse.click(lx, ly)
        await page.wait_for_timeout(5000)

        await page.screenshot(path=str(OUT / "03_after_left_click.png"), full_page=True)
        print(f"[7] 截圖已存: 03_after_left_click.png")
        print(f"    WS 訊息數: {len(ws_messages)}")

        # 再嘗試雙擊中央
        print(f"[8] 雙擊 Canvas 中央...")
        await page.mouse.dblclick(cx, cy)
        await page.wait_for_timeout(5000)

        await page.screenshot(path=str(OUT / "04_after_dblclick.png"), full_page=True)
        print(f"[9] 截圖已存: 04_after_dblclick.png")
        print(f"    總 WS 訊息: {len(ws_messages)}")

        # 印出所有 WS 訊息
        print("\n=== 全部 WS 訊息 ===")
        for i, (d, m) in enumerate(ws_messages):
            print(f"  [{i}] {d}: {m[:200]}")

        await browser.close()
        print("\n探勘完成！截圖在 output/atg_explore/")


asyncio.run(explore())
