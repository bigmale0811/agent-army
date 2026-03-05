# -*- coding: utf-8 -*-
"""Singer Agent — ComfyUI 客戶端測試

涵蓋 ComfyUIClient 的所有公開方法，以及 generate_solid_background
和 build_background_prompt 兩個模組級函式。
所有外部依賴（httpx、PIL 寫檔、BACKGROUNDS_DIR）皆透過 mock 隔離。
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from PIL import Image

from src.singer_agent.models import SongSpec


# =====================================================================
# 輔助：建立標準 SongSpec 測試物件
# =====================================================================

def _make_spec(**kwargs) -> SongSpec:
    """建立用於測試的 SongSpec 實例"""
    defaults = dict(
        title="Test Song",
        artist="Test Artist",
        mood="romantic",
        background_prompt="sunset over ocean",
        visual_style="dreamy watercolor",
        color_palette="warm tones",
        scene_description="夕陽海邊",
    )
    defaults.update(kwargs)
    return SongSpec(**defaults)


# =====================================================================
# ComfyUIClient.is_available()
# =====================================================================

class TestIsAvailable:
    """測試 ComfyUI 服務可用性檢查"""

    @pytest.mark.asyncio
    async def test_is_available_returns_true_on_200(self):
        """當 /system_stats 回傳 200 時，應回傳 True"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        # Mock httpx.AsyncClient 讓 GET 回傳 200
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.singer_agent.comfyui_client.httpx.AsyncClient", return_value=mock_client):
            client = ComfyUIClient(host="127.0.0.1", port=8188)
            result = await client.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_non_200(self):
        """當 /system_stats 回傳非 200 時，應回傳 False"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        mock_resp = MagicMock()
        mock_resp.status_code = 503

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("src.singer_agent.comfyui_client.httpx.AsyncClient", return_value=mock_client):
            client = ComfyUIClient()
            result = await client.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_connection_error(self):
        """連線例外時應回傳 False（不拋出例外）"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("src.singer_agent.comfyui_client.httpx.AsyncClient", return_value=mock_client):
            client = ComfyUIClient()
            result = await client.is_available()

        assert result is False


# =====================================================================
# ComfyUIClient.generate_background()
# =====================================================================

