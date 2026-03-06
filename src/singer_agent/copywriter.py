# -*- coding: utf-8 -*-
"""
DEV-7: YouTube 文案產出模組。

Copywriter 透過 Ollama LLM 根據 SongSpec 產出
YouTube 影片標題、描述和標籤（CopySpec）。
支援 dry_run 模式回傳 stub 資料。
"""
import json
import logging

from src.singer_agent.models import CopySpec, SongSpec
from src.singer_agent.ollama_client import OllamaClient

_logger = logging.getLogger(__name__)

# dry_run 模式使用的預設 stub 資料
_STUB_COPY = CopySpec(
    title="【MV】stub 測試歌曲",
    description="這是 dry_run 模式產生的預設文案。\n\n#虛擬歌手 #MV",
    tags=["虛擬歌手", "MV", "AI"],
)

# 結構化 prompt 模板
_COPY_PROMPT = """You are a YouTube content specialist. Create metadata for a virtual singer MV.
Output a JSON object with these exact keys:
- title: YouTube video title in Traditional Chinese, include 【MV】prefix
- description: YouTube description in Traditional Chinese, include hashtags
- tags: list of 5-10 relevant tags in Traditional Chinese

Song info:
- Title: {title}
- Artist: {artist}
- Language: {language}
- Genre: {genre}
- Mood: {mood}
- Visual style: {visual_style}

Respond ONLY with a valid JSON object, no markdown, no explanation."""


class Copywriter:
    """
    YouTube 文案產出器。

    根據 SongSpec 的歌曲資訊，透過 LLM 產出
    適合 YouTube 上傳的標題、描述和標籤。

    Args:
        ollama_client: OllamaClient 實例，預設自動建立
    """

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.client = ollama_client or OllamaClient()

    def write(self, song_spec: SongSpec, dry_run: bool = False) -> CopySpec:
        """
        根據 SongSpec 產出 YouTube 文案。

        Args:
            song_spec: 歌曲規格
            dry_run: True 時回傳 stub 資料

        Returns:
            CopySpec（title、description、tags）

        Raises:
            json.JSONDecodeError: LLM 回應非合法 JSON
            KeyError: JSON 缺少必要欄位
        """
        if dry_run:
            _logger.info("dry_run 模式：回傳 stub CopySpec")
            return _STUB_COPY

        prompt = _COPY_PROMPT.format(
            title=song_spec.title,
            artist=song_spec.artist,
            language=song_spec.language,
            genre=song_spec.research.genre,
            mood=song_spec.research.mood,
            visual_style=song_spec.research.visual_style,
        )

        _logger.debug("發送文案 prompt 至 Ollama")
        response = self.client.generate(prompt)

        # 清理 markdown 包裹
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]

        data = json.loads(text)

        return CopySpec(
            title=data["title"],
            description=data["description"],
            tags=data["tags"],
        )
