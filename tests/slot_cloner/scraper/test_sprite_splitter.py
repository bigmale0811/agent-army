"""Sprite Splitter 測試"""
import json
import pytest
from PIL import Image
from slot_cloner.scraper.sprite_splitter import SpriteSplitter


@pytest.fixture
def sprite_fixture(tmp_path):
    """建立測試用 sprite sheet + atlas"""
    # 建立 128x64 的測試圖片（2 個 64x64 的 frame）
    img = Image.new("RGBA", (128, 64), (255, 0, 0, 255))
    # 右半部填不同顏色
    for x in range(64, 128):
        for y in range(64):
            img.putpixel((x, y), (0, 0, 255, 255))

    img_path = tmp_path / "sheet.png"
    img.save(img_path)

    # 建立 atlas JSON（Hash 格式）
    atlas = {
        "frames": {
            "symbol_red.png": {"frame": {"x": 0, "y": 0, "w": 64, "h": 64}},
            "symbol_blue.png": {"frame": {"x": 64, "y": 0, "w": 64, "h": 64}},
        }
    }
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(json.dumps(atlas), encoding="utf-8")

    return img_path, atlas_path


class TestSpriteSplitter:
    def test_split_hash_format(self, sprite_fixture, tmp_path):
        img_path, atlas_path = sprite_fixture
        out_dir = tmp_path / "output"

        splitter = SpriteSplitter()
        sheet = splitter.split(img_path, atlas_path, out_dir)

        assert len(sheet.frames) == 2
        assert (out_dir / "symbol_red.png").exists()
        assert (out_dir / "symbol_blue.png").exists()

    def test_split_array_format(self, tmp_path):
        # 建立 Array 格式的 atlas
        img = Image.new("RGBA", (64, 64), (0, 255, 0, 255))
        img_path = tmp_path / "sheet.png"
        img.save(img_path)

        atlas = {
            "frames": [
                {"filename": "green.png", "frame": {"x": 0, "y": 0, "w": 64, "h": 64}},
            ]
        }
        atlas_path = tmp_path / "atlas.json"
        atlas_path.write_text(json.dumps(atlas), encoding="utf-8")

        out_dir = tmp_path / "output"
        splitter = SpriteSplitter()
        sheet = splitter.split(img_path, atlas_path, out_dir)

        assert len(sheet.frames) == 1
        assert sheet.frames[0].name == "green.png"

    def test_frame_dimensions(self, sprite_fixture, tmp_path):
        img_path, atlas_path = sprite_fixture
        splitter = SpriteSplitter()
        sheet = splitter.split(img_path, atlas_path, tmp_path / "out")

        red_frame = next(f for f in sheet.frames if "red" in f.name)
        assert red_frame.width == 64
        assert red_frame.height == 64
