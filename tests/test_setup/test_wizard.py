"""測試 wizard 模組 — 驗證專案偵測邏輯。"""

from pathlib import Path

import pytest


class TestIsExistingProject:
    """_is_existing_project 函式測試。"""

    def test_detects_existing_project(self, tmp_path):
        """偵測到 CLAUDE.md + .claude/settings.json → 既有專案。"""
        from setup.wizard import _is_existing_project

        (tmp_path / "CLAUDE.md").write_text("# Test", encoding="utf-8")
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")

        assert _is_existing_project(tmp_path) is True

    def test_empty_dir_is_not_existing(self, tmp_path):
        """空目錄 → 不是既有專案。"""
        from setup.wizard import _is_existing_project

        assert _is_existing_project(tmp_path) is False

    def test_only_claude_md_is_not_enough(self, tmp_path):
        """只有 CLAUDE.md 但沒有 settings.json → 不是既有專案。"""
        from setup.wizard import _is_existing_project

        (tmp_path / "CLAUDE.md").write_text("# Test", encoding="utf-8")

        assert _is_existing_project(tmp_path) is False


class TestFindTelegramBot:
    """_find_telegram_bot 函式測試。"""

    def test_returns_none_when_not_found(self):
        """找不到 telegram bot 回傳 None。"""
        from setup.telegram import _find_telegram_bot

        # 在測試環境中可能找到也可能找不到
        # 重點是函式不會崩潰
        result = _find_telegram_bot()
        assert result is None or (result / "src").exists()
