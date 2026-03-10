# -*- coding: utf-8 -*-
"""
自然動作引擎（Singer V3.1）。

生成逐幀 LivePortrait 表情參數序列，模擬人類自然微動：
- 隨機眨眼（每 2.5-6 秒一次，持續 ~0.2 秒）
- 頭部柔和擺動（正弦波微動，± 2-3 度）
- 眉毛微動（輕微上下波動）
- 眼球自然掃視（緩慢漂移）

搭配 LivePortrait 的 retarget 功能，將靜態角色圖片
轉換為有自然人體動態的影片幀序列。

用法：
    from src.singer_agent.natural_motion import NaturalMotionEngine
    from src.singer_agent.audio_preprocessor import LivePortraitExpression

    engine = NaturalMotionEngine(seed=42)
    frames = engine.generate_sequence(
        duration_seconds=180.0,
        fps=10,
        base_expression=LivePortraitExpression(smile=8.0, eyebrow=3.0),
    )
    # frames: list[LivePortraitExpression], 每幀一個
"""

import logging
import math
import random
from dataclasses import dataclass

from src.singer_agent.audio_preprocessor import LivePortraitExpression

_logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────
# 眨眼事件資料結構
# ─────────────────────────────────────────────────

@dataclass(frozen=True)
class BlinkEvent:
    """
    眨眼事件（不可變物件）。

    Attributes:
        start_time: 眨眼開始時間（秒）
        duration: 眨眼持續時間（秒），通常 0.15-0.3 秒
    """

    start_time: float
    duration: float


# ─────────────────────────────────────────────────
# 預設動作參數
# ─────────────────────────────────────────────────

DEFAULT_MOTION_CONFIG: dict[str, float] = {
    # 眨眼
    "blink_interval_min": 2.5,      # 最短眨眼間隔（秒）
    "blink_interval_max": 6.0,      # 最長眨眼間隔（秒）
    "blink_duration": 0.2,          # 眨眼持續時間（秒）
    "blink_duration_jitter": 0.05,  # 持續時間隨機偏差（秒）
    "blink_peak_wink": 12.0,        # 眨眼峰值（LivePortrait wink 參數值）

    # 頭部擺動（正弦波）
    "head_pitch_amp": 1.8,          # 俯仰幅度（度）
    "head_pitch_period": 4.0,       # 俯仰週期（秒）
    "head_yaw_amp": 2.2,            # 左右幅度（度）
    "head_yaw_period": 5.5,         # 左右週期（秒）
    "head_roll_amp": 0.8,           # 傾斜幅度（度）
    "head_roll_period": 7.0,        # 傾斜週期（秒）

    # 眉毛
    "eyebrow_amp": 1.2,             # 眉毛幅度
    "eyebrow_period": 3.5,          # 眉毛週期（秒）

    # 眼球移動
    "eye_x_amp": 1.5,               # 水平幅度
    "eye_x_period": 6.0,            # 水平週期（秒）
    "eye_y_amp": 1.0,               # 垂直幅度
    "eye_y_period": 4.5,            # 垂直週期（秒）
}


# ─────────────────────────────────────────────────
# 自然動作引擎
# ─────────────────────────────────────────────────

