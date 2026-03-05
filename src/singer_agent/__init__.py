# -*- coding: utf-8 -*-
"""Singer Agent — 虛擬歌手 MV 自動化流水線

MVP 流程：使用者提供歌名+歌手+MP3 → Qwen3 研究風格 →
產出 SongSpec → 生成文案 → FFmpeg 合成影片。
"""

__version__ = "0.3.0"

from .models import SongMetadata, SongSpec, MVProject, ProjectStatus

__all__ = [
    "SongMetadata",
    "SongSpec",
    "MVProject",
    "ProjectStatus",
]
