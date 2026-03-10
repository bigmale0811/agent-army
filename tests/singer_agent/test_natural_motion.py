# -*- coding: utf-8 -*-
"""
Singer V3.1 自然動作引擎（NaturalMotionEngine）測試。

測試覆蓋：
- 基本幀數生成（正常、零時長、負時長、無效 fps）
- 預設基礎表情（neutral 全零）
- 可複現性（固定 seed 產出相同序列）
- 眨眼機制（存在、峰值、三角波形、返回零）
- 頭部運動（俯仰、偏航、翻滾幅度）
- 基礎表情疊加（smile 保留、head_pitch 偏移累加）
- 自訂配置（眨眼間隔、頭部幅度）
- get_audio_duration_seconds（mock ffprobe、失敗處理）
"""

import math
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.singer_agent.audio_preprocessor import LivePortraitExpression
from src.singer_agent.natural_motion import (
    DEFAULT_MOTION_CONFIG,
    BlinkEvent,
    NaturalMotionEngine,
    get_audio_duration_seconds,
)


# ─────────────────────────────────────────────────
# 輔助函式
# ─────────────────────────────────────────────────

def _make_engine(seed: int = 42, config: dict | None = None) -> NaturalMotionEngine:
    """建立固定 seed 的引擎，減少測試重複程式碼。"""
    return NaturalMotionEngine(seed=seed, config=config)


# ─────────────────────────────────────────────────
# 基本生成測試
# ─────────────────────────────────────────────────

class TestGenerateSequenceBasic:
    """generate_sequence 基本行為測試。"""

    def test_generate_sequence_returns_correct_frame_count(self):
        """正常時長應回傳 duration × fps 幀數。"""
        engine = _make_engine()
        # 5 秒 × 10 fps = 50 幀
        frames = engine.generate_sequence(duration_seconds=5.0, fps=10)
        assert len(frames) == 50

    def test_generate_sequence_frame_count_rounds_down(self):
        """浮點秒數應向下取整（int(duration * fps)）。"""
        engine = _make_engine()
        # 3.9 秒 × 10 fps = int(39.0) = 39 幀
        frames = engine.generate_sequence(duration_seconds=3.9, fps=10)
        assert len(frames) == 39

    def test_generate_sequence_minimum_one_frame(self):
        """極短時長（大於 0）應至少回傳 1 幀。"""
        engine = _make_engine()
        # 0.001 秒 × 10 fps → int(0.01) = 0，但 max(1, 0) = 1
        frames = engine.generate_sequence(duration_seconds=0.001, fps=10)
        assert len(frames) == 1

    def test_generate_sequence_empty_for_zero_duration(self):
        """時長為 0 應回傳空列表。"""
        engine = _make_engine()
        frames = engine.generate_sequence(duration_seconds=0.0, fps=10)
        assert frames == []

    def test_generate_sequence_negative_duration_returns_empty(self):
        """負時長應回傳空列表（不拋例外）。"""
        engine = _make_engine()
        frames = engine.generate_sequence(duration_seconds=-5.0, fps=10)
        assert frames == []

    def test_generate_sequence_raises_on_invalid_fps(self):
        """fps <= 0 應拋出 ValueError。"""
        engine = _make_engine()
        with pytest.raises(ValueError, match="fps"):
            engine.generate_sequence(duration_seconds=5.0, fps=0)

    def test_generate_sequence_raises_on_negative_fps(self):
        """負數 fps 應同樣拋出 ValueError。"""
        engine = _make_engine()
        with pytest.raises(ValueError, match="fps"):
            engine.generate_sequence(duration_seconds=5.0, fps=-1)

    def test_generate_sequence_returns_list_of_liveportrait_expression(self):
        """回傳列表中每個元素都必須是 LivePortraitExpression 實例。"""
        engine = _make_engine()
        frames = engine.generate_sequence(duration_seconds=2.0, fps=10)
        assert all(isinstance(f, LivePortraitExpression) for f in frames)

    def test_generate_sequence_different_fps_scales_frame_count(self):
        """相同時長但不同 fps，幀數應等比縮放。"""
        engine_a = NaturalMotionEngine(seed=0)
        engine_b = NaturalMotionEngine(seed=0)
        frames_10 = engine_a.generate_sequence(duration_seconds=3.0, fps=10)
        frames_25 = engine_b.generate_sequence(duration_seconds=3.0, fps=25)
        assert len(frames_10) == 30
        assert len(frames_25) == 75