class NaturalMotionEngine:
    """
    自然動作引擎。

    生成逐幀 LivePortrait 表情參數序列，
    模擬人類的自然微動（眨眼、頭部擺動、眉毛、眼球）。

    所有動作基於正弦波 + 隨機偏移，確保動作流暢自然。
    使用固定 seed 可複現相同的動作序列。

    Args:
        seed: 隨機種子（可選），用於複現性
        config: 動作參數配置（可選），覆蓋預設值
    """

    def __init__(
        self,
        seed: int | None = None,
        config: dict[str, float] | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._config: dict[str, float] = {
            **DEFAULT_MOTION_CONFIG,
            **(config or {}),
        }

    def generate_sequence(
        self,
        duration_seconds: float,
        fps: int = 10,
        base_expression: LivePortraitExpression | None = None,
    ) -> list[LivePortraitExpression]:
        """
        生成完整的自然動作幀序列。

        Args:
            duration_seconds: 影片總時長（秒）
            fps: 每秒幀數（預設 10，後續 FFmpeg 插值到 25fps）
            base_expression: 基礎表情（來自情緒映射），
                            自然動作會疊加在此基礎上

        Returns:
            逐幀 LivePortraitExpression 列表

        Raises:
            ValueError: fps <= 0
        """
        if duration_seconds <= 0:
            return []
        if fps <= 0:
            raise ValueError(f"fps 必須為正整數，收到：{fps}")

        if base_expression is None:
            base_expression = LivePortraitExpression()

        cfg = self._config

        # 預先生成眨眼事件時間表
        blinks = self._generate_blinks(duration_seconds)

        # 為每種動作生成隨機相位偏移（確保不同動作不同步）
        phases = self._generate_phase_offsets()

        total_frames = max(1, int(duration_seconds * fps))
        frames: list[LivePortraitExpression] = []

        _logger.info(
            "生成自然動作序列：%.1fs × %dfps = %d 幀，"
            "%d 次眨眼，基礎表情 smile=%.1f",
            duration_seconds, fps, total_frames,
            len(blinks), base_expression.smile,
        )

        for i in range(total_frames):
            t = i / fps
            frame = self._compute_frame(t, base_expression, blinks, phases, cfg)
            frames.append(frame)

        return frames

    def _compute_frame(
        self,
        t: float,
        base: LivePortraitExpression,
        blinks: list[BlinkEvent],
        phases: dict[str, float],
        cfg: dict[str, float],
    ) -> LivePortraitExpression:
        """計算單幀的表情參數。"""
        two_pi = 2 * math.pi

        # 眨眼（三角波形：快速閉合 → 快速張開）
        blink_wink = self._blink_value_at(t, blinks, cfg)

        # 頭部擺動（正弦波）
        head_pitch = base.head_pitch + cfg["head_pitch_amp"] * math.sin(
            two_pi * t / cfg["head_pitch_period"] + phases["pitch"],
        )
        head_yaw = base.head_yaw + cfg["head_yaw_amp"] * math.sin(
            two_pi * t / cfg["head_yaw_period"] + phases["yaw"],
        )
        head_roll = base.head_roll + cfg["head_roll_amp"] * math.sin(
            two_pi * t / cfg["head_roll_period"] + phases["roll"],
        )

        # 眉毛微動
        eyebrow = base.eyebrow + cfg["eyebrow_amp"] * math.sin(
            two_pi * t / cfg["eyebrow_period"] + phases["eyebrow"],
        )

        # 眼球掃視
        eye_x = base.eyeball_direction_x + cfg["eye_x_amp"] * math.sin(
            two_pi * t / cfg["eye_x_period"] + phases["eye_x"],
        )
        eye_y = base.eyeball_direction_y + cfg["eye_y_amp"] * math.sin(
            two_pi * t / cfg["eye_y_period"] + phases["eye_y"],
        )

        return LivePortraitExpression(
            smile=base.smile,
            eyebrow=round(eyebrow, 2),
            wink=round(blink_wink + base.wink, 2),
            eyeball_direction_x=round(eye_x, 2),
            eyeball_direction_y=round(eye_y, 2),
            head_pitch=round(head_pitch, 2),
            head_yaw=round(head_yaw, 2),
            head_roll=round(head_roll, 2),
        )

    def _generate_phase_offsets(self) -> dict[str, float]:
        """為每個動作通道生成隨機相位偏移。"""
        two_pi = 2 * math.pi
        return {
            "pitch": self._rng.uniform(0, two_pi),
            "yaw": self._rng.uniform(0, two_pi),
            "roll": self._rng.uniform(0, two_pi),
            "eyebrow": self._rng.uniform(0, two_pi),
            "eye_x": self._rng.uniform(0, two_pi),
            "eye_y": self._rng.uniform(0, two_pi),
        }

    def _generate_blinks(self, duration: float) -> list[BlinkEvent]:
        """
        生成隨機眨眼事件序列。

        人類正常眨眼頻率：每分鐘 15-20 次（每 3-4 秒一次），
        但在唱歌/表演時頻率較低（每 4-6 秒）。
        """
        cfg = self._config
        blinks: list[BlinkEvent] = []

        # 第一次眨眼在 1-3 秒之間
        t = self._rng.uniform(1.0, 3.0)

        while t < duration:
            blink_dur = max(
                0.1,
                cfg["blink_duration"]
                + self._rng.gauss(0, cfg["blink_duration_jitter"]),
            )
            blinks.append(BlinkEvent(start_time=t, duration=blink_dur))

            # 下次眨眼的間隔
            interval = self._rng.uniform(
                cfg["blink_interval_min"],
                cfg["blink_interval_max"],
            )
            t += interval

        return blinks

    @staticmethod
    def _blink_value_at(
        t: float,
        blinks: list[BlinkEvent],
        cfg: dict[str, float],
    ) -> float:
        """
        在時間 t 計算眨眼的 wink 值。

        使用三角波形：
        - 前半段：快速從 0 升到 peak（閉眼）
        - 後半段：快速從 peak 降到 0（張眼）

        Returns:
            wink 值（0 = 張眼，peak = 閉眼）
        """
        peak = cfg["blink_peak_wink"]

        for blink in blinks:
            end_time = blink.start_time + blink.duration
            if blink.start_time <= t <= end_time:
                progress = (t - blink.start_time) / blink.duration
                if progress < 0.5:
                    # 閉眼階段（0 → peak）
                    return peak * (progress * 2)
                else:
                    # 張眼階段（peak → 0）
                    return peak * ((1 - progress) * 2)

        return 0.0


def get_audio_duration_seconds(audio_path: str) -> float:
    """
    用 ffprobe 取得音訊檔案時長（秒）。

    Args:
        audio_path: 音訊檔案路徑

    Returns:
        時長（秒）

    Raises:
        RuntimeError: ffprobe 執行失敗
    """
    import subprocess

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(audio_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffprobe 失敗（exit={result.returncode}）：{result.stderr}"
            )
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"無法取得音訊時長：{exc}") from exc
