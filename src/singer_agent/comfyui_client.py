# -*- coding: utf-8 -*-
"""Singer Agent — ComfyUI API 客戶端

透過 ComfyUI 的 REST + WebSocket API 生成背景圖片。

流程：
    1. POST /prompt 送出 workflow JSON
    2. WS 監聽執行進度
    3. GET /view 下載產出圖片

降級策略：
    ComfyUI 不可用時，產出 PIL 純色背景圖（保持 v0.2 行為）。
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

import httpx

from .config import (
    COMFYUI_HOST,
    COMFYUI_PORT,
    COMFYUI_CHECKPOINT,
    COMFYUI_TIMEOUT,
    COMFYUI_DEFAULT_STEPS,
    COMFYUI_DEFAULT_CFG,
    COMFYUI_NEGATIVE_PROMPT,
    BACKGROUNDS_DIR,
)

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """ComfyUI API 客戶端

    透過 REST API 送出 workflow、下載結果。
    WebSocket 監聽進度（可選，目前用 polling 簡化實作）。
    """

    def __init__(
        self,
        host: str = "",
        port: int = 0,
        checkpoint: str = "",
    ):
        self._host = host or COMFYUI_HOST
        self._port = port or COMFYUI_PORT
        self._checkpoint = checkpoint or COMFYUI_CHECKPOINT
        self._base_url = f"http://{self._host}:{self._port}"
        self._client_id = str(uuid.uuid4())

    # =============================================================
    # 可用性檢查
    # =============================================================

    async def is_available(self) -> bool:
        """檢查 ComfyUI 服務是否在線

        Returns:
            True 表示 ComfyUI 可正常呼叫
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/system_stats")
                return resp.status_code == 200
        except Exception:
            return False

    # =============================================================
    # 背景圖生成
    # =============================================================

    async def generate_background(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1920,
        height: int = 1080,
        steps: int = 0,
        cfg: float = 0,
        seed: int = -1,
        output_filename: str = "",
    ) -> Path:
        """txt2img 生成背景圖（16:9 比例）

        使用 SongSpec.background_prompt + color_palette 組合 prompt。
        固定輸出指定尺寸確保影片比例正確。

        Args:
            prompt: 正面提示詞（英文）
            negative_prompt: 負面提示詞（留空用預設）
            width: 圖片寬度（預設 1920）
            height: 圖片高度（預設 1080）
            steps: 取樣步數（0 用 config 預設）
            cfg: CFG scale（0 用 config 預設）
            seed: 隨機種子（-1 為隨機）
            output_filename: 輸出檔名（留空自動生成）

        Returns:
            生成的背景圖片 Path

        Raises:
            RuntimeError: ComfyUI 執行失敗
        """
        if not steps:
            steps = COMFYUI_DEFAULT_STEPS
        if not cfg:
            cfg = COMFYUI_DEFAULT_CFG
        if not negative_prompt:
            negative_prompt = COMFYUI_NEGATIVE_PROMPT
        if seed == -1:
            import random
            seed = random.randint(0, 2**32 - 1)

        logger.info("🎨 ComfyUI 生成背景圖...")
        logger.info("   Prompt: %s", prompt[:100])
        logger.info("   尺寸: %dx%d, Steps: %d, CFG: %.1f", width, height, steps, cfg)

        # 建構 workflow
        workflow = self._build_txt2img_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
        )

        # 送出並等待完成
        prompt_id = await self._queue_prompt(workflow)
        result = await self._poll_until_complete(prompt_id)

        # 下載輸出圖片
        output_images = self._extract_output_images(result)
        if not output_images:
            raise RuntimeError("ComfyUI 完成但沒有輸出圖片")

        # 取第一張圖片
        img_info = output_images[0]
        image_data = await self._download_output(
            filename=img_info["filename"],
            subfolder=img_info.get("subfolder", ""),
            output_type=img_info.get("type", "output"),
        )

        # 儲存到 backgrounds 目錄
        if not output_filename:
            output_filename = f"bg_{prompt_id[:8]}.png"
        save_path = BACKGROUNDS_DIR / output_filename
        save_path.write_bytes(image_data)

        logger.info("🎨 背景圖已生成: %s (%.1f KB)", save_path, len(image_data) / 1024)
        return save_path

    # =============================================================
    # 釋放 VRAM
    # =============================================================

    async def free_vram(self) -> None:
        """請求 ComfyUI 釋放 GPU VRAM

        在背景圖生成完成後呼叫，讓 SadTalker 有足夠的 VRAM。
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._base_url}/free",
                    json={"unload_models": True, "free_memory": True},
                )
                logger.info("🧹 ComfyUI VRAM 已釋放")
        except Exception as e:
            logger.warning("⚠️ ComfyUI VRAM 釋放失敗: %s", e)

    # =============================================================
    # 內部方法：API 互動
    # =============================================================

    async def _queue_prompt(self, workflow: dict) -> str:
        """送出 workflow 到 ComfyUI

        Args:
            workflow: ComfyUI API 格式的 workflow JSON

        Returns:
            prompt_id

        Raises:
            RuntimeError: 送出失敗
        """
        payload = {
            "prompt": workflow,
            "client_id": self._client_id,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base_url}/prompt",
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"ComfyUI prompt 送出失敗: {resp.status_code} {resp.text[:200]}"
                )
            data = resp.json()
            prompt_id = data.get("prompt_id", "")
            if not prompt_id:
                raise RuntimeError(f"ComfyUI 回應中沒有 prompt_id: {data}")

            logger.info("   prompt_id: %s", prompt_id)
            return prompt_id

    async def _poll_until_complete(
        self, prompt_id: str, timeout: int = 0
    ) -> dict:
        """輪詢等待 ComfyUI 執行完成

        Args:
            prompt_id: 要等待的 prompt ID
            timeout: 最大等待秒數（0 用 config 預設）

        Returns:
            history 中的執行結果

        Raises:
            RuntimeError: 執行失敗或超時
        """
        import asyncio
        import time

        if not timeout:
            timeout = COMFYUI_TIMEOUT

        start = time.time()
        poll_interval = 2.0  # 每 2 秒檢查一次

        while time.time() - start < timeout:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/history/{prompt_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    if prompt_id in data:
                        result = data[prompt_id]
                        # 檢查是否有錯誤
                        status = result.get("status", {})
                        if status.get("status_str") == "error":
                            msgs = status.get("messages", [])
                            raise RuntimeError(
                                f"ComfyUI 執行錯誤: {msgs}"
                            )
                        return result

            await asyncio.sleep(poll_interval)

        raise RuntimeError(f"ComfyUI 執行超時（{timeout} 秒）")

    async def _download_output(
        self,
        filename: str,
        subfolder: str = "",
        output_type: str = "output",
    ) -> bytes:
        """下載 ComfyUI 產出的圖片

        Args:
            filename: 圖片檔名
            subfolder: 子目錄
            output_type: 類型（output / temp）

        Returns:
            圖片的二進位資料
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": output_type,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base_url}/view",
                params=params,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"ComfyUI 圖片下載失敗: {resp.status_code}"
                )
            return resp.content

    # =============================================================
    # 內部方法：Workflow 建構
    # =============================================================

    def _build_txt2img_workflow(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        cfg: float,
        seed: int,
    ) -> dict:
        """建構 txt2img workflow JSON（ComfyUI API 格式）

        ComfyUI API 格式是扁平的節點 dict，key 為節點 ID。

        節點架構：
            3: KSampler → 4: VAEDecode → 9: SaveImage
            4: CheckpointLoaderSimple → 連到 KSampler + CLIPTextEncode
            6: CLIPTextEncode (positive)
            7: CLIPTextEncode (negative)
            5: EmptyLatentImage → 連到 KSampler
        """
        return {
            # 模型載入
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": self._checkpoint,
                },
            },
            # 正面提示
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["4", 1],
                },
            },
            # 負面提示
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["4", 1],
                },
            },
            # 空白 latent
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1,
                },
            },
            # 採樣器
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            # VAE 解碼
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2],
                },
            },
            # 儲存圖片
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["8", 0],
                    "filename_prefix": "singer_bg",
                },
            },
        }

    @staticmethod
    def _extract_output_images(result: dict) -> list[dict]:
        """從 ComfyUI history 結果中提取輸出圖片資訊

        Args:
            result: /history/{prompt_id} 的回應

        Returns:
            [{"filename": "...", "subfolder": "...", "type": "output"}, ...]
        """
        images = []
        outputs = result.get("outputs", {})
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                images.extend(node_output["images"])
        return images


