# -*- coding: utf-8 -*-
"""Memory Manager — 跨對話記憶管理

核心檔案：
    - active_context.md: 當前狀態，每次新對話必讀
    - sessions/YYYY-MM-DD_HHMMSS.md: 每次對話的摘要存檔
    - decisions.md: 重大決策累積紀錄

使用方式：
    from src.memory import MemoryManager

    mm = MemoryManager()

    # 讀取當前記憶（新對話開始時）
    context = mm.recall()

    # 儲存當前狀態（對話結束或重要節點）
    mm.save_context(
        in_progress=["Singer Agent 測試中"],
        completed=["修正 SadTalker 合成"],
        decisions=["使用 SadTalker v3 作為預設"],
        next_steps=["確認影片品質"],
    )

    # 歸檔對話摘要
    mm.archive_session(summary="完成 Singer Agent 功能修正與測試")
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 記憶系統的根目錄
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = _PROJECT_ROOT / "data" / "memory"
SESSIONS_DIR = MEMORY_DIR / "sessions"
ACTIVE_CONTEXT_FILE = MEMORY_DIR / "active_context.md"
DECISIONS_FILE = MEMORY_DIR / "decisions.md"

# 確保目錄存在
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class MemoryManager:
    """跨對話記憶管理器

    負責讀寫 active_context.md、對話歸檔、決策紀錄。
    設計為 Claude Code 在每次對話開始/結束時呼叫。
    """

    def __init__(
        self,
        memory_dir: Optional[Path] = None,
    ):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.sessions_dir = self.memory_dir / "sessions"
        self.active_context_file = self.memory_dir / "active_context.md"
        self.decisions_file = self.memory_dir / "decisions.md"

        # 確保目錄存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # =============================================================
    # 讀取記憶
    # =============================================================

    def recall(self) -> str:
        """讀取 active_context.md，回傳全文

        新對話開始時呼叫，快速了解上次的狀態。

        Returns:
            active_context.md 的內容，若不存在回傳提示訊息
        """
        if not self.active_context_file.exists():
            return "（尚無記憶，這是第一次對話）"

        content = self.active_context_file.read_text(encoding="utf-8")
        logger.info("已讀取 active_context.md（%d 字元）", len(content))
        return content

    def recall_session(self, date: str = "") -> str:
        """讀取特定日期的對話摘要

        Args:
            date: 日期字串（YYYY-MM-DD），留空則讀最新一筆

        Returns:
            對話摘要內容
        """
        sessions = sorted(self.sessions_dir.glob("*.md"), reverse=True)
        if not sessions:
            return "（沒有任何對話紀錄）"

        if date:
            # 搜尋符合日期的檔案
            matched = [s for s in sessions if date in s.name]
            if not matched:
                return f"（找不到 {date} 的對話紀錄）"
            target = matched[0]
        else:
            target = sessions[0]

        content = target.read_text(encoding="utf-8")
        logger.info("已讀取對話紀錄: %s", target.name)
        return content

    def recall_recent(self, count: int = 3) -> str:
        """讀取最近 N 筆對話摘要

        Args:
            count: 要讀取的筆數

        Returns:
            最近幾次對話的摘要合併文字
        """
        sessions = sorted(self.sessions_dir.glob("*.md"), reverse=True)
        if not sessions:
            return "（沒有任何對話紀錄）"

        parts = []
        for session_file in sessions[:count]:
            content = session_file.read_text(encoding="utf-8")
            parts.append(f"---\n📁 {session_file.name}\n{content}")

        return "\n\n".join(parts)

    def recall_decisions(self) -> str:
        """讀取決策紀錄

        Returns:
            decisions.md 的內容
        """
        if not self.decisions_file.exists():
            return "（尚無決策紀錄）"

        return self.decisions_file.read_text(encoding="utf-8")

    # =============================================================
    # 儲存記憶
    # =============================================================

    def save_context(
        self,
        in_progress: Optional[list[str]] = None,
        completed: Optional[list[str]] = None,
        decisions: Optional[list[str]] = None,
        next_steps: Optional[list[str]] = None,
        notes: str = "",
    ) -> str:
        """更新 active_context.md

        覆寫整個檔案，反映當前最新狀態。

        Args:
            in_progress: 目前進行中的項目
            completed: 最近完成的項目
            decisions: 重要決策
            next_steps: 下一步待辦
            notes: 其他備註

        Returns:
            儲存的檔案路徑
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            "# 🧠 Active Context",
            f"更新：{now}",
            "",
        ]

        if in_progress:
            lines.append("## 目前進行中")
            for item in in_progress:
                lines.append(f"- {item}")
            lines.append("")

        if completed:
            lines.append("## 最近完成")
            for item in completed:
                lines.append(f"- {item}")
            lines.append("")

        if decisions:
            lines.append("## 重要決策")
            for item in decisions:
                lines.append(f"- {item}")
            lines.append("")

        if next_steps:
            lines.append("## 下一步")
            for item in next_steps:
                lines.append(f"- {item}")
            lines.append("")

        if notes:
            lines.append("## 備註")
            lines.append(notes)
            lines.append("")

        content = "\n".join(lines)
        self.active_context_file.write_text(content, encoding="utf-8")
        logger.info("active_context.md 已更新（%d 字元）", len(content))

        # 同時更新決策紀錄（追加模式）
        if decisions:
            self._append_decisions(decisions)

        return str(self.active_context_file)

    def archive_session(
        self,
        summary: str,
        details: str = "",
        session_id: str = "",
    ) -> str:
        """歸檔本次對話摘要

        在 sessions/ 建立一個時間戳命名的 .md 檔案。

        Args:
            summary: 對話摘要（1-3 句話）
            details: 詳細內容（選填）
            session_id: 自訂 session ID（留空自動生成）

        Returns:
            儲存的檔案路徑
        """
        now = datetime.now()
        sid = session_id or now.strftime("%Y-%m-%d_%H%M%S")
        filename = f"{sid}.md"
        filepath = self.sessions_dir / filename

        lines = [
            f"# 對話紀錄 — {now.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"## 摘要",
            summary,
            "",
        ]

        if details:
            lines.extend([
                "## 詳細內容",
                details,
                "",
            ])

        content = "\n".join(lines)
        filepath.write_text(content, encoding="utf-8")
        logger.info("對話已歸檔: %s", filepath.name)
        return str(filepath)

    # =============================================================
    # 內部方法
    # =============================================================

    def _append_decisions(self, decisions: list[str]) -> None:
        """追加決策到 decisions.md"""
        now = datetime.now().strftime("%Y-%m-%d")
        new_entries = "\n".join(f"- [{now}] {d}" for d in decisions)

        if self.decisions_file.exists():
            existing = self.decisions_file.read_text(encoding="utf-8")
            content = f"{existing}\n{new_entries}\n"
        else:
            content = (
                "# 📋 決策紀錄\n\n"
                "跨對話累積的重要決策，供未來參考。\n\n"
                f"{new_entries}\n"
            )

        self.decisions_file.write_text(content, encoding="utf-8")
        logger.info("已追加 %d 筆決策", len(decisions))

    def list_sessions(self) -> list[dict]:
        """列出所有對話紀錄

        Returns:
            [{"filename": "...", "date": "...", "preview": "..."}, ...]
        """
        sessions = sorted(self.sessions_dir.glob("*.md"), reverse=True)
        result = []
        for s in sessions:
            content = s.read_text(encoding="utf-8")
            # 取摘要段落的第一行作為 preview
            preview = ""
            for line in content.splitlines():
                if line.strip() and not line.startswith("#"):
                    preview = line.strip()[:100]
                    break

            result.append({
                "filename": s.name,
                "date": s.stem.split("_")[0] if "_" in s.stem else s.stem,
                "preview": preview,
            })
        return result