# ─────────────────────────────────────────────────
# 預設基礎表情測試
# ─────────────────────────────────────────────────

class TestDefaultBaseExpression:
    """未傳入 base_expression 時，預設為全零 neutral 表情。"""

    def test_default_base_expression_is_neutral(self):
        """無 base_expression 時，smile 應為 0.0（neutral）。"""
        engine = _make_engine()
        frames = engine.generate_sequence(duration_seconds=1.0, fps=10)
        # smile 始終等於 base.smile，預設為 0
        for frame in frames:
            assert frame.smile == 0.0

    def test_default_base_expression_head_pitch_is_zero_base(self):
        """預設基礎的 head_pitch 起點為 0，動作疊加後應在 ±amp 範圍內。"""
        cfg = DEFAULT_MOTION_CONFIG
        amp = cfg["head_pitch_amp"]
        engine = _make_engine()
        frames = engine.generate_sequence(duration_seconds=10.0, fps=10)
        for frame in frames:
            assert abs(frame.head_pitch) <= amp + 1e-6


# ─────────────────────────────────────────────────
# 可複現性測試
# ─────────────────────────────────────────────────

class TestReproducibility:
    """固定 seed 可複現相同序列。"""

    def test_same_seed_produces_same_sequence(self):
        """相同 seed 兩次呼叫應回傳完全相同的序列。"""
        frames_a = NaturalMotionEngine(seed=7).generate_sequence(10.0, fps=10)
        frames_b = NaturalMotionEngine(seed=7).generate_sequence(10.0, fps=10)
        assert len(frames_a) == len(frames_b)
        for fa, fb in zip(frames_a, frames_b):
            assert fa == fb

    def test_different_seed_produces_different_sequence(self):
        """不同 seed 應產生不同序列（至少有一幀不同）。"""
        frames_a = NaturalMotionEngine(seed=1).generate_sequence(10.0, fps=10)
        frames_b = NaturalMotionEngine(seed=2).generate_sequence(10.0, fps=10)
        # 用 head_yaw 或 head_pitch 差異判斷（眨眼時機不同也足夠）
        differs = any(fa.head_yaw != fb.head_yaw for fa, fb in zip(frames_a, frames_b))
        assert differs, "不同 seed 應產生不同的頭部運動相位"

    def test_seed_none_does_not_crash(self):
        """seed=None（隨機模式）不應拋例外。"""
        engine = NaturalMotionEngine(seed=None)
        frames = engine.generate_sequence(2.0, fps=10)
        assert len(frames) == 20


# ─────────────────────────────────────────────────
# 眨眼測試
# ─────────────────────────────────────────────────

