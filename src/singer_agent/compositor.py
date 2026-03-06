# -*- coding: utf-8 -*-
"""
DEV-9: 角色合成模組。

Compositor 提供：
- remove_background()：使用 rembg 去背景，產出 RGBA 圖片
- composite()：使用 PIL 將角色合成到背景上（底部置中）
"""
import logging
from pathlib import Path

from PIL import Image

_logger = logging.getLogger(__name__)

# 延遲匯入 rembg，避免無 rembg 時 import 失敗
try:
    from rembg import remove as rembg_remove
except ImportError:
    rembg_remove = None  # type: ignore[assignment]


class Compositor:
    """
    角色圖片去背與合成器。

    Step 5a: remove_background() — rembg 去背景
    Step 5b: composite() — PIL 底部置中合成
    """

    def remove_background(
        self,
        character_path: Path,
        output_path: Path,
        dry_run: bool = False,
    ) -> Path:
        """
        移除角色圖片背景。

        Args:
            character_path: 原始角色圖片路徑
            output_path: 去背後輸出路徑
            dry_run: True 時直接複製為 RGBA 而不呼叫 rembg

        Returns:
            去背後圖片路徑
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            _logger.info("dry_run 模式：複製為 RGBA")
            img = Image.open(character_path).convert("RGBA")
            img.save(output_path, format="PNG")
            return output_path

        _logger.info("使用 rembg 去背：%s", character_path)
        input_img = Image.open(character_path)
        result = rembg_remove(input_img)
        # 確保結果是 RGBA
        if result.mode != "RGBA":
            result = result.convert("RGBA")
        result.save(output_path, format="PNG")
        _logger.info("去背完成：%s", output_path)
        return output_path

    def composite(
        self,
        background_path: Path,
        character_nobg_path: Path,
        output_path: Path,
        dry_run: bool = False,
    ) -> Path:
        """
        將角色合成到背景上（底部置中）。

        Args:
            background_path: 背景圖片路徑
            character_nobg_path: 去背後角色圖片路徑
            output_path: 合成後輸出路徑
            dry_run: True 時簡單合成

        Returns:
            合成後圖片路徑
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        bg = Image.open(background_path).convert("RGBA")
        char = Image.open(character_nobg_path).convert("RGBA")

        # 計算底部置中位置
        bg_w, bg_h = bg.size
        ch_w, ch_h = char.size

        # 水平置中、垂直靠底部
        x = (bg_w - ch_w) // 2
        y = bg_h - ch_h

        # 合成（使用 alpha 通道作為遮罩）
        bg.paste(char, (x, y), char)
        bg.save(output_path, format="PNG")
        _logger.info("合成完成：%s", output_path)
        return output_path
