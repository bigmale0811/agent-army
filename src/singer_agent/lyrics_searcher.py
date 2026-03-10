# -*- coding: utf-8 -*-
"""
Singer V3.2 Phase 2: 歌詞搜尋與分析模組。

LyricsSearcher 透過 Ollama LLM 召回歌詞並進行深度分析，
產出結構化的 LyricsAnalysis 資料（主題、關鍵詞、情感弧線、視覺提示等）。

與 researcher.py（SongResearcher）的分工：
- SongResearcher：分析音樂「風格與視覺元素」
- LyricsSearcher：分析歌詞「故事內容與情感敘事」，補充更豐富的 SDXL 背景提示詞

支援 dry_run 模式回傳 stub 資料，方便測試管線整合。
"""
import json
import logging
from dataclasses import dataclass

from src.singer_agent.ollama_client import OllamaClient

_logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────
# LyricsAnalysis：歌詞分析結果（不可變）
# ─────────────────────────────────────────────────

@dataclass(frozen=True)
class LyricsAnalysis:
    """
    歌詞分析結果，由 LyricsSearcher 透過 Ollama LLM 產出。
    frozen=True 確保資料不可變，符合專案不可變物件原則。
    """
    lyrics_theme: str           # 歌曲主題／故事摘要（繁體中文）
    lyric_keywords: list        # 歌詞關鍵詞列表（5-10 個英文詞）
    emotion_arc: str            # 情感弧線描述（繁體中文）
    enhanced_background_prompt: str  # 強化版 SDXL 背景提示詞（英文，1920x1080 電影風）
    outfit_suggestion: str      # 角色服裝建議（英文）


# ─────────────────────────────────────────────────
# Dry run stub 資料
# ─────────────────────────────────────────────────

# dry_run 模式使用的預設 stub 資料，不呼叫 Ollama
_STUB_ANALYSIS = LyricsAnalysis(
    lyrics_theme="預設歌曲主題",
    lyric_keywords=["love", "memory", "dream"],
    emotion_arc="從溫柔開始，逐漸高昂，最後回歸平靜",
    enhanced_background_prompt="dreamy sunset cityscape, warm golden light, "
                               "bokeh, cinematic 1920x1080, atmospheric haze",
    outfit_suggestion="elegant casual wear, light colored shirt",
)


# ─────────────────────────────────────────────────
# Ollama Prompt 模板
# ─────────────────────────────────────────────────

# 單次呼叫：要求 LLM 同時召回歌詞並完成分析，降低 API 呼叫次數
_LYRICS_ANALYSIS_PROMPT = """You are a music analyst. Given the song title and artist, \
recall or reconstruct the lyrics and analyze them.

Song: "{title}" by "{artist}"
Language: {language}

Return a JSON object with exactly these keys:
{{
    "lyrics_theme": "Brief summary of the song's story/theme (in Traditional Chinese)",
    "lyric_keywords": ["keyword1", "keyword2"],
    "emotion_arc": "Description of emotional progression (in Traditional Chinese)",
    "enhanced_background_prompt": "Detailed SDXL prompt for a background image that \
matches the song's mood (in English, 1920x1080, cinematic)",
    "outfit_suggestion": "Character outfit that matches the song's style (in English)"
}}

Rules:
- lyric_keywords must contain 5 to 10 English words extracted from the song's themes
- enhanced_background_prompt must be a detailed, comma-separated list of visual descriptors \
suitable for Stable Diffusion XL
- Respond ONLY with valid JSON, no markdown fences, no explanation"""


def _strip_markdown_fences(text: str) -> str:
    """
    移除 Ollama 回應中可能包裹的 markdown 程式碼區塊（```json ... ```）。

    Ollama 有時會在 JSON 外加上 markdown fence，導致 json.loads 失敗。
    此函式確保回傳乾淨的 JSON 字串。
    """
    text = text.strip()
    if text.startswith("```"):
        # 移除第一行（可能是 ```json 或 ``` 等）
        lines = text.split("\n")
        # 第一行是 fence 標記，最後一行是結尾 ```
        inner_lines = lines[1:]
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        text = "\n".join(inner_lines)
    return text.strip()


