# -*- coding: utf-8 -*-
"""
DEV-3: path_utils.py 測試。

測試路徑工具函式：to_ascii_temp、cleanup_temp、ensure_dir、safe_stem。
全部使用 tmp_path，不依賴真實路徑。
"""
import os
import re
import string
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────
# to_ascii_temp 測試
# ─────────────────────────────────────────────────

class TestToAsciiTemp:
    """測試 to_ascii_temp()：將非 ASCII 路徑複製到純 ASCII 暫存路徑。"""

    def test_chinese_path_returns_ascii_only(self, tmp_path):
        """中文路徑 → 回傳路徑只含 ASCII 字元。"""
        from src.singer_agent.path_utils import to_ascii_temp

        # 建立含中文名稱的原始檔案
        chinese_file = tmp_path / "月亮代表我的心.mp3"
        chinese_file.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 50)

        result = to_ascii_temp(chinese_file)

        # 回傳路徑的所有字元必須是 ASCII
        assert all(ord(c) < 128 for c in str(result))

    def test_ascii_path_still_returns_valid_path(self, tmp_path):
        """純 ASCII 路徑也能正常處理（不拋出例外）。"""
        from src.singer_agent.path_utils import to_ascii_temp

        ascii_file = tmp_path / "test_song.mp3"
        ascii_file.write_bytes(b"fake audio data")

        result = to_ascii_temp(ascii_file)

        # 結果應是存在的路徑
        assert result.exists()

    def test_copied_file_content_matches_original(self, tmp_path):
        """暫存檔案內容與原始檔案完全一致。"""
        from src.singer_agent.path_utils import to_ascii_temp

        original_content = b"\xff\xfb\x90\x00" + b"\xde\xad\xbe\xef" * 25
        chinese_file = tmp_path / "測試歌曲.mp3"
        chinese_file.write_bytes(original_content)

        result = to_ascii_temp(chinese_file)

        assert result.read_bytes() == original_content

    def test_suffix_parameter_is_appended(self, tmp_path):
        """suffix 參數會附加到暫存檔名。"""
        from src.singer_agent.path_utils import to_ascii_temp

        chinese_file = tmp_path / "歌曲.mp3"
        chinese_file.write_bytes(b"data")

        result = to_ascii_temp(chinese_file, suffix="_work")

        assert "_work" in result.stem or "_work" in result.name

    def test_result_path_is_in_temp_or_accessible_dir(self, tmp_path):
        """回傳的路徑必須存在於磁碟。"""
        from src.singer_agent.path_utils import to_ascii_temp

        chinese_file = tmp_path / "日文タイトル.wav"
        chinese_file.write_bytes(b"wav data")

        result = to_ascii_temp(chinese_file)

        assert result.exists()
        assert result.is_file()

    def test_file_extension_preserved(self, tmp_path):
        """暫存檔案的副檔名與原始一致。"""
        from src.singer_agent.path_utils import to_ascii_temp

        chinese_file = tmp_path / "音樂.wav"
        chinese_file.write_bytes(b"wav data")

        result = to_ascii_temp(chinese_file)

        assert result.suffix == ".wav"


# ─────────────────────────────────────────────────
# cleanup_temp 測試
# ─────────────────────────────────────────────────

class TestCleanupTemp:
    """測試 cleanup_temp()：刪除暫存檔案，不存在時靜默。"""

    def test_existing_file_is_deleted(self, tmp_path):
        """存在的檔案被成功刪除。"""
        from src.singer_agent.path_utils import cleanup_temp

        temp_file = tmp_path / "temp_abc123.mp3"
        temp_file.write_bytes(b"temp data")
        assert temp_file.exists()

        cleanup_temp(temp_file)

        assert not temp_file.exists()

    def test_nonexistent_path_does_not_raise(self, tmp_path):
        """不存在的路徑不拋出任何例外（靜默）。"""
        from src.singer_agent.path_utils import cleanup_temp

        nonexistent = tmp_path / "ghost_file_xyz.mp3"
        assert not nonexistent.exists()

        # 不應拋出任何例外
        cleanup_temp(nonexistent)

    def test_cleanup_returns_none(self, tmp_path):
        """cleanup_temp 回傳 None。"""
        from src.singer_agent.path_utils import cleanup_temp

        temp_file = tmp_path / "temp_xyz.mp3"
        temp_file.write_bytes(b"data")

        result = cleanup_temp(temp_file)

        assert result is None


