# -*- coding: utf-8 -*-
"""
DEV-8: 背景圖生成模組。

BackgroundGenerator 透過 ComfyUI SDXL API 生成 1920×1080 背景圖。
ComfyUI 無法使用時自動降級為 PIL 純色背景。
"""
import json
import logging
import random
import time
import urllib.request
import urllib.error
from pathlib import Path

from PIL import Image

from src.singer_agent import config

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# ComfyUI SDXL 完整 workflow（含所有必要節點與連線）
# 節點 ID 對應：
#   4 = CheckpointLoaderSimple（載入 SDXL 模型）
#   6 = CLIPTextEncode — 正面提示詞
#   7 = CLIPTextEncode — 負面提示詞
#   5 = EmptyLatentImage（1920×1080 潛空間）
#   3 = KSampler（取樣器）
#   8 = VAEDecode（解碼圖片）
#   9 = SaveImage（儲存結果）
# ─────────────────────────────────────────────────

_COMFYUI_WORKFLOW = {
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "sd_xl_base_1.0.safetensors",
        },
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "",  # 正面提示詞（由呼叫端替換）
            "clip": ["4", 1],
        },
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "blurry, low quality, watermark, text, deformed, ugly, nsfw",
            "clip": ["4", 1],
        },
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": 1920,
            "height": 1080,
            "batch_size": 1,
        },
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 25,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["3", 0],
            "vae": ["4", 2],
        },
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "singer_bg",
            "images": ["8", 0],
        },
    },
}


class BackgroundGenerator:
    """
    背景圖生成器。

    主路徑：ComfyUI SDXL REST API 生成 1920×1080 背景。
    降級路徑：PIL 純色背景（使用 prompt 中暗示的色調）。

    Args:
        comfyui_url: ComfyUI 服務 URL，預設從 config 讀取
    """

    def __init__(self, comfyui_url: str | None = None) -> None:
        self.comfyui_url = comfyui_url or config.COMFYUI_URL

    def generate(
        self,
        prompt: str,
        output_path: Path,
        dry_run: bool = False,
    ) -> Path:
        """
        生成背景圖。

        生成完成後自動呼叫 ComfyUI POST /free 卸載 SDXL 模型，
        釋放 VRAM 給後續的 rembg / SadTalker 使用。

        Args:
            prompt: SDXL 圖片生成提示詞
            output_path: 輸出路徑
            dry_run: True 時建立純色佔位圖

        Returns:
            輸出圖片路徑
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            _logger.info("dry_run 模式：建立純色佔位圖")
            return self._create_fallback(output_path)

        # 嘗試 ComfyUI，完成後卸載模型釋放 VRAM
        try:
            result = self._generate_comfyui(prompt, output_path)
            self._free_models()
            return result
        except Exception as exc:
            # 即使生成失敗也嘗試卸載（ComfyUI 可能已載入模型）
            self._free_models()
            _logger.warning("ComfyUI 生成失敗，降級 PIL 純色：%s", exc)
            return self._create_fallback(output_path)

    def _free_models(self) -> None:
        """呼叫 ComfyUI POST /free 卸載 SDXL 模型，釋放 VRAM。"""
        from src.singer_agent.vram_monitor import free_comfyui_models
        free_comfyui_models(self.comfyui_url)

    def _generate_comfyui(self, prompt: str, output_path: Path) -> Path:
        """
        透過 ComfyUI API 生成圖片。

        完整流程：
        1. POST /api/prompt → 取得 prompt_id
        2. 輪詢 /api/history/{prompt_id} 直到完成
        3. GET /api/view?filename=... 下載圖片
        """
        _logger.info("呼叫 ComfyUI API: %s", self.comfyui_url)

        # 組裝 workflow payload（深拷貝避免污染模板）
        workflow = json.loads(json.dumps(_COMFYUI_WORKFLOW))
        workflow["6"]["inputs"]["text"] = prompt
        # 隨機 seed 確保每次產出不同
        workflow["3"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)

        payload = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.comfyui_url}/api/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # Step 1: 提交 prompt，取得 prompt_id
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        prompt_id = result["prompt_id"]
        _logger.info("ComfyUI prompt 已提交：%s", prompt_id)

        # Step 2: 輪詢等待完成（最多 180 秒）
        image_filename = self._poll_for_result(prompt_id, timeout=180)

        # Step 3: 下載生成的圖片
        view_url = (
            f"{self.comfyui_url}/api/view"
            f"?filename={image_filename}&type=output"
        )
        with urllib.request.urlopen(view_url, timeout=30) as resp:
            image_data = resp.read()

        output_path.write_bytes(image_data)
        _logger.info("ComfyUI 背景圖已生成：%s（%d bytes）", output_path, len(image_data))
        return output_path

    def _poll_for_result(self, prompt_id: str, timeout: int = 180) -> str:
        """
        輪詢 ComfyUI 直到 prompt 完成，回傳輸出圖片檔名。

        Args:
            prompt_id: ComfyUI prompt ID
            timeout: 最大等待秒數

        Returns:
            輸出圖片的檔名

        Raises:
            TimeoutError: 超時未完成
            RuntimeError: 生成過程中發生錯誤
        """
        start = time.time()
        while time.time() - start < timeout:
            url = f"{self.comfyui_url}/api/history/{prompt_id}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                history = json.loads(resp.read())

            if prompt_id in history:
                entry = history[prompt_id]
                # 檢查是否有錯誤
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    msgs = status.get("messages", [])
                    raise RuntimeError(f"ComfyUI 生成錯誤：{msgs}")

                # 從輸出節點取得圖片檔名
                outputs = entry.get("outputs", {})
                for node_id, node_output in outputs.items():
                    images = node_output.get("images", [])
                    if images:
                        filename = images[0]["filename"]
                        _logger.info("ComfyUI 生成完成：%s", filename)
                        return filename

            # 尚未完成，等待後重試
            time.sleep(2)

        raise TimeoutError(
            f"ComfyUI 生成超時（{timeout}s），prompt_id={prompt_id}"
        )

    def _create_fallback(self, output_path: Path) -> Path:
        """建立 PIL 純色降級背景（1920×1080）。"""
        # 使用柔和的漸層灰藍色作為預設背景
        img = Image.new("RGB", (1920, 1080), (70, 90, 120))
        img.save(output_path, format="PNG")
        _logger.info("PIL 降級背景已建立：%s", output_path)
        return output_path