class TestGenerateBackground:
    """測試背景圖生成主流程"""

    @pytest.mark.asyncio
    async def test_generate_background_returns_path(self, tmp_path):
        """正常流程應回傳背景圖的 Path 物件"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        # 模擬圖片資料（最小有效 PNG bytes）
        fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        client = ComfyUIClient()
        client._queue_prompt = AsyncMock(return_value="abcd1234-prompt-id")
        client._poll_until_complete = AsyncMock(return_value={
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "singer_bg_00001_.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        })
        client._download_output = AsyncMock(return_value=fake_image_bytes)

        # 將 BACKGROUNDS_DIR 指向 tmp_path
        with patch("src.singer_agent.comfyui_client.BACKGROUNDS_DIR", tmp_path):
            result = await client.generate_background(
                prompt="sunset over ocean, watercolor",
                output_filename="test_bg.png",
            )

        assert isinstance(result, Path)
        assert result.name == "test_bg.png"
        assert result.read_bytes() == fake_image_bytes

    @pytest.mark.asyncio
    async def test_generate_background_raises_on_empty_output(self, tmp_path):
        """ComfyUI 完成但沒有輸出圖片時，應拋出 RuntimeError"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        client = ComfyUIClient()
        client._queue_prompt = AsyncMock(return_value="abcd1234")
        client._poll_until_complete = AsyncMock(return_value={"outputs": {}})
        client._download_output = AsyncMock(return_value=b"")

        with patch("src.singer_agent.comfyui_client.BACKGROUNDS_DIR", tmp_path):
            with pytest.raises(RuntimeError, match="沒有輸出圖片"):
                await client.generate_background(prompt="test prompt")

    @pytest.mark.asyncio
    async def test_generate_background_auto_generates_filename(self, tmp_path):
        """未提供 output_filename 時，應自動產生含 prompt_id 的檔名"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        prompt_id = "deadbeef-0000-0000-0000-000000000000"

        client = ComfyUIClient()
        client._queue_prompt = AsyncMock(return_value=prompt_id)
        client._poll_until_complete = AsyncMock(return_value={
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "out.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        })
        client._download_output = AsyncMock(return_value=fake_image_bytes)

        with patch("src.singer_agent.comfyui_client.BACKGROUNDS_DIR", tmp_path):
            result = await client.generate_background(prompt="ocean sunset")

        # 自動產生的檔名應包含 prompt_id 的前 8 字
        assert "deadbeef" in result.name


# =====================================================================
# ComfyUIClient.free_vram()
# =====================================================================

class TestFreeVram:
    """測試 VRAM 釋放請求"""

    @pytest.mark.asyncio
    async def test_free_vram_posts_to_correct_endpoint(self):
        """應向 /free 送出 POST，帶正確的 JSON body"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock()

        with patch("src.singer_agent.comfyui_client.httpx.AsyncClient", return_value=mock_client):
            client = ComfyUIClient(host="127.0.0.1", port=8188)
            await client.free_vram()

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        # 驗證 URL 包含 /free
        assert "/free" in call_args[0][0]
        # 驗證 payload 欄位
        assert call_args[1]["json"]["unload_models"] is True
        assert call_args[1]["json"]["free_memory"] is True

    @pytest.mark.asyncio
    async def test_free_vram_does_not_raise_on_error(self):
        """連線失敗時不應拋出例外（靜默警告）"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))

        with patch("src.singer_agent.comfyui_client.httpx.AsyncClient", return_value=mock_client):
            client = ComfyUIClient()
            # 不應拋出例外
            await client.free_vram()


# =====================================================================
# ComfyUIClient._build_txt2img_workflow()
# =====================================================================

class TestBuildTxt2imgWorkflow:
    """測試 ComfyUI workflow JSON 結構"""

    def _build(self, **kwargs):
        from src.singer_agent.comfyui_client import ComfyUIClient
        client = ComfyUIClient(checkpoint="test_model.safetensors")
        defaults = dict(
            prompt="ocean sunset",
            negative_prompt="blurry",
            width=1920,
            height=1080,
            steps=20,
            cfg=7.0,
            seed=42,
        )
        defaults.update(kwargs)
        return client._build_txt2img_workflow(**defaults)

    def test_workflow_contains_all_required_node_ids(self):
        """Workflow 必須包含節點 3,4,5,6,7,8,9"""
        workflow = self._build()
        for node_id in ["3", "4", "5", "6", "7", "8", "9"]:
            assert node_id in workflow, f"缺少節點 {node_id}"

    def test_node_4_is_checkpoint_loader(self):
        """節點 4 應為 CheckpointLoaderSimple，並使用指定 checkpoint"""
        workflow = self._build()
        assert workflow["4"]["class_type"] == "CheckpointLoaderSimple"
        assert workflow["4"]["inputs"]["ckpt_name"] == "test_model.safetensors"

    def test_node_6_positive_prompt(self):
        """節點 6 應為正面 CLIPTextEncode，包含 prompt 文字"""
        workflow = self._build(prompt="ocean sunset watercolor")
        assert workflow["6"]["class_type"] == "CLIPTextEncode"
        assert workflow["6"]["inputs"]["text"] == "ocean sunset watercolor"

    def test_node_7_negative_prompt(self):
        """節點 7 應為負面 CLIPTextEncode，包含 negative_prompt 文字"""
        workflow = self._build(negative_prompt="blurry, low quality")
        assert workflow["7"]["class_type"] == "CLIPTextEncode"
        assert workflow["7"]["inputs"]["text"] == "blurry, low quality"

    def test_node_5_empty_latent_image_dimensions(self):
        """節點 5 EmptyLatentImage 的尺寸應與傳入參數一致"""
        workflow = self._build(width=1920, height=1080)
        assert workflow["5"]["class_type"] == "EmptyLatentImage"
        assert workflow["5"]["inputs"]["width"] == 1920
        assert workflow["5"]["inputs"]["height"] == 1080

    def test_node_3_ksampler_parameters(self):
        """節點 3 KSampler 的 steps/cfg/seed 應與傳入一致"""
        workflow = self._build(steps=25, cfg=7.5, seed=12345)
        ksampler = workflow["3"]
        assert ksampler["class_type"] == "KSampler"
        assert ksampler["inputs"]["steps"] == 25
        assert ksampler["inputs"]["cfg"] == 7.5
        assert ksampler["inputs"]["seed"] == 12345

    def test_node_8_vae_decode(self):
        """節點 8 應為 VAEDecode"""
        workflow = self._build()
        assert workflow["8"]["class_type"] == "VAEDecode"

    def test_node_9_save_image_prefix(self):
        """節點 9 SaveImage 的 filename_prefix 應為 singer_bg"""
        workflow = self._build()
        assert workflow["9"]["class_type"] == "SaveImage"
        assert workflow["9"]["inputs"]["filename_prefix"] == "singer_bg"


# =====================================================================
# ComfyUIClient._extract_output_images()
# =====================================================================

class TestExtractOutputImages:
    """測試從 ComfyUI history 結果中提取圖片資訊"""

    def test_extracts_images_from_single_node(self):
        """應從單一節點提取圖片清單"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        result = {
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "bg_001.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        }
        images = ComfyUIClient._extract_output_images(result)
        assert len(images) == 1
        assert images[0]["filename"] == "bg_001.png"

    def test_extracts_images_from_multiple_nodes(self):
        """應合併多個節點的圖片"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        result = {
            "outputs": {
                "9": {
                    "images": [{"filename": "img1.png", "type": "output"}]
                },
                "10": {
                    "images": [{"filename": "img2.png", "type": "output"}]
                },
            }
        }
        images = ComfyUIClient._extract_output_images(result)
        assert len(images) == 2

    def test_returns_empty_list_on_no_outputs(self):
        """沒有 outputs 時應回傳空清單"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        images = ComfyUIClient._extract_output_images({"outputs": {}})
        assert images == []

    def test_ignores_nodes_without_images_key(self):
        """沒有 images key 的節點應被忽略"""
        from src.singer_agent.comfyui_client import ComfyUIClient

        result = {
            "outputs": {
                "3": {"latent": [...]},
                "9": {"images": [{"filename": "bg.png", "type": "output"}]},
            }
        }
        images = ComfyUIClient._extract_output_images(result)
        assert len(images) == 1
        assert images[0]["filename"] == "bg.png"