# =============================================================
# 降級方案：PIL 純色背景
# =============================================================

def generate_solid_background(
    mood: str,
    width: int = 1920,
    height: int = 1080,
    output_filename: str = "",
) -> Path:
    """產出純色背景圖（ComfyUI 不可用時的降級方案）

    Args:
        mood: 情緒分類（決定背景顏色）
        width: 圖片寬度
        height: 圖片高度
        output_filename: 輸出檔名

    Returns:
        背景圖片 Path
    """
    from PIL import Image

    # 情緒對應的 RGB 顏色
    mood_colors = {
        "happy": (255, 248, 220),       # 暖黃
        "sad": (44, 62, 80),            # 深藍灰
        "energetic": (255, 71, 87),     # 活力紅
        "calm": (223, 230, 233),        # 柔和灰
        "romantic": (253, 121, 168),    # 粉紅
        "dark": (45, 52, 54),           # 暗色
        "epic": (108, 92, 231),         # 紫色
        "nostalgic": (253, 203, 110),   # 復古金
    }
    color = mood_colors.get(mood, (44, 62, 80))

    img = Image.new("RGB", (width, height), color)

    if not output_filename:
        output_filename = f"bg_solid_{mood}.png"

    save_path = BACKGROUNDS_DIR / output_filename
    img.save(str(save_path), quality=95)

    logger.info("🎨 純色背景圖已產出（降級模式）: %s", save_path)
    return save_path


def build_background_prompt(spec) -> str:
    """從 SongSpec 組合背景圖的 prompt

    結合 background_prompt、color_palette、visual_style，
    產出適合 Stable Diffusion 的英文 prompt。

    Args:
        spec: SongSpec 物件

    Returns:
        組合後的 prompt 字串
    """
    parts = []

    if spec.background_prompt:
        parts.append(spec.background_prompt)

    if spec.visual_style:
        parts.append(spec.visual_style)

    if spec.color_palette:
        if isinstance(spec.color_palette, list):
            parts.append(f"color palette: {', '.join(spec.color_palette)}")
        elif isinstance(spec.color_palette, str):
            parts.append(spec.color_palette)

    # 品質提示
    parts.append("masterpiece, best quality, highly detailed, cinematic lighting")
    # 確保沒有人物
    parts.append("no people, no characters, empty scene, background only")

    return ", ".join(parts)