# ─────────────────────────────────────────────────
# LyricsSearcher：主要類別
# ─────────────────────────────────────────────────

class LyricsSearcher:
    """
    歌詞搜尋與分析模組。

    透過 Ollama LLM 召回歌詞並分析曲風、故事主題、情感弧線，
    產出強化版 SDXL 背景提示詞供後續背景生成使用。

    Args:
        ollama_client: OllamaClient 實例，預設自動建立
        dry_run: True 時回傳 stub 資料，不呼叫 Ollama（測試用）
    """

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        dry_run: bool = False,
    ) -> None:
        # 若未提供 client，自動建立預設實例
        self.client = ollama_client or OllamaClient()
        # dry_run 模式標記：儲存在實例中，方便 search_and_analyze 使用
        self.dry_run = dry_run

    def search_and_analyze(
        self,
        title: str,
        artist: str,
        language: str = "zh-TW",
    ) -> LyricsAnalysis:
        """
        搜尋歌詞並分析曲風、故事主題、情感弧線。

        由於 Python 環境無法直接調用 WebSearch，
        改以 Ollama LLM 的訓練知識召回歌詞並一次完成分析。

        Steps:
            1. 建立結合「歌詞召回 + 分析」的單一 prompt
            2. 呼叫 Ollama 取得 JSON 回應
            3. 清理可能的 markdown fence 包裹
            4. 解析 JSON 並建立 LyricsAnalysis

        Args:
            title: 歌曲名稱（可含中文）
            artist: 歌手名稱
            language: 歌詞語言標籤，如 "zh-TW"，影響 LLM 輸出語言

        Returns:
            LyricsAnalysis 不可變資料物件

        Raises:
            ValueError: Ollama 回傳空白回應
            json.JSONDecodeError: LLM 回應非合法 JSON
            TypeError: JSON 解析結果非 dict 物件
            KeyError: JSON 缺少必要欄位
        """
        # dry_run 模式：直接回傳 stub，跳過 LLM 呼叫
        if self.dry_run:
            _logger.info("dry_run 模式：回傳 stub LyricsAnalysis（title=%s, artist=%s）",
                         title, artist)
            return _STUB_ANALYSIS

        _logger.info("開始歌詞分析：title=%s, artist=%s, language=%s",
                     title, artist, language)

        # 組裝 prompt，將歌曲資訊填入模板
        prompt = _LYRICS_ANALYSIS_PROMPT.format(
            title=title,
            artist=artist,
            language=language,
        )

        _logger.debug("發送歌詞分析 prompt 至 Ollama（%d 字元）", len(prompt))
        raw_response = self.client.generate(prompt)

        # 防護：generate() 可能回傳空白字串（Ollama 異常回應）
        if not raw_response:
            raise ValueError(
                f"Ollama 回傳空白回應，無法分析歌詞：title={title!r}, artist={artist!r}"
            )

        # 清理 markdown fence 包裹，確保 json.loads 可正常解析
        cleaned = _strip_markdown_fences(raw_response)
        _logger.debug("清理後 JSON 文字（前 300 字）：%s", cleaned[:300])

        # 解析 JSON，讓例外自然往上傳遞給呼叫方
        data = json.loads(cleaned)

        # 防護：json.loads("null") 回傳 None，或回傳非 dict 結構
        if not isinstance(data, dict):
            raise TypeError(
                f"Ollama 歌詞分析回應非 JSON 物件（type={type(data).__name__}），"
                f"原始回應前 200 字：{cleaned[:200]}"
            )

        _logger.info("歌詞分析完成：theme=%s", data.get("lyrics_theme", "（未知）"))

        # 建立不可變 LyricsAnalysis，缺少欄位時 KeyError 自然往上傳遞
        return LyricsAnalysis(
            lyrics_theme=data["lyrics_theme"],
            lyric_keywords=data["lyric_keywords"],
            emotion_arc=data["emotion_arc"],
            enhanced_background_prompt=data["enhanced_background_prompt"],
            outfit_suggestion=data["outfit_suggestion"],
        )