# =====================================================================
# generate_solid_background()
# =====================================================================

class TestGenerateSolidBackground:
    """測試純色背景圖降級方案"""

    def test_creates_image_file(self, tmp_path):
        """應建立實際的 PNG 圖片檔"""
        from src.singer_agent.comfyui_client import generate_solid_background

        with patch("src.singer_agent.comfyui_client.BACKGROUNDS_DIR", tmp_path):
            result = generate_solid_background(
                mood="romantic",
                width=640,
                height=360,
                output_filename="test_solid.png",
            )

        assert result.exists()
        img = Image.open(str(result))
        assert img.size == (640, 360)

    def test_romantic_mood_creates_pink_background(self, tmp_path):
        """romantic 情緒應產出粉紅色背景"""
        from src.singer_agent.comfyui_client import generate_solid_background

        with patch("src.singer_agent.comfyui_client.BACKGROUNDS_DIR", tmp_path):
            result = generate_solid_background(
                mood="romantic",
                output_filename="pink_bg.png",
            )

        img = Image.open(str(result)).convert("RGB")
        pixel = img.getpixel((5, 5))
        # romantic → (253, 121, 168)
        assert pixel[0] > 200, "紅色通道應偏高（粉紅）"

    def test_unknown_mood_falls_back_to_default(self, tmp_path):
        """未知情緒應使用預設顏色，不應拋出例外"""
        from src.singer_agent.comfyui_client import generate_solid_background

        with patch("src.singer_agent.comfyui_client.BACKGROUNDS_DIR", tmp_path):
            result = generate_solid_background(
                mood="unknown_xyz",
                output_filename="fallback_bg.png",
            )

        assert result.exists()

    def test_auto_filename_contains_mood(self, tmp_path):
        """未提供 output_filename 時，自動產生的檔名應含情緒名稱"""
        from src.singer_agent.comfyui_client import generate_solid_background

        with patch("src.singer_agent.comfyui_client.BACKGROUNDS_DIR", tmp_path):
            result = generate_solid_background(mood="happy")

        assert "happy" in result.name


# =====================================================================
# build_background_prompt()
# =====================================================================

class TestBuildBackgroundPrompt:
    """測試從 SongSpec 組合 SD prompt"""

    def test_includes_background_prompt(self):
        """應包含 SongSpec.background_prompt"""
        from src.singer_agent.comfyui_client import build_background_prompt

        spec = _make_spec(background_prompt="ocean sunset with golden waves")
        result = build_background_prompt(spec)
        assert "ocean sunset with golden waves" in result

    def test_includes_visual_style(self):
        """應包含 visual_style"""
        from src.singer_agent.comfyui_client import build_background_prompt

        spec = _make_spec(visual_style="dreamy watercolor")
        result = build_background_prompt(spec)
        assert "dreamy watercolor" in result

    def test_includes_string_color_palette(self):
        """color_palette 為字串時應直接加入"""
        from src.singer_agent.comfyui_client import build_background_prompt

        spec = _make_spec(color_palette="warm tones, pink, gold")
        result = build_background_prompt(spec)
        assert "warm tones, pink, gold" in result

    def test_includes_list_color_palette(self):
        """color_palette 為 list 時應合併加入"""
        from src.singer_agent.comfyui_client import build_background_prompt

        spec = _make_spec(color_palette=["pink", "gold", "sunset orange"])
        result = build_background_prompt(spec)
        assert "pink" in result
        assert "gold" in result

    def test_always_includes_quality_suffix(self):
        """應永遠附加品質提示詞"""
        from src.singer_agent.comfyui_client import build_background_prompt

        spec = _make_spec()
        result = build_background_prompt(spec)
        assert "masterpiece" in result
        assert "no people" in result

    def test_handles_empty_fields(self):
        """欄位為空時不應拋出例外，且仍有品質提示"""
        from src.singer_agent.comfyui_client import build_background_prompt

        spec = SongSpec(title="Empty", artist="Artist")
        result = build_background_prompt(spec)
        assert "masterpiece" in result
        assert isinstance(result, str)
