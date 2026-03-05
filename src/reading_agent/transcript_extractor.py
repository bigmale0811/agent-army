# -*- coding: utf-8 -*-
"""讀書 Agent v2 — YouTube 字幕擷取模組

從 YouTube 影片中擷取字幕/逐字稿，支援繁體中文、簡體中文與英文。
使用 youtube_transcript_api 套件，並以 asyncio.to_thread 包裝同步呼叫。
"""

import asyncio
import logging
import re

from youtube_transcript_api import YouTubeTranscriptApi

from src.reading_agent.config import REQUEST_DELAY
from src.reading_agent.models import Video

logger = logging.getLogger(__name__)

# === 語言優先順序設定 ===
# 依照影片語言設定，定義字幕語言代碼的搜尋優先順序
LANGUAGE_PRIORITY: dict[str, list[str]] = {
    "zh": ["zh-TW", "zh-Hant", "zh", "zh-Hans"],
    "en": ["en", "en-US", "en-GB"],
}

# === 雜訊片段正則表達式 ===
# 清除常見的非語音標記，如 [Music]、[Applause]、[字幕]、[音樂] 等
_NOISE_PATTERN = re.compile(
    r"\["
    r"(?:Music|Applause|Laughter|Noise|Silence|Inaudible"
    r"|音樂|掌聲|笑聲|雜訊|靜音|字幕|旁白|配樂"
    r"|music|applause|laughter|noise|silence|inaudible)"
    r"\]",
    re.IGNORECASE,
)

# 清除多餘空白（連續兩個以上空格或換行）
_WHITESPACE_PATTERN = re.compile(r"\s{2,}")


def _fetch_transcript_sync(video_id: str, language_codes: list[str]) -> list[dict]:
    """同步擷取字幕（供 asyncio.to_thread 使用）

    優先使用新版 API (0.6.x)：YouTubeTranscriptApi().fetch(video_id)
    若失敗則回退至舊版 API：YouTubeTranscriptApi.get_transcript(video_id)

    Args:
        video_id: YouTube 影片 ID
        language_codes: 按優先順序排列的語言代碼列表

    Returns:
        字幕片段列表，每個元素含 text、start、duration 欄位

    Raises:
        任何 youtube_transcript_api 例外，由呼叫端處理
    """
    # 嘗試新版 API (0.6.x instance method)
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        # 依優先順序嘗試取得指定語言字幕
        for lang in language_codes:
            try:
                transcript = transcript_list.find_transcript([lang])
                return transcript.fetch()
            except Exception:
                continue

        # 所有指定語言均找不到，取第一個可用語言作為回退
        try:
            available = list(transcript_list)
            if available:
                logger.debug(
                    "影片 %s 無指定語言字幕，使用回退語言: %s",
                    video_id,
                    available[0].language_code,
                )
                return available[0].fetch()
        except Exception:
            pass

    except TypeError:
        # 舊版 API 不支援 instance 方式，不做任何事，直接進入舊版路徑
        pass
    except Exception as e:
        # 新版 API 呼叫失敗，記錄後繼續嘗試舊版
        logger.debug("新版 API 擷取失敗，嘗試舊版: %s", e)

    # 回退至舊版 API (< 0.6.x class method)
    try:
        return YouTubeTranscriptApi.get_transcript(video_id, languages=language_codes)
    except Exception:
        # 舊版也找不到指定語言，嘗試任意可用語言
        return YouTubeTranscriptApi.get_transcript(video_id)


