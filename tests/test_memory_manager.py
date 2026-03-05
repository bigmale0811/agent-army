# -*- coding: utf-8 -*-
"""Memory Manager 測試

測試跨對話記憶系統的所有核心功能。
"""

import pytest
from pathlib import Path

from src.memory.manager import MemoryManager


@pytest.fixture
def memory_dir(tmp_path):
    """建立臨時記憶目錄"""
    return tmp_path / "memory"


@pytest.fixture
def mm(memory_dir):
    """建立 MemoryManager 實例"""
    return MemoryManager(memory_dir=memory_dir)


# =============================================================
# 初始化測試
# =============================================================


class TestInit:
    """測試 MemoryManager 初始化"""

    def test_creates_directories(self, mm, memory_dir):
        """初始化時自動建立目錄"""
        assert memory_dir.exists()
        assert (memory_dir / "sessions").exists()

    def test_custom_memory_dir(self, tmp_path):
        """支援自訂記憶目錄"""
        custom_dir = tmp_path / "custom_memory"
        manager = MemoryManager(memory_dir=custom_dir)
        assert manager.memory_dir == custom_dir
        assert custom_dir.exists()


# =============================================================
# recall 讀取記憶測試
# =============================================================


class TestRecall:
    """測試記憶讀取功能"""

    def test_recall_no_memory(self, mm):
        """沒有記憶時回傳提示"""
        result = mm.recall()
        assert "第一次對話" in result

    def test_recall_with_memory(self, mm):
        """有記憶時回傳內容"""
        mm.active_context_file.write_text(
            "# 測試記憶\n這是測試內容", encoding="utf-8"
        )
        result = mm.recall()
        assert "測試記憶" in result
        assert "測試內容" in result

    def test_recall_session_no_sessions(self, mm):
        """沒有對話紀錄時"""
        result = mm.recall_session()
        assert "沒有任何對話紀錄" in result

    def test_recall_session_latest(self, mm):
        """讀取最新的對話紀錄"""
        (mm.sessions_dir / "2026-03-04_120000.md").write_text(
            "# 舊的", encoding="utf-8"
        )
        (mm.sessions_dir / "2026-03-05_120000.md").write_text(
            "# 新的", encoding="utf-8"
        )
        result = mm.recall_session()
        assert "新的" in result

    def test_recall_session_by_date(self, mm):
        """依日期讀取特定對話紀錄"""
        (mm.sessions_dir / "2026-03-04_120000.md").write_text(
            "# 三月四號", encoding="utf-8"
        )
        (mm.sessions_dir / "2026-03-05_120000.md").write_text(
            "# 三月五號", encoding="utf-8"
        )
        result = mm.recall_session("2026-03-04")
        assert "三月四號" in result

    def test_recall_session_date_not_found(self, mm):
        """搜尋不存在的日期"""
        # 先建一筆，確保有 sessions 但找不到指定日期
        (mm.sessions_dir / "2026-03-01_120000.md").write_text(
            "# 存在的", encoding="utf-8"
        )
        result = mm.recall_session("2099-01-01")
        assert "找不到" in result

    def test_recall_recent(self, mm):
        """讀取最近 N 筆"""
        for i in range(5):
            (mm.sessions_dir / f"2026-03-0{i+1}_120000.md").write_text(
                f"# 第{i+1}天", encoding="utf-8"
            )
        result = mm.recall_recent(count=3)
        assert "第5天" in result
        assert "第4天" in result
        assert "第3天" in result
        assert "第1天" not in result

    def test_recall_recent_no_sessions(self, mm):
        """沒有紀錄時"""
        result = mm.recall_recent()
        assert "沒有任何對話紀錄" in result


# =============================================================
# save_context 儲存記憶測試
# =============================================================


