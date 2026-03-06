# -*- coding: utf-8 -*-
"""
Singer Agent 核心資料模型。

定義系統中所有 dataclass，無外部依賴。
frozen=True 的 dataclass 為不可變物件，確保資料安全性。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────
# SongResearch：歌曲研究結果（不可變）
# ─────────────────────────────────────────────────

@dataclass(frozen=True)
class SongResearch:
    """
    歌曲風格研究結果。
    由 researcher.py 透過 Ollama LLM 分析產出，不可修改。
    """
    genre: str              # 音樂類型，如 "ballad"
    mood: str               # 情緒描述，如 "romantic, nostalgic"
    visual_style: str       # 視覺風格，如 "Pastel Watercolor"
    color_palette: list     # 主色調列表，如 ["soft_pink", "light_blue"]
    background_prompt: str  # ComfyUI SDXL 背景生成提示詞（英文）
    outfit_prompt: str      # 角色服裝描述（供未來功能使用）
    scene_description: str  # 繁中場景描述
    research_summary: str   # 繁中研究摘要


# ─────────────────────────────────────────────────
# SongSpec：歌曲規格（可變，含序列化）
# ─────────────────────────────────────────────────

@dataclass
class SongSpec:
    """
    歌曲完整規格，包含 metadata 及研究結果。
    可序列化為 dict 以便 JSON 持久化。
    """
    title: str
    artist: str
    language: str
    research: SongResearch
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """將 SongSpec 序列化為字典（含巢狀 SongResearch）。"""
        return {
            "title": self.title,
            "artist": self.artist,
            "language": self.language,
            "research": {
                "genre": self.research.genre,
                "mood": self.research.mood,
                "visual_style": self.research.visual_style,
                "color_palette": list(self.research.color_palette),
                "background_prompt": self.research.background_prompt,
                "outfit_prompt": self.research.outfit_prompt,
                "scene_description": self.research.scene_description,
                "research_summary": self.research.research_summary,
            },
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongSpec":
        """從字典還原 SongSpec（含巢狀 SongResearch）。"""
        research_data = data["research"]
        research = SongResearch(
            genre=research_data["genre"],
            mood=research_data["mood"],
            visual_style=research_data["visual_style"],
            color_palette=research_data["color_palette"],
            background_prompt=research_data["background_prompt"],
            outfit_prompt=research_data["outfit_prompt"],
            scene_description=research_data["scene_description"],
            research_summary=research_data["research_summary"],
        )
        return cls(
            title=data["title"],
            artist=data["artist"],
            language=data["language"],
            research=research,
            created_at=data["created_at"],
        )


# ─────────────────────────────────────────────────
# CopySpec：YouTube 文案規格（不可變）
# ─────────────────────────────────────────────────

@dataclass(frozen=True)
class CopySpec:
    """
    YouTube 影片文案規格。
    由 copywriter.py 透過 Ollama LLM 產出，不可修改。
    """
    title: str          # YouTube 影片標題
    description: str    # YouTube 影片描述
    tags: list          # YouTube 標籤列表


# ─────────────────────────────────────────────────
# PrecheckResult：品質預檢結果（不可變）
# ─────────────────────────────────────────────────

@dataclass(frozen=True)
class PrecheckResult:
    """
    品質預檢結果，包含各項目狀態及 Gemini 視覺評分。
    由 precheck.py 產出，不可修改。
    """
    passed: bool                # 整體是否通過
    checks: dict                # 各項檢查結果 {check_name: bool}
    warnings: list              # 警告訊息列表
    gemini_score: int | None    # Gemini Vision 評分（0-100），無 key 時為 None
    gemini_feedback: str        # Gemini 反饋文字


# ─────────────────────────────────────────────────
# ProjectState：專案狀態（可變，含序列化）
# ─────────────────────────────────────────────────

@dataclass
class ProjectState:
    """
    MV 製作專案的完整狀態。
    貫穿 8 步管線，每步更新對應欄位。
    可序列化為 dict 以便 JSON 持久化。
    """
    project_id: str
    source_audio: str               # 原始音訊路徑（str，儲存時為字串）
    status: str                     # "running" | "completed" | "failed"
    metadata: dict                  # 額外 metadata（duration、sample_rate 等）
    song_spec: SongSpec | None      # Step 1+2 產出
    copy_spec: CopySpec | None      # Step 3 產出
    background_image: str           # Step 4 產出路徑
    composite_image: str            # Step 5 產出路徑
    precheck_result: PrecheckResult | None  # Step 6 產出
    final_video: str                # Step 7 產出路徑
    render_mode: str                # "sadtalker" | "ffmpeg_static"
    error_message: str              # 錯誤訊息，無錯誤時為空字串
    created_at: str                 # 建立時間（ISO 8601）
    completed_at: str               # 完成時間（ISO 8601）

    def to_dict(self) -> dict[str, Any]:
        """將 ProjectState 序列化為字典，含所有巢狀物件。"""
        return {
            "project_id": self.project_id,
            "source_audio": self.source_audio,
            "status": self.status,
            "metadata": dict(self.metadata),
            "song_spec": self.song_spec.to_dict() if self.song_spec is not None else None,
            "copy_spec": {
                "title": self.copy_spec.title,
                "description": self.copy_spec.description,
                "tags": list(self.copy_spec.tags),
            } if self.copy_spec is not None else None,
            "background_image": self.background_image,
            "composite_image": self.composite_image,
            "precheck_result": {
                "passed": self.precheck_result.passed,
                "checks": dict(self.precheck_result.checks),
                "warnings": list(self.precheck_result.warnings),
                "gemini_score": self.precheck_result.gemini_score,
                "gemini_feedback": self.precheck_result.gemini_feedback,
            } if self.precheck_result is not None else None,
            "final_video": self.final_video,
            "render_mode": self.render_mode,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        """從字典還原 ProjectState（含所有巢狀物件）。"""
        # 還原 SongSpec（可為 None）
        song_spec: SongSpec | None = None
        if data.get("song_spec") is not None:
            song_spec = SongSpec.from_dict(data["song_spec"])

        # 還原 CopySpec（可為 None）
        copy_spec: CopySpec | None = None
        if data.get("copy_spec") is not None:
            cs = data["copy_spec"]
            copy_spec = CopySpec(
                title=cs["title"],
                description=cs["description"],
                tags=cs["tags"],
            )

        # 還原 PrecheckResult（可為 None）
        precheck_result: PrecheckResult | None = None
        if data.get("precheck_result") is not None:
            pr = data["precheck_result"]
            precheck_result = PrecheckResult(
                passed=pr["passed"],
                checks=pr["checks"],
                warnings=pr["warnings"],
                gemini_score=pr["gemini_score"],
                gemini_feedback=pr["gemini_feedback"],
            )

        return cls(
            project_id=data["project_id"],
            source_audio=data["source_audio"],
            status=data["status"],
            metadata=data.get("metadata", {}),
            song_spec=song_spec,
            copy_spec=copy_spec,
            background_image=data.get("background_image", ""),
            composite_image=data.get("composite_image", ""),
            precheck_result=precheck_result,
            final_video=data.get("final_video", ""),
            render_mode=data.get("render_mode", ""),
            error_message=data.get("error_message", ""),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
        )


# ─────────────────────────────────────────────────
# PipelineRequest：管線請求（輸入物件）
# ─────────────────────────────────────────────────

@dataclass
class PipelineRequest:
    """
    管線執行請求，由 CLI 或 Telegram Bot 建立並傳入 Pipeline.run()。
    audio_path 使用 Path 物件，支援中文路徑（但 SadTalker 需轉 ASCII）。
    """
    audio_path: Path    # 音訊檔案路徑（Path 物件）
    title: str          # 歌曲標題（可含中文）
    artist: str         # 歌手名稱
    language: str = ""  # 語言標籤，如 "zh-TW"，空字串表示自動偵測
    genre_hint: str = ""    # 使用者提示音樂類型（可選）
    mood_hint: str = ""     # 使用者提示情緒（可選）
    notes: str = ""         # 附加備註（可選）
