"""
音訊前處理模組：使用 Demucs 進行人聲分離 + 情緒映射。

解決問題：
1. 間奏/呼吸段嘴巴亂動 → Demucs 提取純人聲 + noise gate
2. 情緒標籤精準映射 → mood_hint → EDTalk --exp_type / LivePortrait 表情參數
VRAM：3-4GB（Demucs 隔離 subprocess，結束後自動釋放）。
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.singer_agent import config

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# V2.0 EDTalk 情緒映射表
# 中英文關鍵字 → EDTalk --exp_type 字串
# EDTalk 支援 8 種情緒：angry, contempt, disgusted, fear,
#                        happy, sad, surprised, neutral
# ─────────────────────────────────────────────────
EMOTION_EDTALK_MAP: dict[str, str] = {
    # === sad 家族 ===
    "sad": "sad",
    "melancholic": "sad",
    "sorrowful": "sad",
    "depressed": "sad",
    "nostalgic": "sad",
    "感傷": "sad",
    "悲傷": "sad",
    "難過": "sad",
    "低落": "sad",
    "憂鬱": "sad",
    "情緒低落": "sad",
    "懷舊": "sad",
    # === happy 家族 ===
    "happy": "happy",
    "excited": "happy",
    "energetic": "happy",
    "cheerful": "happy",
    "joyful": "happy",
    "開心": "happy",
    "快樂": "happy",
    "興奮": "happy",
    "歡樂": "happy",
    "愉快": "happy",
    # === angry 家族 ===
    "angry": "angry",
    "furious": "angry",
    "passionate": "angry",
    "intense": "angry",
    "憤怒": "angry",
    "生氣": "angry",
    "熱情": "angry",
    "激烈": "angry",
    # === surprised 家族 ===
    "surprised": "surprised",
    "shocked": "surprised",
    "amazed": "surprised",
    "驚訝": "surprised",
    "震驚": "surprised",
    "驚喜": "surprised",
    # === fear 家族 ===
    "fear": "fear",
    "scared": "fear",
    "anxious": "fear",
    "terrified": "fear",
    "恐懼": "fear",
    "害怕": "fear",
    "焦慮": "fear",
    # === disgusted 家族 ===
    "disgusted": "disgusted",
    "disgust": "disgusted",
    "厭惡": "disgusted",
    "噁心": "disgusted",
    # === contempt 家族 ===
    "contempt": "contempt",
    "scornful": "contempt",
    "disdain": "contempt",
    "蔑視": "contempt",
    "輕蔑": "contempt",
    # === neutral 家族 ===
    "neutral": "neutral",
    "calm": "neutral",
    "gentle": "neutral",
    "平靜": "neutral",
    "溫柔": "neutral",
    "中性": "neutral",
}

# 預設情緒：neutral（EDTalk 原生支援）
DEFAULT_EXP_TYPE = "neutral"


# ─────────────────────────────────────────────────
# V3.0 LivePortrait 表情參數映射
# 連續值控制，比 EDTalk 8 種離散情緒更精細
# ─────────────────────────────────────────────────

@dataclass(frozen=True)
class LivePortraitExpression:
    """
    LivePortrait 表情參數集（不可變物件）。

    數值範圍 -20 ~ 20，對應 delta_new keypoint 偏移量。
    正值通常代表加強該表情特徵。
    """
    smile: float = 0.0
    eyebrow: float = 0.0
    wink: float = 0.0
    eyeball_direction_x: float = 0.0
    eyeball_direction_y: float = 0.0
    head_pitch: float = 0.0
    head_yaw: float = 0.0
    head_roll: float = 0.0


# 情緒標籤 → LivePortrait 參數映射表
# key 使用 EDTalk 8 種情緒標籤（由 mood_to_exp_type() 產出）
EMOTION_LIVEPORTRAIT_MAP: dict[str, LivePortraitExpression] = {
    "happy": LivePortraitExpression(smile=8.0, eyebrow=3.0),
    "sad": LivePortraitExpression(smile=-3.0, eyebrow=-5.0, head_pitch=3.0),
    "angry": LivePortraitExpression(smile=-5.0, eyebrow=-8.0),
    "surprised": LivePortraitExpression(eyebrow=10.0, eyeball_direction_y=-3.0),
    "fear": LivePortraitExpression(eyebrow=6.0, eyeball_direction_y=-4.0, smile=-2.0),
    "contempt": LivePortraitExpression(smile=2.0, eyebrow=-3.0, wink=3.0),
    "disgusted": LivePortraitExpression(smile=-4.0, eyebrow=-6.0),
    "neutral": LivePortraitExpression(),
}


def mood_to_liveportrait_params(mood_hint: str) -> LivePortraitExpression:
    """
    從情緒描述推斷 LivePortrait 表情參數。

    先經由 mood_to_exp_type() 取得 EDTalk 標籤，
    再查表取得對應的 LivePortrait 連續表情參數。
    未匹配時 fallback 為 neutral（所有參數為 0）。

    Args:
        mood_hint: 情緒描述字串（如 "感傷、悲傷" 或 "sad, melancholic"）

    Returns:
        LivePortraitExpression 不可變物件
    """
    exp_type = mood_to_exp_type(mood_hint)
    expression = EMOTION_LIVEPORTRAIT_MAP.get(
        exp_type, EMOTION_LIVEPORTRAIT_MAP["neutral"],
    )
    _logger.info(
        "LivePortrait 映射：'%s' → exp_type='%s' → %s",
        mood_hint, exp_type, expression,
    )
    return expression

# V1.0 相容：保留 expression_scale 映射（供舊測試使用）
EMOTION_EXPRESSION_MAP: dict[str, float] = {
    "sad": 0.5, "melancholic": 0.5, "sorrowful": 0.4,
    "depressed": 0.4, "nostalgic": 0.6, "gentle": 0.7,
    "neutral": 1.0, "calm": 0.8, "happy": 1.3,
    "excited": 1.5, "energetic": 1.4, "angry": 1.2,
    "passionate": 1.3, "感傷": 0.5, "悲傷": 0.4,
    "低落": 0.4, "憂鬱": 0.4, "懷舊": 0.6,
    "溫柔": 0.7, "平靜": 0.8, "開心": 1.3,
    "興奮": 1.5, "熱情": 1.3, "憤怒": 1.2,
    "情緒低落": 0.4,
}
DEFAULT_EXPRESSION_SCALE = 1.0


def mood_to_exp_type(mood_hint: str) -> str:
    """
    從情緒描述推斷 EDTalk exp_type。

    掃描 mood_hint 中是否包含已知情緒關鍵字（中英文皆可），
    取第一個匹配的 EDTalk 表情類型。找不到則回傳 'neutral'。

    Args:
        mood_hint: 情緒描述字串（如 "感傷、悲傷" 或 "sad, melancholic"）

    Returns:
        EDTalk exp_type 字串（8 種之一）
    """
    if not mood_hint:
        return DEFAULT_EXP_TYPE

    lower = mood_hint.lower()
    for keyword, exp_type in EMOTION_EDTALK_MAP.items():
        if keyword in lower:
            _logger.info(
                "情緒映射：'%s' → exp_type='%s'（關鍵字：%s）",
                mood_hint, exp_type, keyword,
            )
            return exp_type

    _logger.info("未匹配情緒關鍵字，使用預設 exp_type='%s'", DEFAULT_EXP_TYPE)
    return DEFAULT_EXP_TYPE


def mood_to_expression_scale(mood_hint: str) -> float:
    """V1.0 相容函式：從情緒描述推斷 expression_scale。"""
    if not mood_hint:
        return DEFAULT_EXPRESSION_SCALE
    lower = mood_hint.lower()
    for keyword, scale in EMOTION_EXPRESSION_MAP.items():
        if keyword in lower:
            return scale
    return DEFAULT_EXPRESSION_SCALE


def separate_vocals(
    audio_path: Path,
    output_dir: Path,
    python_bin: str | None = None,
    dry_run: bool = False,
) -> Path:
    """
    使用 Demucs htdemucs 分離人聲軌道。

    Demucs 以獨立 subprocess 執行（使用 SadTalker venv 的 Python，
    確保有 torch + CUDA），結束後 VRAM 自動釋放。

    Args:
        audio_path: 原始音訊路徑（完整混音）
        output_dir: 輸出目錄
        python_bin: 執行 Demucs 的 Python 路徑（需含 torch + demucs）
        dry_run: 乾跑模式，直接回傳原始音訊

    Returns:
        人聲軌道 WAV 路徑（失敗時 fallback 為原始音訊）
    """
    if dry_run:
        _logger.info("dry_run 模式：跳過人聲分離")
        return audio_path

    # 使用 SadTalker 的 venv Python（確保有 torch + CUDA）
    if python_bin is None:
        sadtalker_python = config.SADTALKER_DIR / "venv" / "Scripts" / "python.exe"
        python_bin = str(sadtalker_python)

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        python_bin, "-m", "demucs",
        "--two-stems", "vocals",   # 只分離人聲 + 伴奏（速度最快）
        "-n", "htdemucs",          # 使用 htdemucs 模型（精度高、VRAM ~3GB）
        "-o", str(output_dir),
        str(audio_path),
    ]

    _logger.info("Demucs 人聲分離開始：%s", audio_path.name)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,  # 5 分鐘超時
        )
    except subprocess.TimeoutExpired:
        _logger.error("Demucs 超時（>300s），fallback 使用原始音訊")
        return audio_path
    except FileNotFoundError:
        _logger.error("Demucs Python 不存在：%s，fallback 使用原始音訊", python_bin)
        return audio_path

    if result.returncode != 0:
        _logger.error("Demucs 失敗（exit=%d）：%s", result.returncode, (result.stderr or "")[:500])
        _logger.warning("fallback 使用原始音訊")
        return audio_path

    # Demucs 輸出結構：{output_dir}/htdemucs/{stem}/vocals.wav
    vocals_path = output_dir / "htdemucs" / audio_path.stem / "vocals.wav"

    if not vocals_path.exists():
        _logger.warning("Demucs 輸出不存在：%s，fallback 使用原始音訊", vocals_path)
        return audio_path

    _logger.info("人聲分離完成：%s（%.1f MB）", vocals_path, vocals_path.stat().st_size / 1e6)
    return vocals_path


def apply_noise_gate(
    vocals_path: Path,
    output_path: Path,
    ffmpeg_bin: str | None = None,
    threshold: float = 0.01,
    dry_run: bool = False,
) -> Path:
    """
    對人聲軌道套用噪音閘門（ffmpeg agate 濾鏡）。

    將能量低於閾值的段落強制靜音，確保 SadTalker 在
    間奏、呼吸、殘留伴奏段落不會驅動嘴唇運動。

    必須在 Demucs 人聲分離之後使用，因為純人聲軌的噪音底層
    極低，noise gate 才能精準分離歌聲與靜音段。

    Args:
        vocals_path: 人聲軌道路徑（Demucs 輸出）
        output_path: 處理後的音訊路徑
        ffmpeg_bin: ffmpeg 執行檔路徑
        threshold: 閘門閾值（線性比例，0.01 ≈ -40dB）
        dry_run: 乾跑模式，直接回傳原始路徑

    Returns:
        處理後的音訊路徑（失敗時 fallback 為輸入路徑）
    """
    if dry_run:
        _logger.info("dry_run 模式：跳過噪音閘門")
        return vocals_path

    if ffmpeg_bin is None:
        ffmpeg_bin = str(config.FFMPEG_BIN)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # agate 參數說明：
    # threshold: 閘門觸發閾值（線性）
    # ratio: 衰減比（100 = 幾乎完全靜音）
    # range: 最大增益衰減 dB（-100 = 完全靜音）
    # attack: 開啟速度 ms（5ms 快速反應）
    # release: 關閉速度 ms（50ms 自然衰減）
    af_filter = (
        f"agate=threshold={threshold}:ratio=100"
        f":range=-100:attack=5:release=50"
    )

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(vocals_path),
        "-af", af_filter,
        str(output_path),
    ]

    _logger.info("噪音閘門開始：threshold=%.4f（≈%.0fdB）", threshold, 20 * __import__("math").log10(max(threshold, 1e-10)))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        _logger.error("噪音閘門超時（>120s），fallback 使用原始音訊")
        return vocals_path
    except FileNotFoundError:
        _logger.error("ffmpeg 不存在：%s，fallback 使用原始音訊", ffmpeg_bin)
        return vocals_path

    if result.returncode != 0:
        _logger.error("噪音閘門失敗（exit=%d）：%s", result.returncode, (result.stderr or "")[:500])
        _logger.warning("fallback 使用原始音訊")
        return vocals_path

    if not output_path.exists():
        _logger.warning("噪音閘門輸出不存在：%s，fallback 使用原始音訊", output_path)
        return vocals_path

    _logger.info(
        "噪音閘門完成：%s（%.1f MB）",
        output_path, output_path.stat().st_size / 1e6,
    )
    return output_path
