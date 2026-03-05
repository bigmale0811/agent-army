# -*- coding: utf-8 -*-
"""Singer Agent — 歌曲風格研究模組

MVP 策略：用使用者提供的歌名+歌手，透過 Ollama (Qwen3)
搜尋並整理歌曲的風格、情緒、視覺意象等資訊。

不做音訊分析，純靠歌曲 metadata + LLM 知識庫推論。
"""

import json
import logging
from typing import Optional

import httpx

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL
from .models import SongMetadata

logger = logging.getLogger(__name__)

# Ollama Chat API 端點（v0.17+ 使用 /api/chat）
_OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"

# 歌曲研究 prompt 模板
_RESEARCH_PROMPT = """你是一位資深音樂評論家和視覺藝術顧問。
請根據以下歌曲資訊，分析這首歌的風格並給出視覺建議。

歌曲資訊：
- 歌名：{title}
- 歌手：{artist}
- 語言：{language}
{extra_info}

請用 JSON 格式回傳以下資訊（不要加 markdown 標記）：
{{
    "genre": "音樂類型（如 pop, rock, ballad, electronic, rnb, jazz, folk, hip_hop, anime, chinese_pop）",
    "mood": "情緒（如 happy, sad, energetic, calm, romantic, dark, epic, nostalgic）",
    "research_summary": "用2-3句中文描述這首歌的風格特色和氛圍",
    "visual_style": "用英文描述適合的視覺風格（給 AI 繪圖用）",
    "color_palette": "用英文列出3-5個適合的色調關鍵字",
    "background_prompt": "用英文寫一個 Stable Diffusion prompt，描述適合這首歌的背景場景（不含人物）",
    "outfit_prompt": "用英文描述適合這首歌風格的動漫角色服裝",
    "scene_description": "用中文描述整體場景構想，讓人能想像 MV 的畫面"
}}"""


async def research_song(metadata: SongMetadata) -> dict:
    """研究歌曲風格並產出視覺建議

    透過 Ollama (Qwen3 14B) 本地推論，根據歌曲名稱和歌手資訊，
    產出風格分類和視覺風格建議。

    Args:
        metadata: 使用者提供的歌曲基本資訊

    Returns:
        包含 genre, mood, visual_style 等欄位的 dict

    Raises:
        ConnectionError: 無法連接 Ollama 服務
        ValueError: LLM 回傳的 JSON 無法解析
    """
    # 組合額外資訊
    extra_parts = []
    if metadata.genre_hint:
        extra_parts.append(f"- 風格提示：{metadata.genre_hint}")
    if metadata.mood_hint:
        extra_parts.append(f"- 情緒提示：{metadata.mood_hint}")
    if metadata.notes:
        extra_parts.append(f"- 備註：{metadata.notes}")
    extra_info = "\n".join(extra_parts) if extra_parts else "（無額外資訊）"

    prompt = _RESEARCH_PROMPT.format(
        title=metadata.title or "未知",
        artist=metadata.artist or "未知",
        language=metadata.language or "未知",
        extra_info=extra_info,
    )

    logger.info("🎵 開始研究歌曲風格：%s - %s", metadata.title, metadata.artist)

    try:
        result = await _call_ollama(prompt)
        parsed = _parse_json_response(result)
        logger.info(
            "🎵 風格研究完成：genre=%s, mood=%s",
            parsed.get("genre", "?"),
            parsed.get("mood", "?"),
        )
        return parsed

    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise ConnectionError(
            f"無法連接 Ollama ({OLLAMA_BASE_URL})，請確認服務已啟動: {e}"
        ) from e


async def _call_ollama(prompt: str) -> str:
    """呼叫 Ollama 本地 API

    Args:
        prompt: 要發送給 LLM 的 prompt

    Returns:
        LLM 的回應文字
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1024,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(_OLLAMA_CHAT_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        # /api/chat 回傳格式：{"message": {"role": "assistant", "content": "..."}}
        return data.get("message", {}).get("content", "")


def _parse_json_response(text: str) -> dict:
    """從 LLM 回應中解析 JSON

    LLM 有時會在 JSON 前後加上多餘的文字或 markdown 標記，
    這裡嘗試多種方式提取有效的 JSON。

    Args:
        text: LLM 的原始回應文字

    Returns:
        解析後的 dict

    Raises:
        ValueError: 無法從回應中解析出有效 JSON
    """
    # 嘗試直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 嘗試提取 { } 之間的內容
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # 嘗試移除 markdown code block 標記
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"無法從 LLM 回應中解析 JSON: {text[:200]}...")
