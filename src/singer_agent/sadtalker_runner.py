# -*- coding: utf-8 -*-
"""Singer Agent — SadTalker 動畫影片生成模組

透過 subprocess 呼叫 SadTalker 產出對嘴動畫影片，
搭配 body_motion 模式讓身體有自然搖擺效果。

流程：
    1. 檢查 SadTalker 可用性（inference.py + checkpoints）
    2. 以 subprocess 執行 SadTalker inference.py
    3. 解析 stdout 找到輸出影片路徑
    4. 搬移到 Singer Agent 的 videos 目錄

失敗時由上層（mv_composer）降級為靜態 FFmpeg MV。
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

from .config import (
    SADTALKER_DIR,
    SADTALKER_PYTHON,
    SADTALKER_EXPRESSION_SCALE,
    SADTALKER_POSE_STYLE,
    SADTALKER_SIZE,
    SADTALKER_TIMEOUT,
    SADTALKER_BODY_MOTION,
)

logger = logging.getLogger(__name__)

# SadTalker 子目錄
SADTALKER_INFERENCE = SADTALKER_DIR / "inference.py"
SADTALKER_CHECKPOINTS = SADTALKER_DIR / "checkpoints"
SADTALKER_RESULT_DIR = SADTALKER_DIR / "results"


def _find_ffmpeg_dir() -> str | None:
    """找到 FFmpeg 所在目錄（供注入 PATH）

    Returns:
        FFmpeg 目錄路徑，找不到時回傳 None
    """
    import shutil

    # 先檢查 PATH 裡有沒有
    if shutil.which("ffprobe"):
        return None  # 已在 PATH，不需額外注入

    # WinGet 預設安裝位置
    winget_dir = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links"
    if (winget_dir / "ffprobe.exe").exists():
        return str(winget_dir)

    # 常見安裝路徑
    for d in [Path(r"C:\ffmpeg\bin"), Path(r"C:\Program Files\ffmpeg\bin")]:
        if (d / "ffprobe.exe").exists():
            return str(d)

    return None


def is_sadtalker_available() -> bool:
    """檢查 SadTalker 是否可用

    確認 inference.py 存在且 checkpoints 目錄有模型檔案。

    Returns:
        True 表示 SadTalker 可正常呼叫
    """
    if not SADTALKER_INFERENCE.exists():
        logger.warning("SadTalker inference.py 不存在: %s", SADTALKER_INFERENCE)
        return False

    if not SADTALKER_CHECKPOINTS.exists():
        logger.warning("SadTalker checkpoints 目錄不存在: %s", SADTALKER_CHECKPOINTS)
        return False

    # 檢查至少有一個模型權重檔案（.safetensors 或 .pth）
    model_files = (
        list(SADTALKER_CHECKPOINTS.glob("*.safetensors"))
        + list(SADTALKER_CHECKPOINTS.glob("*.pth"))
    )
    if not model_files:
        logger.warning("SadTalker checkpoints 中沒有模型檔案")
        return False

    return True


def generate_singing_video(
    source_image: str,
    driven_audio: str,
    output_path: str,
    expression_scale: float | None = None,
    pose_style: int | None = None,
    size: int | None = None,
    body_motion: bool | None = None,
    timeout: int | None = None,
) -> str:
    """使用 SadTalker 產出唱歌動畫影片

    以 subprocess 呼叫 SadTalker，使用 --preprocess full 模式
    將動畫臉部貼回原圖，並透過 --body_motion 啟用身體搖擺。

    Args:
        source_image: 角色圖片路徑（全身或半身 PNG/JPG）
        driven_audio: 音檔路徑（.mp3 / .wav）
        output_path: 輸出影片路徑
        expression_scale: 表情強度（預設從 config 讀取 1.3）
        pose_style: 頭部姿態風格 0-46（預設從 config 讀取）
        size: 臉部渲染解析度 256 或 512（預設從 config 讀取）
        body_motion: 是否啟用身體搖擺動態（預設從 config 讀取）
        timeout: 最大執行時間秒數（預設從 config 讀取 600）

    Returns:
        輸出影片的絕對路徑

    Raises:
        FileNotFoundError: 找不到角色圖片或音檔
        RuntimeError: SadTalker 不可用或執行失敗
    """
    # 參數預設值從 config 讀取
    if expression_scale is None:
        expression_scale = SADTALKER_EXPRESSION_SCALE
    if pose_style is None:
        pose_style = SADTALKER_POSE_STYLE
    if size is None:
        size = SADTALKER_SIZE
    if body_motion is None:
        body_motion = SADTALKER_BODY_MOTION
    if timeout is None:
        timeout = SADTALKER_TIMEOUT

    # 驗證輸入檔案
    if not Path(source_image).exists():
        raise FileNotFoundError(f"找不到角色圖片: {source_image}")
    if not Path(driven_audio).exists():
        raise FileNotFoundError(f"找不到音檔: {driven_audio}")
    if not is_sadtalker_available():
        raise RuntimeError("SadTalker 不可用，請檢查安裝路徑與 checkpoints")

    logger.info("🎤 啟動 SadTalker 唱歌模式...")
    logger.info("   角色圖片: %s", source_image)
    logger.info("   音檔: %s", driven_audio)
    logger.info("   身體動態: %s", body_motion)
    logger.info("   表情強度: %s", expression_scale)

    # SadTalker 的 OpenCV 無法讀取含非 ASCII 字元的路徑
    # 解決方案：複製到 SadTalker 目錄下的暫存資料夾（純 ASCII 路徑）
    tmp_dir = SADTALKER_DIR / "_singer_tmp"
    tmp_dir.mkdir(exist_ok=True)
    _safe_image = str(source_image)
    _safe_audio = str(driven_audio)
    _cleanup_files = []

    try:
        # 檢查路徑是否全為 ASCII
        if not str(source_image).isascii():
            ext = Path(source_image).suffix
            safe_img = tmp_dir / f"input_image{ext}"
            shutil.copy2(str(source_image), str(safe_img))
            _safe_image = str(safe_img)
            _cleanup_files.append(safe_img)
            logger.info("   圖片已複製到 ASCII 路徑: %s", _safe_image)

        if not str(driven_audio).isascii():
            ext = Path(driven_audio).suffix
            safe_aud = tmp_dir / f"input_audio{ext}"
            shutil.copy2(str(driven_audio), str(safe_aud))
            _safe_audio = str(safe_aud)
            _cleanup_files.append(safe_aud)
            logger.info("   音檔已複製到 ASCII 路徑: %s", _safe_audio)
    except Exception as e:
        logger.warning("⚠️ 暫存複製失敗，使用原路徑: %s", e)

    # 建構 SadTalker 指令
    cmd = [
        SADTALKER_PYTHON,
        str(SADTALKER_INFERENCE),
        "--source_image", _safe_image,
        "--driven_audio", _safe_audio,
        "--checkpoint_dir", str(SADTALKER_CHECKPOINTS),
        "--result_dir", str(SADTALKER_RESULT_DIR),
        "--preprocess", "full",
        "--expression_scale", str(expression_scale),
        "--pose_style", str(pose_style),
        "--size", str(size),
    ]

    # 啟用身體搖擺（唱歌模式核心）
    if body_motion:
        cmd.append("--body_motion")

    # 不加 --still，讓頭部自由轉動

    # 確保 SadTalker 子程序能找到 FFmpeg / FFprobe
    # pydub 需要 ffprobe 才能合成最終影片
    env = os.environ.copy()
    _ffmpeg_dir = _find_ffmpeg_dir()
    if _ffmpeg_dir:
        env["PATH"] = _ffmpeg_dir + os.pathsep + env.get("PATH", "")
        logger.info("   已注入 FFmpeg 路徑: %s", _ffmpeg_dir)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(SADTALKER_DIR),
            env=env,
        )

        if result.returncode != 0:
            logger.error("SadTalker stderr:\n%s", result.stderr[-1000:])
            raise RuntimeError(
                f"SadTalker 執行失敗 (code={result.returncode})"
            )

        # 解析 stdout 找到輸出影片路徑
        generated_path = _find_generated_video(result.stdout)

        if not generated_path or not Path(generated_path).exists():
            # 備用策略：找 results 目錄中最新的 .mp4
            generated_path = _find_latest_video(SADTALKER_RESULT_DIR)

        if not generated_path:
            raise RuntimeError("SadTalker 完成但找不到輸出影片")

        # 搬移到目標路徑
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(generated_path), str(output_path))

        file_size = os.path.getsize(output_path)
        logger.info(
            "🎬 SadTalker 影片已產出: %s (%.1f MB)",
            output_path,
            file_size / 1024 / 1024,
        )
        return str(output_path)

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"SadTalker 執行超時（超過 {timeout} 秒）")
    except FileNotFoundError:
        raise RuntimeError(
            f"找不到 Python 執行檔: {SADTALKER_PYTHON}\n"
            f"請設定 SADTALKER_PYTHON 環境變數指向正確的 Python"
        )
    finally:
        # 清理暫存檔案
        for f in _cleanup_files:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass


def _find_generated_video(stdout: str) -> str | None:
    """從 SadTalker stdout 解析輸出影片路徑

    SadTalker 會印出格式如：
        The generated video is named: results/2024_01_01_12.00.00.mp4
        或
        The generated video is named results/xxx_full.mp4

    Args:
        stdout: SadTalker 的標準輸出

    Returns:
        影片絕對路徑，找不到時回傳 None
    """
    for line in stdout.splitlines():
        if "generated video is named" in line.lower():
            # 取 "named" 之後的部分
            parts = line.split("named")
            if len(parts) >= 2:
                path_str = parts[-1].strip().lstrip(":").strip()
                if not path_str:
                    continue

                # 嘗試直接路徑
                if Path(path_str).exists():
                    return str(Path(path_str).resolve())

                # 嘗試在 SadTalker 目錄下找
                full_path = SADTALKER_DIR / path_str
                if full_path.exists():
                    return str(full_path.resolve())

    return None


def _find_latest_video(result_dir: Path) -> str | None:
    """找 results 目錄中最新的 .mp4 檔案

    作為 stdout 解析失敗時的備用策略。

    Args:
        result_dir: SadTalker results 目錄

    Returns:
        最新 .mp4 的絕對路徑，找不到時回傳 None
    """
    if not result_dir.exists():
        return None

    videos = sorted(
        result_dir.glob("*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(videos[0].resolve()) if videos else None