class TestBlinkBehavior:
    """眨眼（wink 通道）的正確性測試。"""

    def test_blinks_exist_in_sequence(self):
        """10 秒序列中至少應有一幀的 wink > 0（發生眨眼）。"""
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=10.0, fps=10)
        wink_values = [f.wink for f in frames]
        assert any(v > 0 for v in wink_values), "10 秒內應至少有一次眨眼"

    def test_blink_peak_value_matches_config(self):
        """眨眼峰值 wink 應不超過 config 設定的 blink_peak_wink。"""
        peak = DEFAULT_MOTION_CONFIG["blink_peak_wink"]
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=30.0, fps=10)
        max_wink = max(f.wink for f in frames)
        # 允許浮點誤差
        assert max_wink <= peak + 1e-6

    def test_blink_triangular_shape(self):
        """
        三角波形驗證：在眨眼過程中，wink 值應先上升後下降。
        使用已知眨眼事件直接呼叫 _blink_value_at 測試波形形狀。
        """
        cfg = DEFAULT_MOTION_CONFIG
        blink = BlinkEvent(start_time=1.0, duration=0.2)

        # 前半段（0.0 ~ 0.5 進度）：wink 從 0 升到 peak
        t_quarter = 1.0 + 0.05      # 進度 = 0.25 → wink = peak × 0.5
        v_quarter = NaturalMotionEngine._blink_value_at(t_quarter, [blink], cfg)

        t_mid = 1.0 + 0.1           # 進度 = 0.5 → wink = peak（峰值）
        v_mid = NaturalMotionEngine._blink_value_at(t_mid, [blink], cfg)

        # 後半段（0.5 ~ 1.0 進度）：wink 從 peak 降到 0
        t_three_quarter = 1.0 + 0.15  # 進度 = 0.75 → wink = peak × 0.5
        v_three_quarter = NaturalMotionEngine._blink_value_at(
            t_three_quarter, [blink], cfg,
        )

        t_end = 1.0 + 0.2           # 進度 = 1.0 → 恰好離開眨眼範圍
        v_end = NaturalMotionEngine._blink_value_at(t_end, [blink], cfg)

        peak = cfg["blink_peak_wink"]
        # 上升階段驗證
        assert v_quarter == pytest.approx(peak * 0.5, abs=1e-6)
        assert v_mid == pytest.approx(peak, abs=1e-6)
        # 下降階段驗證
        assert v_three_quarter == pytest.approx(peak * 0.5, abs=1e-6)
        # 眨眼結束後回到 0
        assert v_end == pytest.approx(0.0, abs=1e-6)

    def test_blink_value_zero_outside_blink(self):
        """眨眼範圍外的時間點 wink 應為 0。"""
        cfg = DEFAULT_MOTION_CONFIG
        blink = BlinkEvent(start_time=5.0, duration=0.2)

        v_before = NaturalMotionEngine._blink_value_at(4.9, [blink], cfg)
        v_after = NaturalMotionEngine._blink_value_at(5.21, [blink], cfg)

        assert v_before == 0.0
        assert v_after == 0.0

    def test_no_permanent_blink(self):
        """眨眼後 wink 應回到 0（不能永久停在非零值）。"""
        engine = _make_engine(seed=0)
        # 長序列確保有多次眨眼
        frames = engine.generate_sequence(duration_seconds=20.0, fps=10)
        wink_values = [f.wink for f in frames]

        # 若有眨眼發生，必定存在 wink == 0 的幀（眨眼之間）
        has_blink = any(v > 0 for v in wink_values)
        if has_blink:
            assert any(v == 0.0 for v in wink_values), "眨眼之間應存在 wink=0 的幀"

    def test_blink_value_at_start_of_blink_is_zero(self):
        """眨眼開始的瞬間（progress=0）wink 應為 0（從閉到開）。"""
        cfg = DEFAULT_MOTION_CONFIG
        blink = BlinkEvent(start_time=2.0, duration=0.4)
        v = NaturalMotionEngine._blink_value_at(2.0, [blink], cfg)
        assert v == pytest.approx(0.0, abs=1e-6)

    def test_multiple_blinks_no_overlap(self):
        """_generate_blinks 產生的眨眼事件不應重疊（下一次的 start_time > 上一次的 end_time）。"""
        engine = _make_engine(seed=99)
        blinks = engine._generate_blinks(30.0)
        for i in range(1, len(blinks)):
            prev_end = blinks[i - 1].start_time + blinks[i - 1].duration
            # 眨眼間隔最小值 (blink_interval_min=2.5) 遠大於眨眼持續時間 (0.2s)
            # 因此相鄰眨眼不應重疊
            assert blinks[i].start_time >= prev_end - 1e-6

    def test_blink_duration_above_minimum(self):
        """每次眨眼持續時間應 >= 0.1（強制最小值保護）。"""
        engine = _make_engine(seed=77)
        blinks = engine._generate_blinks(60.0)
        for blink in blinks:
            assert blink.duration >= 0.1


# ─────────────────────────────────────────────────
# 頭部運動測試
# ─────────────────────────────────────────────────

