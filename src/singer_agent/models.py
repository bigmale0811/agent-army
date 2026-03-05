# -*- coding: utf-8 -*-
"""Singer Agent — 資料模型

MVP 版本：使用者提供歌名等基本資訊 → 網路搜尋+LLM 產出風格規格 → 影片合成。
使用 dataclass + to_dict/from_dict 模式（與 reading_agent 一致）。
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class ProjectStatus(Enum):
    """MV 專案狀態"""
    PENDING = "pending"             # 等待處理
    RESEARCHING = "researching"     # 搜尋歌曲資訊中
    CLASSIFYING = "classifying"     # LLM 風格分類中
    WRITING_COPY = "writing_copy"   # 文案生成中
    GENERATING_BG = "generating_bg" # ComfyUI 生成背景圖（v0.3）
    COMPOSITING = "compositing"     # 角色去背 + 背景合成（v0.3）
    PRECHECKING = "prechecking"     # 預檢驗證（v0.3）
    COMPOSING = "composing"         # 影片合成中
    COMPLETED = "completed"         # 完成
    FAILED = "failed"               # 失敗


@dataclass
class SongMetadata:
    """使用者提供的歌曲基本資訊

    MVP 策略：不做音訊分析，由使用者提供歌名等資訊，
    再透過網路搜尋補充風格資料。
    """
    title: str = ""                 # 歌曲名稱（必填）
    artist: str = ""                # 原唱歌手（選填，有助風格判斷）
    language: str = ""              # 語言：zh / en / ja 等
    genre_hint: str = ""            # 使用者自己描述的風格提示（選填）
    mood_hint: str = ""             # 使用者描述的情緒提示（選填）
    lyrics_file: str = ""           # 歌詞檔路徑 .lrc / .srt（選填）
    notes: str = ""                 # 其他備註（選填）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SongMetadata":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SongSpec:
    """歌曲風格規格書（網路搜尋 + LLM 產出）

    用於指導後續的圖片生成、影片風格、文案撰寫。
    """
    # 基本資訊（來自 SongMetadata）
    title: str = ""
    artist: str = ""
    language: str = ""

    # 網路搜尋補充的資訊
    research_summary: str = ""          # 搜尋到的歌曲風格摘要

    # LLM 分類結果
    genre: str = ""                     # 音樂類型（pop, rock, ballad...）
    mood: str = ""                      # 情緒（happy, sad, energetic...）

    # 視覺風格建議（LLM 產出）
    visual_style: str = ""              # 整體視覺風格描述
    color_palette: str = ""             # 色調建議
    background_prompt: str = ""         # SD 背景 prompt（英文）
    outfit_prompt: str = ""             # 服裝描述 prompt（英文）
    scene_description: str = ""         # 場景描述（中文，給人看的）

    # 時間戳
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SongSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MVProject:
    """MV 專案狀態追蹤

    MVP 版本：追蹤從歌曲資訊 → 風格分析 → 影片合成的流程。
    """
    project_id: str = ""                # 專案 ID
    source_audio: str = ""              # 原始音檔路徑
    status: str = ProjectStatus.PENDING.value

    # 使用者輸入
    metadata: Optional[SongMetadata] = None

    # 各步驟產出
    song_spec: Optional[SongSpec] = None
    final_video: str = ""               # 最終影片路徑
    render_mode: str = ""               # 渲染模式: "sadtalker" / "ffmpeg_static"

    # v0.3 新增：中間產物路徑
    background_image: str = ""          # ComfyUI 生成的背景圖
    character_nobg: str = ""            # 去背後的角色圖
    composite_image: str = ""           # 合成圖（角色+背景）
    precheck_passed: bool = False       # 預檢是否通過
    precheck_summary: str = ""          # 預檢摘要

    # 文案
    youtube_title: str = ""
    youtube_description: str = ""
    youtube_tags: list[str] = field(default_factory=list)

    # 時間戳
    created_at: str = ""
    completed_at: str = ""
    error_message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MVProject":
        meta_data = data.pop("metadata", None)
        spec_data = data.pop("song_spec", None)
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        project = cls(**valid)
        if meta_data and isinstance(meta_data, dict):
            project.metadata = SongMetadata.from_dict(meta_data)
        if spec_data and isinstance(spec_data, dict):
            project.song_spec = SongSpec.from_dict(spec_data)
        return project
