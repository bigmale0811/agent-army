# -*- coding: utf-8 -*-
"""Singer Agent — 文案生成模組

根據 SongSpec 產出 YouTube 標題、描述、標籤。
使用 Ollama (Qwen3 14B) 本地推論。
"""

import json
import logging

import httpx

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL
from .models import SongSpec

logger = logging.getLogger(__name__)

_OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"

# 文案生成 prompt 模板
_COPYWRITE_PROMPT = """你是一位專業的 YouTube 頻道經營者，擅長撰寫吸引人的影片標題和描述。
我的頻道是一個虛擬歌手頻道，使用動漫風格的虛擬角色演唱歌曲。

歌曲資訊：
- 歌名：{title}
- 原唱：{artist}
- 風格：{genre}
- 情緒：{mood}
- 語言：{language}
- 場景描述：{scene_description}

請用 JSON 格式回傳（不要加 markdown 標記）：
{{
    "youtube_title": "YouTube 標題（吸引人、含歌名、50字內）",
    "youtube_description": "YouTube 描述（含歌曲資訊、hashtag、3-5行）",
    "youtube_tags": ["標籤1", "標籤2", "標籤3", "...最多10個"]
}}

注意：
- 標題要吸引人點擊，可以用 emoji
- 描述要包含歌名、原唱、翻唱等資訊
- 標籤要涵蓋：歌名、歌手、風格、虛擬歌手、cover 等關鍵字
- 全部用繁體中文"""


async def generate_copy(spec: SongSpec) -> dict:
    """根據歌曲規格產出 YouTube 文案

    Args:
        spec: 歌曲風格規格書

    Returns:
        包含 youtube_title, youtube_description, youtube_tags 的 dict

    Raises:
        ConnectionError: 無法連接 Ollama
        ValueError: LLM 回傳格式錯誤
    """
    prompt = _COPYWRITE_PROMPT.format(
        title=spec.title or "未知",
        artist=spec.artist or "未知",
        genre=spec.genre or "未知",
        mood=spec.mood or "未知",
        language=spec.language or "未知",
        scene_description=spec.scene_description or "無",
    )

    logger.info("✍️ 開始生成 YouTube 文案：%s", spec.title)

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.8,
                "num_predict": 800,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(_OLLAMA_CHAT_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            # /api/chat 回傳格式：{"message": {"role": "assistant", "content": "..."}}
            text = data.get("message", {}).get("content", "")

        result = _parse_copy_response(text)
        logger.info("✍️ 文案生成完成：%s", result.get("youtube_title", "?"))
        return result

    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise ConnectionError(
            f"無法連接 Ollama ({OLLAMA_BASE_URL}): {e}"
        ) from e


def _parse_copy_response(text: str) -> dict:
    """從 LLM 回應中解析文案 JSON

    Args:
        text: LLM 原始回應

    Returns:
        包含 youtube_title, youtube_description, youtube_tags 的 dict
    """
    # 嘗試多種方式解析 JSON
    for attempt_text in [
        text.strip(),
        text[text.find("{"):text.rfind("}") + 1] if "{" in text else "",
        text.replace("```json", "").replace("```", "").strip(),
    ]:
        if not attempt_text:
            continue
        try:
            result = json.loads(attempt_text)
            # 確保必要欄位存在
            return {
                "youtube_title": result.get("youtube_title", ""),
                "youtube_description": result.get("youtube_description", ""),
                "youtube_tags": result.get("youtube_tags", []),
            }
        except json.JSONDecodeError:
            continue

    # 解析全部失敗時，回傳基本預設值
    logger.warning("⚠️ 無法解析文案 JSON，使用預設值")
    return {
        "youtube_title": "",
        "youtube_description": "",
        "youtube_tags": [],
    }
