# -*- coding: utf-8 -*-
"""讀書 Agent v2 — Gemini 深度內容分析模組

功能：
1. 從影片字幕進行全面的重點整理（非摘要）
2. 將英文重點翻譯為繁體中文
3. 支援中英雙語影片，批次處理多部影片

重要設計原則：
- 輸出為「重點整理」，不是摘要。需完整聆聽影片後提取所有核心知識點。
- 中文影片：分析結果同時放入 key_points_original 與 key_points_zh
- 英文影片：原文分析 → key_points_original，翻譯後 → key_points_zh
"""

import asyncio
import logging

from google import genai

from .config import GEMINI_API_KEY
from .models import Video

logger = logging.getLogger(__name__)

# 批次處理時，每部影片之間的延遲秒數（避免超過 Gemini API 速率限制）
_BATCH_DELAY = 2.0

# Gemini 模型名稱
_MODEL = "gemini-2.5-flash"


def _init_client() -> genai.Client:
    """初始化 Gemini 客戶端"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未設定，請檢查 .env 檔案")
    return genai.Client(api_key=GEMINI_API_KEY)


class ContentAnalyzer:
    """Gemini 深度內容分析器

    負責從影片字幕中萃取完整的重點整理，並提供中英雙語輸出。
    核心理念：「把整個影片的內容聽完之後，重點整理給我」，而非摘要。

    Attributes:
        client: Gemini API 客戶端
    """

    def __init__(self) -> None:
        """初始化分析器，建立 Gemini 客戶端"""
        self.client = _init_client()

    # ------------------------------------------------------------------ #
    #  公開方法                                                             #
    # ------------------------------------------------------------------ #

    async def analyze_video(self, video: Video) -> Video:
        """分析單部影片，填入重點整理欄位

        流程：
        - 中文影片：執行中文分析 → 同時寫入 key_points_original 與 key_points_zh
        - 英文影片：執行英文分析 → 寫入 key_points_original；翻譯後寫入 key_points_zh
        - 若 Gemini 呼叫失敗：記錄錯誤並將錯誤訊息寫入兩個欄位，不拋出例外

        Args:
            video: 待分析的 Video 物件（需含 transcript / title / description）

        Returns:
            填入 key_points_original 與 key_points_zh 後的 Video 物件
        """
        logger.info(
            "開始分析影片 [%s] 語言=%s 字幕長度=%d",
            video.title[:40],
            video.language,
            len(video.transcript),
        )

        try:
            if video.language == "zh":
                # 中文影片：只需一次呼叫，結果直接作為雙語欄位
                result = await self._call_gemini(
                    self._build_analysis_prompt(video)
                )
                video.key_points_original = result
                video.key_points_zh = result

            else:
                # 英文影片（或其他語言）：先產生英文重點，再翻譯成中文
                original = await self._call_gemini(
                    self._build_analysis_prompt(video)
                )
                video.key_points_original = original

                # 翻譯步驟：將英文重點整理轉為繁體中文
                if original and not original.startswith("（錯誤"):
                    zh_result = await self.translate_to_chinese(original)
                    video.key_points_zh = zh_result
                else:
                    # 分析階段已失敗，不重複呼叫翻譯 API
                    video.key_points_zh = original

        except Exception as exc:
            # 任何未預期的錯誤都記錄下來，不讓整個批次中斷
            err_msg = f"（分析失敗：{exc}）"
            logger.error("分析影片失敗 [%s]: %s", video.title[:40], exc)
            video.key_points_original = err_msg
            video.key_points_zh = err_msg

        logger.info(
            "完成分析影片 [%s]，重點整理 %d 字",
            video.title[:40],
            len(video.key_points_zh),
        )
        return video

    async def analyze_batch(self, videos: list[Video]) -> list[Video]:
        """批次分析多部影片

        依序處理每部影片，每部影片間等待 _BATCH_DELAY 秒以避免觸發速率限制。
        單部影片失敗不影響其餘影片的處理。

        Args:
            videos: 待分析的 Video 列表

        Returns:
            所有 Video 填入重點整理後的列表（順序與輸入相同）
        """
        if not videos:
            return []

        results: list[Video] = []
        total = len(videos)

        for idx, video in enumerate(videos, start=1):
            logger.info("批次分析進度 %d/%d：%s", idx, total, video.title[:40])

            # 分析單部影片（內部已包含錯誤處理）
            updated = await self.analyze_video(video)
            results.append(updated)

            # 最後一部影片之後不需要等待
            if idx < total:
                await asyncio.sleep(_BATCH_DELAY)

        logger.info("批次分析完成，共處理 %d 部影片", total)
        return results

    async def translate_to_chinese(self, text: str) -> str:
        """將英文重點整理翻譯為繁體中文

        Args:
            text: 英文重點整理文字

        Returns:
            繁體中文翻譯結果；若翻譯失敗則回傳含錯誤說明的字串
        """
        if not text or not text.strip():
            return ""

        prompt = self._build_translation_prompt(text)

        try:
            result = await self._call_gemini(prompt)
            logger.info("翻譯完成，輸出 %d 字", len(result))
            return result
        except Exception as exc:
            logger.error("翻譯失敗: %s", exc)
            return f"（翻譯失敗：{exc}）\n\n原文：\n{text}"

    # ------------------------------------------------------------------ #
    #  Prompt 建構方法                                                      #
    # ------------------------------------------------------------------ #

    def _build_analysis_prompt(self, video: Video) -> str:
        """建構深度重點整理 Prompt

        根據影片語言決定輸出語言：
        - 中文影片 → 繁體中文輸出
        - 英文影片 → 英文輸出（後續再翻譯）

        若影片沒有字幕，則改用標題與描述作為備用資訊來源，
        並在輸出中標注「完整字幕不可用」。

        Args:
            video: 包含標題、描述、字幕等資訊的 Video 物件

        Returns:
            完整的 Gemini prompt 字串
        """
        # 判斷是否有可用字幕
        has_transcript = bool(video.transcript and video.transcript.strip())

        if has_transcript:
            # 有字幕：使用完整逐字稿作為分析素材
            content_block = f"以下是影片的完整逐字稿：\n\n{video.transcript}"
            fallback_note = ""
        else:
            # 無字幕：改用標題 + 描述作為備用資訊來源
            content_block = (
                f"注意：此影片無法取得完整字幕，以下僅提供影片標題與描述作為參考：\n\n"
                f"標題：{video.title}\n\n"
                f"描述：{video.description or '（無描述）'}"
            )
            # 標注資訊不完整的說明，需在輸出中呈現
            if video.language == "zh":
                fallback_note = (
                    "\n\n重要提示：由於無法取得完整字幕，"
                    "以下整理僅依據影片標題與描述，內容可能不完整，請以實際影片為準。"
                )
            else:
                fallback_note = (
                    "\n\nImportant note: Full transcript was unavailable. "
                    "The following key points are based on the video title and description only, "
                    "and may be incomplete. Please refer to the actual video for full content."
                )

        # 根據影片語言選擇不同的 prompt 模板
        if video.language == "zh":
            return self._build_zh_analysis_prompt(
                video, content_block, fallback_note
            )
        else:
            return self._build_en_analysis_prompt(
                video, content_block, fallback_note
            )

    def _build_zh_analysis_prompt(
        self, video: Video, content_block: str, fallback_note: str
    ) -> str:
        """建構中文影片的重點整理 Prompt（繁體中文輸出）

        Args:
            video: Video 物件（含標題、頻道等 metadata）
            content_block: 字幕或備用描述的文字區塊
            fallback_note: 字幕不可用時需附加的說明（可為空字串）

        Returns:
            完整 Prompt 字串
        """
        return f"""你是一位專業的說書整理員。你的任務是把整部說書影片的內容「完整聽完後，重點整理給我」。

