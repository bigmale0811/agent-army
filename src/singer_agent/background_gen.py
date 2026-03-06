# -*- coding: utf-8 -*-
"""
DEV-8: 背景圖生成模組。

BackgroundGenerator 透過 ComfyUI SDXL API 生成 1920×1080 背景圖。
ComfyUI 無法使用時自動降級為 PIL 純色背景。
"""
import json
import logging
import urllib.request
import urllib.error
from pathlib import Path

from PIL import Image

from src.singer_agent import config

_logger = logging.getLogger(__name__)

# ComfyUI SDXL workflow 簡化版 JSON（prompt → image）
_COMFYUI_WORKFLOW = {
    "prompt": {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": ""},  # 會被替換為實際 prompt
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

        # 嘗試 ComfyUI
        try:
            return self._generate_comfyui(prompt, output_path)
        except Exception as exc:
            _logger.warning("ComfyUI 生成失敗，降級 PIL 純色：%s", exc)
            return self._create_fallback(output_path)

    def _generate_comfyui(self, prompt: str, output_path: Path) -> Path:
        """透過 ComfyUI API 生成圖片。"""
        _logger.debug("呼叫 ComfyUI API: %s", self.comfyui_url)

        # 組裝 workflow payload
        workflow = json.loads(json.dumps(_COMFYUI_WORKFLOW))
        workflow["prompt"]["6"]["inputs"]["text"] = prompt

        data = json.dumps(workflow).encode("utf-8")
        req = urllib.request.Request(
            f"{self.comfyui_url}/api/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            image_data = resp.read()

        output_path.write_bytes(image_data)
        _logger.info("ComfyUI 背景圖已生成：%s", output_path)
        return output_path

    def _create_fallback(self, output_path: Path) -> Path:
        """建立 PIL 純色降級背景（1920×1080）。"""
        # 使用柔和的漸層灰藍色作為預設背景
        img = Image.new("RGB", (1920, 1080), (70, 90, 120))
        img.save(output_path, format="PNG")
        _logger.info("PIL 降級背景已建立：%s", output_path)
        return output_path
