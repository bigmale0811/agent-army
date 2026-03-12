"""資源相關資料模型"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict


class ImageAsset(BaseModel):
    """圖片資源"""
    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    width: int = 0
    height: int = 0
    mime_type: str = "image/png"
    source_url: str = ""


class AudioAsset(BaseModel):
    """音效資源"""
    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    duration_ms: int = 0
    mime_type: str = "audio/mpeg"
    source_url: str = ""


class SpriteFrame(BaseModel):
    """Sprite Sheet 中的單一 frame"""
    model_config = ConfigDict(frozen=True)

    name: str
    x: int
    y: int
    width: int
    height: int


class SpriteSheet(BaseModel):
    """Sprite Sheet（合圖 + atlas）"""
    model_config = ConfigDict(frozen=True)

    name: str
    image_path: Path
    atlas_path: Path | None = None
    frames: tuple[SpriteFrame, ...] = ()


class AssetBundle(BaseModel):
    """完整的遊戲資源包"""
    model_config = ConfigDict(frozen=True)

    images: tuple[ImageAsset, ...] = ()
    sprites: tuple[SpriteSheet, ...] = ()
    audio: tuple[AudioAsset, ...] = ()
    raw_configs: dict[str, object] = {}
    # Scraper 同 session 攔截到的 WS 訊息（傳給 ReverseEngine 用）
    ws_messages: tuple[dict[str, Any], ...] = ()
