# -*- coding: utf-8 -*-
"""讀書 Agent — 報告產生器

將蒐集到的影片和 Gemini 摘要編排成結構化的繁體中文報告，
格式化為適合 Telegram 傳送的訊息（支援自動分段）。

v2 新增：generate_v2() 方法，以書籍為單位產生暢銷書說書整理報告，
支援中英文雙語顯示、自訂頻道追蹤區段，每本書獨立分段以符合 Telegram 限制。
"""

import logging
from datetime import datetime
from typing import Optional

from .config import AI_CATEGORIES, BOOK_CATEGORIES, TELEGRAM_MAX_LENGTH
from .models import Book, Video, ReadingReport

logger = logging.getLogger(__name__)


class ReportGenerator:
    """讀書摘要報告產生器

    將 ReadingReport 物件和 Gemini 摘要轉換為格式化的 Telegram 訊息。
    支援兩種模式：
    - 智慧摘要模式（使用 Gemini 書籍識別＋重點整理）
    - 原文列表模式（降級方案）
    若內容超過 Telegram 4096 字元上限，自動分段。

    v2 新增：generate_v2() 以書籍為主體產生暢銷書說書整理報告，
    每本書獨立為一個訊息段落，英文書同時顯示原文與中文翻譯。
    """

    def generate(
        self,
        report: ReadingReport,
        summary: Optional[str] = None,
    ) -> list[str]:
        """產生完整報告文字

        Args:
            report: 蒐集報告物件
            summary: Gemini 產生的智慧摘要（可選）

        Returns:
            分段後的訊息文字列表（每段 <= 4096 字元）
        """
        if not report.videos:
            return [self._generate_empty_report(report)]

        # 根據有無 Gemini 摘要選擇報告格式
        if summary:
            full_text = self._build_smart_report(report, summary)
        else:
            full_text = self._build_basic_report(report)

        # 分段處理
        segments = self._split_message(full_text)
        logger.info("報告共 %d 字，分成 %d 段", len(full_text), len(segments))

        return segments

    def _build_smart_report(self, report: ReadingReport, summary: str) -> str:
        """建構 Gemini 智慧摘要版報告"""
        lines: list[str] = []

        # === 報告標題 ===
        lines.append("📚 本週讀書摘要")
        lines.append(f"📅 {report.period_start} ~ {report.period_end}")
        lines.append("━" * 18)
        lines.append("")

        # === Gemini 智慧摘要 ===
        lines.append(summary)
        lines.append("")

        # === 報告尾部 ===
        lines.append("━" * 18)
        lines.append(f"📊 本週追蹤 {len(set(v.channel_name for v in report.videos))} 個頻道")
        lines.append(f"📺 共 {report.total_count} 部新影片")

        # 頻道統計
        stat_parts = []
        for ch_name, count in sorted(
            report.channel_counts.items(), key=lambda x: -x[1]
        ):
            stat_parts.append(f"{ch_name}:{count}")
        if stat_parts:
            lines.append(f"📈 {' | '.join(stat_parts[:6])}")

        lines.append(f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        lines.append("🤖 Agent Army ｜ 讀書 Agent + Gemini 摘要")

        return "\n".join(lines)

    def _build_basic_report(self, report: ReadingReport) -> str:
        """建構基本報告（無 Gemini 摘要時）"""
        lines: list[str] = []

        # === 報告標題 ===
        lines.append("📚 本週讀書摘要")
        lines.append(f"📅 {report.period_start} ~ {report.period_end}")
        lines.append("━" * 18)
        lines.append("")

        # === 按頻道列出影片 ===
        by_channel: dict[str, list[Video]] = {}
        for v in report.videos:
            if v.channel_name not in by_channel:
                by_channel[v.channel_name] = []
            by_channel[v.channel_name].append(v)

        for channel_name, videos in by_channel.items():
            # 取得該頻道的分類 icon
            cat = videos[0].category if videos else "general"
            cat_info = BOOK_CATEGORIES.get(cat, {"icon": "📺", "name": "其他"})
            icon = cat_info["icon"]

            lines.append(f"{icon} {channel_name}（{len(videos)} 部）")
            lines.append("")

            for i, video in enumerate(videos[:10], 1):
                lines.append(f"{i}. {video.title}")
                lines.append(f"   🔗 {video.url}")
                date_str = video.published_at[:10] if video.published_at else ""
                lines.append(f"   📅 {date_str}")

                # 描述摘要（如果有）
                if video.description:
                    desc = video.description[:80]
                    if len(video.description) > 80:
                        desc += "..."
                    lines.append(f"   {desc}")
                lines.append("")

            if len(videos) > 10:
                lines.append(f"   ...還有 {len(videos) - 10} 部")
                lines.append("")

        # === 報告尾部 ===
        lines.append("━" * 18)
        lines.append(f"📺 共 {report.total_count} 部新影片")
        lines.append(f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M')}")
        lines.append("🤖 Agent Army ｜ 讀書 Agent")

        return "\n".join(lines)

    def _generate_empty_report(self, report: ReadingReport) -> str:
        """產生無資料時的報告"""
        lines = [
            "📚 本週讀書摘要",
            f"📅 {report.period_start} ~ {report.period_end}",
            "━" * 18,
            "",
            "📭 本週追蹤的頻道未有新影片",
            "",
            "可能原因：",
            "• 頻道本週未更新",
            "• YouTube RSS 存取問題",
            "• 頻道 ID 設定有誤",
            "",
            "━" * 18,
            "🤖 Agent Army ｜ 讀書 Agent",
        ]
        return "\n".join(lines)

    # =========================================================
    # v2 方法：以暢銷書為單位產生說書整理報告
    # =========================================================

    def generate_v2(
        self,
        books: list[Book],
        book_videos: dict[str, list[Video]],
        custom_videos: list[Video] | None = None,
    ) -> list[str]:
        """產生 v2 暢銷書說書整理報告

        每本書獨立產生一個訊息段落，以便控制 Telegram 4096 字元上限。
        若單本書的段落仍超過限制，則再透過 _split_message 二次分段。

        Args:
            books: 暢銷書列表（已依排名或重要性排序）
            book_videos: 書名 -> 說書影片列表的對應字典
            custom_videos: 自訂頻道追蹤影片（非暢銷書對應，額外附加）

        Returns:
            分段後的訊息文字列表（每段 <= 4096 字元）
        """
        segments: list[str] = []

        # 取得日期範圍，優先從影片中推算，否則以當週為預設
        period_start, period_end = self._infer_period(book_videos, custom_videos)

        # 報告標題區塊（獨立為第一段）
        header_lines = [
            "📚 本週暢銷書說書整理",
            f"📅 {period_start} ~ {period_end}",
            "━" * 18,
        ]
        segments.append("\n".join(header_lines))

        # 逐本書產生段落
        for idx, book in enumerate(books, 1):
            videos = book_videos.get(book.title, [])
            # 以書名為鍵找不到時，嘗試正規化比對
            if not videos:
                for key, vlist in book_videos.items():
                    if Book._normalize(key) == Book._normalize(book.title):
                        videos = vlist
                        break

            book_text = self._build_v2_book_segment(
                book=book,
                videos=videos,
                index=idx,
            )
            # 若單本書段落超過上限則再分段，否則直接加入
            if len(book_text) > TELEGRAM_MAX_LENGTH:
                segments.extend(self._split_message(book_text))
            else:
                segments.append(book_text)

        # 自訂頻道追蹤區段（若有）
        if custom_videos:
            custom_text = self._build_v2_custom_section(custom_videos)
            if len(custom_text) > TELEGRAM_MAX_LENGTH:
                segments.extend(self._split_message(custom_text))
            else:
                segments.append(custom_text)

        # 頁尾段落
        footer_lines = [
            "━" * 18,
            f"📊 本週共整理 {len(books)} 本暢銷書",
            "🤖 Agent Army ｜ 讀書 Agent v2",
        ]
        segments.append("\n".join(footer_lines))

        logger.info(
            "v2 報告產生完成：%d 本書，%d 段訊息",
            len(books),
            len(segments),
        )
        return segments

    def _build_v2_book_segment(
        self,
        book: Book,
        videos: list[Video],
        index: int,
    ) -> str:
        """建構單本書的 v2 報告段落

        英文書（language == "en"）會同時輸出原文重點與中文翻譯；
        中文書只輸出 key_points_zh。

        Args:
            book: 書籍資料物件
            videos: 該書對應的說書影片列表
            index: 書在本週排行中的序號（從 1 開始）

        Returns:
            格式化後的單本書段落文字
        """
        lines: list[str] = []

        # --- 書籍標題列 ---
        lines.append(f"📖 第 {index} 本：《{book.title}》")

        # --- 作者（有值才顯示）---
        if book.author:
            lines.append(f"👤 作者：{book.author}")

        # --- 來源平台（sources 清單格式化）---
        if book.sources:
            # 將來源列表合併為「博客來 #3 / Amazon #7」形式
            lines.append(f"🌐 來源：{' / '.join(book.sources)}")

        # --- 第一部影片資訊（取第一支作為代表）---
        if videos:
            primary = videos[0]
            lines.append(f"📺 影片：{primary.channel_name} - {primary.title}")
            if primary.duration_seconds > 0:
                lines.append(f"⏱️ 片長：{self._format_duration(primary.duration_seconds)}")

        lines.append("")

        # --- 重點整理區塊 ---
        lines.append("【重點整理】")

        # 英文書：同時顯示原文重點與中文翻譯
        if book.language == "en":
            # 取第一部影片的重點（若無則跳過原文區塊）
            primary_video = videos[0] if videos else None
            original_points = (
                primary_video.key_points_original if primary_video else ""
            )
            zh_points = primary_video.key_points_zh if primary_video else ""

            if original_points:
                lines.append("")
                lines.append("🌐 English Key Points:")
                lines.append(original_points)

            if zh_points:
                lines.append("")
                lines.append("🇹🇼 中文翻譯：")
                lines.append(zh_points)
            elif not original_points:
                # 兩者皆空時給占位符，避免區塊空白
                lines.append("（尚無重點整理）")
        else:
            # 中文書：只顯示中文重點整理
            zh_points = videos[0].key_points_zh if videos else ""
            if zh_points:
                lines.append(zh_points)
            else:
                lines.append("（尚無重點整理）")

        # --- 若有多部影片，列出其餘影片連結 ---
        if len(videos) > 1:
            lines.append("")
            lines.append("📋 其他相關影片：")
            for extra in videos[1:]:
                duration_str = (
                    f"（{self._format_duration(extra.duration_seconds)}）"
                    if extra.duration_seconds > 0
                    else ""
                )
                lines.append(
                    f"  • {extra.channel_name} - {extra.title}{duration_str}"
                )

        lines.append("")
        lines.append("━" * 18)

        return "\n".join(lines)

    def _build_v2_custom_section(self, custom_videos: list[Video]) -> str:
        """建構自訂頻道追蹤區段

        非暢銷書對應的頻道影片統一收錄於此區段，
        格式與書籍段落類似，但以影片為主體。

        Args:
            custom_videos: 自訂頻道追蹤影片列表

        Returns:
            格式化後的自訂頻道段落文字
        """
        lines: list[str] = []

        lines.append("━" * 18)
        lines.append("📺 自訂頻道追蹤")
        lines.append("━" * 18)
        lines.append("")

        for video in custom_videos:
            lines.append(f"📺 {video.channel_name} - {video.title}")
            if video.duration_seconds > 0:
                lines.append(f"⏱️ 片長：{self._format_duration(video.duration_seconds)}")
            if video.url:
                lines.append(f"🔗 {video.url}")

            lines.append("")
            lines.append("【重點整理】")

            # 英文影片：雙語輸出
            if video.language == "en":
                if video.key_points_original:
                    lines.append("")
                    lines.append("🌐 English Key Points:")
                    lines.append(video.key_points_original)
                if video.key_points_zh:
                    lines.append("")
                    lines.append("🇹🇼 中文翻譯：")
                    lines.append(video.key_points_zh)
                if not video.key_points_original and not video.key_points_zh:
                    lines.append("（尚無重點整理）")
            else:
                # 中文影片：只顯示中文重點整理
                if video.key_points_zh:
                    lines.append(video.key_points_zh)
                else:
                    lines.append("（尚無重點整理）")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """將秒數轉換為「MM:SS」或「H:MM:SS」格式

        Args:
            seconds: 影片長度（秒）

        Returns:
            格式化後的時間字串，例如 "18:32" 或 "1:03:45"
        """
        if seconds <= 0:
            return "0:00"

        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)

        if hours > 0:
            # 超過一小時：H:MM:SS
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            # 不足一小時：MM:SS（分鐘不補零）
            return f"{minutes}:{secs:02d}"

    @staticmethod
    def _infer_period(
        book_videos: dict[str, list[Video]],
        custom_videos: list[Video] | None,
    ) -> tuple[str, str]:
        """從影片的 published_at 推算報告的起迄日期

        若無法從影片推算，則回傳預設的佔位字串。

        Args:
            book_videos: 書名 -> 影片列表的對應字典
            custom_videos: 自訂頻道影片列表（可為 None）

        Returns:
            (period_start, period_end) 日期字串元組（YYYY-MM-DD 格式）
        """
        # 收集所有影片的發布日期
        all_videos: list[Video] = []
        for vlist in book_videos.values():
            all_videos.extend(vlist)
        if custom_videos:
            all_videos.extend(custom_videos)

        dates: list[str] = []
        for v in all_videos:
            # published_at 格式為 ISO 字串，取前 10 字元即為 YYYY-MM-DD
            if v.published_at and len(v.published_at) >= 10:
                dates.append(v.published_at[:10])

        if dates:
            return min(dates), max(dates)

        # 無法推算時回傳佔位字串
        return "----/--/--", "----/--/--"

    # =========================================================
    # AI Weekly 方法：以 AI 資訊分類產生報告
    # =========================================================

    def generate_ai_weekly(self, videos: list[Video]) -> list[str]:
        """產生 AI Weekly 資訊整理報告

        依 AI 分類（研究、新聞、工具、應用、技術等）分組顯示，
        每部影片含頻道名、片長、重點整理。英文影片同時顯示原文與中文翻譯。

        Args:
            videos: 已完成分析的 AI 影片列表

        Returns:
            分段後的訊息文字列表（每段 <= 4096 字元）
        """
        segments: list[str] = []

        # 報告日期範圍
        dates = [
            v.published_at[:10]
            for v in videos
            if v.published_at and len(v.published_at) >= 10
        ]
        period_start = min(dates) if dates else "----/--/--"
        period_end = max(dates) if dates else "----/--/--"

        # 報告標題
        header_lines = [
            "🤖 本週 AI 資訊整理",
            f"📅 {period_start} ~ {period_end}",
            "━" * 18,
        ]
        segments.append("\n".join(header_lines))

        # 依分類分組
        categorized: dict[str, list[Video]] = {}
        for video in videos:
            cat = video.category if video.category in AI_CATEGORIES else "ai_general"
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(video)

        # 按分類順序輸出
        global_idx = 0
        for cat_key, cat_info in AI_CATEGORIES.items():
            cat_videos = categorized.get(cat_key, [])
            if not cat_videos:
                continue

            cat_text = self._build_ai_category_segment(
                cat_info=cat_info,
                videos=cat_videos,
                start_index=global_idx + 1,
            )
            global_idx += len(cat_videos)

            if len(cat_text) > TELEGRAM_MAX_LENGTH:
                segments.extend(self._split_message(cat_text))
            else:
                segments.append(cat_text)

        # 頁尾
        footer_lines = [
            "━" * 18,
            f"📊 本週共整理 {len(videos)} 則 AI 資訊",
            "🤖 Agent Army ｜ AI Weekly",
        ]
        segments.append("\n".join(footer_lines))

        logger.info(
            "AI Weekly 報告產生完成：%d 部影片，%d 段訊息",
            len(videos),
            len(segments),
        )
        return segments

    def _build_ai_category_segment(
        self,
        cat_info: dict,
        videos: list[Video],
        start_index: int,
    ) -> str:
        """建構單一 AI 分類的報告段落

        Args:
            cat_info: 分類資訊字典 {"name": ..., "icon": ...}
            videos: 該分類下的影片列表
            start_index: 全域編號起始值

        Returns:
            格式化後的分類段落文字
        """
        lines: list[str] = []

        lines.append(f"{cat_info['icon']} {cat_info['name']}")
        lines.append("")

        for i, video in enumerate(videos):
            idx = start_index + i
            lines.append(f"{idx}. 《{video.title}》— {video.channel_name}")
            if video.duration_seconds > 0:
                lines.append(f"   ⏱️ {self._format_duration(video.duration_seconds)}")
            if video.url:
                lines.append(f"   🔗 {video.url}")

            lines.append("")
            lines.append("   【重點整理】")

            # 英文影片：雙語輸出
            if video.language == "en":
                if video.key_points_original:
                    lines.append("")
                    lines.append("   🌐 English Key Points:")
                    lines.append(video.key_points_original)
                if video.key_points_zh:
                    lines.append("")
                    lines.append("   🇹🇼 中文翻譯：")
                    lines.append(video.key_points_zh)
                if not video.key_points_original and not video.key_points_zh:
                    lines.append("   （尚無重點整理）")
            else:
                # 中文影片
                if video.key_points_zh:
                    lines.append(video.key_points_zh)
                else:
                    lines.append("   （尚無重點整理）")

            lines.append("")

        return "\n".join(lines)

    def _split_message(
        self, text: str, max_length: int = TELEGRAM_MAX_LENGTH,
    ) -> list[str]:
        """將長文字分段，確保每段不超過 Telegram 限制

        分段策略：
        1. 優先在空行處分段
        2. 其次在換行符處分段
        3. 最差情況在 max_length 處硬切
        """
        if len(text) <= max_length:
            return [text]

        segments: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                segments.append(remaining)
                break

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
