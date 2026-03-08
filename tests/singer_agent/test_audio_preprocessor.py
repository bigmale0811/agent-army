# -*- coding: utf-8 -*-
"""
audio_preprocessor 模組測試。

涵蓋：
- mood_to_expression_scale（情緒映射）
- separate_vocals（Demucs subprocess）
- apply_noise_gate（ffmpeg agate）
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.singer_agent.audio_preprocessor import (
    EMOTION_EXPRESSION_MAP,
    DEFAULT_EXPRESSION_SCALE,
    mood_to_expression_scale,
    separate_vocals,
    apply_noise_gate,
)


# ─── mood_to_expression_scale ─────────────────────────────


class TestMoodToExpressionScale:
    """情緒 → expression_scale 映射測試。"""

    def test_empty_string_returns_default(self):
        assert mood_to_expression_scale("") == DEFAULT_EXPRESSION_SCALE

    def test_sad_returns_low_scale(self):
        result = mood_to_expression_scale("sad")
        assert result == 0.5

    def test_happy_returns_high_scale(self):
        result = mood_to_expression_scale("happy")
        assert result == 1.3

    def test_chinese_sad_keyword(self):
        """繁體中文「感傷」應映射到低 scale。"""
        result = mood_to_expression_scale("感傷")
        assert result == 0.5

    def test_chinese_depressed_keyword(self):
        """「情緒低落」應映射到 0.4。"""
        result = mood_to_expression_scale("情緒低落")
        assert result == 0.4

    def test_mixed_english_keywords(self):
        """包含多個關鍵字時，取第一個匹配。"""
        result = mood_to_expression_scale("sad and melancholic")
        assert result == 0.5

    def test_unknown_mood_returns_default(self):
        result = mood_to_expression_scale("completely random text")
        assert result == DEFAULT_EXPRESSION_SCALE

    def test_case_insensitive(self):
        """英文大小寫不敏感。"""
        result = mood_to_expression_scale("SAD")
        assert result == 0.5

    def test_all_english_keywords_mapped(self):
        """確保所有英文關鍵字都有合法映射值。"""
        for keyword, scale in EMOTION_EXPRESSION_MAP.items():
            assert 0.0 < scale < 2.0, f"keyword={keyword}, scale={scale}"


# ─── separate_vocals ──────────────────────────────────────


class TestSeparateVocals:
    """Demucs 人聲分離測試（mock subprocess）。"""

    def test_dry_run_returns_original(self, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.touch()
        result = separate_vocals(audio, tmp_path / "out", dry_run=True)
        assert result == audio

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_success_returns_vocals_path(self, mock_run, tmp_path):
        """成功時回傳 Demucs 輸出的 vocals.wav 路徑。"""
        audio = tmp_path / "song.mp3"
        audio.touch()
        out_dir = tmp_path / "out"

        # 模擬 Demucs 成功輸出
        mock_run.return_value = MagicMock(returncode=0)
        vocals = out_dir / "htdemucs" / "song" / "vocals.wav"
        vocals.parent.mkdir(parents=True)
        vocals.write_bytes(b"\x00" * 1024)

        result = separate_vocals(audio, out_dir, python_bin="python")
        assert result == vocals
        mock_run.assert_called_once()

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_failure_fallback_to_original(self, mock_run, tmp_path):
        """Demucs 失敗時 fallback 回傳原始音訊。"""
        audio = tmp_path / "song.mp3"
        audio.touch()
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        result = separate_vocals(audio, tmp_path / "out", python_bin="python")
        assert result == audio

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_timeout_fallback(self, mock_run, tmp_path):
        """超時時 fallback 回傳原始音訊。"""
        import subprocess as sp
        audio = tmp_path / "song.mp3"
        audio.touch()
        mock_run.side_effect = sp.TimeoutExpired(cmd="demucs", timeout=300)

        result = separate_vocals(audio, tmp_path / "out", python_bin="python")
        assert result == audio

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_python_not_found_fallback(self, mock_run, tmp_path):
        """Python 路徑不存在時 fallback。"""
        audio = tmp_path / "song.mp3"
        audio.touch()
        mock_run.side_effect = FileNotFoundError("python not found")

        result = separate_vocals(
            audio, tmp_path / "out", python_bin="/nonexistent/python",
        )
        assert result == audio


# ─── apply_noise_gate ─────────────────────────────────────


class TestApplyNoiseGate:
    """ffmpeg noise gate 測試（mock subprocess）。"""

    def test_dry_run_returns_original(self, tmp_path):
        vocals = tmp_path / "vocals.wav"
        vocals.touch()
        result = apply_noise_gate(
            vocals, tmp_path / "gated.wav", dry_run=True,
        )
        assert result == vocals

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_success_returns_output_path(self, mock_run, tmp_path):
        """成功時回傳處理後的音訊路徑。"""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()
        output = tmp_path / "gated.wav"

        mock_run.return_value = MagicMock(returncode=0)
        # 模擬 ffmpeg 產出檔案
        output.write_bytes(b"\x00" * 512)

        result = apply_noise_gate(
            vocals, output, ffmpeg_bin="ffmpeg",
        )
        assert result == output

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_failure_fallback(self, mock_run, tmp_path):
        """ffmpeg 失敗時 fallback 回傳原始音訊。"""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()
        mock_run.return_value = MagicMock(returncode=1, stderr="err")

        result = apply_noise_gate(
            vocals, tmp_path / "gated.wav", ffmpeg_bin="ffmpeg",
        )
        assert result == vocals

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_timeout_fallback(self, mock_run, tmp_path):
        """ffmpeg 超時時 fallback。"""
        import subprocess as sp
        vocals = tmp_path / "vocals.wav"
        vocals.touch()
        mock_run.side_effect = sp.TimeoutExpired(cmd="ffmpeg", timeout=120)

        result = apply_noise_gate(
            vocals, tmp_path / "gated.wav", ffmpeg_bin="ffmpeg",
        )
        assert result == vocals

    @patch("src.singer_agent.audio_preprocessor.subprocess.run")
    def test_custom_threshold(self, mock_run, tmp_path):
        """自訂閾值應傳入 ffmpeg 命令。"""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()
        output = tmp_path / "gated.wav"
        output.write_bytes(b"\x00" * 512)
        mock_run.return_value = MagicMock(returncode=0)

        apply_noise_gate(
            vocals, output, ffmpeg_bin="ffmpeg", threshold=0.05,
        )
        # 檢查 ffmpeg 被呼叫時包含自訂閾值
        call_args = mock_run.call_args[0][0]
        af_arg = [a for a in call_args if "agate" in str(a)]
        assert len(af_arg) > 0
        assert "0.05" in af_arg[0]
