# -*- coding: utf-8 -*-
"""
quality_checker 模組測試。

涵蓋：
- QualityChecker.check() 主流程
- dry_run 模式
- 依賴缺失時的優雅跳過
- _ensure_pcm16 音訊轉換
- _analyze_audio_energy 能量分析
- _analyze_lip_motion 嘴唇追蹤
"""
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from src.singer_agent.quality_checker import (
    QualityChecker,
    QAResult,
    _SILENCE_THRESHOLD,
    _LIP_VARIANCE_THRESHOLD,
    _MAX_SILENT_MOTION_RATIO,
)


# ─── QAResult ─────────────────────────────────────────────


class TestQAResult:
    """QAResult dataclass 基本測試。"""

    def test_frozen_dataclass(self):
        """QAResult 應為不可變（frozen）。"""
        result = QAResult(
            passed=True,
            lip_sync_score=95.0,
            silent_motion_ratio=0.05,
            total_frames=100,
            silent_frames=20,
            moving_in_silence=1,
            details={"mode": "test"},
        )
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore[misc]

    def test_all_fields_present(self):
        result = QAResult(
            passed=False,
            lip_sync_score=50.0,
            silent_motion_ratio=0.5,
            total_frames=200,
            silent_frames=100,
            moving_in_silence=50,
            details={},
        )
        assert result.passed is False
        assert result.lip_sync_score == 50.0
        assert result.total_frames == 200


# ─── QualityChecker.check() ──────────────────────────────


class TestQualityCheckerCheck:
    """check() 方法主流程測試。"""

    def test_dry_run_returns_pass(self, tmp_path):
        """dry_run 模式直接通過。"""
        qa = QualityChecker()
        result = qa.check(
            tmp_path / "video.mp4",
            tmp_path / "vocals.wav",
            dry_run=True,
        )
        assert result.passed is True
        assert result.lip_sync_score == 100.0
        assert result.details["mode"] == "dry_run"

    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_lip_motion")
    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_audio_energy")
    @patch("src.singer_agent.quality_checker.QualityChecker._ensure_pcm16")
    def test_no_frames_returns_skip(
        self, mock_pcm, mock_energy, mock_lip, tmp_path,
    ):
        """音訊或影片幀數為 0 時跳過。"""
        mock_pcm.return_value = tmp_path / "pcm.wav"
        mock_energy.return_value = []
        mock_lip.return_value = []

        qa = QualityChecker()
        # 需要 cv2 和 mediapipe 可匯入
        with patch.dict("sys.modules", {"cv2": MagicMock(), "mediapipe": MagicMock()}):
            result = qa.check(tmp_path / "v.mp4", tmp_path / "a.wav")

        assert result.passed is True
        assert result.details["reason"] == "no_frames"

    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_lip_motion")
    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_audio_energy")
    @patch("src.singer_agent.quality_checker.QualityChecker._ensure_pcm16")
    def test_all_silent_no_motion_passes(
        self, mock_pcm, mock_energy, mock_lip, tmp_path,
    ):
        """全靜音 + 嘴唇不動 → 通過。"""
        mock_pcm.return_value = tmp_path / "pcm.wav"
        # 20 幀全靜音
        mock_energy.return_value = [0.001] * 20
        # 嘴唇方差全為 0
        mock_lip.return_value = [0.0] * 20

        qa = QualityChecker()
        with patch.dict("sys.modules", {"cv2": MagicMock(), "mediapipe": MagicMock()}):
            result = qa.check(tmp_path / "v.mp4", tmp_path / "a.wav")

        assert result.passed is True
        assert result.silent_frames == 20
        assert result.moving_in_silence == 0

    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_lip_motion")
    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_audio_energy")
    @patch("src.singer_agent.quality_checker.QualityChecker._ensure_pcm16")
    def test_silent_with_lip_motion_fails(
        self, mock_pcm, mock_energy, mock_lip, tmp_path,
    ):
        """靜音段嘴唇劇烈運動 → FAIL。"""
        mock_pcm.return_value = tmp_path / "pcm.wav"
        # 20 幀全靜音
        mock_energy.return_value = [0.001] * 20
        # 嘴唇方差全部超標
        mock_lip.return_value = [0.01] * 20

        qa = QualityChecker()
        with patch.dict("sys.modules", {"cv2": MagicMock(), "mediapipe": MagicMock()}):
            result = qa.check(tmp_path / "v.mp4", tmp_path / "a.wav")

        assert result.passed is False
        assert result.moving_in_silence == 20
        assert result.silent_motion_ratio == 1.0

    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_lip_motion")
    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_audio_energy")
    @patch("src.singer_agent.quality_checker.QualityChecker._ensure_pcm16")
    def test_vocal_frames_with_motion_passes(
        self, mock_pcm, mock_energy, mock_lip, tmp_path,
    ):
        """有聲段嘴唇運動（正常）→ 通過。"""
        mock_pcm.return_value = tmp_path / "pcm.wav"
        # 20 幀全部有聲
        mock_energy.return_value = [0.5] * 20
        # 嘴唇都在動（正常）
        mock_lip.return_value = [0.01] * 20

        qa = QualityChecker()
        with patch.dict("sys.modules", {"cv2": MagicMock(), "mediapipe": MagicMock()}):
            result = qa.check(tmp_path / "v.mp4", tmp_path / "a.wav")

        assert result.passed is True
        assert result.silent_frames == 0

    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_lip_motion")
    @patch("src.singer_agent.quality_checker.QualityChecker._analyze_audio_energy")
    @patch("src.singer_agent.quality_checker.QualityChecker._ensure_pcm16")
    def test_mixed_frames_under_threshold_passes(
        self, mock_pcm, mock_energy, mock_lip, tmp_path,
    ):
        """混合幀：靜音段嘴唇運動比率低於閾值 → 通過。"""
        mock_pcm.return_value = tmp_path / "pcm.wav"
        # 10 幀靜音 + 10 幀有聲
        mock_energy.return_value = [0.001] * 10 + [0.5] * 10
        # 靜音段：2 幀超標 + 8 幀正常 → 比率 20% < 30%
        mock_lip.return_value = (
            [0.01] * 2 + [0.001] * 8 + [0.01] * 10
        )

        qa = QualityChecker()
        with patch.dict("sys.modules", {"cv2": MagicMock(), "mediapipe": MagicMock()}):
            result = qa.check(tmp_path / "v.mp4", tmp_path / "a.wav")

        assert result.passed is True
        assert result.moving_in_silence == 2
        assert result.silent_frames == 10


