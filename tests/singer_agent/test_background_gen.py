# -*- coding: utf-8 -*-
"""
DEV-8: background_gen.py 測試。

測試覆蓋：
- BackgroundGenerator 初始化
- dry_run 建立佔位圖並回傳路徑
- ComfyUI 呼叫（mock HTTP）
- ComfyUI 失敗時降級 PIL 純色
- 輸出圖片 1920×1080
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBackgroundGeneratorInit:
    def test_default_uses_config_url(self):
        """預設使用 config.COMFYUI_URL。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        bg = BackgroundGenerator()
        assert bg.comfyui_url is not None

    def test_custom_url_is_stored(self):
        """可注入自訂 URL。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        bg = BackgroundGenerator(comfyui_url="http://test:8188")
        assert bg.comfyui_url == "http://test:8188"


class TestGenerateDryRun:
    def test_dry_run_creates_file(self, tmp_path):
        """dry_run 建立檔案。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        bg = BackgroundGenerator()
        out = tmp_path / "bg.png"
        result = bg.generate("test prompt", out, dry_run=True)
        assert result.exists()

    def test_dry_run_returns_output_path(self, tmp_path):
        """dry_run 回傳 output_path。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        bg = BackgroundGenerator()
        out = tmp_path / "bg.png"
        result = bg.generate("test prompt", out, dry_run=True)
        assert result == out

    def test_dry_run_creates_valid_png(self, tmp_path):
        """dry_run 建立的檔案是合法圖片。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        from PIL import Image
        bg = BackgroundGenerator()
        out = tmp_path / "bg.png"
        bg.generate("prompt", out, dry_run=True)
        img = Image.open(out)
        assert img.size == (1920, 1080)


class TestGenerateFallback:
    def test_fallback_creates_1920x1080_image(self, tmp_path):
        """ComfyUI 失敗時降級 PIL，建立 1920×1080。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        from PIL import Image
        bg = BackgroundGenerator(comfyui_url="http://unreachable:9999")
        out = tmp_path / "bg.png"
        with patch("src.singer_agent.background_gen.urllib.request.urlopen",
                    side_effect=Exception("connection refused")):
            result = bg.generate("test", out)
        assert result.exists()
        img = Image.open(result)
        assert img.size == (1920, 1080)

    def test_fallback_returns_path(self, tmp_path):
        """降級 PIL 回傳路徑。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        bg = BackgroundGenerator(comfyui_url="http://unreachable:9999")
        out = tmp_path / "bg.png"
        with patch("src.singer_agent.background_gen.urllib.request.urlopen",
                    side_effect=Exception("fail")):
            result = bg.generate("test", out)
        assert result == out


class TestGenerateComfyUI:
    def test_calls_comfyui_api(self, tmp_path):
        """正常時呼叫 ComfyUI API。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        from PIL import Image
        import io

        # 建立假圖片 bytes
        img = Image.new("RGB", (1920, 1080), (100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        fake_png_bytes = buf.getvalue()

        bg = BackgroundGenerator(comfyui_url="http://localhost:8188")
        out = tmp_path / "bg.png"

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_png_bytes
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.singer_agent.background_gen.urllib.request.urlopen",
                    return_value=mock_resp):
            result = bg.generate("beautiful landscape", out)

        assert result.exists()

    def test_output_is_valid_image(self, tmp_path):
        """ComfyUI 回傳的圖片可開啟。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        from PIL import Image
        import io

        img = Image.new("RGB", (1920, 1080), (50, 100, 150))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        bg = BackgroundGenerator(comfyui_url="http://localhost:8188")
        out = tmp_path / "bg.png"

        mock_resp = MagicMock()
        mock_resp.read.return_value = buf.getvalue()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.singer_agent.background_gen.urllib.request.urlopen",
                    return_value=mock_resp):
            bg.generate("test", out)

        opened = Image.open(out)
        assert opened.size[0] > 0


class TestGenerateVramCleanup:
    """DEV-1: ComfyUI 生成後呼叫 POST /free 卸載模型。"""

    def test_free_models_called_after_success(self, tmp_path):
        """ComfyUI 成功後呼叫 _free_models。"""
        from src.singer_agent.background_gen import BackgroundGenerator
        from PIL import Image
        import io

        img = Image.new("RGB", (1920, 1080), (100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        bg = BackgroundGenerator(comfyui_url="http://localhost:8188")
        out = tmp_path / "bg.png"

        mock_resp = MagicMock()
        mock_resp.read.return_value = buf.getvalue()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.singer_agent.background_gen.urllib.request.urlopen",
                    return_value=mock_resp), \
             patch.object(bg, "_free_models") as mock_free:
            bg.generate("test", out)
            mock_free.assert_called_once()

    def test_free_models_called_after_failure(self, tmp_path):
        """ComfyUI 失敗後也呼叫 _free_models（模型可能已載入）。"""
        from src.singer_agent.background_gen import BackgroundGenerator

        bg = BackgroundGenerator(comfyui_url="http://unreachable:9999")
        out = tmp_path / "bg.png"

        with patch("src.singer_agent.background_gen.urllib.request.urlopen",
                    side_effect=Exception("connection refused")), \
             patch.object(bg, "_free_models") as mock_free:
            bg.generate("test", out)
            mock_free.assert_called_once()

    def test_free_models_not_called_in_dry_run(self, tmp_path):
        """dry_run 不呼叫 _free_models。"""
        from src.singer_agent.background_gen import BackgroundGenerator

        bg = BackgroundGenerator()
        out = tmp_path / "bg.png"

        with patch.object(bg, "_free_models") as mock_free:
            bg.generate("test", out, dry_run=True)
            mock_free.assert_not_called()

    def test_free_models_calls_vram_monitor(self):
        """_free_models 透過 vram_monitor.free_comfyui_models 執行。"""
        from src.singer_agent.background_gen import BackgroundGenerator

        bg = BackgroundGenerator(comfyui_url="http://localhost:8188")

        with patch(
            "src.singer_agent.vram_monitor.free_comfyui_models"
        ) as mock_free:
            bg._free_models()
            mock_free.assert_called_once_with("http://localhost:8188")