這不是摘要，而是重點整理。請確保所有重要觀點、論據、案例、建議都被提取出來，讓讀者不需要看影片也能獲得完整的知識。

影片資訊：
- 標題：{video.title}
- 頻道：{video.channel_name}
- 描述：{video.description[:300] if video.description else "（無描述）"}

{content_block}

===== 請依照以下格式進行完整重點整理 =====

書籍基本資訊
書名（若有英文原名請附上）：
作者：
出版年份（若有提及）：
書籍類型 / 主題：

核心觀點（3 到 7 個主要觀點，每個用 2 到 3 句話詳述）
1.
2.
3.
（視內容增減）

作者的主要論點與論據
（說明作者為何提出這些觀點，以及用什麼根據來支撐）

書中關鍵案例、故事或實驗
（列出影片中提到的具體例子，這是重點整理的精華所在）

實用建議或可執行的行動方案
（作者或說書人提出哪些讀者可以立即實踐的方法或建議）

說書人的個人見解或推薦理由
（說書人對這本書有什麼獨到看法，為什麼值得一讀）{fallback_note}

格式規範：
- 全部使用繁體中文輸出
- 結構清晰，使用數字和縮排區隔層次
- 保留專有名詞，並附上英文原文，例如：心流（Flow）、成長型思維（Growth Mindset）
- 適合在 Telegram 上閱讀，文字不宜過於密集
- 不使用 Markdown 格式符號（不用 ** 或 #）
- 內容要詳盡完整，不能流於表面
"""

    def _build_en_analysis_prompt(
        self, video: Video, content_block: str, fallback_note: str
    ) -> str:
        """建構英文影片的重點整理 Prompt（英文輸出，供後續翻譯使用）

        Args:
            video: Video 物件（含標題、頻道等 metadata）
            content_block: 字幕或備用描述的文字區塊
            fallback_note: 字幕不可用時需附加的說明（可為空字串）

        Returns:
            完整 Prompt 字串
        """
        return f"""You are a professional book summarizer. Your task is to extract COMPLETE KEY POINTS from this book summary video — not a brief summary, but a thorough extraction of all important knowledge points, so the reader gains full value without watching the video.

