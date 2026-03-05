# -*- coding: utf-8 -*-
"""讀書 Agent — Gemini 摘要模組

使用 Google Gemini API 將蒐集到的影片資訊進行智慧摘要：
1. 判斷每部影片介紹的是哪本書
2. 提取書籍重點與推薦理由
3. 依主題分類整理
4. 全部以繁體中文輸出
"""

import asyncio
import logging
from typing import Optional

from google import genai

from .config import GEMINI_API_KEY, BOOK_CATEGORIES
from .models import Video, ReadingReport

logger = logging.getLogger(__name__)

# 每次處理的影片上限（避免超出 token 限制）
_BATCH_SIZE = 20


def _init_client() -> genai.Client:
    """初始化 Gemini 客戶端"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未設定，請檢查 .env 檔案")
    return genai.Client(api_key=GEMINI_API_KEY)


def _build_summary_prompt(videos: list[Video]) -> str:
    """建構讀書摘要的 prompt

    要求 Gemini：
    1. 從影片標題和描述判斷討論的書籍
    2. 整理每本書的重點摘要
    3. 提供閱讀推薦和分類
    """
    video_texts = []
    for i, v in enumerate(videos[:_BATCH_SIZE], 1):
        desc_preview = v.description[:300] if v.description else "（無描述）"
        video_texts.append(
            f"{i}. 頻道: {v.channel_name}\n"
            f"   標題: {v.title}\n"
            f"   日期: {v.published_at[:10]}\n"
            f"   描述: {desc_preview}"
        )
    videos_block = "\n\n".join(video_texts)

    return f"""你是一位專業的書評家和知識策展人。以下是本週從各個說書 YouTube 頻道蒐集到的影片資訊。

請完成以下工作：

1. 書籍識別：從每部影片的標題和描述中，判斷該影片介紹的是哪本書（如果有的話）。
   若影片不是在介紹書籍（例如是 vlog、Q&A、時事評論等），請標記為「非書籍內容」並簡短描述主題。

2. 本週推薦書單：從所有影片中挑選 3-5 本最值得一讀的書，每本書提供：
   - 書名（繁體中文，若為外文書附上原文書名）
   - 作者
   - 一句話推薦理由
   - 三個重點摘要
   - 推薦的說書頻道和影片

3. 其他值得關注的內容：列出本週其他有趣但非書籍的影片主題（如果有的話）。

4. 本週閱讀趨勢：用 1-2 句話總結本週說書頻道關注的主要方向或趨勢。

格式要求：
- 全部使用繁體中文輸出
- 簡潔有力，適合在 Telegram 閱讀
- 不要使用 Markdown 格式符號（如 ** 或 #）
- 用數字編號和縮排讓結構清晰

===== 本週影片列表 =====
{videos_block}
"""


async def summarize_videos(videos: list[Video]) -> str:
    """用 Gemini 摘要所有影片

    Args:
        videos: 影片列表

    Returns:
        繁體中文摘要文字
    """
    if not videos:
        return ""

    client = _init_client()
    prompt = _build_summary_prompt(videos)

    try:
        # 使用新版 SDK 呼叫（同步，用 asyncio.to_thread 避免阻塞）
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        result = (response.text or "").strip()
        if not result:
            return _build_fallback_summary(videos)
        logger.info("Gemini 讀書摘要完成：%d 字", len(result))
        return result

    except Exception as e:
        logger.error("Gemini 讀書摘要失敗: %s", e)
        # 降級方案：回傳基本的影片列表
        return _build_fallback_summary(videos)


def _build_fallback_summary(videos: list[Video]) -> str:
    """降級方案：當 Gemini 不可用時產生基本摘要"""
    lines = ["（Gemini 摘要暫時無法使用，以下為原始影片列表）", ""]

    # 按頻道分組
    by_channel: dict[str, list[Video]] = {}
    for v in videos:
        if v.channel_name not in by_channel:
            by_channel[v.channel_name] = []
        by_channel[v.channel_name].append(v)

    for channel_name, channel_videos in by_channel.items():
        lines.append(f"📺 {channel_name}（{len(channel_videos)} 部）")
        for i, v in enumerate(channel_videos[:5], 1):
            lines.append(f"  {i}. {v.title}")
            lines.append(f"     📅 {v.published_at[:10]}")
        if len(channel_videos) > 5:
            lines.append(f"  ...還有 {len(channel_videos) - 5} 部")
        lines.append("")

    return "\n".join(lines)


async def summarize_by_channel(
    videos: list[Video],
    channel_name: str,
) -> str:
    """摘要單一頻道的影片（用於大量影片時分批處理）

    Args:
        videos: 該頻道的影片列表
        channel_name: 頻道名稱

    Returns:
        繁體中文摘要
    """
    if not videos:
        return ""

    client = _init_client()

    video_texts = []
    for i, v in enumerate(videos[:_BATCH_SIZE], 1):
        desc_preview = v.description[:200] if v.description else "（無描述）"
        video_texts.append(
            f"{i}. 標題: {v.title}\n"
            f"   日期: {v.published_at[:10]}\n"
            f"   描述: {desc_preview}"
        )
    videos_block = "\n\n".join(video_texts)

    prompt = f"""你是一位書評家。以下是「{channel_name}」頻道本週的影片。

請辨識每部影片討論的書籍或主題，並用繁體中文列出重點。
格式簡潔，適合 Telegram 閱讀，不使用 Markdown 格式符號。

{videos_block}
"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        result = (response.text or "").strip()
        if not result:
            return _build_fallback_summary(videos)
        logger.info("Gemini 頻道摘要完成 [%s]: %d 字", channel_name, len(result))
        return result
    except Exception as e:
        logger.error("Gemini 頻道摘要失敗 [%s]: %s", channel_name, e)
        fallback = [f"（{channel_name} 摘要失敗）"]
        for i, v in enumerate(videos[:5], 1):
            fallback.append(f"{i}. {v.title} ({v.published_at[:10]})")
        return "\n".join(fallback)
