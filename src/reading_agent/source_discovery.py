# -*- coding: utf-8 -*-
"""讀書 Agent v2 — Source Discovery 來源探索核心模組

功能：
1. 自動探索新的說書 YouTube 頻道（依關鍵字搜尋）
2. 探索固定書評網站（使用預設清單）
3. 使用 Gemini 評估候選來源的品質與相關性
4. 管理已發現的來源（讀取、寫入、審核）
5. 審核通過後自動寫入 channels.json

評分維度（總分 100）：
- 內容相關性（40 分）：是否專注於說書、書評、閱讀推薦
- 品質（30 分）：內容深度、製作水準、資訊可信度
- 活躍度（20 分）：更新頻率、近期發布時間
- 受眾契合度（10 分）：語言、目標受眾與本系統使用者的符合程度

v2.1 新增
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

# ------------------------------------------------------------------ #
# 相容性修補：youtube-search-python 1.6.x 使用已被 httpx 0.28+ 移除的
# proxies 參數，導致 post() got an unexpected keyword argument 'proxies'。
# 必須在 import youtubesearchpython 之前套用此修補。
# ------------------------------------------------------------------ #
if not hasattr(httpx.post, "_patched_for_proxies"):
    _original_httpx_post = httpx.post

    def _patched_httpx_post(*args, **kwargs):
        kwargs.pop("proxies", None)
        return _original_httpx_post(*args, **kwargs)

    _patched_httpx_post._patched_for_proxies = True  # type: ignore[attr-defined]
    httpx.post = _patched_httpx_post

from youtubesearchpython import VideosSearch  # noqa: E402

from google import genai  # noqa: E402

from .config import (  # noqa: E402
    CHANNELS_FILE,
    DISCOVERED_SOURCES_FILE,
    DISCOVERY_INTERVAL_DAYS,
    DISCOVERY_KNOWN_WEBSITES,
    DISCOVERY_LOG_FILE,
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MIN_SCORE,
    DISCOVERY_SEARCH_LIMIT_PER_KEYWORD,
    DISCOVERY_YOUTUBE_KEYWORDS_EN,
    DISCOVERY_YOUTUBE_KEYWORDS_ZH,
    GEMINI_API_KEY,
    REQUEST_DELAY,
)
from .models import DiscoveredSource  # noqa: E402

logger = logging.getLogger(__name__)

# Gemini 模型名稱（與 content_analyzer.py 保持一致）
_MODEL = "gemini-2.5-flash"

# Gemini API 呼叫之間的最小間隔（秒），避免觸發速率限制
_GEMINI_CALL_DELAY = 2.0


def _init_gemini_client() -> genai.Client:
    """初始化 Gemini 客戶端

    Returns:
        已設定 API key 的 Gemini 客戶端

    Raises:
        ValueError: 若 GEMINI_API_KEY 未設定
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未設定，請檢查 .env 檔案")
    return genai.Client(api_key=GEMINI_API_KEY)


