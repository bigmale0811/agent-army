# -*- coding: utf-8 -*-
"""
DEV-11: 影片合成模組。

VideoRenderer 提供：
- SadTalker 主路徑（subprocess 呼叫對嘴動畫）
- FFmpeg 靜態降級（靜態圖片 + 音訊合成影片）
- 非 ASCII 路徑自動處理（透過 path_utils）
"""
import logging
import subprocess
from pathlib import Path

from src.singer_agent import config
from src.singer_agent.path_utils import to_ascii_temp, cleanup_temp

_logger = logging.getLogger(__name__)


class VideoRenderer:
    """
    影片渲染器。

    主路徑：SadTalker 對嘴動畫。
    降級路徑：FFmpeg 靜態圖片迴圈 + 音訊合成。

    Args:
        sadtalker_dir: SadTalker 安裝目錄
        ffmpeg_bin: FFmpeg 執行檔路徑
    """

    def __init__(
        self,
        sadtalker_dir: Path | None = None,
        ffmpeg_bin: Path | None = None,
    ) -> None:
        self.sadtalker_dir = sadtalker_dir or config.SADTALKER_DIR
        self.ffmpeg_bin = ffmpeg_bin or config.FFMPEG_BIN

    def render(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        dry_run: bool = False,
    ) -> tuple[Path, str]:
        """
        渲染影片。

        Args:
            composite_image: 合成圖片路徑
            audio_path: 音訊檔案路徑
            output_path: 輸出影片路徑
            dry_run: True 時建立佔位檔

        Returns:
            (輸出路徑, 渲染模式) — 模式為 "sadtalker"、"ffmpeg_static" 或 "dry_run"
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            _logger.info("dry_run 模式：建立佔位影片檔")
            output_path.write_bytes(b"\x00" * 100)
            return output_path, "dry_run"

        # 嘗試 SadTalker
        try:
            return self._render_sadtalker(composite_image, audio_path, output_path)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            _logger.warning("SadTalker 渲染失敗，降級 FFmpeg：%s", exc)
            return self._render_ffmpeg(composite_image, audio_path, output_path)

    def _render_sadtalker(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
    ) -> tuple[Path, str]:
        """透過 SadTalker subprocess 渲染對嘴動畫。"""
        _logger.info("開始 SadTalker 渲染")

        # 處理非 ASCII 路徑（SadTalker 不支援中文路徑）
        ascii_img = to_ascii_temp(composite_image)
        ascii_audio = to_ascii_temp(audio_path)

        try:
            cmd = [
                "python",
                str(self.sadtalker_dir / "inference.py"),
                "--driven_audio", str(ascii_audio),
                "--source_image", str(ascii_img),
                "--result_dir", str(output_path.parent),
            ]

            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=600,
            )

            # SadTalker 可能產出在 result_dir 下，需搬移到 output_path
            if not output_path.exists():
                # 尋找 result_dir 下最新的 .mp4
                result_dir = output_path.parent
                mp4_files = sorted(result_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
                if mp4_files:
                    mp4_files[-1].rename(output_path)

            _logger.info("SadTalker 渲染完成：%s", output_path)
            return output_path, "sadtalker"

        finally:
            # 清理暫存 ASCII 路徑
            cleanup_temp(ascii_img)
            cleanup_temp(ascii_audio)

    def _render_ffmpeg(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
    ) -> tuple[Path, str]:
        """透過 FFmpeg 建立靜態圖片 + 音訊影片（降級方案）。"""
        _logger.info("開始 FFmpeg 靜態渲染")

        cmd = [
            str(self.ffmpeg_bin),
            "-y",
            "-loop", "1",
            "-i", str(composite_image),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path),
        ]

        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=300,
        )

        _logger.info("FFmpeg 靜態渲染完成：%s", output_path)
        return output_path, "ffmpeg_static"
