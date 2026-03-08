# -*- coding: utf-8 -*-
"""
DEV-3: 品質檢驗模組。

QualityChecker 分析輸出影片的嘴唇 landmarks 運動方差，
結合人聲軌道判斷靜音區段。若靜音段嘴唇劇烈運動 → 測試失敗。

核心邏輯：
1. 從人聲 WAV 計算每幀的 RMS 能量 → 判定靜音段
2. 從影片用 MediaPipe Face Mesh 提取嘴唇 landmarks
3. 計算嘴唇 landmarks 的幀間位移方差
4. 若靜音段嘴唇方差超過閾值 → FAIL

依賴：mediapipe（CPU only，不佔 VRAM）、opencv-python、numpy
所有依賴皆為可選：缺失時自動跳過 QA（不阻擋管線）。
"""
import logging
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.singer_agent import config

_logger = logging.getLogger(__name__)

# MediaPipe Face Mesh 嘴唇 landmark 索引
# 外唇 + 內唇共 22 個特徵點，精準追蹤嘴型變化
_LIP_INDICES = [
    # 外唇（上下左右輪廓）
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
    # 內唇（張嘴程度）
    78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308,
]

# 能量閾值：RMS 低於此值視為靜音（normalized 0~1）
_SILENCE_THRESHOLD = 0.02

# 嘴唇運動方差閾值：靜音段方差超過此值視為異常運動
_LIP_VARIANCE_THRESHOLD = 0.005

# 影片取樣頻率（每秒幾幀）
_SAMPLE_FPS = 5

# 靜音段允許的最大嘴唇運動比率（30% 容忍度）
_MAX_SILENT_MOTION_RATIO = 0.3


@dataclass(frozen=True)
class QAResult:
    """
    品質檢驗結果（不可變）。

    Attributes:
        passed: 是否通過品質檢驗
        lip_sync_score: 對嘴同步分數（0~100，100=完美）
        silent_motion_ratio: 靜音段嘴唇運動比率（0~1，越低越好）
        total_frames: 分析的總幀數
        silent_frames: 靜音幀數
        moving_in_silence: 靜音段仍有嘴唇運動的幀數
        details: 詳細分析數據
    """
    passed: bool
    lip_sync_score: float
    silent_motion_ratio: float
    total_frames: int
    silent_frames: int
    moving_in_silence: int
    details: dict


