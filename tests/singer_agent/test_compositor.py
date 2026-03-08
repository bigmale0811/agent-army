# -*- coding: utf-8 -*-
"""
DEV-9: compositor.py 測試。

測試覆蓋：
- Compositor 初始化
- remove_background() dry_run
- remove_background() 呼叫 rembg（mock）
- composite() dry_run
- composite() PIL 底部置中合成
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

import pytest


def _create_test_image(path: Path, size=(200, 300), color=(255, 0, 0)):
    """建立測試用 PNG 圖片。"""
    img = Image.new("RGBA", size, color)
    img.save(path, format="PNG")
    return path


class TestCompositorInit:
    def test_can_create_instance(self):
        """可建立 Compositor 實例。"""
        from src.singer_agent.compositor import Compositor
        c = Compositor()
        assert c is not None


class TestRemoveBackgroundDryRun:
    def test_dry_run_creates_output_file(self, tmp_path):
        """dry_run 建立輸出檔。"""
        from src.singer_agent.compositor import Compositor
        src = _create_test_image(tmp_path / "char.png")
        out = tmp_path / "char_nobg.png"
        c = Compositor()
        result = c.remove_background(src, out, dry_run=True)
        assert result.exists()

    def test_dry_run_returns_output_path(self, tmp_path):
        """dry_run 回傳 output_path。"""
        from src.singer_agent.compositor import Compositor
        src = _create_test_image(tmp_path / "char.png")
        out = tmp_path / "char_nobg.png"
        c = Compositor()
        result = c.remove_background(src, out, dry_run=True)
        assert result == out

    def test_dry_run_output_is_rgba(self, tmp_path):
        """dry_run 輸出是 RGBA 格式。"""
        from src.singer_agent.compositor import Compositor
        src = _create_test_image(tmp_path / "char.png")
        out = tmp_path / "char_nobg.png"
        c = Compositor()
        c.remove_background(src, out, dry_run=True)
        img = Image.open(out)
        assert img.mode == "RGBA"


class TestRemoveBackgroundNormal:
    def test_calls_rembg_remove(self, tmp_path):
        """呼叫 rembg.remove()。"""
        from src.singer_agent.compositor import Compositor
        src = _create_test_image(tmp_path / "char.png")
        out = tmp_path / "char_nobg.png"

        # mock rembg.remove 回傳 RGBA 圖片
        mock_result = Image.new("RGBA", (200, 300), (255, 0, 0, 128))
        with patch("src.singer_agent.compositor.rembg_remove",
                    return_value=mock_result) as mock_fn:
            c = Compositor()
            c.remove_background(src, out)
            mock_fn.assert_called_once()

    def test_output_file_exists(self, tmp_path):
        """去背後輸出檔存在。"""
        from src.singer_agent.compositor import Compositor
        src = _create_test_image(tmp_path / "char.png")
        out = tmp_path / "char_nobg.png"

        mock_result = Image.new("RGBA", (200, 300), (255, 0, 0, 128))
        with patch("src.singer_agent.compositor.rembg_remove",
                    return_value=mock_result):
            c = Compositor()
            result = c.remove_background(src, out)
        assert result.exists()


class TestCompositeDryRun:
    def test_dry_run_creates_output(self, tmp_path):
        """dry_run 建立合成圖。"""
        from src.singer_agent.compositor import Compositor
        bg = _create_test_image(tmp_path / "bg.png", (1920, 1080), (0, 0, 255))
        char = _create_test_image(tmp_path / "char.png", (200, 300))
        out = tmp_path / "composite.png"
        c = Compositor()
        result = c.composite(bg, char, out, dry_run=True)
        assert result.exists()

    def test_dry_run_returns_path(self, tmp_path):
        """dry_run 回傳路徑。"""
        from src.singer_agent.compositor import Compositor
        bg = _create_test_image(tmp_path / "bg.png", (1920, 1080))
        char = _create_test_image(tmp_path / "char.png", (200, 300))
        out = tmp_path / "composite.png"
        c = Compositor()
        result = c.composite(bg, char, out, dry_run=True)
        assert result == out


class TestCompositeNormal:
    def test_composite_creates_image(self, tmp_path):
        """合成產出圖片檔。"""
        from src.singer_agent.compositor import Compositor
        bg = _create_test_image(tmp_path / "bg.png", (1920, 1080), (0, 0, 255))
        char = _create_test_image(tmp_path / "char.png", (200, 300), (255, 0, 0))
        out = tmp_path / "composite.png"
        c = Compositor()
        result = c.composite(bg, char, out)
        assert result.exists()

    def test_composite_size_matches_background(self, tmp_path):
        """合成圖尺寸與背景相同。"""
        from src.singer_agent.compositor import Compositor
        bg = _create_test_image(tmp_path / "bg.png", (1920, 1080), (0, 0, 255))
        char = _create_test_image(tmp_path / "char.png", (200, 300), (255, 0, 0))
        out = tmp_path / "composite.png"
        c = Compositor()
        c.composite(bg, char, out)
        img = Image.open(out)
        assert img.size == (1920, 1080)

    def test_composite_character_at_bottom_center(self, tmp_path):
        """角色放在底部置中（檢查非背景像素位於底部中央）。"""
        from src.singer_agent.compositor import Compositor
        bg = _create_test_image(tmp_path / "bg.png", (1920, 1080), (0, 0, 255, 255))
        # 角色是紅色 RGBA
        char = _create_test_image(tmp_path / "char.png", (200, 300), (255, 0, 0, 255))
        out = tmp_path / "composite.png"
        c = Compositor()
        c.composite(bg, char, out)
        img = Image.open(out).convert("RGBA")
        # 底部中央應有紅色像素
        center_x = 1920 // 2
        bottom_y = 1080 - 1
        pixel = img.getpixel((center_x, bottom_y))
        assert pixel[0] == 255  # 紅色通道


class TestRemoveBackgroundVramCleanup:
    """DEV-2: rembg 去背後釋放 VRAM。"""

    def test_cleanup_vram_called_after_rembg(self, tmp_path):
        """rembg 去背後呼叫 _cleanup_vram。"""
        from src.singer_agent.compositor import Compositor

        src = _create_test_image(tmp_path / "char.png")
        out = tmp_path / "char_nobg.png"

        mock_result = Image.new("RGBA", (200, 300), (255, 0, 0, 128))
        with patch("src.singer_agent.compositor.rembg_remove",
                    return_value=mock_result), \
             patch.object(Compositor, "_cleanup_vram") as mock_cleanup:
            c = Compositor()
            c.remove_background(src, out)
            mock_cleanup.assert_called_once()

    def test_cleanup_not_called_in_dry_run(self, tmp_path):
        """dry_run 不呼叫 _cleanup_vram。"""
        from src.singer_agent.compositor import Compositor

        src = _create_test_image(tmp_path / "char.png")
        out = tmp_path / "char_nobg.png"

        with patch.object(Compositor, "_cleanup_vram") as mock_cleanup:
            c = Compositor()
            c.remove_background(src, out, dry_run=True)
            mock_cleanup.assert_not_called()

    def test_cleanup_calls_force_cleanup(self):
        """_cleanup_vram 透過 vram_monitor.force_cleanup 執行。"""
        from src.singer_agent.compositor import Compositor

        with patch(
            "src.singer_agent.vram_monitor.force_cleanup"
        ) as mock_force:
            Compositor._cleanup_vram()
            mock_force.assert_called_once()
