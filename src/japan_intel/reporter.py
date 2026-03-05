# -*- coding: utf-8 -*-
"""日本博弈資訊蒐集 Agent — 報告產生器

將蒐集到的文章編排成結構化的繁體中文報告，
格式化為適合 Telegram 傳送的訊息（支援自動分段）。
"""

import logging
from datetime import datetime
from typing import Optional

from .config import CATEGORIES, TELEGRAM_MAX_LENGTH
from .models import Article, Report

logger = logging.getLogger(__name__)


class ReportGenerator:
    """繁體中文報告產生器

    將 Report 物件轉換為格式化的 Telegram 訊息文字。
    支援兩種模式：
    - 智慧摘要模式（使用 Gemini 翻譯＋重點整理）
    - 原文列表模式（降級方案）
    若內容超過 Telegram 4096 字元上限，自動分段。
    """

    def generate(
        self,
        report: Report,
        summaries: Optional[dict[str, str]] = None,
    ) -> list[str]:
        """產生完整報告文字

        Args:
            report: 蒐集報告物件
            summaries: Gemini 產生的各分類摘要（可選）

        Returns:
            分段後的訊息文字列表（每段 <= 4096 字元）
        """
        if not report.articles:
            return [self._generate_empty_report(report)]

        # 根據有無 Gemini 摘要選擇報告格式
        if summaries:
            full_text = self._build_smart_report(report, summaries)
        else:
            full_text = self._build_report_text(report)

        # 分段處理
        segments = self._split_message(full_text)
        logger.info("報告共 %d 字，分成 %d 段", len(full_text), len(segments))

        return segments

    def generate_monthly_reports(self, report: Report) -> list[list[str]]:
        """將大型報告（initial 模式）按月份分批

        用於年度蒐集，避免一次發送過多訊息。

        Args:
            report: 年度蒐集報告

        Returns:
            按月分批的訊息列表，每批為一組分段訊息
        """
        # 按月份分組文章
        monthly: dict[str, list[Article]] = {}
        for article in report.articles:
            # 從 published_at 取出年月
            month_key = article.published_at[:7] if len(article.published_at) >= 7 else "unknown"
            if month_key not in monthly:
                monthly[month_key] = []
            monthly[month_key].append(article)

        batches: list[list[str]] = []
        for month_key in sorted(monthly.keys(), reverse=True):
            articles = monthly[month_key]
            month_report = Report(
                period_start=f"{month_key}-01",
                period_end=f"{month_key}-28",
                articles=articles,
                mode="monthly",
            )
            segments = self.generate(month_report)
            batches.append(segments)

        return batches

    def _build_smart_report(self, report: Report, summaries: dict[str, str]) -> str:
        """建構 Gemini 智慧摘要版報告（翻譯＋重點整理）"""
        lines: list[str] = []

        # === 報告標題 ===
        if report.mode == "initial":
            title = "📊 日本博弈產業年度總覽"
        elif report.mode == "monthly":
            title = "📊 日本博弈產業月報"
        else:
            title = "📊 日本博弈產業週報"

        lines.append(title)
        lines.append(f"📅 {report.period_start} ~ {report.period_end}")
        lines.append("━" * 18)
        lines.append("")

        # === 各分類 Gemini 摘要 ===
        for cat_code, cat_info in CATEGORIES.items():
            if cat_code not in summaries:
                continue

            icon = cat_info["icon"]
            name = cat_info["name"]
            count = len(report.get_articles_by_category(cat_code))
            lines.append(f"{icon} {name}（{count} 則）")
            lines.append("")
            lines.append(summaries[cat_code])
            lines.append("")

        # === 報告尾部 ===
        lines.append("━" * 18)
        lines.append(f"📈 共蒐集 {report.total_count} 則資訊")

        stat_parts = []
        for cat_code, count in sorted(report.category_counts.items(), key=lambda x: -x[1]):
            if count > 0 and cat_code in CATEGORIES:
                icon = CATEGORIES[cat_code]["icon"]
                stat_parts.append(f"{icon}{count}")
        if stat_parts:
            lines.append(f"📊 {' '.join(stat_parts)}")

        lines.append(f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        lines.append("🤖 Agent Army ｜ Gemini 翻譯摘要")

        return "\n".join(lines)

    def _build_report_text(self, report: Report) -> str:
        """建構報告的完整文字內容"""
        lines: list[str] = []

        # === 報告標題 ===
        if report.mode == "initial":
            title = "📊 日本博弈產業年度總覽"
        elif report.mode == "monthly":
            title = "📊 日本博弈產業月報"
        else:
            title = "📊 日本博弈產業週報"

        lines.append(title)
        lines.append(f"📅 {report.period_start} ~ {report.period_end}")
        lines.append("━" * 18)
        lines.append("")

        # === 各分類文章 ===
        for cat_code, cat_info in CATEGORIES.items():
            articles = report.get_articles_by_category(cat_code)
            if not articles:
                continue

            icon = cat_info["icon"]
            name = cat_info["name"]
            count = len(articles)
            lines.append(f"{icon} {name}（{count} 則）")
            lines.append("")

            for i, article in enumerate(articles[:15], 1):
                # 標題（帶連結）
                lines.append(f"{i}. {article.title}")
                lines.append(f"   🔗 {article.url}")

                # 來源與日期
                meta_parts = []
                if article.source:
                    meta_parts.append(f"📰 {article.source}")
                if article.published_at:
                    # 只取日期部分
                    date_str = article.published_at[:10]
                    meta_parts.append(f"📅 {date_str}")
                if meta_parts:
                    lines.append(f"   {' | '.join(meta_parts)}")

                # 摘要（如果有的話，限制長度）
                if article.summary:
                    summary = article.summary[:100]
                    if len(article.summary) > 100:
                        summary += "..."
                    lines.append(f"   {summary}")

                lines.append("")

            # 如果文章超過 15 篇，顯示省略提示
            if count > 15:
                lines.append(f"   ...還有 {count - 15} 則，詳見完整報告")
                lines.append("")

        # === 報告尾部 ===
        lines.append("━" * 18)
        lines.append(f"📈 共蒐集 {report.total_count} 則資訊")

        # 分類統計
        stat_parts = []
        for cat_code, count in sorted(report.category_counts.items(), key=lambda x: -x[1]):
            if count > 0 and cat_code in CATEGORIES:
                icon = CATEGORIES[cat_code]["icon"]
                stat_parts.append(f"{icon}{count}")
        if stat_parts:
            lines.append(f"📊 {' '.join(stat_parts)}")

        lines.append(f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        lines.append("🤖 Agent Army 自動產生")

        return "\n".join(lines)

    def _generate_empty_report(self, report: Report) -> str:
        """產生無資料時的報告"""
        if report.mode == "initial":
            title = "📊 日本博弈產業年度總覽"
        else:
            title = "📊 日本博弈產業週報"
        lines = [
            title,
            f"📅 {report.period_start} ~ {report.period_end}",
            "━" * 18,
            "",
            "📭 本期未蒐集到相關資訊",
            "",
            "可能原因：",
            "• 來源網站結構變更",
            "• 網路連線問題",
            "• 該期間無相關新聞",
            "",
            "━" * 18,
            "🤖 Agent Army 自動產生",
        ]
        return "\n".join(lines)

    def _split_message(self, text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
        """將長文字分段，確保每段不超過 Telegram 限制

        分段策略：
        1. 優先在空行處分段
        2. 其次在換行符處分段
        3. 最差情況在 max_length 處硬切

        Args:
            text: 完整報告文字
            max_length: 單段最大字元數

        Returns:
            分段後的文字列表
        """
        if len(text) <= max_length:
            return [text]

        segments: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                segments.append(remaining)
                break

            # 在 max_length 範圍內尋找最佳分段點
            chunk = remaining[:max_length]

            # 優先找空行
            split_pos = chunk.rfind("\n\n")
            if split_pos == -1 or split_pos < max_length // 2:
                # 其次找換行符
                split_pos = chunk.rfind("\n")
            if split_pos == -1 or split_pos < max_length // 2:
                # 最差情況：硬切
                split_pos = max_length

            segments.append(remaining[:split_pos].rstrip())
            remaining = remaining[split_pos:].lstrip()

        return segments
