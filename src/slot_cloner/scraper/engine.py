"""資源擷取引擎 — 攔截 Network 請求，分類下載遊戲資源"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
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
    """資源擷取引擎 — 透過 Playwright Network 攔截"""

    def __init__(
        self,
        output_dir: Path | None = None,
        headless: bool = True,
        timeout_ms: int = 60000,
    ) -> None:
        self._output_dir = output_dir or Path("./output")
        self._headless = headless
        self._timeout_ms = timeout_ms

    async def scrape(self, fingerprint: GameFingerprint) -> AssetBundle:
        """擷取目標遊戲的所有資源"""
        images: list[ImageAsset] = []
        audio_list: list[AudioAsset] = []
        sprites: list[SpriteSheet] = []
        raw_configs: dict[str, object] = {}

        # 確保輸出目錄存在
        img_dir = self._output_dir / "assets" / "images"
        audio_dir = self._output_dir / "assets" / "audio"
        config_dir = self._output_dir / "analysis"
        for d in (img_dir, audio_dir, config_dir):
            d.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self._headless)
            try:
                page = await browser.new_page()

                # 攔截所有回應，依 MIME type 分類儲存
                async def handle_response(response):
                    try:
                        content_type = response.headers.get("content-type", "")
                        url = response.url
                        status = response.status

                        if status != 200:
                            return

                        # 從 URL 提取檔名
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
                            import json
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

                # 注入 Web Audio API hook — 攔截動態載入的音效
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

                logger.info("開始擷取資源: %s", fingerprint.url)
                await page.goto(fingerprint.url, wait_until="networkidle", timeout=self._timeout_ms)

                # 等待遊戲完全載入
                await page.wait_for_selector("canvas", timeout=self._timeout_ms)

                # 嘗試觸發更多資源載入（點擊遊戲區域、開啟 paytable 等）
                await self._trigger_extra_loads(page)

                # 收集 Web Audio API hook 攔截到的音效 URL
                hooked_urls = await page.evaluate("window.__audioUrls || []")
                if hooked_urls:
                    logger.info("Web Audio hook 偵測到 %d 個額外音效 URL", len(hooked_urls))
                    for url in hooked_urls:
                        file_name = self._url_to_filename(url)
                        # 避免重複（已被 response handler 擷取的不重複下載）
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
                    "擷取完成: %d 圖片, %d 音效, %d 設定檔",
                    len(images), len(audio_list), len(raw_configs),
                )

            finally:
                await browser.close()

        return AssetBundle(
            images=tuple(images),
            sprites=tuple(sprites),
            audio=tuple(audio_list),
            raw_configs=raw_configs,
        )

    async def _trigger_extra_loads(self, page: Page) -> None:
        """嘗試觸發更多資源載入"""
        try:
            # 嘗試點擊常見的 paytable/info 按鈕
            for selector in ["[class*='info']", "[class*='paytable']", "[class*='help']", "button"]:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements[:3]:  # 最多點擊 3 個
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