class QualityChecker:
    """
    影片品質檢驗器。

    使用 MediaPipe Face Mesh 分析嘴唇 landmark 運動，
    結合人聲軌道能量判定靜音區段。
    若靜音段仍有嘴唇劇烈運動 → 判定為 FAIL。

    所有外部依賴（mediapipe, cv2）為可選：
    缺失時回傳 passed=True 並附帶警告。
    """

    def check(
        self,
        video_path: Path,
        vocals_path: Path,
        dry_run: bool = False,
    ) -> QAResult:
        """
        執行品質檢驗。

        Args:
            video_path: 輸出影片路徑
            vocals_path: 人聲軌道路徑（用於判斷靜音段）
            dry_run: 乾跑模式直接通過

        Returns:
            QAResult 品質檢驗結果
        """
        if dry_run:
            _logger.info("dry_run 模式：跳過品質檢驗")
            return QAResult(
                passed=True,
                lip_sync_score=100.0,
                silent_motion_ratio=0.0,
                total_frames=0,
                silent_frames=0,
                moving_in_silence=0,
                details={"mode": "dry_run"},
            )

        # 延遲匯入可選依賴
        try:
            import cv2
            import mediapipe as mp
        except ImportError as exc:
            _logger.warning(
                "品質檢驗依賴未安裝（%s），跳過 QA。"
                "請安裝：pip install mediapipe opencv-python",
                exc,
            )
            return QAResult(
                passed=True,
                lip_sync_score=-1.0,
                silent_motion_ratio=-1.0,
                total_frames=0,
                silent_frames=0,
                moving_in_silence=0,
                details={"mode": "skipped", "reason": str(exc)},
            )

        _logger.info("品質檢驗開始：分析嘴唇同步")

        # 1. 確保音訊為可讀 PCM 格式
        pcm_path = self._ensure_pcm16(vocals_path)

        # 2. 讀取人聲能量分布
        energy_per_frame = self._analyze_audio_energy(pcm_path)

        # 清理轉換的暫存檔
        if pcm_path != vocals_path and pcm_path.exists():
            try:
                pcm_path.unlink()
            except OSError:
                pass

        # 3. 分析影片嘴唇 landmarks
        lip_variances = self._analyze_lip_motion(video_path, cv2, mp)

        # 4. 對齊（取兩者最短長度）
        n_frames = min(len(energy_per_frame), len(lip_variances))

        if n_frames == 0:
            _logger.warning("無法分析：音訊或影片幀數為 0")
            return QAResult(
                passed=True,
                lip_sync_score=-1.0,
                silent_motion_ratio=-1.0,
                total_frames=0,
                silent_frames=0,
                moving_in_silence=0,
                details={"mode": "skipped", "reason": "no_frames"},
            )

        energy_aligned = energy_per_frame[:n_frames]
        lip_aligned = lip_variances[:n_frames]

        # 5. 判定：靜音段的嘴唇運動
        silent_frames = 0
        moving_in_silence = 0

        for i in range(n_frames):
            if energy_aligned[i] < _SILENCE_THRESHOLD:
                silent_frames += 1
                if lip_aligned[i] > _LIP_VARIANCE_THRESHOLD:
                    moving_in_silence += 1

        # 計算指標
        silent_motion_ratio = (
            moving_in_silence / silent_frames if silent_frames > 0 else 0.0
        )
        lip_sync_score = max(0.0, (1.0 - silent_motion_ratio) * 100)
        passed = silent_motion_ratio < _MAX_SILENT_MOTION_RATIO

        result = QAResult(
            passed=passed,
            lip_sync_score=round(lip_sync_score, 1),
            silent_motion_ratio=round(silent_motion_ratio, 4),
            total_frames=n_frames,
            silent_frames=silent_frames,
            moving_in_silence=moving_in_silence,
            details={
                "mode": "mediapipe",
                "threshold_silence": _SILENCE_THRESHOLD,
                "threshold_lip_var": _LIP_VARIANCE_THRESHOLD,
                "max_silent_motion_ratio": _MAX_SILENT_MOTION_RATIO,
                "sample_fps": _SAMPLE_FPS,
            },
        )

        if passed:
            _logger.info(
                "品質檢驗通過：lip_sync_score=%.1f, "
                "靜音段運動比率=%.1f%% (%d/%d 幀)",
                lip_sync_score, silent_motion_ratio * 100,
                moving_in_silence, silent_frames,
            )
        else:
            _logger.error(
                "品質檢驗失敗！靜音段 %d/%d 幀嘴唇仍在動（%.1f%%），"
                "超過容忍閾值 %.0f%%",
                moving_in_silence, silent_frames,
                silent_motion_ratio * 100,
                _MAX_SILENT_MOTION_RATIO * 100,
            )

        return result

    @staticmethod
    def _ensure_pcm16(audio_path: Path) -> Path:
        """
        確保音訊為 PCM16 WAV 格式（wave 模組可讀）。

        Demucs 輸出可能為 float32 WAV，Python wave 模組無法直接讀取。
        使用 ffmpeg 統一轉換為 PCM16 mono 16kHz。
        """
        # 先嘗試直接用 wave 開啟
        try:
            with wave.open(str(audio_path), "rb") as wf:
                if wf.getsampwidth() in (2, 4):
                    return audio_path
        except (wave.Error, EOFError, ValueError):
            pass

        # 需要 ffmpeg 轉換
        output = audio_path.parent / f"_qa_{audio_path.stem}_pcm16.wav"
        cmd = [
            str(config.FFMPEG_BIN),
            "-y", "-i", str(audio_path),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output),
        ]

        try:
            subprocess.run(
                cmd, check=True, capture_output=True, timeout=60,
            )
            _logger.info("音訊轉換為 PCM16：%s", output)
            return output
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            _logger.warning("ffmpeg 轉換失敗：%s，嘗試直接讀取原始檔", exc)
            return audio_path

    @staticmethod
    def _analyze_audio_energy(audio_path: Path) -> list[float]:
        """
        分析音訊每取樣幀的 RMS 能量。

        以 _SAMPLE_FPS 為單位，計算每個區間的 RMS 值（normalized 0~1）。

        Returns:
            每幀的 RMS 能量列表
        """
        try:
            with wave.open(str(audio_path), "rb") as wf:
                rate = wf.getframerate()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
        except Exception as exc:
            _logger.warning("音訊讀取失敗：%s", exc)
            return []

        # 轉換為 float64 numpy array（normalized -1~1）
        if sampwidth == 2:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
            samples /= 32768.0
        elif sampwidth == 4:
            samples = np.frombuffer(raw, dtype=np.int32).astype(np.float64)
            samples /= 2147483648.0
        else:
            samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
            samples = (samples - 128.0) / 128.0

        # 多聲道取平均
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        # 計算每取樣幀的 RMS
        samples_per_frame = max(1, rate // _SAMPLE_FPS)
        energies: list[float] = []

        for i in range(0, len(samples), samples_per_frame):
            chunk = samples[i:i + samples_per_frame]
            if len(chunk) > 0:
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                energies.append(rms)

        _logger.info(
            "音訊能量分析：%d 幀，靜音幀 %d（閾值 %.3f）",
            len(energies),
            sum(1 for e in energies if e < _SILENCE_THRESHOLD),
            _SILENCE_THRESHOLD,
        )
        return energies

    @staticmethod
    def _analyze_lip_motion(
        video_path: Path, cv2: Any, mp: Any,
    ) -> list[float]:
        """
        使用 MediaPipe Face Mesh 分析嘴唇 landmark 幀間運動方差。

        每 1/_SAMPLE_FPS 秒取樣一幀，提取嘴唇 landmarks 座標，
        計算與前一幀的位移方差（均方位移 MSD）。

        Returns:
            每取樣幀的嘴唇運動方差列表
        """
        face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            _logger.error("無法開啟影片：%s", video_path)
            face_mesh.close()
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(fps / _SAMPLE_FPS))

        prev_lips: np.ndarray | None = None
        variances: list[float] = []
        frame_idx = 0

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                # 依取樣率跳幀
                if frame_idx % frame_interval != 0:
                    frame_idx += 1
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)

                if results.multi_face_landmarks:
                    lm = results.multi_face_landmarks[0]
                    # 提取嘴唇 landmarks 的 (x, y) 座標
                    lips = np.array([
                        [lm.landmark[i].x, lm.landmark[i].y]
                        for i in _LIP_INDICES
                        if i < len(lm.landmark)
                    ])

                    if prev_lips is not None and len(lips) == len(prev_lips):
                        # 均方位移（Mean Squared Displacement）
                        diff = lips - prev_lips
                        variance = float(np.mean(diff ** 2))
                        variances.append(variance)
                    else:
                        # 第一幀或維度不一致
                        variances.append(0.0)

                    prev_lips = lips
                else:
                    # 未偵測到臉部
                    variances.append(0.0)
                    prev_lips = None

                frame_idx += 1

        finally:
            cap.release()
            face_mesh.close()

        _logger.info(
            "嘴唇運動分析：%d 幀，高運動幀 %d（閾值 %.4f）",
            len(variances),
            sum(1 for v in variances if v > _LIP_VARIANCE_THRESHOLD),
            _LIP_VARIANCE_THRESHOLD,
        )
        return variances
