# -*- coding: utf-8 -*-
"""
Wan2.1 / Wan2.2 影片生成適配器。

提供兩種模式：
1. I2V（Image-to-Video）：靜態背景圖 → 動態背景影片（Phase 2）
2. S2V（Sound-to-Video）：圖片+音訊 → 完整 MV（Phase 3，Wan2.2-S2V）

以 subprocess 方式執行，與主程序的 VRAM 隔離。

Wan2.1 特性：
- 1.3B T2V 模型：~8GB VRAM（RTX 5070 可執行）
- 14B I2V 模型：需 Wan2GP 量化，~12GB VRAM（極限）
- Apache 2.0 開源授權
"""
import logging
import subprocess
from pathlib import Path

from src.singer_agent import config

_logger = logging.getLogger(__name__)

# 超時設定
_WAN_I2V_TIMEOUT: int = 600    # I2V 背景生成
_WAN_S2V_TIMEOUT: int = 1800   # S2V 完整 MV 生成


def generate_background_video(
    background_image: Path,
    output_path: Path,
    prompt: str = "",
    duration_seconds: int = 5,
    dry_run: bool = False,
) -> Path | None:
    """
    使用 Wan2.1 將靜態背景圖轉為動態背景影片。

    Args:
        background_image: 靜態背景圖片路徑
        output_path: 輸出影片路徑
        prompt: 動態描述（如 "gentle camera drift, atmospheric"）
        duration_seconds: 影片長度（秒）
        dry_run: 乾跑模式

    Returns:
        影片路徑，失敗時回傳 None（呼叫端可 fallback 到靜態背景）
    """
    if dry_run:
        _logger.info("dry_run 模式：跳過 Wan2.1 背景影片生成")
        return None

    wan_python = config.WAN_PYTHON
    wan_dir = config.WAN_DIR

    if not wan_python.exists():
        _logger.warning("Wan2.1 Python 不存在：%s，使用靜態背景", wan_python)
        return None

    # 預設 prompt：微動效果
    if not prompt:
        prompt = (
            "Subtle cinematic camera drift, slow parallax movement, "
            "atmospheric lighting, smooth and seamless, high quality"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用 Wan2.1 generate.py 進行 I2V 推理
    cmd = [
        str(wan_python),
        str(wan_dir / "generate.py"),
        "--task", "i2v-14B",
        "--size", "832*480",
        "--image", str(background_image),
        "--prompt", prompt,
        "--sample_steps", "30",
        "--sample_guide_scale", "5.0",
        "--output", str(output_path),
    ]

    _logger.info(
        "Wan2.1 I2V 背景影片生成開始：%s → %s",
        background_image.name, output_path.name,
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_WAN_I2V_TIMEOUT,
            cwd=str(wan_dir),
        )
    except subprocess.TimeoutExpired:
        _logger.error("Wan2.1 I2V 超時（>%ds），使用靜態背景", _WAN_I2V_TIMEOUT)
        return None
    except FileNotFoundError as e:
        _logger.error("Wan2.1 執行失敗：%s", e)
        return None

    if result.returncode != 0:
        _logger.error(
            "Wan2.1 I2V 失敗（exit=%d）：%s",
            result.returncode,
            (result.stderr or "")[:500],
        )
        return None

    if not output_path.exists():
        _logger.error("Wan2.1 輸出不存在：%s", output_path)
        return None

    file_size_mb = output_path.stat().st_size / 1e6
    _logger.info("Wan2.1 I2V 完成：%s（%.1f MB）", output_path, file_size_mb)
    return output_path


def render_s2v(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    dry_run: bool = False,
) -> tuple[Path, str]:
    """
    使用 Wan2.2-S2V 從圖片+音訊直接生成影片（Phase 3）。

    這是最終目標：一步完成整個 MV，取代大部分管線步驟。

    Args:
        image_path: 角色人像圖片
        audio_path: 音訊（歌曲）
        output_path: 輸出影片路徑

    Returns:
        (影片路徑, 渲染模式字串)
    """
    if dry_run:
        _logger.info("dry_run 模式：跳過 Wan2.2-S2V")
        return output_path, "wan_s2v_dry_run"

    wan_s2v_dir = config.WAN_S2V_DIR
    wan_python = config.WAN_PYTHON

    if not wan_s2v_dir.exists():
        _logger.error("Wan2.2-S2V 目錄不存在：%s", wan_s2v_dir)
        return output_path, "wan_s2v_error"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Wan2.2-S2V 推理指令（具體參數待模型安裝後確認）
    cmd = [
        str(wan_python),
        str(wan_s2v_dir / "generate.py"),
        "--task", "s2v-14B",
        "--image", str(image_path),
        "--audio", str(audio_path),
        "--output", str(output_path),
    ]

    _logger.info(
        "Wan2.2-S2V 渲染開始：image=%s, audio=%s",
        image_path.name, audio_path.name,
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_WAN_S2V_TIMEOUT,
            cwd=str(wan_s2v_dir),
        )
    except subprocess.TimeoutExpired:
        _logger.error("Wan2.2-S2V 超時（>%ds）", _WAN_S2V_TIMEOUT)
        return output_path, "wan_s2v_timeout"
    except FileNotFoundError as e:
        _logger.error("Wan2.2-S2V 執行失敗：%s", e)
        return output_path, "wan_s2v_error"

    if result.returncode != 0:
        _logger.error(
            "Wan2.2-S2V 失敗（exit=%d）：%s",
            result.returncode,
            (result.stderr or "")[:500],
        )
        return output_path, "wan_s2v_error"

    if not output_path.exists():
        _logger.error("Wan2.2-S2V 輸出不存在：%s", output_path)
        return output_path, "wan_s2v_error"

    file_size_mb = output_path.stat().st_size / 1e6
    _logger.info("Wan2.2-S2V 完成：%s（%.1f MB）", output_path, file_size_mb)
    return output_path, "wan_s2v"
