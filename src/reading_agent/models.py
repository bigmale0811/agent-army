# -*- coding: utf-8 -*-
"""讀書 Agent v2 — 資料模型

定義 Book、Video、ReadingReport 與 DiscoveredSource 等核心資料結構。
v2 新增：Book 暢銷書資料模型，Video 擴充字幕與重點整理欄位。
v2.1 新增：DiscoveredSource 來源探索資料模型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Book:
    """暢銷書資料

    Attributes:
        title: 書名
        author: 作者
        language: 書籍語言（"zh" 或 "en"）
        sources: 來源平台列表（博客來 / 誠品 / 金石堂 / Amazon）
        rank: 排行榜最高排名
        isbn: ISBN 編號
        cover_url: 封面圖 URL
        category: 書籍分類
        collected_at: 蒐集時間
    """
    title: str
    author: str = ""
    language: str = "zh"
    sources: list[str] = field(default_factory=list)
    rank: int = 0
    isbn: str = ""
    cover_url: str = ""
    category: str = ""
    collected_at: str = ""

    def __post_init__(self):
        if not self.collected_at:
            self.collected_at = datetime.now().isoformat()

    def __eq__(self, other):
        """以書名判斷是否為同一本書（忽略大小寫與空格）"""
        if not isinstance(other, Book):
            return False
        return self._normalize(self.title) == self._normalize(other.title)

    def __hash__(self):
        return hash(self._normalize(self.title))

    @staticmethod
    def _normalize(title: str) -> str:
        """正規化書名：去除空格、轉小寫"""
        return title.strip().lower().replace(" ", "").replace("　", "")

    def to_dict(self) -> dict:
        """轉換為字典（用於 JSON 序列化）"""
        return {
            "title": self.title,
            "author": self.author,
            "language": self.language,
            "sources": self.sources,
            "rank": self.rank,
            "isbn": self.isbn,
            "cover_url": self.cover_url,
            "category": self.category,
            "collected_at": self.collected_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Book":
        """從字典建立 Book 物件"""
        return cls(
            title=data.get("title", ""),
            author=data.get("author", ""),
            language=data.get("language", "zh"),
            sources=data.get("sources", []),
            rank=data.get("rank", 0),
            isbn=data.get("isbn", ""),
            cover_url=data.get("cover_url", ""),
            category=data.get("category", ""),
            collected_at=data.get("collected_at", ""),
        )


@dataclass
class Video:
    """YouTube 影片資料

    Attributes:
        title: 影片標題
        url: 影片連結
        channel_name: 頻道名稱
        channel_id: YouTube 頻道 ID
        published_at: 發布日期（ISO 格式字串）
        description: 影片描述（前 500 字）
        category: 頻道分類
        video_id: YouTube 影片 ID
        thumbnail: 縮圖 URL
        collected_at: 蒐集時間（ISO 格式字串）
    """
    title: str
    url: str
    channel_name: str
    channel_id: str
    published_at: str
    description: str = ""
    category: str = "general"
    video_id: str = ""
    thumbnail: str = ""
    collected_at: str = ""
    # === v2 新增欄位 ===
    duration_seconds: int = 0         # 影片長度（秒）
    transcript: str = ""              # 完整字幕/逐字稿
    key_points_original: str = ""     # 原語言重點整理
    key_points_zh: str = ""           # 中文重點整理
    language: str = "zh"              # 影片語言（zh / en）
    book_title: str = ""              # 關聯的書名

    def __post_init__(self):
        if not self.collected_at:
            self.collected_at = datetime.now().isoformat()

    def __eq__(self, other):
        """以影片 URL 判斷是否為同一部影片"""
        if not isinstance(other, Video):
            return False
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def to_dict(self) -> dict:
        """轉換為字典（用於 JSON 序列化）"""
        return {
            "title": self.title,
            "url": self.url,
            "channel_name": self.channel_name,
            "channel_id": self.channel_id,
            "published_at": self.published_at,
            "description": self.description[:500],
            "category": self.category,
            "video_id": self.video_id,
            "thumbnail": self.thumbnail,
            "collected_at": self.collected_at,
            "duration_seconds": self.duration_seconds,
            "transcript": self.transcript[:5000] if self.transcript else "",
            "key_points_original": self.key_points_original,
            "key_points_zh": self.key_points_zh,
            "language": self.language,
            "book_title": self.book_title,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Video":
        """從字典建立 Video 物件"""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            channel_name=data.get("channel_name", ""),
            channel_id=data.get("channel_id", ""),
            published_at=data.get("published_at", ""),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            video_id=data.get("video_id", ""),
            thumbnail=data.get("thumbnail", ""),
            collected_at=data.get("collected_at", ""),
            duration_seconds=data.get("duration_seconds", 0),
            transcript=data.get("transcript", ""),
            key_points_original=data.get("key_points_original", ""),
            key_points_zh=data.get("key_points_zh", ""),
            language=data.get("language", "zh"),
            book_title=data.get("book_title", ""),
        )


@dataclass
class ReadingReport:
    """讀書摘要報告

    Attributes:
        period_start: 報告起始日期
        period_end: 報告結束日期
        videos: 蒐集到的影片列表
        mode: 執行模式（weekly / initial）
        generated_at: 報告產生時間
    """
    period_start: str
    period_end: str
    videos: list[Video] = field(default_factory=list)
    mode: str = "weekly"
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()

    @property
    def total_count(self) -> int:
        """影片總數"""
        return len(self.videos)

    @property
    def channel_counts(self) -> dict[str, int]:
        """各頻道影片數量統計"""
        counts: dict[str, int] = {}
        for v in self.videos:
            counts[v.channel_name] = counts.get(v.channel_name, 0) + 1
        return counts

    @property
    def category_counts(self) -> dict[str, int]:
        """各分類影片數量統計"""
        counts: dict[str, int] = {}
        for v in self.videos:
            counts[v.category] = counts.get(v.category, 0) + 1
        return counts

    def get_videos_by_channel(self, channel_name: str) -> list[Video]:
        """取得指定頻道的影片"""
        return [v for v in self.videos if v.channel_name == channel_name]

    def get_videos_by_category(self, category: str) -> list[Video]:
        """取得指定分類的影片"""
        return [v for v in self.videos if v.category == category]

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "total_count": self.total_count,
            "channel_counts": self.channel_counts,
            "category_counts": self.category_counts,
            "videos": [v.to_dict() for v in self.videos],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReadingReport":
        """從字典建立 ReadingReport 物件"""
        videos = [Video.from_dict(v) for v in data.get("videos", [])]
        return cls(
            period_start=data.get("period_start", ""),
            period_end=data.get("period_end", ""),
            videos=videos,
            mode=data.get("mode", "weekly"),
            generated_at=data.get("generated_at", ""),
        )


# =========================================================
# Source Discovery 資料模型
# =========================================================

@dataclass
class DiscoveredSource:
    """已發現的推薦來源（頻道或網站）

    由 Source Discovery 模組自動探索產生，
    使用者透過 Telegram 確認（approved）或拒絕（rejected）。

    Attributes:
        name: 來源名稱（頻道名或網站名）
        url: 主要 URL
        source_type: 來源類型（"youtube_channel" / "website" / "rss_feed"）
        category: 對應 BOOK_CATEGORIES 的分類鍵值
        language: 內容語言（"zh" / "en" / "both"）
        score: Gemini 評分（0-100）
        reason: 推薦理由（Gemini 輸出的繁體中文說明）
        status: 審核狀態（"pending" / "approved" / "rejected"）
        discovered_at: 發現時間（ISO 格式字串）
        metadata: 額外資訊（頻道 ID、近期影片標題、更新頻率等）
    """
    name: str
    url: str
    source_type: str = "youtube_channel"
    category: str = "general"
    language: str = "zh"
    score: float = 0.0
    reason: str = ""
    status: str = "pending"
    discovered_at: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.discovered_at:
            self.discovered_at = datetime.now().isoformat()

    def __eq__(self, other):
        """以 URL 判斷是否為同一個來源"""
        if not isinstance(other, DiscoveredSource):
            return False
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def to_dict(self) -> dict:
        """轉換為字典（用於 JSON 序列化）"""
        return {
            "name": self.name,
            "url": self.url,
            "source_type": self.source_type,
            "category": self.category,
            "language": self.language,
            "score": self.score,
            "reason": self.reason,
            "status": self.status,
            "discovered_at": self.discovered_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveredSource":
        """從字典建立 DiscoveredSource 物件"""
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            source_type=data.get("source_type", "youtube_channel"),
            category=data.get("category", "general"),
            language=data.get("language", "zh"),
            score=data.get("score", 0.0),
            reason=data.get("reason", ""),
            status=data.get("status", "pending"),
            discovered_at=data.get("discovered_at", ""),
            metadata=data.get("metadata", {}),
        )
