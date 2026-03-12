"""資源擷取引擎 — 統一 Session：同時攔截 Network 資源 + WebSocket 訊息 + 觸發 Spin

核心設計：一個 Playwright browser session 完成所有工作：
1. Network 攔截 → 下載圖片/音效/JSON 設定檔
2. WebSocket 攔截 → 收集 Socket.IO 訊息（含遊戲資料）
3. Spin 觸發 → 取得伺服器回傳的賠率/結果資料
4. 互動模式 → 使用者可在可見瀏覽器中處理認證

為什麼合併？因為 ATG 等平台的 Token 只在一個 session 中有效。
"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Any
from playwright.async_api import async_playwright, Page, Route, Request
from slot_cloner.models.game import GameFingerprint
from slot_cloner.models.asset import AssetBundle, ImageAsset, AudioAsset, SpriteSheet

# 單一資源最大大小限制（50MB）
MAX_ASSET_BYTES = 50 * 1024 * 1024

logger = logging.getLogger(__name__)

# MIME type 分類對照表
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"}
AUDIO_TYPES = {
    "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm", "audio/mp3",
    "audio/aac", "audio/x-m4a", "audio/mp4", "audio/flac",
}
# 從 URL 副檔名偵測音效（繞過 MIME type 問題）
AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".webm", ".m4a", ".aac", ".flac"}
CONFIG_TYPES = {"application/json", "text/json"}


class ScraperEngine:
    """資源擷取引擎 — 統一 Session 架構

    在同一個 Playwright browser session 中：
    - 攔截 Network responses（圖片/音效/JSON）
    - 攔截 WebSocket 訊息（Socket.IO 通訊）
    - 觸發 Spin 操作以取得遊戲資料
    - 支援互動模式（非 headless，使用者可處理認證）
    - 支援持久化瀏覽器 profile（保留 Cookie/Session）
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        headless: bool = True,
        timeout_ms: int = 60000,
        interactive: bool = False,
        browser_profile: str | None = None,
    ) -> None:
        self._output_dir = output_dir or Path("./output")
        # 互動模式強制非 headless
        self._headless = False if interactive else headless
        self._timeout_ms = timeout_ms
        self._interactive = interactive
        self._browser_profile = browser_profile

    async def scrape(self, fingerprint: GameFingerprint) -> AssetBundle:
        """擷取目標遊戲的所有資源 + 同步攔截 WS 訊息"""
        images: list[ImageAsset] = []
        audio_list: list[AudioAsset] = []
        sprites: list[SpriteSheet] = []
        raw_configs: dict[str, object] = {}
        # 統一 Session 新增：WS 訊息收集
        ws_messages: list[dict[str, Any]] = []

        # 確保輸出目錄存在
        img_dir = self._output_dir / "assets" / "images"
        audio_dir = self._output_dir / "assets" / "audio"
        config_dir = self._output_dir / "analysis"
        for d in (img_dir, audio_dir, config_dir):
            d.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            # 支援持久化瀏覽器 profile（保留 Cookie/Session）
            if self._browser_profile:
                logger.info("使用持久化瀏覽器 profile: %s", self._browser_profile)
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=self._browser_profile,
                    headless=self._headless,
                )
                page = context.pages[0] if context.pages else await context.new_page()
                browser = None  # persistent context 不用單獨的 browser
            else:
                browser = await p.chromium.launch(headless=self._headless)
                context = await browser.new_context()
                page = await context.new_page()

            try:
                # === 1. Network 攔截 ===
                async def handle_response(response):
                    try:
                        content_type = response.headers.get("content-type", "")
                        url = response.url
                        status = response.status

                        if status != 200:
                            return

                        file_name = self._url_to_filename(url)

                        if any(t in content_type for t in IMAGE_TYPES):
                            body = await response.body()
                            file_path = img_dir / file_name
                            file_path.write_bytes(body)
                            images.append(ImageAsset(
                                name=file_name,
                                path=file_path,
                                mime_type=content_type.split(";")[0].strip(),
                                source_url=url,
                            ))
                            logger.debug("圖片: %s (%d bytes)", file_name, len(body))

                        elif any(t in content_type for t in AUDIO_TYPES):
                            body = await response.body()
                            file_path = audio_dir / file_name
                            file_path.write_bytes(body)
                            audio_list.append(AudioAsset(
                                name=file_name,
                                path=file_path,
                                mime_type=content_type.split(";")[0].strip(),
                                source_url=url,
                            ))
                            logger.debug("音效: %s (%d bytes)", file_name, len(body))

                        elif any(t in content_type for t in CONFIG_TYPES):
                            try:
                                body = await response.body()
                                data = json.loads(body)
                                raw_configs[file_name] = data
                                file_path = config_dir / file_name
                                file_path.write_text(
                                    json.dumps(data, indent=2, ensure_ascii=False),
                                    encoding="utf-8",
                                )
                                logger.debug("設定檔: %s", file_name)
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                pass

                    except Exception as e:
                        logger.warning("擷取資源失敗: %s — %s", response.url, e)

                page.on("response", handle_response)

                # === 2. WebSocket 攔截（統一 Session 核心！） ===
                def on_ws(ws):
                    """攔截所有 WebSocket 訊息"""
                    def on_frame_received(data):
                        ws_messages.append({
                            "direction": "received",
                            "raw": data if isinstance(data, str) else data.hex(),
                            "url": ws.url,
                        })
                    def on_frame_sent(data):
                        ws_messages.append({
                            "direction": "sent",
                            "raw": data if isinstance(data, str) else data.hex(),
                            "url": ws.url,
                        })
                    ws.on("framereceived", on_frame_received)
                    ws.on("framesent", on_frame_sent)
                    logger.info("WebSocket 連線攔截中: %s", ws.url)

                page.on("websocket", on_ws)

                # === 3. Web Audio API hook ===
                await page.add_init_script("""
                    window.__audioUrls = [];
                    const origFetch = window.fetch;
                    window.fetch = function(...args) {
                        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
                        const audioExts = ['.mp3', '.ogg', '.wav', '.webm', '.m4a', '.aac'];
                        if (audioExts.some(ext => url.toLowerCase().includes(ext))) {
                            window.__audioUrls.push(url);
                        }
                        return origFetch.apply(this, args);
                    };
                    const origXHR = XMLHttpRequest.prototype.open;
                    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
                        const audioExts = ['.mp3', '.ogg', '.wav', '.webm', '.m4a', '.aac'];
                        if (typeof url === 'string' && audioExts.some(ext => url.toLowerCase().includes(ext))) {
                            window.__audioUrls.push(url);
                        }
                        return origXHR.call(this, method, url, ...rest);
                    };
                """)

                # === 4. 載入遊戲頁面 ===
                logger.info("開始擷取資源: %s", fingerprint.url)
                await page.goto(fingerprint.url, wait_until="networkidle", timeout=self._timeout_ms)

                # 嘗試等 canvas（某些頁面可能沒有）
                try:
                    await page.wait_for_selector("canvas", timeout=15000)
                except Exception:
                    logger.info("未偵測到 canvas（可能是大廳/登入頁面）")

                # === 5. Token 錯誤偵測 + 互動模式 ===
                await page.wait_for_timeout(3000)  # 等待 WS 初始交握
                token_ok = self._check_ws_auth(ws_messages)

                if not token_ok and self._interactive:
                    # Token 失敗 → 互動模式引導使用者
                    logger.info("=" * 60)
                    logger.info("🔐 Token 認證失敗！偵測到 401 錯誤")
                    logger.info("=" * 60)
                    logger.info("📋 請在瀏覽器中執行以下操作：")
                    logger.info("   1. 如果有彈出錯誤對話框，點擊「確定」關閉它")
                    logger.info("   2. 導航到遊戲平台的登入/大廳頁面")
                    logger.info("   3. 登入後選擇要 Clone 的遊戲")
                    logger.info("   4. 等遊戲正常顯示即可，工具會自動偵測")
                    logger.info("⏳ 最長等待 5 分鐘...")
                    logger.info("=" * 60)

                    # 清空先前的 WS 錯誤訊息，重新收集
                    ws_messages.clear()
                    await self._wait_for_valid_game(page, ws_messages)

                elif not token_ok and not self._interactive:
                    logger.warning(
                        "🔐 Token 認證失敗（401）。建議使用 --interactive 模式 "
                        "或提供尚未在瀏覽器中開啟過的 URL"
                    )

                elif self._interactive:
                    logger.info("🎮 互動模式：Token 認證成功，繼續處理...")
                    await self._wait_for_game_ready(page)

                # === 6. 等待初始 WS 訊息 ===
                logger.info("等待遊戲初始化 WS 訊息（5 秒）...")
                await page.wait_for_timeout(5000)

                # === 7. 觸發 Spin + 額外載入 ===
                await self._trigger_extra_loads(page)
                spin_triggered = await self._trigger_spin(page)
                if spin_triggered:
                    logger.info("Spin 已觸發，等待 WS 回應（8 秒）...")
                    await page.wait_for_timeout(8000)

                    # 嘗試第二次 Spin
                    logger.info("嘗試第二次 Spin...")
                    await self._trigger_spin(page)
                    await page.wait_for_timeout(5000)

                # === 8. 收集 Web Audio hook 音效 ===
                hooked_urls = await page.evaluate("window.__audioUrls || []")
                if hooked_urls:
                    logger.info("Web Audio hook 偵測到 %d 個額外音效 URL", len(hooked_urls))
                    for url in hooked_urls:
                        file_name = self._url_to_filename(url)
                        if not any(a.name == file_name for a in audio_list):
                            ext = Path(file_name).suffix.lower()
                            if ext in AUDIO_EXTENSIONS:
                                try:
                                    resp = await page.request.get(url)
                                    body = await resp.body()
                                    file_path = audio_dir / file_name
                                    file_path.write_bytes(body)
                                    audio_list.append(AudioAsset(
                                        name=file_name,
                                        path=file_path,
                                        mime_type=f"audio/{ext.lstrip('.')}",
                                        source_url=url,
                                    ))
                                    logger.debug("Hook 音效: %s (%d bytes)", file_name, len(body))
                                except Exception as e:
                                    logger.debug("Hook 音效下載失敗: %s — %s", url, e)

                logger.info(
                    "擷取完成: %d 圖片, %d 音效, %d 設定檔, %d WS 訊息",
                    len(images), len(audio_list), len(raw_configs), len(ws_messages),
                )

            finally:
                if browser:
                    await browser.close()
                else:
                    await context.close()

        return AssetBundle(
            images=tuple(images),
            sprites=tuple(sprites),
            audio=tuple(audio_list),
            raw_configs=raw_configs,
            ws_messages=tuple(ws_messages),
        )

    @staticmethod
    def _check_ws_auth(ws_messages: list[dict]) -> bool:
        """檢查 WS 訊息中是否有 401 Token 錯誤

        ATG 的 Socket.IO 認證流程：
        1. Client → 420["initial",{"token":"..."}]
        2. Server → 430[{"status":401,"message":"找不到 Token 資訊"}] （失敗）
        2. Server → 430[{"status":200,...}] （成功）
        """
        for msg in ws_messages:
            raw = msg.get("raw", "")
            if msg.get("direction") == "received":
                if "401" in raw or "找不到" in raw or "token" in raw.lower():
                    if "status" in raw and ("401" in raw or "找不到" in raw):
                        logger.warning("WS 認證失敗: %s", raw[:200])
                        return False
        # 沒有明確的失敗訊息 → 假設 OK（可能還沒收到回應）
        return True

    async def _wait_for_valid_game(
        self, page: Page, ws_messages: list[dict]
    ) -> None:
        """互動模式：Token 失敗後等待使用者導航到有效遊戲

        偵測策略（任一滿足即視為成功）：
        1. WS 收到非 401 的 received 訊息（表示認證成功）
        2. Canvas 可見且 WS 有活動（表示遊戲正常載入）
        3. 最長等待 300 秒（5 分鐘）
        """
        max_wait = 300_000
        check_interval = 3_000
        waited = 0

        while waited < max_wait:
            await page.wait_for_timeout(check_interval)
            waited += check_interval

            # 策略 1: 檢查 WS 是否有成功的 received 訊息
            received_msgs = [
                m for m in ws_messages
                if m.get("direction") == "received"
                and "401" not in m.get("raw", "")
                and "找不到" not in m.get("raw", "")
                and len(m.get("raw", "")) > 5  # 排除純控制訊息如 "3"
            ]
            if received_msgs:
                logger.info(
                    "🎮 偵測到有效 WS 回應（%d 則），遊戲認證成功！",
                    len(received_msgs),
                )
                return

            # 策略 2: Canvas 存在且有 WS 活動
            canvas = await page.query_selector("canvas")
            if canvas and len(ws_messages) > 4:
                bbox = await canvas.bounding_box()
                if bbox and bbox["width"] > 100:
                    logger.info("🎮 偵測到遊戲 Canvas + WS 活動，繼續處理...")
                    return

            # 進度提示（每 30 秒）
            if waited % 30_000 == 0:
                logger.info(
                    "⏳ 等待中... 已 %d 秒，WS 訊息: %d 則",
                    waited // 1000, len(ws_messages),
                )

        logger.warning("等待超時（5 分鐘），繼續嘗試處理...")

    async def _wait_for_game_ready(self, page: Page) -> None:
        """互動模式：Token 成功後等待遊戲完全載入

        偵測策略：
        1. Canvas 可見 → 遊戲已載入
        2. 最長等待 120 秒
        """
        max_wait = 120_000
        check_interval = 3_000
        waited = 0

        while waited < max_wait:
            await page.wait_for_timeout(check_interval)
            waited += check_interval

            canvas = await page.query_selector("canvas")
            if canvas:
                bbox = await canvas.bounding_box()
                if bbox and bbox["width"] > 100:
                    logger.info("🎮 偵測到遊戲已載入，繼續處理...")
                    return

        logger.warning("等待超時（120 秒），繼續處理...")

    async def _trigger_spin(self, page: Page) -> bool:
        """嘗試觸發一次 Spin（與 ReverseEngine 相同策略）

        策略（依序嘗試）：
        1. 搜尋常見 Spin 按鈕選擇器
        2. 對 Canvas 遊戲：點擊底部中央區域
        3. 嘗試用鍵盤 Space 觸發
        """
        # 策略 1: DOM 按鈕
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

        # 策略 2: Canvas 底部中央點擊
        try:
            canvas = await page.query_selector("canvas")
            if canvas:
                bbox = await canvas.bounding_box()
                if bbox:
                    x = bbox["x"] + bbox["width"] / 2
                    y = bbox["y"] + bbox["height"] * 0.88
                    await page.mouse.click(x, y)
                    logger.info("Spin 觸發嘗試（Canvas 底部中央）: (%.0f, %.0f)", x, y)
                    return True
        except Exception as e:
            logger.debug("Canvas 點擊失敗: %s", e)

        # 策略 3: Space 鍵
        try:
            await page.keyboard.press("Space")
            logger.info("Spin 觸發嘗試（Space 鍵）")
            return True
        except Exception:
            pass

        logger.warning("無法觸發 Spin")
        return False

    async def _trigger_extra_loads(self, page: Page) -> None:
        """嘗試觸發更多資源載入"""
        try:
            for selector in ["[class*='info']", "[class*='paytable']", "[class*='help']", "button"]:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements[:3]:
                        await el.click(timeout=2000)
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass
        except Exception as e:
            logger.debug("觸發額外載入失敗（非嚴重）: %s", e)

    @staticmethod
    def _url_to_filename(url: str) -> str:
        """從 URL 提取合理的檔名（含 path traversal 防護）"""
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        path = unquote(parsed.path)
        name = path.split("/")[-1] or "unknown"
        if "?" in name:
            name = name.split("?")[0]
        if "." not in name:
            name += ".bin"
        # 防止 path traversal: 移除 .. 和路徑分隔符
        name = name.replace("..", "").replace("/", "").replace("\\", "")
        # 清理不合法字元
        name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
        # 移除前後的點（防止隱藏檔案攻擊）
        name = name.strip(".")
        return (name or "unknown")[:200]

    @staticmethod
    def _safe_write(file_path: Path, target_dir: Path, body: bytes) -> bool:
        """安全寫入檔案（含路徑穿越驗證 + 大小限制）"""
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(target_dir.resolve())):
            logger.warning("路徑穿越攻擊已阻擋: %s", file_path)
            return False
        if len(body) > MAX_ASSET_BYTES:
            logger.warning("資源超過大小限制: %s (%d bytes)", file_path.name, len(body))
            return False
        file_path.write_bytes(body)
        return True
