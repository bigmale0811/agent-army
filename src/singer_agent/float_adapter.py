# -*- coding: utf-8 -*-
"""
FLOAT 渲染引擎適配器。

封裝 FLOAT（Flow Matching for Audio-driven Talking Portrait）的推理，
以 subprocess 方式執行，與主程序的 VRAM 隔離。

FLOAT 特性：
- Flow Matching（非 Diffusion），速度快、記憶體省
- 7 種情緒支援（angry, disgust, fear, happy, neutral, sad, surprise）
- 輸入：人像圖片 + 音訊 → 輸出：說話/唱歌影片
- VRAM：約 8-10GB（RTX 5070 12GB 可執行）
"""
import json
import logging
import subprocess
import tempfile
from pathlib import Path

from src.singer_agent import config

_logger = logging.getLogger(__name__)

# FLOAT 情緒白名單（與 EDTalk 8 種情緒的映射）
_EDTALK_TO_FLOAT_EMOTION: dict[str, str] = {
    "angry": "angry",
    "contempt": "disgust",   # FLOAT 無 contempt，映射到 disgust
    "disgusted": "disgust",
    "fear": "fear",
    "happy": "happy",
    "neutral": "neutral",
    "sad": "sad",
    "surprised": "surprise",  # FLOAT 用 surprise（無 d）
}

# FLOAT 推理超時（秒）— Flow Matching 比 Diffusion 快很多
_FLOAT_TIMEOUT: int = 600


def render_float(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    exp_type: str = "neutral",
    dry_run: bool = False,
) -> tuple[Path, str]:
    """
    使用 FLOAT 引擎渲染影片。

    Args:
        image_path: 角色人像圖片路徑
        audio_path: 音訊路徑（MP3 / WAV）
        output_path: 輸出影片路徑
        exp_type: 情緒標籤（EDTalk 格式，會自動轉換）
        dry_run: 乾跑模式

    Returns:
        (影片路徑, 使用的渲染模式字串)
    """
    if dry_run:
        _logger.info("dry_run 模式：跳過 FLOAT 渲染")
        return output_path, "float_dry_run"

    # 檢查 FLOAT 環境
    float_python = config.FLOAT_PYTHON
    float_dir = config.FLOAT_DIR
    ckpt_path = float_dir / "checkpoints" / "float.pth"

    if not float_python.exists():
        _logger.error("FLOAT Python 不存在：%s", float_python)
        return output_path, "float_error"

    if not ckpt_path.exists():
        _logger.error("FLOAT checkpoint 不存在：%s", ckpt_path)
        return output_path, "float_error"

    # 轉換情緒標籤
    float_emo = _EDTALK_TO_FLOAT_EMOTION.get(exp_type, "neutral")
    _logger.info(
        "FLOAT 渲染開始：image=%s, audio=%s, emotion=%s",
        image_path.name, audio_path.name, float_emo,
    )

    # 確保輸出目錄存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 所有路徑必須是絕對路徑（cwd 會切到 FLOAT 目錄）
    cmd = [
        str(float_python),
        str(float_dir / "generate.py"),
        "--ref_path", str(image_path.resolve()),
        "--aud_path", str(audio_path.resolve()),
        "--res_video_path", str(output_path.resolve()),
        "--ckpt_path", str(ckpt_path),
        "--emo", float_emo,
        "--nfe", "30",       # Flow Matching 步數（預設 30，可調）
        "--seed", "25",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_FLOAT_TIMEOUT,
            cwd=str(float_dir),
        )
    except subprocess.TimeoutExpired:
        _logger.error("FLOAT 渲染超時（>%ds）", _FLOAT_TIMEOUT)
        return output_path, "float_timeout"
    except FileNotFoundError as e:
        _logger.error("FLOAT 執行失敗：%s", e)
        return output_path, "float_error"

    if result.returncode != 0:
        _logger.error(
            "FLOAT 渲染失敗（exit=%d）：%s",
            result.returncode,
            (result.stderr or "")[:500],
        )
        return output_path, "float_error"

    if not output_path.exists():
        _logger.error("FLOAT 輸出不存在：%s", output_path)
        return output_path, "float_error"

    file_size_mb = output_path.stat().st_size / 1e6
    _logger.info("FLOAT 渲染完成：%s（%.1f MB）", output_path, file_size_mb)
    return output_path, "float"