class TestHeadMovement:
    """頭部俯仰/偏航/翻滾的正弦波動作驗證。"""

    def test_head_pitch_varies_sinusoidally(self):
        """head_pitch 在多幀序列中應有變化（非定值）。"""
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=10.0, fps=10)
        pitches = [f.head_pitch for f in frames]
        # 最大值與最小值之差應接近 2×amplitude
        pitch_range = max(pitches) - min(pitches)
        amp = DEFAULT_MOTION_CONFIG["head_pitch_amp"]
        # 10 秒 > 一個完整週期（4.0s），應能看到足夠的變化
        assert pitch_range > 0.0, "head_pitch 應隨時間變化"
        assert pitch_range <= 2 * amp + 1e-6, "head_pitch 變化幅度不應超過 2×amp"

    def test_head_yaw_varies(self):
        """head_yaw 在序列中應有變化。"""
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=10.0, fps=10)
        yaws = [f.head_yaw for f in frames]
        yaw_range = max(yaws) - min(yaws)
        assert yaw_range > 0.0, "head_yaw 應隨時間變化"

    def test_head_roll_amplitude_within_config(self):
        """head_roll 絕對值不應超過 config 設定的幅度。"""
        amp = DEFAULT_MOTION_CONFIG["head_roll_amp"]
        engine = _make_engine(seed=42)
        # 使用 base_expression 全零確保只有動作偏移
        frames = engine.generate_sequence(
            duration_seconds=20.0,
            fps=10,
            base_expression=LivePortraitExpression(),
        )
        for frame in frames:
            assert abs(frame.head_roll) <= amp + 1e-6

    def test_head_pitch_amplitude_within_config(self):
        """head_pitch 絕對值不應超過 config 設定的幅度。"""
        amp = DEFAULT_MOTION_CONFIG["head_pitch_amp"]
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(
            duration_seconds=20.0,
            fps=10,
            base_expression=LivePortraitExpression(),
        )
        for frame in frames:
            assert abs(frame.head_pitch) <= amp + 1e-6

    def test_head_yaw_amplitude_within_config(self):
        """head_yaw 絕對值不應超過 config 設定的幅度。"""
        amp = DEFAULT_MOTION_CONFIG["head_yaw_amp"]
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(
            duration_seconds=20.0,
            fps=10,
            base_expression=LivePortraitExpression(),
        )
        for frame in frames:
            assert abs(frame.head_yaw) <= amp + 1e-6

    def test_phase_offsets_are_unique(self):
        """各動作通道的相位偏移應各自獨立（不全部相同）。"""
        engine = _make_engine(seed=123)
        phases = engine._generate_phase_offsets()
        # 6 個通道應有各自的相位值（極端情況下才會碰巧相等）
        phase_values = list(phases.values())
        # 至少有兩個不同的值（排除全部相同的情況）
        assert len(set(round(v, 6) for v in phase_values)) > 1


# ─────────────────────────────────────────────────
# 基礎表情疊加測試
# ─────────────────────────────────────────────────

