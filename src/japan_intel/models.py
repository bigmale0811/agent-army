# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — 資料模型

定義文章（Article）和報告（Report）的資料結構，
提供序列化/反序列化方法以支援 JSON 儲存。
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional


@dataclass
class Article:
    """單篇蒐集到的文章資料

    Attributes:
        title: 文章標題
        url: 原文連結（作為唯一識別）
        source: 來源名稱（如 "GGRAsia"、"Google News"）
        published_at: 發佈日期（ISO 格式字串）
        summary: 摘要文字（前 300 字或 meta description）
        category: 分類代碼（ir_casino / online_gambling / pachinko / gaming / regulation / other）
        language: 語言代碼（"ja" / "en"）
        collected_at: 蒐集時間（ISO 格式字串）
    """
    title: str
    url: str
    source: str
    published_at: str
    summary: str = ""
    category: str = "other"
    language: str = "en"
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """序列化為字典，供 JSON 儲存"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        """從字典反序列化建立 Article 實例"""
        # 只取 Article 有定義的欄位，忽略多餘的欄位
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def __eq__(self, other: object) -> bool:
        """以 URL 作為唯一識別進行比較"""
        if not isinstance(other, Article):
            return NotImplemented
        return self.url == other.url

    def __hash__(self) -> int:
        """以 URL 作為 hash 基礎，支援 set 去重"""
        return hash(self.url)


@dataclass
class Report:
    """蒐集報告資料結構

    Attributes:
        period_start: 報告期間起始日（ISO 格式字串）
        period_end: 報告期間結束日（ISO 格式字串）
        articles: 該期間蒐集到的所有文章
        generated_at: 報告產生時間（ISO 格式字串）
        mode: 蒐集模式（"initial" / "weekly"）
        total_count: 文章總數
        category_counts: 各分類文章數量
    """
    period_start: str
    period_end: str
    articles: list[Article] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    mode: str = "weekly"
    total_count: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """初始化後自動計算統計數據"""
        self._update_stats()

    def _update_stats(self):
        """更新文章總數與各分類計數"""
        self.total_count = len(self.articles)
        self.category_counts = {}
        for article in self.articles:
            cat = article.category
            self.category_counts[cat] = self.category_counts.get(cat, 0) + 1

    def add_articles(self, articles: list[Article]):
        """批次新增文章並更新統計"""
        self.articles.extend(articles)
        self._update_stats()

    def get_articles_by_category(self, category: str) -> list[Article]:
        """取得特定分類的所有文章"""
        return [a for a in self.articles if a.category == category]

    def to_dict(self) -> dict:
        """序列化為字典，供 JSON 儲存"""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "generated_at": self.generated_at,
            "mode": self.mode,
            "total_count": self.total_count,
            "category_counts": self.category_counts,
            "articles": [a.to_dict() for a in self.articles],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Report":
        """從字典反序列化建立 Report 實例"""
        articles = [Article.from_dict(a) for a in data.get("articles", [])]
        return cls(
            period_start=data["period_start"],
            period_end=data["period_end"],
            articles=articles,
            generated_at=data.get("generated_at", datetime.now().isoformat()),
            mode=data.get("mode", "weekly"),
        )
