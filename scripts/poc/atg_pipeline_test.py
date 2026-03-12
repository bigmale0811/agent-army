"""ATG Pipeline 整合測試

1. 從 ATG 官網取得 Demo URL（新鮮 Token）
2. 用 slot_cloner pipeline 跑完整流程
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def get_demo_url() -> str:
    """從 ATG 官網取得新鮮 Demo URL"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="zh-TW",
        )
        page = await context.new_page()

        await page.goto(
            "https://www.atg-games.com/en/game/storm-of-seth/",
            wait_until="networkidle",
            timeout=30000,
        )
        await page.wait_for_timeout(2000)

        # 攔截彈出視窗取得 URL
        async with context.expect_page() as popup_info:
            await page.click("text=DEMO PLAY", timeout=10000)

        game_page = await popup_info.value
        url = game_page.url

        await browser.close()
        return url


async def main() -> None:
    print("=== Step 1: 取得 ATG Demo URL ===")
    demo_url = await get_demo_url()
    print(f"  URL: {demo_url}")

    # 將語言改為 zh-tw 以取得中文資源
    demo_url = demo_url.replace("&l=en&", "&l=zh-tw&")
    print(f"  URL (zh-tw): {demo_url}")

    print("\n=== Step 2: 執行 slot_cloner Pipeline ===")
    # 直接呼叫 CLI
    import subprocess
    import sys

    cmd = [
        sys.executable, "-m", "slot_cloner", "clone",
        demo_url,
        "--name", "storm-of-seth-demo",
        "--phases", "recon,scrape,reverse,report",
    ]
    print(f"  CMD: {' '.join(cmd[:6])}...")

    env = {**__import__("os").environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        cmd,
        cwd=str(Path(__file__).parent.parent.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )

    print("\n--- STDOUT ---")
    # 只印最後 100 行
    lines = result.stdout.strip().split("\n")
    for line in lines[-100:]:
        print(line)

    if result.returncode != 0:
        print("\n--- STDERR (last 30 lines) ---")
        err_lines = result.stderr.strip().split("\n")
        for line in err_lines[-30:]:
            print(line)

    print(f"\nExit code: {result.returncode}")


if __name__ == "__main__":
    asyncio.run(main())