# ─── _analyze_audio_energy ────────────────────────────────


class TestAnalyzeAudioEnergy:
    """音訊能量分析測試。"""

    def _make_wav(self, path: Path, samples: list[int], rate: int = 16000):
        """建立 PCM16 mono WAV 測試檔。"""
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    def test_silent_audio_returns_low_energy(self, tmp_path):
        """全靜音音訊的能量應低於閾值。"""
        wav = tmp_path / "silent.wav"
        # 1 秒靜音（16000 個 0 值）
        self._make_wav(wav, [0] * 16000)

        qa = QualityChecker()
        energies = qa._analyze_audio_energy(wav)

        assert len(energies) > 0
        assert all(e < _SILENCE_THRESHOLD for e in energies)

    def test_loud_audio_returns_high_energy(self, tmp_path):
        """大音量音訊的能量應高於閾值。"""
        wav = tmp_path / "loud.wav"
        # 1 秒大音量（正弦波模擬）
        import math
        samples = [int(30000 * math.sin(2 * math.pi * 440 * i / 16000))
                   for i in range(16000)]
        self._make_wav(wav, samples)

        qa = QualityChecker()
        energies = qa._analyze_audio_energy(wav)

        assert len(energies) > 0
        assert all(e > _SILENCE_THRESHOLD for e in energies)

    def test_missing_file_returns_empty(self, tmp_path):
        """不存在的檔案回傳空列表。"""
        qa = QualityChecker()
        energies = qa._analyze_audio_energy(tmp_path / "missing.wav")
        assert energies == []


# ─── 依賴缺失測試 ────────────────────────────────────────


class TestDependencyMissing:
    """mediapipe/cv2 未安裝時的優雅處理。"""

    def test_import_error_returns_skip(self, tmp_path):
        """ImportError 時回傳 passed=True + skipped。"""
        qa = QualityChecker()

        with patch.dict("sys.modules", {"cv2": None, "mediapipe": None}):
            with patch("builtins.__import__", side_effect=ImportError("no cv2")):
                result = qa.check(tmp_path / "v.mp4", tmp_path / "a.wav")

        assert result.passed is True
        assert result.details.get("mode") == "skipped"
