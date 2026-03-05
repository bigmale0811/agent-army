# -*- coding: utf-8 -*-
"""Singer Agent — MV 合成模組

合成策略（v0.3.0）：
    1. 優先使用合成圖（角色+背景）作為輸入
    2. SadTalker 唱歌模式（對嘴動畫 + 身體搖擺）
    3. SadTalker 失敗時，降級為 FFmpeg 靜態圖片 + 呼吸效果

v0.3 改進：
- 支援 composite_image 參數（角色+背景合成圖）
- FFmpeg 靜態模式修正比例拉伸問題（pad 取代 force resize）
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

from .config import CHARACTER_IMAGE, VIDEOS_DIR
from .models import SongSpec

logger = logging.getLogger(__name__)

# FFmpeg 執行檔路徑（自動偵測）
_FFMPEG_SEARCH_PATHS = [
    # winget 預設安裝位置
    Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
    # 常見安裝路徑
    Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
]


def _find_ffmpeg() -> str:
    """搜尋 FFmpeg 執行檔路徑

    優先順序：PATH > 已知安裝路徑
    """
    # 先嘗試 PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 搜尋已知路徑
    for p in _FFMPEG_SEARCH_PATHS:
        if p.exists():
            logger.info("在非 PATH 路徑找到 FFmpeg: %s", p)
            return str(p)

    raise FileNotFoundError(
        "找不到 FFmpeg，請安裝 FFmpeg 並加入 PATH\n"
        "下載: https://ffmpeg.org/download.html"
    )


def compose_mv(
    audio_path: str,
    spec: SongSpec,
    project_id: str,
    character_image: str = "",
    composite_image: str = "",
) -> tuple[str, str]:
    """合成 MV 影片（優先 SadTalker 唱歌模式，失敗降級為靜態 FFmpeg）

    v0.3 新增：composite_image 參數。如果有合成圖（角色+背景），
    優先用合成圖作為 SadTalker 的輸入圖片。

    策略：
        1. 嘗試 SadTalker 動畫模式（對嘴 + 身體搖擺）
        2. 若 SadTalker 失敗，降級為 FFmpeg 靜態圖片 + 呼吸效果

    Args:
        audio_path: 音檔路徑（.mp3 / .wav）
        spec: 歌曲風格規格書（用於決定背景色）
        project_id: 專案 ID（用於輸出檔名）
        character_image: 角色圖片路徑（留空則用預設）
        composite_image: v0.3 合成圖路徑（角色+背景，留空則用角色圖）

    Returns:
        (影片路徑, 渲染模式) — 渲染模式為 "sadtalker" 或 "ffmpeg_static"

    Raises:
        FileNotFoundError: 找不到音檔或角色圖片
        RuntimeError: 所有合成方式都失敗
    """
    audio = Path(audio_path)
    if not audio.exists():
        raise FileNotFoundError(f"找不到音檔: {audio_path}")

    # v0.3：優先使用合成圖，否則用角色原圖
    source_img = None
    if composite_image and Path(composite_image).exists():
        source_img = Path(composite_image)
        logger.info("🖼️ 使用合成圖（角色+背景）: %s", source_img)
    else:
        source_img = Path(character_image) if character_image else CHARACTER_IMAGE
        if not source_img.exists():
            raise FileNotFoundError(
                f"找不到角色圖片: {source_img}\n"
                f"請將角色圖片放到: {CHARACTER_IMAGE}"
            )
        logger.info("🖼️ 使用原始角色圖: %s", source_img)

    output_path = VIDEOS_DIR / f"{project_id}.mp4"

    # === 優先嘗試 SadTalker 唱歌模式 ===
    try:
        from .sadtalker_runner import is_sadtalker_available, generate_singing_video

        if is_sadtalker_available():
            logger.info("🎤 嘗試使用 SadTalker 唱歌模式...")
            video_path = generate_singing_video(
                source_image=str(source_img),
                driven_audio=str(audio),
                output_path=str(output_path),
            )
            logger.info("🎬 SadTalker 唱歌模式成功: %s", video_path)
            return video_path, "sadtalker"
        else:
            logger.info("⚠️ SadTalker 不可用，降級為靜態 FFmpeg MV")
    except Exception as e:
        logger.warning("⚠️ SadTalker 失敗，降級為靜態 FFmpeg MV: %s", e)

    # === 降級：FFmpeg 靜態圖片模式 ===
    video_path = _compose_static_mv(
        audio_path, spec, project_id, source_img, output_path,
        has_background=bool(composite_image and Path(composite_image).exists()),
    )
    return video_path, "ffmpeg_static"


def _compose_static_mv(
    audio_path: str,
    spec: SongSpec,
    project_id: str,
    char_img: Path,
    output_path: Path,
    has_background: bool = False,
) -> str:
    """靜態 FFmpeg MV（降級方案）

    v0.3 改進：
    - 如果有合成圖（has_background=True），直接全螢幕呈現 + 呼吸效果
    - 如果沒有合成圖，使用純色背景 + 角色居中（修正比例拉伸）

    Args:
        audio_path: 音檔路徑
        spec: 歌曲風格規格書
        project_id: 專案 ID
        char_img: 圖片 Path（可能是合成圖或角色原圖）
        output_path: 輸出影片 Path
        has_background: 輸入圖片是否已含背景（v0.3 合成圖）

    Returns:
        輸出影片的路徑

    Raises:
        RuntimeError: FFmpeg 執行失敗
    """
    logger.info("🎬 開始合成靜態 FFmpeg 影片（降級模式）...")
    logger.info("   音檔: %s", audio_path)
    logger.info("   圖片: %s (含背景: %s)", char_img, has_background)
    logger.info("   輸出: %s", output_path)

    ffmpeg_bin = _find_ffmpeg()

    if has_background:
        # v0.3：合成圖已含背景（1920x1080），直接用 + 輕微呼吸效果
        # 圖片是 input 1（input 0 是音檔）
        filter_complex = (
            # 合成圖：先等比縮放 + pad 確保剛好 1920x1080
            "[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
            # zoompan 輕微呼吸式縮放
            "zoompan=z='1+0.03*sin(2*PI*in/200)'"
            ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            ":d=1:s=1920x1080:fps=25"
            "[out]"
        )
    else:
        # v0.2 相容模式：純色背景 + 角色居中
        # 修正比例拉伸：先等比縮放 + pad 到固定大小，再 zoompan
        bg_color = _get_background_color(spec.mood)
        logger.info("   背景色: %s", bg_color)
        filter_complex = (
            # 純色背景
            f"color=c={bg_color}:s=1920x1080:r=25[bg];"
            # 角色圖片：等比縮放到 920 高以內，pad 到固定大小避免拉伸
            "[1:v]scale='min(1080,iw)':920"
            ":force_original_aspect_ratio=decrease,"
            "pad=1080:920:(ow-iw)/2:(oh-ih)/2:0x00000000,"
            "format=rgba,"
            # zoompan 呼吸式縮放（固定輸出大小）
            "zoompan=z='1+0.05*sin(2*PI*in/200)'"
            ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            ":d=1:s=1080x920:fps=25[char];"
            # 疊合：角色置中，y 軸 sin 浮動
            "[bg][char]overlay="
            "(W-w)/2"
            ":(H-h)/2+8*sin(2*PI*t/4)"
            "[out]"
        )

    cmd = [
        ffmpeg_bin, "-y",
        # 音樂輸入
        "-i", str(audio_path),
        # 角色圖片（無限循環）
        "-loop", "1", "-i", str(char_img),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "0:a",
        # 編碼設定
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )

        if result.returncode != 0:
            logger.error("FFmpeg stderr: %s", result.stderr[-500:])
            raise RuntimeError(f"FFmpeg 執行失敗 (code={result.returncode})")

        logger.info("🎬 靜態影片合成完成: %s", output_path)
        return str(output_path)

    except FileNotFoundError as e:
        raise RuntimeError(str(e))
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg 執行超時（超過 10 分鐘）")


def _get_background_color(mood: str) -> str:
    """根據情緒取得背景色（hex 格式，不含 #）

    Args:
        mood: 情緒分類

    Returns:
        FFmpeg 用的色彩字串
    """
    mood_colors = {
        "happy": "0xFFF8DC",        # 暖黃
        "sad": "0x2C3E50",          # 深藍灰
        "energetic": "0xFF4757",    # 活力紅
        "calm": "0xDFE6E9",         # 柔和灰
        "romantic": "0xFD79A8",     # 粉紅
        "dark": "0x2D3436",         # 暗色
        "epic": "0x6C5CE7",         # 紫色
        "nostalgic": "0xFDCB6E",    # 復古金
    }
    return mood_colors.get(mood, "0x2C3E50")