# ─────────────────────────────────────────────────
# ensure_dir 測試
# ─────────────────────────────────────────────────

class TestEnsureDir:
    """測試 ensure_dir()：建立目錄（含巢狀），回傳相同 Path。"""

    def test_creates_new_directory(self, tmp_path):
        """新目錄被成功建立。"""
        from src.singer_agent.path_utils import ensure_dir

        new_dir = tmp_path / "new_directory"
        assert not new_dir.exists()

        result = ensure_dir(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        """巢狀目錄一次建立成功。"""
        from src.singer_agent.path_utils import ensure_dir

        nested_dir = tmp_path / "level1" / "level2" / "level3"
        assert not nested_dir.exists()

        result = ensure_dir(nested_dir)

        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_existing_directory_does_not_raise(self, tmp_path):
        """已存在的目錄不拋出例外。"""
        from src.singer_agent.path_utils import ensure_dir

        existing_dir = tmp_path / "already_exists"
        existing_dir.mkdir()
        assert existing_dir.exists()

        # 不應拋出例外
        result = ensure_dir(existing_dir)

        assert existing_dir.exists()

    def test_returns_same_path(self, tmp_path):
        """回傳與輸入相同的 Path 物件。"""
        from src.singer_agent.path_utils import ensure_dir

        target_dir = tmp_path / "my_dir"

        result = ensure_dir(target_dir)

        assert result == target_dir
        assert isinstance(result, Path)


# ─────────────────────────────────────────────────
# safe_stem 測試
# ─────────────────────────────────────────────────

class TestSafeStem:
    """測試 safe_stem()：中文或任意字串轉 ASCII 安全檔名。"""

    def test_chinese_title_returns_ascii_only(self):
        """中文歌名回傳純 ASCII 字串。"""
        from src.singer_agent.path_utils import safe_stem

        result = safe_stem("月亮代表我的心")

        # 所有字元必須是 ASCII 可列印字元
        assert all(ord(c) < 128 for c in result)

    def test_result_is_non_empty(self):
        """回傳字串非空。"""
        from src.singer_agent.path_utils import safe_stem

        result = safe_stem("月亮代表我的心")

        assert len(result) > 0

    def test_ascii_title_is_safe(self):
        """純英文歌名回傳安全字串（不含路徑分隔符或特殊字元）。"""
        from src.singer_agent.path_utils import safe_stem

        result = safe_stem("My Favorite Song")

        # 不含路徑分隔符
        assert "/" not in result
        assert "\\" not in result
        # 不含空白（或已被替換）
        unsafe_chars = set('<>:"/\\|?*')
        assert not any(c in unsafe_chars for c in result)

    def test_empty_string_returns_fallback(self):
        """空字串輸入回傳有意義的後備值，不拋出例外。"""
        from src.singer_agent.path_utils import safe_stem

        result = safe_stem("")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_usable_as_filename(self):
        """回傳值可直接用作檔名（無非法字元）。"""
        from src.singer_agent.path_utils import safe_stem

        result = safe_stem("愛的代價：完整版（2024 Remaster）")

        # 不含 Windows/Unix 檔名非法字元
        illegal = set('<>:"/\\|?*\x00')
        assert not any(c in illegal for c in result)

    def test_different_inputs_may_produce_unique_stems(self):
        """不同輸入最好產出不同結果（不強制，但驗證函式能處理多種輸入）。"""
        from src.singer_agent.path_utils import safe_stem

        titles = ["月亮代表我的心", "夜空中最亮的星", "童話", "小幸運"]
        results = [safe_stem(t) for t in titles]

        # 每個結果都是非空 ASCII 字串
        for r in results:
            assert len(r) > 0
            assert all(ord(c) < 128 for c in r)

    def test_special_characters_handled(self):
        """特殊字元不造成崩潰。"""
        from src.singer_agent.path_utils import safe_stem

        # 含有 SQL 特殊字元、emoji、引號等
        result = safe_stem("O'Brien's Song: \"Hello\" & Goodbye!")

        assert isinstance(result, str)
        assert len(result) > 0
