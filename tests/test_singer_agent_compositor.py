# -*- coding: utf-8 -*-
"""Singer Agent — 圖片合成模組測試

涵蓋 ImageCompositor 的去背、合成、SadTalker 驗證方法，
以及 _calculate_position 工具函式。
所有外部依賴（rembg、cv2）皆透過 mock 隔離。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.singer_agent.image_compositor import (
    ImageCompositor,
    _calculate_position,
)


# =====================================================================
# 輔助：建立測試用圖片
# =====================================================================

def _create_rgb_image(tmp_path: Path, name: str = "test.png",
                      size: tuple = (640, 480), color=(100, 150, 200)) -> Path:
    """在 tmp_path 建立 RGB PNG 圖片"""
    img = Image.new("RGB", size, color)
    p = tmp_path / name
    img.save(str(p))
    return p


def _create_rgba_image(tmp_path: Path, name: str = "test_rgba.png",
                       size: tuple = (300, 600),
                       has_transparency: bool = True) -> Path:
    """在 tmp_path 建立 RGBA PNG 圖片（含透明像素）"""
    img = Image.new("RGBA", size, (255, 0, 0, 255))
    if has_transparency:
        # 讓部分像素為透明
        pixels = img.load()
        for x in range(50):
            for y in range(50):
                pixels[x, y] = (0, 0, 0, 0)
    p = tmp_path / name
    img.save(str(p))
    return p


# =====================================================================
# ImageCompositor.remove_background()
# =====================================================================

class TestRemoveBackground:
    """測試角色圖片去背功能"""

    def test_raises_file_not_found_for_missing_image(self, tmp_path):
        """圖片不存在時應拋出 FileNotFoundError"""
        missing = str(tmp_path / "nonexistent.png")
        with pytest.raises(FileNotFoundError, match="找不到角色圖片"):
            ImageCompositor.remove_background(missing)

    def test_rgba_with_transparency_passthrough(self, tmp_path):
        """已有透明背景的 RGBA 圖片應直接回傳，不呼叫 rembg"""
        rgba_path = _create_rgba_image(tmp_path, has_transparency=True)

        with patch("rembg.remove") as mock_rembg:
            result = ImageCompositor.remove_background(str(rgba_path))

        # 已有透明像素，不應呼叫 rembg
        mock_rembg.assert_not_called()
        assert result.mode == "RGBA"

    def test_rgb_image_calls_rembg(self, tmp_path):
        """RGB 圖片應呼叫 rembg.remove 去背，結果為 RGBA 模式"""
        rgb_path = _create_rgb_image(tmp_path)
        expected_result = Image.new("RGBA", (640, 480), (255, 0, 0, 128))

        # rembg 是在 try block 內以 `from rembg import remove` 引入，
        # 透過 sys.modules 注入 mock 模組來截取呼叫
        mock_rembg_remove = MagicMock(return_value=expected_result)
        import sys
        fake_rembg = MagicMock()
        fake_rembg.remove = mock_rembg_remove
        with patch.dict(sys.modules, {"rembg": fake_rembg}):
            result = ImageCompositor.remove_background(str(rgb_path))

        # rembg.remove 應被呼叫，且回傳 RGBA 圖片
        mock_rembg_remove.assert_called_once()
        assert result.mode == "RGBA"

    def test_rgba_fully_opaque_calls_rembg(self, tmp_path):
        """RGBA 圖片但無透明像素（完全不透明）時，應呼叫 rembg 去背"""
        # 建立完全不透明的 RGBA 圖片
        rgba_path = _create_rgba_image(tmp_path, name="opaque_rgba.png", has_transparency=False)
        expected = Image.new("RGBA", (300, 600), (0, 255, 0, 128))

        import sys
        fake_rembg = MagicMock()
        fake_rembg.remove = MagicMock(return_value=expected)
        with patch.dict(sys.modules, {"rembg": fake_rembg}):
            result = ImageCompositor.remove_background(str(rgba_path))

        assert result.mode == "RGBA"

    def test_rembg_failure_falls_back_to_rgba_convert(self, tmp_path):
        """rembg 拋出例外時，應降級為轉換 RGBA 而不是拋出例外"""
        rgb_path = _create_rgb_image(tmp_path)

        import sys
        fake_rembg = MagicMock()
        fake_rembg.remove = MagicMock(side_effect=RuntimeError("GPU out of memory"))
        with patch.dict(sys.modules, {"rembg": fake_rembg}):
            result = ImageCompositor.remove_background(str(rgb_path))

        # 降級後仍應是 RGBA 模式
        assert result.mode == "RGBA"


# =====================================================================
# ImageCompositor.composite()
# =====================================================================

class TestComposite:
    """測試角色與背景合成"""

    def test_composite_creates_output_file(self, tmp_path):
        """合成應建立實際的 PNG 輸出檔"""
        # 建立背景圖（1920x1080 的 RGB）
        bg_path = _create_rgb_image(tmp_path, "bg.png", (1920, 1080), (44, 62, 80))
        # 建立角色圖（300x600 的 RGBA）
        char_img = Image.new("RGBA", (300, 600), (255, 100, 100, 200))
        output_path = str(tmp_path / "composite.png")

        with patch("src.singer_agent.image_compositor.COMPOSITE_CHARACTER_SCALE", 0.85), \
             patch("src.singer_agent.image_compositor.COMPOSITE_POSITION", "bottom_center"):
            result = ImageCompositor.composite(
                background_path=str(bg_path),
                character_image=char_img,
                output_path=output_path,
            )

        assert Path(result).exists()
        out_img = Image.open(result)
        # 輸出應為 RGB（SadTalker 不需要 alpha）
        assert out_img.mode == "RGB"

    def test_composite_raises_for_missing_background(self, tmp_path):
        """背景圖不存在時應拋出 FileNotFoundError"""
        missing_bg = str(tmp_path / "no_bg.png")
        char_img = Image.new("RGBA", (200, 400), (255, 255, 0, 255))
        output_path = str(tmp_path / "out.png")

        with pytest.raises(FileNotFoundError, match="找不到背景圖"):
            ImageCompositor.composite(
                background_path=missing_bg,
                character_image=char_img,
                output_path=output_path,
            )

    def test_composite_respects_custom_scale(self, tmp_path):
        """custom character_scale 應影響角色縮放比例"""
        bg_path = _create_rgb_image(tmp_path, "bg.png", (800, 600))
        char_img = Image.new("RGBA", (200, 400), (0, 255, 0, 200))
        output_path = str(tmp_path / "scaled.png")

        ImageCompositor.composite(
            background_path=str(bg_path),
            character_image=char_img,
            output_path=output_path,
            character_scale=0.5,
            position="center",
        )

        assert Path(output_path).exists()

    def test_composite_output_is_rgb_not_rgba(self, tmp_path):
        """合成結果必須是 RGB（不含 alpha），確保 SadTalker 相容性"""
        bg_path = _create_rgb_image(tmp_path, "bg.png", (1920, 1080))
        char_img = Image.new("RGBA", (300, 500), (100, 200, 255, 180))
        output_path = str(tmp_path / "rgb_out.png")

        ImageCompositor.composite(
            background_path=str(bg_path),
            character_image=char_img,
            output_path=output_path,
        )

        out_img = Image.open(output_path)
        assert out_img.mode == "RGB"

    def test_composite_creates_parent_dirs(self, tmp_path):
        """輸出路徑的父目錄不存在時，應自動建立"""
        bg_path = _create_rgb_image(tmp_path, "bg.png", (1920, 1080))
        char_img = Image.new("RGBA", (200, 300), (255, 200, 100, 200))
        nested_output = str(tmp_path / "deep" / "nested" / "output.png")

        ImageCompositor.composite(
            background_path=str(bg_path),
            character_image=char_img,
            output_path=nested_output,
        )

        assert Path(nested_output).exists()


# =====================================================================
# ImageCompositor.validate_for_sadtalker()
# =====================================================================

class TestValidateForSadtalker:
    """測試 SadTalker 相容性驗證"""

    def test_returns_invalid_for_missing_image(self, tmp_path):
        """圖片不存在時結果應為 invalid"""
        missing = str(tmp_path / "no_file.png")
        result = ImageCompositor.validate_for_sadtalker(missing)

        assert result["valid"] is False
        assert any("不存在" in issue for issue in result["issues"])

    def test_returns_valid_with_face_detected(self, tmp_path):
        """偵測到人臉時應為 valid"""
        img_path = _create_rgb_image(tmp_path, "face.png", (1920, 1080))

        # 模擬 cv2 偵測到一張人臉
        fake_faces = np.array([[400, 300, 200, 200]])  # (x, y, w, h)

        mock_cv2 = MagicMock()
        mock_cv2.cvtColor = MagicMock(return_value=np.zeros((1080, 1920, 3), dtype=np.uint8))
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.data = MagicMock()
        mock_cv2.data.haarcascades = ""

        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale = MagicMock(return_value=fake_faces)
        mock_cv2.CascadeClassifier = MagicMock(return_value=mock_cascade)

        import sys
        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": np}):
            result = ImageCompositor.validate_for_sadtalker(str(img_path))

        assert result["face_detected"] is True
        assert result["face_count"] == 1
        assert result["face_area_ratio"] > 0

    def test_returns_invalid_when_no_face_detected(self, tmp_path):
        """未偵測到人臉時，valid 應為 False"""
        img_path = _create_rgb_image(tmp_path, "no_face.png", (1920, 1080))

        # 模擬 cv2 沒有偵測到人臉（回傳空 array）
        mock_cv2 = MagicMock()
        mock_cv2.cvtColor = MagicMock(return_value=np.zeros((1080, 1920, 3), dtype=np.uint8))
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.data = MagicMock()
        mock_cv2.data.haarcascades = ""

        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale = MagicMock(return_value=np.array([]))
        mock_cv2.CascadeClassifier = MagicMock(return_value=mock_cascade)

        import sys
        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": np}):
            result = ImageCompositor.validate_for_sadtalker(str(img_path))

        assert result["face_detected"] is False
        assert result["valid"] is False

    def test_reports_issue_for_small_image(self, tmp_path):
        """圖片尺寸小於 512x512 時 issues 應有警告"""
        # 建立 200x200 的小圖（不含人臉偵測）
        small_img = Image.new("RGB", (200, 200), (100, 100, 100))
        p = tmp_path / "small.png"
        small_img.save(str(p))

        # 讓 cv2 import 失敗（ImportError），確認尺寸檢查仍觸發
        import sys
        broken_cv2 = MagicMock()
        broken_cv2.cvtColor = MagicMock(side_effect=ImportError("no cv2"))
        # 注意：validate_for_sadtalker 在 except ImportError 才加入「OpenCV 未安裝」
        # 使圖片尺寸問題先被記錄
        with patch.dict(sys.modules, {"cv2": None}):
            result = ImageCompositor.validate_for_sadtalker(str(p))

        assert result["width"] == 200
        assert result["height"] == 200
        # 尺寸問題應在 issues 中
        assert any("小" in issue or "512" in issue for issue in result["issues"])

    def test_returns_width_and_height(self, tmp_path):
        """結果 dict 應包含正確的寬度與高度"""
        img_path = _create_rgb_image(tmp_path, "size_test.png", (1920, 1080))

        # 讓 cv2 不可用，只測尺寸部分
        import sys
        with patch.dict(sys.modules, {"cv2": None}):
            result = ImageCompositor.validate_for_sadtalker(str(img_path))

        assert result["width"] == 1920
        assert result["height"] == 1080


# =====================================================================
# _calculate_position()
# =====================================================================

class TestCalculatePosition:
    """測試角色位置計算工具函式"""

    # 背景 1920x1080，角色 400x700
    BG_W, BG_H = 1920, 1080
    CHAR_W, CHAR_H = 400, 700

    def test_center_position(self):
        """center：角色應居中於背景"""
        x, y = _calculate_position(
            self.BG_W, self.BG_H, self.CHAR_W, self.CHAR_H, "center"
        )
        assert x == (self.BG_W - self.CHAR_W) // 2
        assert y == (self.BG_H - self.CHAR_H) // 2

    def test_bottom_center_position(self):
        """bottom_center：角色水平置中，垂直貼齊底部"""
        x, y = _calculate_position(
            self.BG_W, self.BG_H, self.CHAR_W, self.CHAR_H, "bottom_center"
        )
        assert x == (self.BG_W - self.CHAR_W) // 2
        assert y == self.BG_H - self.CHAR_H

    def test_bottom_left_position(self):
        """bottom_left：角色靠左（10% 邊距），垂直貼齊底部"""
        x, y = _calculate_position(
            self.BG_W, self.BG_H, self.CHAR_W, self.CHAR_H, "bottom_left"
        )
        assert x == int(self.BG_W * 0.1)
        assert y == self.BG_H - self.CHAR_H

    def test_bottom_right_position(self):
        """bottom_right：角色靠右（10% 邊距），垂直貼齊底部"""
        x, y = _calculate_position(
            self.BG_W, self.BG_H, self.CHAR_W, self.CHAR_H, "bottom_right"
        )
        expected_x = self.BG_W - self.CHAR_W - int(self.BG_W * 0.1)
        assert x == expected_x
        assert y == self.BG_H - self.CHAR_H

    def test_default_position_is_bottom_center(self):
        """未知 position 字串應使用預設（底部置中）"""
        x_default, y_default = _calculate_position(
            self.BG_W, self.BG_H, self.CHAR_W, self.CHAR_H, "unknown_position"
        )
        x_bc, y_bc = _calculate_position(
            self.BG_W, self.BG_H, self.CHAR_W, self.CHAR_H, "bottom_center"
        )
        assert x_default == x_bc
        assert y_default == y_bc

    def test_position_values_are_integers(self):
        """回傳的座標應為整數類型"""
        x, y = _calculate_position(
            self.BG_W, self.BG_H, self.CHAR_W, self.CHAR_H, "center"
        )
        assert isinstance(x, int)
        assert isinstance(y, int)

    def test_bottom_center_with_square_images(self):
        """正方形圖片的 bottom_center 座標計算應正確"""
        x, y = _calculate_position(1000, 1000, 500, 500, "bottom_center")
        assert x == 250
        assert y == 500
