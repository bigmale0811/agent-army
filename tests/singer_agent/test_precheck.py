# -*- coding: utf-8 -*-
"""
DEV-10: precheck.py 測試。

測試覆蓋：
- QualityPrecheck 初始化
- dry_run 回傳 passed=True
- 圖片/音訊存在性檢查
- 磁碟空間檢查
- FFmpeg 可用性檢查
- 無 Gemini key 時跳過評分
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.singer_agent.models import PrecheckResult


def _create_file(path: Path, content: bytes = b"\x00" * 100):
    """建立測試用檔案。"""
    path.write_bytes(content)
    return path


class TestQualityPrecheckInit:
    def test_can_create_instance(self):
        """可建立 QualityPrecheck 實例。"""
        from src.singer_agent.precheck import QualityPrecheck
        qp = QualityPrecheck()
        assert qp is not None


class TestPrecheckDryRun:
    def test_dry_run_returns_precheck_result(self, tmp_path):
        """dry_run 回傳 PrecheckResult。"""
        from src.singer_agent.precheck import QualityPrecheck
        qp = QualityPrecheck()
        result = qp.run(
            tmp_path / "img.png", tmp_path / "audio.mp3", dry_run=True
        )
        assert isinstance(result, PrecheckResult)

    def test_dry_run_passed_is_true(self, tmp_path):
        """dry_run 結果 passed=True。"""
        from src.singer_agent.precheck import QualityPrecheck
        qp = QualityPrecheck()
        result = qp.run(
            tmp_path / "img.png", tmp_path / "audio.mp3", dry_run=True
        )
        assert result.passed is True

    def test_dry_run_has_checks_dict(self, tmp_path):
        """dry_run 結果有 checks 字典。"""
        from src.singer_agent.precheck import QualityPrecheck
        qp = QualityPrecheck()
        result = qp.run(
            tmp_path / "img.png", tmp_path / "audio.mp3", dry_run=True
        )
        assert isinstance(result.checks, dict)


class TestPrecheckImageAudio:
    def test_image_missing_fails(self, tmp_path):
        """圖片不存在時 passed=False。"""
        from src.singer_agent.precheck import QualityPrecheck
        audio = _create_file(tmp_path / "audio.mp3")
        qp = QualityPrecheck()
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=10 * 1024**3)):
            result = qp.run(tmp_path / "missing.png", audio)
        assert result.passed is False
        assert result.checks["image_exists"] is False

    def test_audio_missing_fails(self, tmp_path):
        """音訊不存在時 passed=False。"""
        from src.singer_agent.precheck import QualityPrecheck
        img = _create_file(tmp_path / "img.png")
        qp = QualityPrecheck()
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=10 * 1024**3)):
            result = qp.run(img, tmp_path / "missing.mp3")
        assert result.passed is False
        assert result.checks["audio_exists"] is False

    def test_both_exist_checks_pass(self, tmp_path):
        """圖片音訊都在時對應 checks 為 True。"""
        from src.singer_agent.precheck import QualityPrecheck
        img = _create_file(tmp_path / "img.png")
        audio = _create_file(tmp_path / "audio.mp3")
        qp = QualityPrecheck()
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=10 * 1024**3)):
            result = qp.run(img, audio)
        assert result.checks["image_exists"] is True
        assert result.checks["audio_exists"] is True


class TestPrecheckDiskSpace:
    def test_low_disk_space_fails(self, tmp_path):
        """磁碟空間不足（< 1GB）時 passed=False。"""
        from src.singer_agent.precheck import QualityPrecheck
        img = _create_file(tmp_path / "img.png")
        audio = _create_file(tmp_path / "audio.mp3")
        qp = QualityPrecheck()
        # 模擬只有 500MB
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=500 * 1024**2)):
            result = qp.run(img, audio)
        assert result.checks["disk_space"] is False

    def test_sufficient_disk_space_passes(self, tmp_path):
        """磁碟空間足夠時 disk_space=True。"""
        from src.singer_agent.precheck import QualityPrecheck
        img = _create_file(tmp_path / "img.png")
        audio = _create_file(tmp_path / "audio.mp3")
        qp = QualityPrecheck()
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=10 * 1024**3)):
            result = qp.run(img, audio)
        assert result.checks["disk_space"] is True


class TestPrecheckGemini:
    def test_no_gemini_key_score_is_none(self, tmp_path):
        """無 Gemini API key 時 gemini_score=None。"""
        from src.singer_agent.precheck import QualityPrecheck
        img = _create_file(tmp_path / "img.png")
        audio = _create_file(tmp_path / "audio.mp3")
        qp = QualityPrecheck()
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=10 * 1024**3)), \
             patch("src.singer_agent.precheck.config.GEMINI_API_KEY", ""):
            result = qp.run(img, audio)
        assert result.gemini_score is None


class TestPrecheckResult:
    def test_all_pass_returns_passed_true(self, tmp_path):
        """所有檢查通過時 passed=True。"""
        from src.singer_agent.precheck import QualityPrecheck
        img = _create_file(tmp_path / "img.png")
        audio = _create_file(tmp_path / "audio.mp3")
        qp = QualityPrecheck()
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=10 * 1024**3)), \
             patch("src.singer_agent.precheck.config.GEMINI_API_KEY", ""):
            result = qp.run(img, audio)
        assert result.passed is True

    def test_result_warnings_is_list(self, tmp_path):
        """warnings 是 list 類型。"""
        from src.singer_agent.precheck import QualityPrecheck
        img = _create_file(tmp_path / "img.png")
        audio = _create_file(tmp_path / "audio.mp3")
        qp = QualityPrecheck()
        with patch("src.singer_agent.precheck.shutil.disk_usage",
                    return_value=MagicMock(free=10 * 1024**3)):
            result = qp.run(img, audio)
        assert isinstance(result.warnings, list)