class TestBaseExpressionOverlay:
    """base_expression 的保留與疊加邏輯。"""

    def test_base_expression_smile_preserved(self):
        """base_expression.smile 應完整保留到每一幀（不被動作覆蓋）。"""
        base = LivePortraitExpression(smile=8.5)
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(
            duration_seconds=5.0, fps=10, base_expression=base,
        )
        for frame in frames:
            assert frame.smile == pytest.approx(8.5), "smile 應等於 base_expression.smile"

    def test_base_expression_offsets_applied_to_head_pitch(self):
        """base head_pitch 偏移應疊加在動作正弦波之上。"""
        base_pitch = 5.0
        base = LivePortraitExpression(head_pitch=base_pitch)
        engine_a = NaturalMotionEngine(seed=42)
        engine_b = NaturalMotionEngine(seed=42)

        frames_with_base = engine_a.generate_sequence(
            duration_seconds=5.0, fps=10, base_expression=base,
        )
        frames_neutral = engine_b.generate_sequence(
            duration_seconds=5.0, fps=10,
            base_expression=LivePortraitExpression(),
        )

        # 每幀的 head_pitch 應等於 neutral 版本加上 base_pitch
        for fb, fn in zip(frames_with_base, frames_neutral):
            assert fb.head_pitch == pytest.approx(fn.head_pitch + base_pitch, abs=1e-6)

    def test_base_expression_wink_offset_applied(self):
        """base_expression.wink 應疊加在眨眼 wink 之上。"""
        base_wink = 3.0
        base = LivePortraitExpression(wink=base_wink)
        engine_a = NaturalMotionEngine(seed=42)
        engine_b = NaturalMotionEngine(seed=42)

        frames_with_base = engine_a.generate_sequence(
            duration_seconds=5.0, fps=10, base_expression=base,
        )
        frames_neutral = engine_b.generate_sequence(
            duration_seconds=5.0, fps=10,
            base_expression=LivePortraitExpression(),
        )

        # 每幀的 wink 差值應恰好為 base_wink
        for fb, fn in zip(frames_with_base, frames_neutral):
            assert fb.wink == pytest.approx(fn.wink + base_wink, abs=1e-6)

    def test_base_expression_eyeball_direction_x_offset(self):
        """base_expression.eyeball_direction_x 應疊加在眼球動作之上。"""
        base_eye_x = 2.5
        base = LivePortraitExpression(eyeball_direction_x=base_eye_x)
        engine_a = NaturalMotionEngine(seed=10)
        engine_b = NaturalMotionEngine(seed=10)

        frames_with_base = engine_a.generate_sequence(
            duration_seconds=3.0, fps=10, base_expression=base,
        )
        frames_neutral = engine_b.generate_sequence(
            duration_seconds=3.0, fps=10,
            base_expression=LivePortraitExpression(),
        )

        for fb, fn in zip(frames_with_base, frames_neutral):
            assert fb.eyeball_direction_x == pytest.approx(
                fn.eyeball_direction_x + base_eye_x, abs=1e-6,
            )

    def test_base_expression_all_fields_composite(self):
        """多個 base_expression 欄位同時疊加時，smile 保留、其餘偏移累加。"""
        base = LivePortraitExpression(
            smile=-3.0,
            eyebrow=-5.0,
            head_pitch=3.0,
        )
        engine = _make_engine(seed=55)
        frames = engine.generate_sequence(
            duration_seconds=3.0, fps=10, base_expression=base,
        )
        # smile 固定保留 -3.0
        for frame in frames:
            assert frame.smile == pytest.approx(-3.0)
        # head_pitch 應在 base_pitch ± amp 範圍內（正弦波疊加）
        amp = DEFAULT_MOTION_CONFIG["head_pitch_amp"]
        for frame in frames:
            assert abs(frame.head_pitch - 3.0) <= amp + 1e-6


# ─────────────────────────────────────────────────
# 自訂配置測試
# ─────────────────────────────────────────────────