Video Information:
- Title: {video.title}
- Channel: {video.channel_name}
- Description: {video.description[:300] if video.description else "(no description)"}

{content_block}

===== Please provide a complete key points extraction in the following format =====

Book Information
Title:
Author:
Publication Year (if mentioned):
Genre / Topic:

Core Concepts (3 to 7 main ideas, 2 to 3 sentences each)
1.
2.
3.
(add more as needed)

Author's Main Arguments and Supporting Evidence
(Explain why the author makes these claims and what evidence supports them)

Key Case Studies, Stories, or Experiments
(List specific examples from the video — these are the most valuable parts)

Practical Advice and Actionable Steps
(What concrete methods or recommendations does the author or presenter offer?)

Presenter's Personal Insights and Recommendation
(What is the presenter's unique perspective on the book, and why do they recommend it?){fallback_note}

Format requirements:
- Output entirely in English (translation to Chinese will be handled separately)
- Use numbered lists and indentation for clear structure
- Preserve proper nouns and technical terms as-is
- Be thorough and detailed — do not be superficial
- No Markdown formatting symbols (no ** or #)
"""

    def _build_translation_prompt(self, text: str) -> str:
        """建構英文→繁體中文翻譯 Prompt

        翻譯要求：
        - 保留結構（標題、編號、縮排）
        - 專有名詞保留英文原文並附中文譯名
        - 使用流暢的繁體中文，避免機翻腔
        - 不使用 Markdown 格式符號

        Args:
            text: 待翻譯的英文重點整理文字

        Returns:
            完整翻譯 Prompt 字串
        """
        return f"""請將以下英文書籍重點整理翻譯成繁體中文。

翻譯要求：
1. 保留原文的結構（標題、編號、縮排），逐段翻譯
2. 專有名詞（書名、人名、概念名稱）保留英文原文並附上繁體中文譯名，格式為：中文譯名（英文原文）
3. 使用流暢自然的繁體中文，避免逐字直譯造成的生硬感
4. 不使用 Markdown 格式符號（不用 ** 或 #）
5. 確保技術術語、學術概念的翻譯準確

以下是待翻譯的英文內容：

{text}
"""

    # ------------------------------------------------------------------ #
    #  內部輔助方法                                                         #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  AI Weekly 專用方法                                                    #
    # ------------------------------------------------------------------ #

    async def analyze_ai_video(self, video: Video) -> Video:
        """分析單部 AI 資訊影片，填入重點整理欄位

        與 analyze_video() 邏輯相同，但使用 AI 資訊專用 prompt。

        Args:
            video: 待分析的 AI 資訊影片 Video 物件

        Returns:
            填入 key_points_original 與 key_points_zh 後的 Video 物件
        """
        logger.info(
            "開始分析 AI 影片 [%s] 語言=%s 字幕長度=%d",
            video.title[:40],
            video.language,
            len(video.transcript),
        )

        try:
            if video.language == "zh":
                result = await self._call_gemini(
                    self._build_ai_analysis_prompt(video)
                )
                video.key_points_original = result
                video.key_points_zh = result
            else:
                original = await self._call_gemini(
                    self._build_ai_analysis_prompt(video)
                )
                video.key_points_original = original

                if original and not original.startswith("（錯誤"):
                    zh_result = await self.translate_to_chinese(original)
                    video.key_points_zh = zh_result
                else:
                    video.key_points_zh = original

        except Exception as exc:
            err_msg = f"（AI 分析失敗：{exc}）"
            logger.error("分析 AI 影片失敗 [%s]: %s", video.title[:40], exc)
            video.key_points_original = err_msg
            video.key_points_zh = err_msg

        logger.info(
            "完成分析 AI 影片 [%s]，重點整理 %d 字",
            video.title[:40],
            len(video.key_points_zh),
        )
        return video

    async def analyze_ai_batch(self, videos: list[Video]) -> list[Video]:
        """批次分析多部 AI 資訊影片

        Args:
            videos: 待分析的 AI 影片列表

        Returns:
            所有 Video 填入重點整理後的列表
        """
        if not videos:
            return []

        results: list[Video] = []
        total = len(videos)

        for idx, video in enumerate(videos, start=1):
            logger.info("AI 批次分析進度 %d/%d：%s", idx, total, video.title[:40])
            updated = await self.analyze_ai_video(video)
            results.append(updated)

            if idx < total:
                await asyncio.sleep(_BATCH_DELAY)

        logger.info("AI 批次分析完成，共處理 %d 部影片", total)
        return results

    # ------------------------------------------------------------------ #
    #  AI 專用 Prompt 建構方法                                               #
    # ------------------------------------------------------------------ #

    def _build_ai_analysis_prompt(self, video: Video) -> str:
        """建構 AI 資訊專用的分析 prompt

        與書籍分析不同，AI 資訊著重於：技術突破、產品更新、
        產業影響、實際應用場景、趨勢與風險。

        Args:
            video: 包含標題、描述、字幕的 Video 物件

        Returns:
            完整的 Gemini prompt 字串
        """
        has_transcript = bool(video.transcript and video.transcript.strip())

        if has_transcript:
            content_block = f"以下是影片的完整逐字稿：\n\n{video.transcript}"
            fallback_note = ""
        else:
            content_block = (
                f"注意：此影片無法取得完整字幕，以下僅提供影片標題與描述作為參考：\n\n"
                f"標題：{video.title}\n\n"
                f"描述：{video.description or '（無描述）'}"
            )
            if video.language == "zh":
                fallback_note = (
                    "\n\n重要提示：由於無法取得完整字幕，"
                    "以下整理僅依據影片標題與描述，內容可能不完整，請以實際影片為準。"
                )
            else:
                fallback_note = (
                    "\n\nImportant note: Full transcript was unavailable. "
                    "The following key points are based on the video title and description only, "
                    "and may be incomplete. Please refer to the actual video for full content."
                )

        if video.language == "zh":
            return self._build_ai_zh_prompt(video, content_block, fallback_note)
        else:
            return self._build_ai_en_prompt(video, content_block, fallback_note)

    def _build_ai_zh_prompt(
        self, video: Video, content_block: str, fallback_note: str
    ) -> str:
        """建構中文 AI 資訊影片的分析 Prompt

        Args:
            video: Video 物件
            content_block: 字幕或備用描述的文字區塊
            fallback_note: 字幕不可用時需附加的說明

        Returns:
            完整 Prompt 字串
        """
        return f"""你是一位專業的 AI 科技資訊整理員。你的任務是把整部 AI 相關影片的內容「完整聽完後，重點整理給我」。

這不是摘要，而是完整的重點整理。請確保所有重要的技術突破、產品更新、應用案例、產業動態都被提取出來。

影片資訊：
- 標題：{video.title}
- 頻道：{video.channel_name}
- 描述：{video.description[:300] if video.description else "（無描述）"}

{content_block}

===== 請依照以下格式進行完整重點整理 =====

主題概述
一句話說明這部影片在講什麼

涉及的 AI 技術 / 產品 / 公司
（列出所有提到的技術名稱、模型版本、公司名稱，例如：GPT-4o、Claude 3.5、Gemini 2.0 等）

核心發現或突破（3 到 7 個重點，每個用 2 到 3 句話詳述）
1.
2.
3.
（視內容增減）

實際應用場景與案例
（列出影片中提到的具體應用案例、demo、使用方式）

對產業 / 職場 / 日常生活的影響
（這些 AI 進展如何影響工作方式、產業趨勢、或一般人的生活）

值得關注的趨勢或風險
（未來可能的發展方向、潛在風險、值得持續追蹤的事項）

推薦的 AI 工具或資源
（若影片中有提到值得嘗試的工具、網站、開源專案等，請列出名稱）{fallback_note}

格式規範：
- 全部使用繁體中文輸出
- 結構清晰，使用數字和縮排區隔層次
- 保留所有 AI 技術專有名詞的英文原名，例如：大型語言模型（LLM）、檢索增強生成（RAG）
- 適合在 Telegram 上閱讀，文字不宜過於密集
- 不使用 Markdown 格式符號（不用 ** 或 #）
- 內容要詳盡完整，不能流於表面
"""

    def _build_ai_en_prompt(
        self, video: Video, content_block: str, fallback_note: str
    ) -> str:
        """建構英文 AI 資訊影片的分析 Prompt

        Args:
            video: Video 物件
            content_block: 字幕或備用描述的文字區塊
            fallback_note: 字幕不可用時需附加的說明

        Returns:
            完整 Prompt 字串
        """
        return f"""You are a professional AI technology analyst. Your task is to extract COMPLETE KEY POINTS from this AI-related video — not a brief summary, but a thorough extraction of all important information.

Video Information:
- Title: {video.title}
- Channel: {video.channel_name}
- Description: {video.description[:300] if video.description else "(no description)"}

{content_block}

===== Please provide a complete key points extraction in the following format =====

Topic Overview
One sentence describing what this video covers

AI Technologies / Products / Companies Mentioned
(List all technology names, model versions, company names, e.g., GPT-4o, Claude 3.5, Gemini 2.0)

Core Findings or Breakthroughs (3 to 7 key points, 2 to 3 sentences each)
1.
2.
3.
(add more as needed)

Real-World Applications and Use Cases
(List specific applications, demos, or practical usage scenarios mentioned)

Impact on Industry / Workforce / Daily Life
(How do these AI developments affect work, industry trends, or everyday life?)

Trends and Risks Worth Watching
(Future developments, potential risks, things to keep an eye on)

Recommended AI Tools or Resources
(Any tools, websites, or open-source projects mentioned that are worth trying){fallback_note}

Format requirements:
- Output entirely in English (translation to Chinese will be handled separately)
- Use numbered lists and indentation for clear structure
- Preserve all AI technical terms and proper nouns as-is
- Be thorough and detailed — do not be superficial
- No Markdown formatting symbols (no ** or #)
"""

    # ------------------------------------------------------------------ #
    #  內部輔助方法                                                         #
    # ------------------------------------------------------------------ #

    async def _call_gemini(self, prompt: str) -> str:
        """呼叫 Gemini API 取得回應

        使用 asyncio.to_thread 將同步 SDK 呼叫包裝為非同步，
        避免阻塞事件迴圈。

        Args:
            prompt: 傳送給 Gemini 的完整 prompt 字串

        Returns:
            Gemini 回應的純文字內容（已去除前後空白）

        Raises:
            Exception: 任何 API 呼叫錯誤都直接向上拋出，由呼叫方決定如何處理
        """
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=_MODEL,
            contents=prompt,
        )
        result = (response.text or "").strip()
        return result