class SourceDiscovery:
    """來源探索器

    自動探索新的 YouTube 說書頻道與書評網站，
    透過 Gemini 評估品質，並管理已發現的來源清單。

    Attributes:
        client: Gemini API 客戶端（延遲初始化，使用時才建立）
    """

    def __init__(self) -> None:
        """初始化探索器，Gemini 客戶端延遲初始化以避免 API key 尚未設定時報錯"""
        # 延遲初始化 Gemini 客戶端（呼叫評估方法時才建立）
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        """取得 Gemini 客戶端（懶載入）"""
        if self._client is None:
            self._client = _init_gemini_client()
        return self._client

    # ================================================================== #
    #  公開方法                                                             #
    # ================================================================== #

    async def run_discovery(self) -> list[DiscoveredSource]:
        """執行完整的來源探索流程

        流程：
        1. 載入已追蹤頻道 ID（避免重複推薦）
        2. 載入已發現的來源（避免重複推薦 approved/rejected）
        3. YouTube 頻道探索
        4. 書評網站探索
        5. 合併候選，過濾已發現的（比對 URL）
        6. Gemini 評分
        7. 按分數排序，過濾低於門檻的，取前 N 個
        8. 存入 discovered_sources.json
        9. 寫入 discovery_log.json
        10. 回傳候選清單

        Returns:
            通過評分門檻的 DiscoveredSource 列表（依分數由高到低排序）
        """
        start_time = time.time()
        logger.info("開始執行來源探索流程")

        # 步驟 1：載入已追蹤頻道 ID
        tracked_ids = self._load_tracked_channel_ids()
        logger.info("已追蹤頻道數量：%d", len(tracked_ids))

        # 步驟 2：載入已發現的來源（pending / approved / rejected 都算）
        existing_sources = self.load_discovered()
        existing_urls: set[str] = {s.url for s in existing_sources}
        logger.info("已發現來源數量：%d", len(existing_sources))

        # 步驟 3：YouTube 頻道探索
        youtube_candidates: list[DiscoveredSource] = []
        try:
            youtube_candidates = await self._discover_youtube_channels(tracked_ids)
            logger.info("YouTube 探索到 %d 個候選頻道", len(youtube_candidates))
        except Exception as exc:
            # YouTube 探索失敗不中斷整體流程
            logger.error("YouTube 頻道探索發生錯誤，略過：%s", exc)

        # 步驟 4：書評網站探索
        website_candidates: list[DiscoveredSource] = []
        try:
            website_candidates = await self._discover_websites()
            logger.info("網站探索到 %d 個候選來源", len(website_candidates))
        except Exception as exc:
            logger.error("書評網站探索發生錯誤，略過：%s", exc)

        # 步驟 5：合併候選，過濾已發現的（比對 URL）
        all_candidates = youtube_candidates + website_candidates
        new_candidates = [c for c in all_candidates if c.url not in existing_urls]
        logger.info(
            "新候選來源數量：%d（已過濾 %d 個重複）",
            len(new_candidates),
            len(all_candidates) - len(new_candidates),
        )

        if not new_candidates:
            logger.info("本次探索無新候選來源")
            self._log_discovery_run(
                trigger="manual",
                candidates_found=0,
                duration=time.time() - start_time,
            )
            return []

        # 步驟 6：Gemini 評分
        evaluated_candidates: list[DiscoveredSource] = []
        try:
            evaluated_candidates = await self._evaluate_sources_with_gemini(
                new_candidates
            )
        except Exception as exc:
            logger.error("Gemini 評分流程發生錯誤，使用未評分的候選：%s", exc)
            evaluated_candidates = new_candidates

        # 步驟 7：按分數排序，過濾低於門檻的，取前 N 個
        qualified = [
            s for s in evaluated_candidates if s.score >= DISCOVERY_MIN_SCORE
        ]
        qualified.sort(key=lambda s: s.score, reverse=True)
        final_candidates = qualified[:DISCOVERY_MAX_CANDIDATES]
        logger.info(
            "最終候選：%d 個（高於 %.1f 分），取前 %d 個",
            len(qualified),
            DISCOVERY_MIN_SCORE,
            len(final_candidates),
        )

        # 步驟 8：存入 discovered_sources.json（合併既有的）
        merged = existing_sources + final_candidates
        self.save_discovered(merged)

        # 步驟 9：寫入 discovery_log.json
        duration = time.time() - start_time
        self._log_discovery_run(
            trigger="manual",
            candidates_found=len(final_candidates),
            duration=duration,
        )

        logger.info(
            "來源探索流程完成，耗時 %.1f 秒，回傳 %d 個候選",
            duration,
            len(final_candidates),
        )
        # 步驟 10：回傳候選清單
        return final_candidates

    async def discover_if_due(self) -> list[DiscoveredSource]:
        """若超過設定週期才執行探索

        檢查 discovery_log.json 中最後一次執行的時間，
        若距今超過 DISCOVERY_INTERVAL_DAYS 天則執行 run_discovery()，
        否則回傳空列表並記錄跳過原因。

        Returns:
            若執行探索則回傳候選清單；否則回傳空列表
        """
        if not self._is_due_for_discovery():
            logger.info(
                "距上次探索未超過 %d 天，跳過本次探索",
                DISCOVERY_INTERVAL_DAYS,
            )
            return []

        logger.info("已超過探索週期，開始自動探索")
        results = await self.run_discovery()

        # 更新 trigger 為 scheduled
        self._log_discovery_run(
            trigger="scheduled",
            candidates_found=len(results),
            duration=0,
        )
        return results

    def load_discovered(self) -> list[DiscoveredSource]:
        """從 discovered_sources.json 讀取已發現的來源清單

        Returns:
            DiscoveredSource 列表；檔案不存在或解析失敗時回傳空列表
        """
        if not DISCOVERED_SOURCES_FILE.exists():
            logger.debug("discovered_sources.json 不存在，回傳空列表")
            return []

        try:
            with open(DISCOVERED_SOURCES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            sources = [DiscoveredSource.from_dict(item) for item in data]
            logger.debug("載入 %d 個已發現來源", len(sources))
            return sources
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("載入 discovered_sources.json 失敗：%s", exc)
            return []

    def save_discovered(self, sources: list[DiscoveredSource]) -> None:
        """將來源清單寫入 discovered_sources.json

        Args:
            sources: 要寫入的 DiscoveredSource 列表
        """
        try:
            # 確保父目錄存在
            DISCOVERED_SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [s.to_dict() for s in sources]
            with open(DISCOVERED_SOURCES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("已寫入 %d 個來源至 %s", len(sources), DISCOVERED_SOURCES_FILE)
        except OSError as exc:
            logger.error("寫入 discovered_sources.json 失敗：%s", exc)

    def approve_source(self, name: str) -> bool:
        """審核通過指定名稱的來源

        1. 從 discovered_sources.json 找到 name 匹配的來源
        2. 更新 status = "approved"
        3. 若是 youtube_channel，同時寫入 channels.json
        4. 存回 discovered_sources.json

        Args:
            name: 來源名稱（DiscoveredSource.name）

        Returns:
            True 表示成功找到並更新；False 表示找不到指定名稱
        """
        sources = self.load_discovered()

        # 尋找名稱匹配的來源（名稱比對不區分前後空白）
        target: DiscoveredSource | None = None
        for source in sources:
            if source.name.strip() == name.strip():
                target = source
                break

        if target is None:
            logger.warning("找不到名稱為「%s」的來源，無法 approve", name)
            return False

        # 更新狀態
        target.status = "approved"
        self.save_discovered(sources)
        logger.info("已 approve 來源：%s", name)

        # 若是 YouTube 頻道，寫入 channels.json
        if target.source_type == "youtube_channel":
            self._add_to_channels_json(target)

        return True

    def reject_source(self, name: str) -> bool:
        """拒絕指定名稱的來源

        Args:
            name: 來源名稱（DiscoveredSource.name）

        Returns:
            True 表示成功找到並更新；False 表示找不到指定名稱
        """
        sources = self.load_discovered()

        # 尋找名稱匹配的來源
        target: DiscoveredSource | None = None
        for source in sources:
            if source.name.strip() == name.strip():
                target = source
                break

        if target is None:
            logger.warning("找不到名稱為「%s」的來源，無法 reject", name)
            return False

        # 更新狀態
        target.status = "rejected"
        self.save_discovered(sources)
        logger.info("已 reject 來源：%s", name)
        return True

    # ================================================================== #
    #  私有方法                                                             #
    # ================================================================== #

    async def _discover_youtube_channels(
        self, tracked_ids: set[str]
    ) -> list[DiscoveredSource]:
        """探索 YouTube 說書頻道

        合併中英文關鍵字，逐一搜尋，從搜尋結果中提取頻道資訊，
        以 channel_id 去重，並過濾已追蹤的頻道。

        Args:
            tracked_ids: 已追蹤的 YouTube channel_id 集合（用於去重過濾）

        Returns:
            新發現的 YouTube 頻道 DiscoveredSource 列表
        """
        # 合併中英文關鍵字
        all_keywords = DISCOVERY_YOUTUBE_KEYWORDS_ZH + DISCOVERY_YOUTUBE_KEYWORDS_EN
        logger.info("開始 YouTube 頻道探索，共 %d 個關鍵字", len(all_keywords))

        # 以 channel_id 為鍵收集候選頻道，避免重複
        # 值包含：DiscoveredSource 物件 與 近期影片標題列表
        channel_map: dict[str, DiscoveredSource] = {}

        for keyword in all_keywords:
            logger.debug("搜尋關鍵字：%s", keyword)
            try:
                # 使用 asyncio.to_thread 包裝同步的 YouTubeSearch 呼叫
                raw_results = await asyncio.to_thread(
                    self._run_videos_search,
                    keyword,
                    DISCOVERY_SEARCH_LIMIT_PER_KEYWORD,
                )

                for result in raw_results:
                    # 從搜尋結果提取頻道資訊
                    channel_info = result.get("channel", {})
                    channel_id = channel_info.get("id", "")
                    channel_name = channel_info.get("name", "")

                    # 必要欄位驗證
                    if not channel_id or not channel_name:
                        continue

                    # 過濾已追蹤的頻道
                    if channel_id in tracked_ids:
                        logger.debug("頻道已追蹤，略過：%s (%s)", channel_name, channel_id)
                        continue

                    # 建立頻道 URL
                    channel_url = f"https://www.youtube.com/channel/{channel_id}"

                    # 若已在候選清單中，附加近期影片標題
                    if channel_id in channel_map:
                        existing = channel_map[channel_id]
                        recent_titles: list[str] = existing.metadata.get(
                            "recent_video_titles", []
                        )
                        video_title = result.get("title", "")
                        if video_title and video_title not in recent_titles:
                            recent_titles.append(video_title)
                            existing.metadata["recent_video_titles"] = recent_titles[:5]
                        continue

                    # 建立新候選來源
                    recent_video_titles: list[str] = []
                    video_title = result.get("title", "")
                    if video_title:
                        recent_video_titles.append(video_title)

                    source = DiscoveredSource(
                        name=channel_name,
                        url=channel_url,
                        source_type="youtube_channel",
                        category="general",
                        language="zh",  # 預設中文，Gemini 評估後會更新
                        score=0.0,
                        reason="",
                        status="pending",
                        metadata={
                            "channel_id": channel_id,
                            "recent_video_titles": recent_video_titles,
                            "discovered_by_keyword": keyword,
                        },
                    )
                    channel_map[channel_id] = source

            except Exception as exc:
                # 單一關鍵字搜尋失敗不中斷整體流程
                logger.warning("關鍵字「%s」搜尋失敗，略過：%s", keyword, exc)

            # 搜尋之間加入延遲，避免請求過於頻繁
            await asyncio.sleep(REQUEST_DELAY)

        candidates = list(channel_map.values())
        logger.info("YouTube 頻道探索完成，共找到 %d 個新頻道", len(candidates))
        return candidates

    async def _discover_websites(self) -> list[DiscoveredSource]:
        """探索書評網站

        使用 DISCOVERY_KNOWN_WEBSITES 清單產生候選來源，
        過濾已在 discovered_sources.json 中出現的（比對 URL）。

        Returns:
            新發現的網站 DiscoveredSource 列表
        """
        logger.info("開始書評網站探索")

        # 載入已發現的來源 URL 集合
        existing_sources = self.load_discovered()
        existing_urls: set[str] = {s.url for s in existing_sources}

        candidates: list[DiscoveredSource] = []

        for website_info in DISCOVERY_KNOWN_WEBSITES:
            url = website_info.get("url", "")
            name = website_info.get("name", "")
            language = website_info.get("language", "zh")
            description = website_info.get("description", "")

            # 必要欄位驗證
            if not url or not name:
                continue

            # 過濾已發現的
            if url in existing_urls:
                logger.debug("網站已在發現清單中，略過：%s", name)
                continue

            source = DiscoveredSource(
                name=name,
                url=url,
                source_type="website",
                category="general",
                language=language,
                score=0.0,
                reason="",
                status="pending",
                metadata={
                    "description": description,
                },
            )
            candidates.append(source)

        logger.info("書評網站探索完成，共找到 %d 個新網站", len(candidates))
        return candidates

    async def _evaluate_sources_with_gemini(
        self, candidates: list[DiscoveredSource]
    ) -> list[DiscoveredSource]:
        """使用 Gemini 逐一評估候選來源

        評分維度（總分 100）：
        - 內容相關性（40 分）
        - 品質（30 分）
        - 活躍度（20 分）
        - 受眾契合度（10 分）

        Args:
            candidates: 待評估的 DiscoveredSource 列表

        Returns:
            填入 score / category / reason / language 後的 DiscoveredSource 列表
            （單個來源評估失敗不影響其他來源）
        """
        logger.info("開始 Gemini 評估，共 %d 個候選來源", len(candidates))
        results: list[DiscoveredSource] = []

        for idx, source in enumerate(candidates, start=1):
            logger.info(
                "Gemini 評估進度 %d/%d：%s", idx, len(candidates), source.name
            )
            try:
                prompt = self._build_evaluation_prompt(source)
                # 使用 asyncio.to_thread 包裝同步 Gemini SDK 呼叫
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=_MODEL,
                    contents=prompt,
                )
                raw_text = (response.text or "").strip()
                evaluation = self._parse_gemini_evaluation(raw_text)

                # 將評估結果填入來源物件
                source.score = float(evaluation.get("score", 0.0))
                source.category = evaluation.get("category", "general")
                source.reason = evaluation.get("reason", "")
                source.language = evaluation.get("language", source.language)

                # 將更新頻率寫入 metadata
                update_frequency = evaluation.get("update_frequency", "")
                if update_frequency:
                    source.metadata["update_frequency"] = update_frequency

                logger.info(
                    "評估完成：%s，分數：%.1f，分類：%s",
                    source.name,
                    source.score,
                    source.category,
                )

            except Exception as exc:
                # 單個來源評估失敗不中斷整體批次
                logger.warning("來源「%s」Gemini 評估失敗，略過：%s", source.name, exc)
                source.score = 0.0
                source.reason = f"評估失敗：{exc}"

            results.append(source)

            # 呼叫之間加入延遲，避免觸發 Gemini 速率限制
            if idx < len(candidates):
                await asyncio.sleep(_GEMINI_CALL_DELAY)

        logger.info("Gemini 評估完成，共評估 %d 個來源", len(results))
        return results

    def _build_evaluation_prompt(self, source: DiscoveredSource) -> str:
        """建構 Gemini 評估 prompt

        要求 Gemini 輸出純 JSON（不加 markdown），包含以下欄位：
        - score: 0-100 的整數評分
        - category: 對應 BOOK_CATEGORIES 的分類鍵值
        - reason: 繁體中文的推薦理由（1-3 句）
        - language: 內容語言（"zh" / "en" / "both"）
        - update_frequency: 更新頻率描述（如 "每週"、"不定期" 等）

        評分維度（總分 100）：
        - 內容相關性（40 分）：是否專注於說書、書評、閱讀推薦
        - 品質（30 分）：內容深度、製作水準、資訊可信度
        - 活躍度（20 分）：更新頻率、近期發布時間
        - 受眾契合度（10 分）：語言、目標受眾符合程度

        Args:
            source: 待評估的 DiscoveredSource 物件

        Returns:
            完整的 Gemini prompt 字串
        """
        # 組裝額外資訊（頻道近期影片、網站描述等）
        extra_info_parts: list[str] = []

        if source.source_type == "youtube_channel":
            recent_titles = source.metadata.get("recent_video_titles", [])
            if recent_titles:
                titles_str = "\n".join(f"  - {t}" for t in recent_titles[:5])
                extra_info_parts.append(f"近期影片標題：\n{titles_str}")
            channel_id = source.metadata.get("channel_id", "")
            if channel_id:
                extra_info_parts.append(f"頻道 ID：{channel_id}")

        elif source.source_type in ("website", "rss_feed"):
            description = source.metadata.get("description", "")
            if description:
                extra_info_parts.append(f"網站描述：{description}")

        extra_info = "\n".join(extra_info_parts) if extra_info_parts else "（無額外資訊）"

        # 來源類型的繁體中文描述
        type_labels = {
            "youtube_channel": "YouTube 頻道",
            "website": "書評網站",
            "rss_feed": "RSS Feed",
        }
        type_label = type_labels.get(source.source_type, source.source_type)

        # 可用的分類清單
        available_categories = (
            "business（商業管理）、self_help（自我成長）、science（科學新知）、"
            "philosophy（哲學思辨）、history（歷史人文）、psychology（心理學）、"
            "fiction（文學小說）、tech（科技趨勢）、finance（投資理財）、"
            "current_affairs（時事議題）、general（綜合知識）"
        )

        return f"""你是一個說書內容品質評估專家。請評估以下{type_label}是否適合加入說書/書評內容訂閱系統。

來源資訊：
- 名稱：{source.name}
- 類型：{type_label}
- URL：{source.url}
- 語言：{source.language}
{extra_info}

評分標準（請嚴格按照以下維度評分，總分 100）：
1. 內容相關性（40 分）：是否專注於說書、書評、閱讀推薦、知識分享
2. 品質（30 分）：內容深度、製作水準、資訊可信度、專業程度
3. 活躍度（20 分）：近期更新頻率、是否持續在產出內容
4. 受眾契合度（10 分）：語言是否為繁體中文或英文，目標受眾是否為知識型讀者

可選分類（category 欄位請選擇其中之一）：
{available_categories}

請只輸出純 JSON，不要加任何 markdown 標記（不要 ```json）。格式如下：
{{"score": 75, "category": "general", "reason": "繁體中文的推薦理由，1到3句話", "language": "zh", "update_frequency": "每週"}}"""

    def _parse_gemini_evaluation(self, text: str) -> dict:
        """解析 Gemini 回應的 JSON 評估結果

        防禦性解析：
        1. 先嘗試直接 json.loads()
        2. 失敗則用 regex 擷取 JSON 物件再解析
        3. 最終失敗回傳預設值

        Args:
            text: Gemini 回應的原始文字

        Returns:
            包含 score / category / reason / language / update_frequency 的字典
        """
        # 預設值（評估失敗時的 fallback）
        default_result = {
            "score": 0.0,
            "category": "general",
            "reason": "無法解析評估結果",
            "language": "zh",
            "update_frequency": "",
        }

        if not text:
            return default_result

        # 嘗試 1：直接解析整個回應
        try:
            parsed = json.loads(text)
            return self._validate_evaluation_dict(parsed, default_result)
        except json.JSONDecodeError:
            pass

        # 嘗試 2：用 regex 擷取 JSON 物件（處理 Gemini 可能加了說明文字的情況）
        json_pattern = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if json_pattern:
            try:
                parsed = json.loads(json_pattern.group())
                return self._validate_evaluation_dict(parsed, default_result)
            except json.JSONDecodeError:
                pass

        # 嘗試 3：更寬鬆的 regex（允許巢狀結構）
        json_pattern_greedy = re.search(r"\{.*\}", text, re.DOTALL)
        if json_pattern_greedy:
            try:
                parsed = json.loads(json_pattern_greedy.group())
                return self._validate_evaluation_dict(parsed, default_result)
            except json.JSONDecodeError:
                pass

        logger.warning("無法從 Gemini 回應中解析 JSON，回應前 200 字：%s", text[:200])
        return default_result

    def _validate_evaluation_dict(
        self, parsed: dict, default_result: dict
    ) -> dict:
        """驗證並正規化評估結果字典

        確保所有必要欄位存在且型別正確。

        Args:
            parsed: 從 JSON 解析出的字典
            default_result: 解析失敗時的預設值字典

        Returns:
            驗證後的評估結果字典
        """
        result = dict(default_result)

        # score：確保為數值，範圍 0-100
        try:
            score = float(parsed.get("score", 0))
            result["score"] = max(0.0, min(100.0, score))
        except (TypeError, ValueError):
            result["score"] = 0.0

        # category：確保為字串
        category = parsed.get("category", "general")
        result["category"] = str(category) if category else "general"

        # reason：確保為字串
        reason = parsed.get("reason", "")
        result["reason"] = str(reason) if reason else ""

        # language：確保為字串
        language = parsed.get("language", "zh")
        result["language"] = str(language) if language else "zh"

        # update_frequency：確保為字串
        update_frequency = parsed.get("update_frequency", "")
        result["update_frequency"] = str(update_frequency) if update_frequency else ""

        return result

    def _load_tracked_channel_ids(self) -> set[str]:
        """從 channels.json 讀取已追蹤的 channel_id 集合

        Returns:
            已追蹤的 YouTube channel_id 集合；
            檔案不存在或解析失敗時回傳空集合
        """
        if not CHANNELS_FILE.exists():
            logger.debug("channels.json 不存在，回傳空集合")
            return set()

        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                channels = json.load(f)

            # 提取所有有效的 channel_id
            ids: set[str] = set()
            for ch in channels:
                channel_id = ch.get("channel_id", "")
                if channel_id:
                    ids.add(channel_id)

            logger.debug("從 channels.json 載入 %d 個已追蹤頻道 ID", len(ids))
            return ids

        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("載入 channels.json 失敗：%s", exc)
            return set()

    def _run_videos_search(self, query: str, limit: int) -> list[dict]:
        """同步執行 YouTube 影片搜尋

        此方法設計為在 asyncio.to_thread() 中執行，
        因為 youtubesearchpython 是同步阻塞式 API。

        Args:
            query: 搜尋關鍵字
            limit: 最多取得的結果數量

        Returns:
            搜尋結果字典列表；失敗時回傳空列表
        """
        try:
            search = VideosSearch(query, limit=limit)
            result = search.result()
            # result() 回傳 {"result": [...], "nextPage": ...} 結構
            raw_results = result.get("result", [])
            logger.debug(
                "YouTube 搜尋「%s」取得 %d 筆結果", query, len(raw_results)
            )
            return raw_results
        except Exception as exc:
            logger.warning("YouTube 搜尋失敗，關鍵字「%s」：%s", query, exc)
            return []

    def _log_discovery_run(
        self, trigger: str, candidates_found: int, duration: float
    ) -> None:
        """寫入探索執行記錄至 discovery_log.json

        記錄格式：
        [
          {
            "timestamp": "ISO 字串",
            "trigger": "manual" | "scheduled",
            "candidates_found": 數量,
            "duration_seconds": 耗時
          },
          ...
        ]

        Args:
            trigger: 觸發方式（"manual" 或 "scheduled"）
            candidates_found: 本次找到的候選數量
            duration: 執行耗時（秒）
        """
        try:
            # 讀取現有記錄
            existing_logs: list[dict] = []
            if DISCOVERY_LOG_FILE.exists():
                try:
                    with open(DISCOVERY_LOG_FILE, "r", encoding="utf-8") as f:
                        existing_logs = json.load(f)
                    if not isinstance(existing_logs, list):
                        existing_logs = []
                except (json.JSONDecodeError, OSError):
                    existing_logs = []

            # 新增本次記錄
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "trigger": trigger,
                "candidates_found": candidates_found,
                "duration_seconds": round(duration, 2),
            }
            existing_logs.append(log_entry)

            # 只保留最近 100 筆，避免檔案無限增長
            if len(existing_logs) > 100:
                existing_logs = existing_logs[-100:]

            # 寫回檔案
            DISCOVERY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(DISCOVERY_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing_logs, f, ensure_ascii=False, indent=2)

            logger.debug("已寫入探索執行記錄：%s", log_entry)

        except OSError as exc:
            logger.warning("寫入 discovery_log.json 失敗：%s", exc)

    def _is_due_for_discovery(self) -> bool:
        """判斷是否超過設定週期，需要執行自動探索

        從 discovery_log.json 讀取最後一次執行時間，
        若距今超過 DISCOVERY_INTERVAL_DAYS 天（或尚無記錄），
        則回傳 True 表示應該執行探索。

        Returns:
            True 表示需要執行探索；False 表示尚未到期
        """
        if not DISCOVERY_LOG_FILE.exists():
            # 尚無記錄，應該執行探索
            logger.debug("discovery_log.json 不存在，判定需要執行探索")
            return True

        try:
            with open(DISCOVERY_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)

            if not logs or not isinstance(logs, list):
                return True

            # 取最後一筆記錄的時間戳
            last_log = logs[-1]
            last_timestamp_str = last_log.get("timestamp", "")
            if not last_timestamp_str:
                return True

            last_run = datetime.fromisoformat(last_timestamp_str)
            elapsed = datetime.now() - last_run
            due_threshold = timedelta(days=DISCOVERY_INTERVAL_DAYS)

            is_due = elapsed >= due_threshold
            logger.debug(
                "距上次探索 %.1f 天，門檻 %d 天，需要探索：%s",
                elapsed.total_seconds() / 86400,
                DISCOVERY_INTERVAL_DAYS,
                is_due,
            )
            return is_due

        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("讀取 discovery_log.json 失敗，判定需要執行探索：%s", exc)
            return True

    def _add_to_channels_json(self, source: DiscoveredSource) -> None:
        """將 approved 的 YouTube 頻道加入 channels.json

        讀取現有的 channels.json，檢查是否已存在相同 channel_id，
        若不存在則追加新頻道並寫回檔案。

        Args:
            source: 已 approved 的 YouTube 頻道 DiscoveredSource
        """
        channel_id = source.metadata.get("channel_id", "")
        if not channel_id:
            logger.warning("來源「%s」缺少 channel_id，無法寫入 channels.json", source.name)
            return

        # 讀取現有頻道清單
        existing_channels: list[dict] = []
        if CHANNELS_FILE.exists():
            try:
                with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                    existing_channels = json.load(f)
                if not isinstance(existing_channels, list):
                    existing_channels = []
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("讀取 channels.json 失敗，將建立新清單：%s", exc)
                existing_channels = []

        # 檢查是否已存在相同 channel_id
        existing_ids = {ch.get("channel_id", "") for ch in existing_channels}
        if channel_id in existing_ids:
            logger.info("頻道「%s」已在 channels.json 中，略過寫入", source.name)
            return

        # 建立新頻道記錄（與現有 channels.json 格式一致）
        new_channel = {
            "channel_id": channel_id,
            "name": source.name,
            "url": source.url,
            "category": source.category,
            "description": source.reason,
            "language": source.language,
            "added_by": "source_discovery",
            "added_at": datetime.now().isoformat(),
        }
        existing_channels.append(new_channel)

        try:
            CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump(existing_channels, f, ensure_ascii=False, indent=2)
            logger.info("已將頻道「%s」寫入 channels.json", source.name)
        except OSError as exc:
            logger.error("寫入 channels.json 失敗：%s", exc)