class TestCustomConfig:
    """自訂 config 覆蓋預設值的行為。"""

    def test_custom_blink_interval_min_max(self):
        """自訂極短眨眼間隔應讓眨眼更頻繁出現。"""
        # 設定極短間隔（0.5~1.0 秒），10 秒內應有多次眨眼
        custom_cfg = {
            "blink_interval_min": 0.5,
            "blink_interval_max": 1.0,
        }
        engine = NaturalMotionEngine(seed=42, config=custom_cfg)
        blinks = engine._generate_blinks(10.0)
        # 10 秒 / 1.0 秒間隔 ≈ 至少 5 次眨眼
        assert len(blinks) >= 5

    def test_custom_blink_interval_long_reduces_blinks(self):
        """自訂極長眨眼間隔（60~120 秒），5 秒內應無眨眼。"""
        custom_cfg = {
            "blink_interval_min": 60.0,
            "blink_interval_max": 120.0,
        }
        engine = NaturalMotionEngine(seed=42, config=custom_cfg)
        blinks = engine._generate_blinks(5.0)
        # 5 秒內第一次眨眼就已超出範圍（第一次在 1-3 秒後，下次在 60+ 秒後）
        # 但第一次眨眼可能在 5 秒內，最多 1 次
        assert len(blinks) <= 1

    def test_custom_head_pitch_amplitude(self):
        """自訂 head_pitch_amp 應改變頭部俯仰幅度。"""
        custom_amp = 10.0
        custom_cfg = {"head_pitch_amp": custom_amp}
        engine = NaturalMotionEngine(seed=42, config=custom_cfg)
        frames = engine.generate_sequence(
            duration_seconds=10.0,
            fps=10,
            base_expression=LivePortraitExpression(),
        )
        pitches = [f.head_pitch for f in frames]
        max_pitch = max(abs(p) for p in pitches)
        # 自訂幅度 10.0，最大值應接近（但不超過）10.0
        assert max_pitch <= custom_amp + 1e-6
        # 並且明顯大於預設幅度 1.8
        assert max_pitch > DEFAULT_MOTION_CONFIG["head_pitch_amp"]

    def test_custom_blink_peak_wink(self):
        """自訂 blink_peak_wink 應改變眨眼最大值。"""
        custom_peak = 5.0
        custom_cfg = {
            "blink_peak_wink": custom_peak,
            "blink_interval_min": 0.5,   # 縮短間隔確保有眨眼
            "blink_interval_max": 1.0,
        }
        engine = NaturalMotionEngine(seed=42, config=custom_cfg)
        frames = engine.generate_sequence(
            duration_seconds=10.0,
            fps=10,
            base_expression=LivePortraitExpression(),
        )
        max_wink = max(f.wink for f in frames)
        # 峰值應不超過自訂值
        assert max_wink <= custom_peak + 1e-6
        # 且峰值應明顯低於預設的 12.0
        assert max_wink < DEFAULT_MOTION_CONFIG["blink_peak_wink"]

    def test_config_partial_override_preserves_defaults(self):
        """部分覆蓋 config 時，未指定的鍵應保留預設值。"""
        custom_cfg = {"head_roll_amp": 5.0}
        engine = NaturalMotionEngine(seed=42, config=custom_cfg)
        # 自訂 head_roll_amp
        assert engine._config["head_roll_amp"] == 5.0
        # 其他鍵應保留預設
        assert engine._config["head_pitch_amp"] == DEFAULT_MOTION_CONFIG["head_pitch_amp"]
        assert engine._config["blink_peak_wink"] == DEFAULT_MOTION_CONFIG["blink_peak_wink"]

    def test_config_none_uses_all_defaults(self):
        """config=None 時，所有參數應與 DEFAULT_MOTION_CONFIG 完全一致。"""
        engine = NaturalMotionEngine(seed=42, config=None)
        assert engine._config == DEFAULT_MOTION_CONFIG


# ─────────────────────────────────────────────────
# BlinkEvent 資料結構測試
# ─────────────────────────────────────────────────

class TestBlinkEvent:
    """BlinkEvent 資料類別基本測試。"""

    def test_blink_event_is_immutable(self):
        """BlinkEvent 為 frozen dataclass，不允許修改欄位。"""
        blink = BlinkEvent(start_time=1.0, duration=0.2)
        with pytest.raises(Exception):
            blink.start_time = 2.0  # type: ignore[misc]

    def test_blink_event_fields(self):
        """BlinkEvent 的欄位值應正確儲存。"""
        blink = BlinkEvent(start_time=3.5, duration=0.15)
        assert blink.start_time == 3.5
        assert blink.duration == 0.15


# ─────────────────────────────────────────────────
# DEFAULT_MOTION_CONFIG 完整性測試
# ─────────────────────────────────────────────────

class TestDefaultMotionConfig:
    """驗證 DEFAULT_MOTION_CONFIG 的結構與數值合理性。"""

    EXPECTED_KEYS = [
        "blink_interval_min",
        "blink_interval_max",
        "blink_duration",
        "blink_duration_jitter",
        "blink_peak_wink",
        "head_pitch_amp",
        "head_pitch_period",
        "head_yaw_amp",
        "head_yaw_period",
        "head_roll_amp",
        "head_roll_period",
        "eyebrow_amp",
        "eyebrow_period",
        "eye_x_amp",
        "eye_x_period",
        "eye_y_amp",
        "eye_y_period",
    ]

    def test_all_expected_keys_present(self):
        """所有必要配置鍵都應存在。"""
        for key in self.EXPECTED_KEYS:
            assert key in DEFAULT_MOTION_CONFIG, f"缺少配置鍵：{key}"

    def test_blink_interval_min_less_than_max(self):
        """眨眼最短間隔應小於最長間隔。"""
        cfg = DEFAULT_MOTION_CONFIG
        assert cfg["blink_interval_min"] < cfg["blink_interval_max"]

    def test_all_amplitudes_are_positive(self):
        """所有幅度值應為正數。"""
        cfg = DEFAULT_MOTION_CONFIG
        for key in ["head_pitch_amp", "head_yaw_amp", "head_roll_amp",
                    "eyebrow_amp", "eye_x_amp", "eye_y_amp"]:
            assert cfg[key] > 0, f"{key} 應為正數"

    def test_all_periods_are_positive(self):
        """所有週期值應為正數。"""
        cfg = DEFAULT_MOTION_CONFIG
        for key in ["head_pitch_period", "head_yaw_period", "head_roll_period",
                    "eyebrow_period", "eye_x_period", "eye_y_period"]:
            assert cfg[key] > 0, f"{key} 應為正數"

    def test_blink_peak_wink_is_positive(self):
        """blink_peak_wink 應為正數。"""
        assert DEFAULT_MOTION_CONFIG["blink_peak_wink"] > 0


