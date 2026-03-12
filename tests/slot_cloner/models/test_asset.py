"""資源模型測試"""
import pytest
from pathlib import Path
from pydantic import ValidationError
from slot_cloner.models.asset import (
    ImageAsset, AudioAsset, SpriteFrame, SpriteSheet, AssetBundle,
)


class TestImageAsset:
    def test_create(self, tmp_path):
        img = ImageAsset(name="test", path=tmp_path / "test.png")
        assert img.name == "test"
        assert img.mime_type == "image/png"

    def test_frozen(self, tmp_path):
        img = ImageAsset(name="test", path=tmp_path / "test.png")
        with pytest.raises(ValidationError):
            img.name = "changed"

    def test_json_roundtrip(self, tmp_path):
        img = ImageAsset(name="test", path=tmp_path / "test.png", width=100, height=200)
        data = img.model_dump_json()
        restored = ImageAsset.model_validate_json(data)
        assert restored.name == img.name
        assert restored.width == 100


class TestSpriteFrame:
    def test_create(self):
        frame = SpriteFrame(name="symbol_0", x=0, y=0, width=64, height=64)
        assert frame.width == 64

    def test_frozen(self):
        frame = SpriteFrame(name="test", x=0, y=0, width=32, height=32)
        with pytest.raises(ValidationError):
            frame.x = 10


class TestSpriteSheet:
    def test_create_with_frames(self, tmp_path):
        frames = (
            SpriteFrame(name="f1", x=0, y=0, width=64, height=64),
            SpriteFrame(name="f2", x=64, y=0, width=64, height=64),
        )
        sheet = SpriteSheet(
            name="symbols",
            image_path=tmp_path / "sheet.png",
            frames=frames,
        )
        assert len(sheet.frames) == 2


class TestAssetBundle:
    def test_empty_bundle(self):
        bundle = AssetBundle()
        assert len(bundle.images) == 0
        assert len(bundle.sprites) == 0
        assert len(bundle.audio) == 0

    def test_bundle_with_assets(self, tmp_path):
        img = ImageAsset(name="bg", path=tmp_path / "bg.png")
        audio = AudioAsset(name="bgm", path=tmp_path / "bgm.mp3")
        bundle = AssetBundle(images=(img,), audio=(audio,))
        assert len(bundle.images) == 1
        assert len(bundle.audio) == 1

    def test_frozen(self, tmp_path):
        bundle = AssetBundle()
        with pytest.raises(ValidationError):
            bundle.images = ()
