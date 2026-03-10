# -*- coding: utf-8 -*-
"""
DEV-6: 歌曲研究模組。

SongResearcher 透過 Ollama LLM 分析歌曲風格，
產出結構化的 SongResearch 資料（genre、mood、visual_style 等）。
支援 dry_run 模式回傳 stub 資料。
"""
import json
import logging

from src.singer_agent.models import SongResearch
from src.singer_agent.ollama_client import OllamaClient

_logger = logging.getLogger(__name__)

# dry_run 模式使用的預設 stub 資料
_STUB_RESEARCH = SongResearch(
    genre="pop",
    mood="upbeat",
    visual_style="Modern Minimalist",
    color_palette=["white", "sky_blue"],
    background_prompt="minimalist white background with soft blue accents",
    outfit_prompt="casual modern outfit",
    scene_description="簡約現代風格場景",
    research_summary="（dry_run 模式：略過實際 LLM 分析）",
)

# 結構化 prompt 模板，要求 LLM 回傳 JSON
_RESEARCH_PROMPT = """You are a music visual director. Analyze the song and output a JSON object with these exact keys:
- genre: music genre in English (e.g. "ballad", "pop")
- mood: mood in English (e.g. "romantic, nostalgic")
- visual_style: visual art style in English (e.g. "Pastel Watercolor")
- color_palette: list of 2-5 color names in English
- background_prompt: SDXL prompt in English for a 1920x1080 background
- outfit_prompt: outfit description in English
- scene_description: scene description in Traditional Chinese
- research_summary: research summary in Traditional Chinese

Song title: {title}
Artist: {artist}
{extra}
Respond ONLY with a valid JSON object, no markdown, no explanation."""


class SongResearcher:
    """
    歌曲風格研究器。

    透過 Ollama LLM 分析歌曲的風格、情緒和視覺元素，
    產出用於後續管線步驟的 SongResearch 資料。

    Args:
        ollama_client: OllamaClient 實例，預設自動建立
    """

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.client = ollama_client or OllamaClient()

    def research(
        self,
        title: str,
        artist: str,
        language: str = "",
        genre_hint: str = "",
        mood_hint: str = "",
        notes: str = "",
        lyrics_context: str = "",
        dry_run: bool = False,
    ) -> SongResearch:
        """
        分析歌曲風格，回傳 SongResearch。

        Args:
            title: 歌名
            artist: 歌手
            language: 語言（可選）
            genre_hint: 曲風提示（可選）
            mood_hint: 情緒提示（可選）
            notes: 額外備註（可選）
            dry_run: True 時回傳 stub 資料，不呼叫 LLM

        Returns:
            SongResearch 結構化資料

        Raises:
            json.JSONDecodeError: LLM 回應非合法 JSON
            KeyError: JSON 缺少必要欄位
        """
        if dry_run:
            _logger.info("dry_run 模式：回傳 stub SongResearch")
            return _STUB_RESEARCH

        # 組裝額外提示
        extra_parts: list[str] = []
        if language:
            extra_parts.append(f"Language: {language}")
        if genre_hint:
            extra_parts.append(f"Genre hint: {genre_hint}")
        if mood_hint:
            extra_parts.append(f"Mood hint: {mood_hint}")
        if notes:
            extra_parts.append(f"Notes: {notes}")
        if lyrics_context:
            extra_parts.append(
                f"Lyrics Analysis (use this to generate more accurate "
                f"background_prompt and outfit_prompt):\n{lyrics_context}"
            )
        extra = "\n".join(extra_parts)

        prompt = _RESEARCH_PROMPT.format(
            title=title, artist=artist, extra=extra
        )

        _logger.debug("發送研究 prompt 至 Ollama")
        response = self.client.generate(prompt)

        # 防護：generate() 可能回傳 None（Ollama 異常回應）
        if not response:
            raise ValueError("Ollama 回傳空白回應，無法解析歌曲研究")

        # 清理可能的 markdown 包裹（```json ... ```）
        text = response.strip()
        if text.startswith("```"):
            # 移除第一行（```json）和最後的 ```
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]

        data = json.loads(text)

        # 防護：json.loads("null") → None，或回傳非 dict 結構
        if not isinstance(data, dict):
            raise TypeError(
                f"Ollama 回應非 JSON 物件（type={type(data).__name__}），"
                f"原始回應前 200 字：{text[:200]}"
            )

        return SongResearch(
            genre=data["genre"],
            mood=data["mood"],
            visual_style=data["visual_style"],
            color_palette=data["color_palette"],
            background_prompt=data["background_prompt"],
            outfit_prompt=data["outfit_prompt"],
            scene_description=data["scene_description"],
            research_summary=data["research_summary"],
        )