# ─────────────────────────────────────────────────
# get_audio_duration_seconds 測試（mock ffprobe）
# ─────────────────────────────────────────────────

class TestGetAudioDurationSeconds:
    """get_audio_duration_seconds 的 ffprobe subprocess 測試。

    注意：natural_motion.py 在函式內部才 import subprocess，
    因此需要 patch 標準函式庫的 subprocess.run（所有呼叫者共用同一個物件）。
    """

    @patch("subprocess.run")
    def test_get_audio_duration_mocked_success(self, mock_run):
        """正常情況下應回傳 ffprobe 輸出的浮點秒數。"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="183.456789\n",
            stderr="",
        )
        result = get_audio_duration_seconds("/fake/audio.mp3")
        assert result == pytest.approx(183.456789, abs=1e-4)
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_audio_duration_calls_ffprobe(self, mock_run):
        """應呼叫 ffprobe 命令，且包含 format=duration 參數。"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="60.0\n",
            stderr="",
        )
        get_audio_duration_seconds("/path/to/song.mp3")
        call_args = mock_run.call_args[0][0]
        # 確認命令中包含 ffprobe 與 duration 相關參數
        cmd_str = " ".join(call_args)
        assert "ffprobe" in cmd_str
        assert "duration" in cmd_str

    @patch("subprocess.run")
    def test_get_audio_duration_ffprobe_nonzero_exit_raises(self, mock_run):
        """ffprobe 回傳非零 exit code 時應拋出 RuntimeError。"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="No such file or directory",
        )
        with pytest.raises(RuntimeError, match="ffprobe"):
            get_audio_duration_seconds("/nonexistent/audio.mp3")

    @patch("subprocess.run")
    def test_get_audio_duration_ffprobe_failure_includes_exit_code(self, mock_run):
        """錯誤訊息應包含 exit code 資訊。"""
        mock_run.return_value = MagicMock(
            returncode=255,
            stdout="",
            stderr="fatal error",
        )
        with pytest.raises(RuntimeError, match="255"):
            get_audio_duration_seconds("/bad/path.mp3")

    @patch("subprocess.run")
    def test_get_audio_duration_invalid_output_raises(self, mock_run):
        """ffprobe 輸出非數字時應拋出 RuntimeError（ValueError 包裝）。"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not_a_number\n",
            stderr="",
        )
        with pytest.raises(RuntimeError):
            get_audio_duration_seconds("/audio.mp3")

    @patch("subprocess.run")
    def test_get_audio_duration_timeout_raises(self, mock_run):
        """ffprobe 超時應拋出 RuntimeError（TimeoutExpired 包裝）。"""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="ffprobe", timeout=30,
        )
        with pytest.raises(RuntimeError, match="無法取得音訊時長"):
            get_audio_duration_seconds("/slow/audio.mp3")

    @patch("subprocess.run")
    def test_get_audio_duration_strips_whitespace(self, mock_run):
        """ffprobe 輸出帶有首尾空白時應正確解析。"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  245.0  \n",
            stderr="",
        )
        result = get_audio_duration_seconds("/audio.mp3")
        assert result == pytest.approx(245.0)

    @patch("subprocess.run")
    def test_get_audio_duration_passes_audio_path(self, mock_run):
        """音訊路徑應正確傳入 ffprobe 命令。"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="90.0\n",
            stderr="",
        )
        audio_path = "/my/project/song.wav"
        get_audio_duration_seconds(audio_path)
        call_args = mock_run.call_args[0][0]
        cmd_str = " ".join(call_args)
        assert audio_path in cmd_str