class TestSaveContext:
    """測試儲存 active_context.md"""

    def test_save_basic(self, mm):
        """基本儲存"""
        mm.save_context(
            in_progress=["做 A"],
            completed=["做完 B"],
        )
        content = mm.active_context_file.read_text(encoding="utf-8")
        assert "做 A" in content
        assert "做完 B" in content
        assert "Active Context" in content

    def test_save_all_fields(self, mm):
        """所有欄位都有值"""
        mm.save_context(
            in_progress=["進行中項目"],
            completed=["已完成項目"],
            decisions=["決策 A"],
            next_steps=["下一步 X"],
            notes="額外備註",
        )
        content = mm.active_context_file.read_text(encoding="utf-8")
        assert "進行中項目" in content
        assert "已完成項目" in content
        assert "決策 A" in content
        assert "下一步 X" in content
        assert "額外備註" in content

    def test_save_overwrites(self, mm):
        """儲存會覆寫舊內容"""
        mm.save_context(in_progress=["舊項目"])
        mm.save_context(in_progress=["新項目"])
        content = mm.active_context_file.read_text(encoding="utf-8")
        assert "新項目" in content
        assert "舊項目" not in content

    def test_save_updates_decisions_file(self, mm):
        """有決策時同步更新 decisions.md"""
        mm.save_context(decisions=["重要決策 X"])
        assert mm.decisions_file.exists()
        decisions = mm.decisions_file.read_text(encoding="utf-8")
        assert "重要決策 X" in decisions

    def test_save_returns_path(self, mm):
        """回傳檔案路徑"""
        result = mm.save_context(in_progress=["test"])
        assert "active_context.md" in result


# =============================================================
# archive_session 對話歸檔測試
# =============================================================


class TestArchiveSession:
    """測試對話歸檔"""

    def test_archive_basic(self, mm):
        """基本歸檔"""
        path = mm.archive_session(summary="完成了測試")
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "完成了測試" in content

    def test_archive_with_details(self, mm):
        """有詳細內容的歸檔"""
        path = mm.archive_session(
            summary="摘要",
            details="這是詳細內容\n包含多行",
        )
        content = Path(path).read_text(encoding="utf-8")
        assert "摘要" in content
        assert "詳細內容" in content

    def test_archive_custom_id(self, mm):
        """自訂 session ID"""
        path = mm.archive_session(
            summary="test",
            session_id="custom_session_001",
        )
        assert "custom_session_001.md" in path

    def test_archive_auto_id(self, mm):
        """自動產生 session ID（時間戳格式）"""
        path = mm.archive_session(summary="test")
        filename = Path(path).name
        assert "202" in filename


# =============================================================
# decisions 決策紀錄測試
# =============================================================


class TestDecisions:
    """測試決策紀錄"""

    def test_recall_decisions_empty(self, mm):
        """沒有決策紀錄時"""
        result = mm.recall_decisions()
        assert "尚無決策紀錄" in result

    def test_recall_decisions_with_content(self, mm):
        """有決策紀錄時"""
        mm.save_context(decisions=["決策 A"])
        result = mm.recall_decisions()
        assert "決策 A" in result

    def test_decisions_accumulate(self, mm):
        """決策應累積不覆蓋"""
        mm.save_context(decisions=["第一個決策"])
        mm.save_context(decisions=["第二個決策"])
        result = mm.recall_decisions()
        assert "第一個決策" in result
        assert "第二個決策" in result


# =============================================================
# list_sessions 列出對話測試
# =============================================================


class TestListSessions:
    """測試列出對話紀錄"""

    def test_list_empty(self, mm):
        """沒有紀錄"""
        result = mm.list_sessions()
        assert result == []

    def test_list_with_sessions(self, mm):
        """有紀錄時回傳列表"""
        mm.archive_session(summary="第一次", session_id="2026-03-04_120000")
        mm.archive_session(summary="第二次", session_id="2026-03-05_120000")
        result = mm.list_sessions()
        assert len(result) == 2
        assert result[0]["filename"] == "2026-03-05_120000.md"
        assert "preview" in result[0]


# =============================================================
# UTF-8 編碼測試
# =============================================================


class TestEncoding:
    """測試繁體中文和特殊字元的處理"""

    def test_chinese_content(self, mm):
        """繁體中文內容正確儲存和讀取"""
        mm.save_context(
            in_progress=["修正 Singer Agent 的 SadTalker 動畫合成"],
            completed=["愛我的人和我愛的人 — 游鴻明 測試完成"],
        )
        content = mm.recall()
        assert "Singer Agent" in content
        assert "游鴻明" in content

    def test_special_characters(self, mm):
        """特殊字元處理"""
        mm.archive_session(
            summary="處理了特殊字元的檔名",
        )
        sessions = mm.list_sessions()
        assert len(sessions) == 1
