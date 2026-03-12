"""ATG Demo 完整流程擷取

完整流程: 官網 Demo Play -> START -> 選機台 -> confirm -> Spin -> 擷取 WS
"""

import asyncio
import json
import zlib
from pathlib import Path

from playwright.async_api import async_playwright, Page


OUTPUT_DIR = Path("output/atg_full_capture")


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ws_messages: list[dict] = []
    binary_payloads: list[bytes] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="zh-TW",
        )
        page = await context.new_page()

        # === Step 1: ATG 官網 -> Demo Play ===
        print("=== Step 1: ATG 官網 -> Demo Play ===")
        await page.goto(
            "https://www.atg-games.com/en/game/storm-of-seth/",
            wait_until="networkidle",
            timeout=30000,
        )
        await page.wait_for_timeout(2000)

        async with context.expect_page() as popup_info:
            await page.click("text=DEMO PLAY", timeout=10000)

        game_page: Page = await popup_info.value
        print(f"  Game URL: {game_page.url[:120]}")

        # === Step 2: WS 攔截（含二進位資料） ===
        print("\n=== Step 2: 設置 WS 攔截 ===")

        def on_ws(ws):
            print(f"  [WS OPEN] {ws.url}")

            def on_received(payload):
                if isinstance(payload, bytes):
                    binary_payloads.append(payload)
                    ws_messages.append({
                        "direction": "received",
                        "type": "binary",
                        "size": len(payload),
                        "raw": f"<binary {len(payload)} bytes>",
                    })
                    print(f"  [WS <-BIN] {len(payload)} bytes")
                    # 嘗試 zlib 解壓
                    try:
                        decompressed = zlib.decompress(payload)
                        text = decompressed.decode("utf-8", errors="replace")
                        ws_messages[-1]["decompressed"] = text[:5000]
                        ws_messages[-1]["decompressed_size"] = len(text)
                        print(f"  [DECOMP] {len(text)} chars: {text[:200]}")
                        # 保存解壓資料
                        with open(OUTPUT_DIR / f"ws_binary_{len(binary_payloads)}.json",
                                  "w", encoding="utf-8") as f:
                            f.write(text)
                    except Exception:
                        # 嘗試其他解壓方式
                        for wbits in [-15, 15, 31, 47]:
                            try:
                                dec = zlib.decompress(payload, wbits)
                                text = dec.decode("utf-8", errors="replace")
                                ws_messages[-1]["decompressed"] = text[:5000]
                                ws_messages[-1]["decompressed_size"] = len(text)
                                ws_messages[-1]["wbits"] = wbits
                                print(f"  [DECOMP wbits={wbits}] {len(text)} chars: {text[:200]}")
                                with open(OUTPUT_DIR / f"ws_binary_{len(binary_payloads)}.json",
                                          "w", encoding="utf-8") as f:
                                    f.write(text)
                                break
                            except Exception:
                                pass
                else:
                    raw = str(payload)
                    ws_messages.append({
                        "direction": "received",
                        "type": "text",
                        "raw": raw[:3000],
                    })
                    # 只印關鍵訊息
                    if any(kw in raw.lower() for kw in [
                        "initial", "spin", "result", "config", "game",
                        "status", "balance", "bet", "paytable", "table",
                        "zip", "placeholder", "401", "token", "seat",
                    ]):
                        print(f"  [WS <-KEY] {raw[:200]}")

            def on_sent(payload):
                raw = str(payload)
                ws_messages.append({
                    "direction": "sent",
                    "type": "text" if isinstance(payload, str) else "binary",
                    "raw": raw[:3000],
                })
                if len(raw) > 3 or raw not in ["2", "3"]:
                    print(f"  [WS ->] {raw[:200]}")

            ws.on("framereceived", on_received)
            ws.on("framesent", on_sent)

        game_page.on("websocket", on_ws)

        # === Step 3: 等遊戲載入 ===
        print("\n=== Step 3: 等待遊戲載入 ===")
        await game_page.wait_for_timeout(12000)
        await game_page.screenshot(path=str(OUTPUT_DIR / "01_start_screen.png"))
        print(f"  WS: {len(ws_messages)} msgs, Binary: {len(binary_payloads)} payloads")

        # === Step 4: 點擊 START ===
        print("\n=== Step 4: 點擊 START 按鈕 ===")
        canvas = await game_page.query_selector("canvas")
        if canvas:
            bbox = await canvas.bounding_box()
            # START 按鈕在底部中間
            start_x = bbox["x"] + bbox["width"] * 0.5
            start_y = bbox["y"] + bbox["height"] * 0.92
            print(f"  點擊 START ({start_x:.0f}, {start_y:.0f})")
            await game_page.mouse.click(start_x, start_y)
            await game_page.wait_for_timeout(3000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "02_slot_table.png"))

        # === Step 5: 選擇機台 (點第一個空位) ===
        print("\n=== Step 5: 選擇機台 ===")
        # 機台選擇表是 Canvas 上的 UI，需要點擊正確位置
        # 先點 "Vacant Tables" 頁籤（在表格頂部偏右）
        if bbox:
            vacant_x = bbox["x"] + bbox["width"] * 0.42
            vacant_y = bbox["y"] + bbox["height"] * 0.12
            print(f"  點擊 Vacant Tables ({vacant_x:.0f}, {vacant_y:.0f})")
            await game_page.mouse.click(vacant_x, vacant_y)
            await game_page.wait_for_timeout(2000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "03_vacant_tables.png"))

            # 點第一個空機台（表格左上角第一格）
            first_slot_x = bbox["x"] + bbox["width"] * 0.15
            first_slot_y = bbox["y"] + bbox["height"] * 0.28
            print(f"  點擊第一個機台 ({first_slot_x:.0f}, {first_slot_y:.0f})")
            await game_page.mouse.click(first_slot_x, first_slot_y)
            await game_page.wait_for_timeout(2000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "04_selected_machine.png"))

            # 點 confirm 按鈕（機台選擇表底部右側）
            confirm_x = bbox["x"] + bbox["width"] * 0.72
            confirm_y = bbox["y"] + bbox["height"] * 0.88
            print(f"  點擊 confirm ({confirm_x:.0f}, {confirm_y:.0f})")
            await game_page.mouse.click(confirm_x, confirm_y)
            await game_page.wait_for_timeout(5000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "05_in_game.png"))
            print(f"  WS: {len(ws_messages)} msgs")

        # === Step 6: 觸發 Spin ===
        print("\n=== Step 6: 觸發 Spin ===")
        pre_spin = len(ws_messages)

        # Spin 按鈕通常在底部中間偏右
        if bbox:
            spin_x = bbox["x"] + bbox["width"] * 0.92
            spin_y = bbox["y"] + bbox["height"] * 0.5
            print(f"  點擊 Spin ({spin_x:.0f}, {spin_y:.0f})")
            await game_page.mouse.click(spin_x, spin_y)
            await game_page.wait_for_timeout(3000)

            # 也試空白鍵
            await game_page.keyboard.press("Space")
            await game_page.wait_for_timeout(5000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "06_after_spin.png"))

            new_msgs = len(ws_messages) - pre_spin
            print(f"  Spin 後新增 {new_msgs} 則 WS 訊息")

            # 第二次 Spin
            print("  第二次 Spin...")
            pre_spin2 = len(ws_messages)
            await game_page.keyboard.press("Space")
            await game_page.wait_for_timeout(5000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "07_second_spin.png"))
            new_msgs2 = len(ws_messages) - pre_spin2
            print(f"  第二次 Spin 新增 {new_msgs2} 則 WS 訊息")

            # 第三次
            print("  第三次 Spin...")
            await game_page.mouse.click(spin_x, spin_y)
            await game_page.wait_for_timeout(5000)
            await game_page.screenshot(path=str(OUTPUT_DIR / "08_third_spin.png"))

        # === 結果 ===
        print("\n" + "=" * 60)
        print("=== 結果彙整 ===")
        print("=" * 60)
        print(f"WS 訊息: {len(ws_messages)}")
        print(f"二進位 payload: {len(binary_payloads)}")

        # 找出所有非 notify 的關鍵訊息
        print("\n--- 非 notify 關鍵 WS 訊息 ---")
        for m in ws_messages:
            raw = m.get("raw", "")
            if "notify" not in raw and "slotTable" not in raw and raw not in ["2", "3"]:
                if m.get("type") == "binary":
                    d = m.get("decompressed", "")
                    print(f"  [{m['direction']}] BINARY {m['size']}b -> decomp: {d[:300]}")
                elif len(raw) > 5:
                    print(f"  [{m['direction']}] {raw[:300]}")

        # 找 spin 相關
        print("\n--- Spin 相關訊息 ---")
        for m in ws_messages:
            raw = m.get("raw", "")
            if any(kw in raw.lower() for kw in ["spin", "result", "bet", "win", "round", "seat"]):
                print(f"  [{m['direction']}] {raw[:400]}")

        # 保存
        results = {
            "ws_count": len(ws_messages),
            "binary_count": len(binary_payloads),
            "ws_messages": ws_messages,
        }
        with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n所有結果已保存到: {OUTPUT_DIR}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