# ─────────────────────────────────────────────────
# 輸出欄位精度測試
# ─────────────────────────────────────────────────

class TestOutputPrecision:
    """驗證 _compute_frame 的輸出格式。"""

    def test_frame_values_are_rounded_to_2_decimal_places(self):
        """
        _compute_frame 輸出的欄位應被 round(..., 2) 處理，
        驗證最多 2 位小數（不是硬性保證 2 位，而是不超過 2 位有效小數位）。
        """
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=5.0, fps=10)
        for frame in frames:
            for field_name in ["eyebrow", "wink", "eyeball_direction_x",
                               "eyeball_direction_y", "head_pitch", "head_yaw", "head_roll"]:
                val = getattr(frame, field_name)
                # 驗證 round(val, 2) 等於原始值（即已被截斷到 2 位小數）
                assert round(val, 2) == pytest.approx(val, abs=1e-9), (
                    f"{field_name}={val} 未被四捨五入到 2 位小數"
                )

    def test_smile_not_rounded(self):
        """smile 欄位直接來自 base.smile，不參與動作運算，應保留原始值。"""
        base = LivePortraitExpression(smile=8.123456)
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(
            duration_seconds=1.0, fps=10, base_expression=base,
        )
        for frame in frames:
            assert frame.smile == pytest.approx(8.123456)


# ─────────────────────────────────────────────────
# 眼球運動測試
# ─────────────────────────────────────────────────

class TestEyeballMovement:
    """眼球水平/垂直方向動作驗證。"""

    def test_eyeball_direction_x_varies(self):
        """eyeball_direction_x 應在序列中產生變化。"""
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=10.0, fps=10)
        x_values = [f.eyeball_direction_x for f in frames]
        assert max(x_values) - min(x_values) > 0.0

    def test_eyeball_direction_y_varies(self):
        """eyeball_direction_y 應在序列中產生變化。"""
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=10.0, fps=10)
        y_values = [f.eyeball_direction_y for f in frames]
        assert max(y_values) - min(y_values) > 0.0

    def test_eyeball_x_amplitude_within_config(self):
        """eyeball_direction_x 的幅度不應超過 config 設定值。"""
        amp = DEFAULT_MOTION_CONFIG["eye_x_amp"]
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(
            duration_seconds=20.0, fps=10,
            base_expression=LivePortraitExpression(),
        )
        for frame in frames:
            assert abs(frame.eyeball_direction_x) <= amp + 1e-6

    def test_eyeball_y_amplitude_within_config(self):
        """eyeball_direction_y 的幅度不應超過 config 設定值。"""
        amp = DEFAULT_MOTION_CONFIG["eye_y_amp"]
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(
            duration_seconds=20.0, fps=10,
            base_expression=LivePortraitExpression(),
        )
        for frame in frames:
            assert abs(frame.eyeball_direction_y) <= amp + 1e-6


# ─────────────────────────────────────────────────
# 眉毛動作測試
# ─────────────────────────────────────────────────

class TestEyebrowMovement:
    """眉毛動作正弦波驗證。"""

    def test_eyebrow_varies_in_sequence(self):
        """eyebrow 值在序列中應有變化。"""
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(duration_seconds=10.0, fps=10)
        eyebrow_values = [f.eyebrow for f in frames]
        assert max(eyebrow_values) - min(eyebrow_values) > 0.0

    def test_eyebrow_amplitude_within_config(self):
        """eyebrow 的幅度不應超過 config 設定值。"""
        amp = DEFAULT_MOTION_CONFIG["eyebrow_amp"]
        engine = _make_engine(seed=42)
        frames = engine.generate_sequence(
            duration_seconds=20.0, fps=10,
            base_expression=LivePortraitExpression(),
        )
        for frame in frames:
            assert abs(frame.eyebrow) <= amp + 1e-6