class TranscriptExtractor:
    """YouTube 字幕擷取器

    支援單一影片與批次擷取，自動處理語言優先順序與錯誤情境。

    Attributes:
        _request_delay: 每次請求間隔秒數，避免觸發速率限制
    """

    def __init__(self, request_delay: float = REQUEST_DELAY) -> None:
        self._request_delay = request_delay

    # ------------------------------------------------------------------
    # 公開介面
    # ------------------------------------------------------------------

    async def extract(self, video_id: str, language: str = "zh") -> str:
        """擷取單一影片的字幕文字

        依照 language 參數決定字幕語言搜尋順序：
        - "zh"：優先嘗試 zh-TW → zh-Hant → zh → zh-Hans
        - "en"：優先嘗試 en → en-US → en-GB
        - 其他：直接使用該語言代碼，並以所有可用語言為回退

        Args:
            video_id: YouTube 影片 ID（非完整 URL）
            language: 影片語言代碼，預設為 "zh"

        Returns:
            合併後的字幕純文字字串；若無法取得則回傳空字串
        """
        # 根據語言設定決定搜尋順序
        language_codes = LANGUAGE_PRIORITY.get(language, [language])

        try:
            # youtube_transcript_api 為同步阻塞呼叫，使用 to_thread 避免阻塞事件迴圈
            segments = await asyncio.to_thread(
                _fetch_transcript_sync, video_id, language_codes
            )
            transcript_text = self._merge_transcript_segments(segments)
            logger.debug(
                "影片 %s 字幕擷取成功，共 %d 字元", video_id, len(transcript_text)
            )
            return transcript_text

        except Exception as e:
            # 統一在此捕捉所有 youtube_transcript_api 例外
            # 包含：TranscriptsDisabled、NoTranscriptFound、VideoUnavailable 等
            error_type = type(e).__name__
            logger.warning(
                "影片 %s 無法取得字幕 [%s]: %s", video_id, error_type, e
            )
            return ""

    async def extract_batch(self, videos: list[Video]) -> list[Video]:
        """批次擷取多部影片的字幕

        逐一處理每部影片，並在每次請求之間加入延遲以遵守速率限制。
        若某部影片擷取失敗，僅記錄警告並繼續處理其餘影片（不中斷批次）。

        Args:
            videos: 待處理的 Video 物件列表

        Returns:
            已更新 transcript 欄位的 Video 物件列表
            （成功擷取者填入字幕文字，失敗者保留空字串）
        """
        total = len(videos)
        logger.info("開始批次擷取字幕，共 %d 部影片", total)

        for index, video in enumerate(videos, start=1):
            # 確保影片有 video_id，否則無法查詢字幕
            if not video.video_id:
                logger.warning(
                    "[%d/%d] 影片 '%s' 缺少 video_id，跳過字幕擷取",
                    index,
                    total,
                    video.title,
                )
                continue

            logger.info(
                "[%d/%d] 擷取字幕: %s (ID: %s)",
                index,
                total,
                video.title,
                video.video_id,
            )

            transcript_text = await self.extract(video.video_id, video.language)
            video.transcript = transcript_text

            if transcript_text:
                logger.info(
                    "[%d/%d] 完成: %s，字幕長度 %d 字元",
                    index,
                    total,
                    video.title,
                    len(transcript_text),
                )
            else:
                logger.warning(
                    "[%d/%d] 字幕為空: %s", index, total, video.title
                )

            # 非最後一部影片才需要等待，避免觸發 YouTube 速率限制
            if index < total:
                await asyncio.sleep(self._request_delay)

        logger.info("批次字幕擷取完成，共處理 %d 部影片", total)
        return videos

    # ------------------------------------------------------------------
    # 內部工具方法
    # ------------------------------------------------------------------

    def _merge_transcript_segments(self, segments: list[dict]) -> str:
        """合併字幕片段為單一文字字串

        youtube_transcript_api 回傳格式：
            [{"text": "...", "start": 0.0, "duration": 2.5}, ...]

        處理流程：
        1. 取出每個片段的 "text" 欄位
        2. 移除 [Music]、[Applause] 等非語音標記
        3. 去除多餘空白後，以單一空格合併所有片段
        4. 最終結果進行 strip() 清理首尾空白

        Args:
            segments: youtube_transcript_api 回傳的字幕片段列表

        Returns:
            清理後的完整字幕純文字字串
        """
        cleaned_texts: list[str] = []

        for segment in segments:
            raw_text: str = segment.get("text", "")

            # 移除 HTML 換行符號（部分字幕含有 \n）
            text = raw_text.replace("\n", " ")

            # 移除 [Music]、[Applause] 等音效/動作標記
            text = _NOISE_PATTERN.sub("", text)

            # 去除首尾空白後，過濾掉空字串
            text = text.strip()
            if text:
                cleaned_texts.append(text)

        # 以空格合併所有片段，並清理連續空白
        merged = " ".join(cleaned_texts)
        merged = _WHITESPACE_PATTERN.sub(" ", merged)
        return merged.strip()
