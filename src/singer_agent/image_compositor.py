# -*- coding: utf-8 -*-
"""Singer Agent — 圖片合成模組（v0.3）

負責角色去背、角色 + 背景圖合成。

流程：
    1. rembg 去背（U2-Net，支援 GPU 加速）
    2. 角色縮放到背景高度的 85%
    3. 底部置中貼合
    4. 輸出 1920x1080 合成圖

降級策略：
    rembg 失敗 → 跳過去背，直接用原圖。
    合成失敗 → 直接使用原始角色圖。
"""

import logging
from pathlib import Path
from typing import Optional

from PIL import Image

from .config import (
    COMPOSITE_CHARACTER_SCALE,
    COMPOSITE_POSITION,
    COMPOSITES_DIR,
    IMAGES_DIR,
)

logger = logging.getLogger(__name__)


class ImageCompositor:
    """角色 + 背景合成模組"""

    # =============================================================
    # 角色去背
    # =============================================================

    @staticmethod
    def remove_background(image_path: str) -> Image.Image:
        """角色圖片去背

        使用 rembg（基於 U2-Net），支援 GPU 加速。
        如果原圖已有 alpha channel 且背景為透明，直接使用。

        Args:
            image_path: 角色圖片路徑

        Returns:
            去背後的 PIL Image（RGBA 模式）

        Raises:
            FileNotFoundError: 找不到圖片
            RuntimeError: rembg 處理失敗
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"找不到角色圖片: {image_path}")

        img = Image.open(str(path))
        logger.info("🖼️ 角色圖片: %dx%d, mode=%s", img.width, img.height, img.mode)

        # 如果已經有 alpha channel，檢查是否已去背
        if img.mode == "RGBA":
            # 檢查 alpha channel 是否有透明像素
            alpha = img.getchannel("A")
            if alpha.getextrema()[0] < 255:
                logger.info("   圖片已有透明背景，跳過去背")
                return img

        try:
            from rembg import remove
            logger.info("   rembg 去背中...")
            result = remove(img)
            logger.info("   去背完成: %dx%d", result.width, result.height)
            return result
        except Exception as e:
            logger.warning("⚠️ rembg 去背失敗: %s", e)
            # 降級：轉為 RGBA 但不去背
            return img.convert("RGBA")

    # =============================================================
    # 合成
    # =============================================================

    @staticmethod
    def composite(
        background_path: str,
        character_image: Image.Image,
        output_path: str,
        character_scale: float = 0,
        position: str = "",
    ) -> str:
        """合成角色與背景

        將去背後的角色貼到背景圖上。

        Args:
            background_path: 背景圖路徑（應為 1920x1080）
            character_image: 去背後的角色圖片（RGBA 模式）
            output_path: 輸出路徑
            character_scale: 角色高度占背景的比例（0 用 config 預設）
            position: 位置策略（留空用 config 預設）

        Returns:
            合成圖片的路徑

        Raises:
            FileNotFoundError: 找不到背景圖
        """
        if not character_scale:
            character_scale = COMPOSITE_CHARACTER_SCALE
        if not position:
            position = COMPOSITE_POSITION

        bg_path = Path(background_path)
        if not bg_path.exists():
            raise FileNotFoundError(f"找不到背景圖: {background_path}")

        bg = Image.open(str(bg_path)).convert("RGBA")
        logger.info("🖼️ 背景: %dx%d", bg.width, bg.height)

        # 確保角色是 RGBA
        char = character_image
        if char.mode != "RGBA":
            char = char.convert("RGBA")

        # 計算角色目標大小
        target_h = int(bg.height * character_scale)
        ratio = target_h / char.height
        target_w = int(char.width * ratio)

        # 避免角色寬度超過背景
        if target_w > bg.width * 0.9:
            target_w = int(bg.width * 0.9)
            ratio = target_w / char.width
            target_h = int(char.height * ratio)

        logger.info("   角色縮放: %dx%d → %dx%d (scale=%.2f)",
                     char.width, char.height, target_w, target_h, character_scale)

        char_resized = char.resize((target_w, target_h), Image.LANCZOS)

        # 計算位置
        x, y = _calculate_position(
            bg.width, bg.height,
            target_w, target_h,
            position,
        )

        # Alpha 合成
        bg.paste(char_resized, (x, y), char_resized)

        # 轉回 RGB 儲存（SadTalker 不需要 alpha）
        output = bg.convert("RGB")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        output.save(str(output_path), quality=95)

        logger.info("🖼️ 合成圖已產出: %s", output_path)
        return str(output_path)

    # =============================================================
    # SadTalker 相容性驗證
    # =============================================================

    @staticmethod
    def validate_for_sadtalker(composite_path: str) -> dict:
        """驗證合成圖是否適合 SadTalker full mode

        檢查項目：
            - 圖片尺寸是否合理（至少 512x512）
            - 人臉偵測（OpenCV Haar Cascade）
            - 人臉在圖中的面積比例

        Args:
            composite_path: 合成圖路徑

        Returns:
            {
                "valid": bool,
                "width": int,
                "height": int,
                "face_detected": bool,
                "face_count": int,
                "face_area_ratio": float,
                "issues": list[str],
            }
        """
        result = {
            "valid": True,
            "width": 0,
            "height": 0,
            "face_detected": False,
            "face_count": 0,
            "face_area_ratio": 0.0,
            "issues": [],
        }

        path = Path(composite_path)
        if not path.exists():
            result["valid"] = False
            result["issues"].append(f"圖片不存在: {composite_path}")
            return result

        img = Image.open(str(path))
        result["width"] = img.width
        result["height"] = img.height

        # 檢查尺寸
        if img.width < 512 or img.height < 512:
            result["issues"].append(
                f"圖片太小: {img.width}x{img.height}，建議至少 512x512"
            )

        # 人臉偵測
        try:
            import cv2
            import numpy as np

            # 轉為 OpenCV 格式
            cv_img = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

            # Haar Cascade 人臉偵測
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 50),
            )

            result["face_count"] = len(faces)
            result["face_detected"] = len(faces) > 0

            if len(faces) > 0:
                # 計算最大人臉的面積比
                max_area = max(w * h for (x, y, w, h) in faces)
                total_area = img.width * img.height
                result["face_area_ratio"] = max_area / total_area
            else:
                result["issues"].append("未偵測到人臉，SadTalker 可能無法運作")

        except ImportError:
            result["issues"].append("OpenCV 未安裝，跳過人臉偵測")
        except Exception as e:
            result["issues"].append(f"人臉偵測失敗: {e}")

        # 判斷整體是否通過
        if not result["face_detected"]:
            result["valid"] = False

        return result


# =============================================================
# 工具函式
# =============================================================

def _calculate_position(
    bg_w: int, bg_h: int,
    char_w: int, char_h: int,
    position: str,
) -> tuple[int, int]:
    """計算角色在背景上的位置

    Args:
        bg_w, bg_h: 背景尺寸
        char_w, char_h: 角色尺寸
        position: 位置策略

    Returns:
        (x, y) 左上角座標
    """
    if position == "center":
        x = (bg_w - char_w) // 2
        y = (bg_h - char_h) // 2
    elif position == "bottom_center":
        x = (bg_w - char_w) // 2
        y = bg_h - char_h  # 貼齊底部
    elif position == "bottom_left":
        x = int(bg_w * 0.1)
        y = bg_h - char_h
    elif position == "bottom_right":
        x = bg_w - char_w - int(bg_w * 0.1)
        y = bg_h - char_h
    else:
        # 預設底部置中
        x = (bg_w - char_w) // 2
        y = bg_h - char_h

    return x, y
