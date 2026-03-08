# -*- coding: utf-8 -*-
"""
DEV-11: 影片合成模組（V2.0 — EDTalk 引擎）。

VideoRenderer 提供：
- EDTalk 主路徑（subprocess 呼叫，支援 8 種情緒標籤）
- FFmpeg 靜態降級（靜態圖片 + 音訊合成影片）
- 非 ASCII 路徑自動處理（透過 path_utils）

V2.0 變更：
- 廢棄 SadTalker，全面改用 EDTalk
- 情緒控制由 expression_scale → exp_type（8 種原生情緒）
- VRAM 峰值：~2.4GB（比 SadTalker 的 4-5GB 省 50%）
"""
import logging
import shutil
import subprocess
from pathlib import Path

from src.singer_agent import config
from src.singer_agent.path_utils import to_ascii_temp, cleanup_temp

_logger = logging.getLogger(__name__)


class VideoRenderer:
    """
    影片渲染器（V2.0 — EDTalk 引擎）。

    主路徑：EDTalk 對嘴動畫（支援情緒標籤）。
    降級路徑：FFmpeg 靜態圖片迴圈 + 音訊合成。

    Args:
        edtalk_dir: EDTalk 安裝目錄
        ffmpeg_bin: FFmpeg 執行檔路徑
    """

    def __init__(
        self,
        edtalk_dir: Path | None = None,
        ffmpeg_bin: Path | None = None,
    ) -> None:
        self.edtalk_dir = edtalk_dir or config.EDTALK_DIR
        self.ffmpeg_bin = ffmpeg_bin or config.FFMPEG_BIN
        # EDTalk 使用自己的 venv（含 torch cu128）
        self._edtalk_python = config.EDTALK_PYTHON
        self._edtalk_demo = config.EDTALK_DEMO_SCRIPT
        self._pose_video = config.EDTALK_POSE_VIDEO

    # EDTalk 推論超時（秒）
    _RENDER_TIMEOUT: int = 600

    def render(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        dry_run: bool = False,
        exp_type: str = "neutral",
        expression_scale: float = 1.0,
    ) -> tuple[Path, str]:
        """
        渲染影片。

        Args:
            composite_image: 合成圖片路徑（角色 + 背景）
            audio_path: 音訊檔案路徑（應為 Demucs 純人聲）
            output_path: 輸出影片路徑
            dry_run: True 時建立佔位檔
            exp_type: EDTalk 情緒類型（8 種之一）
            expression_scale: V1.0 相容參數（V2.0 已忽略）

        Returns:
            (輸出路徑, 渲染模式) — 模式為 "edtalk"、"ffmpeg_static" 或 "dry_run"
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            _logger.info("dry_run 模式：建立佔位影片檔")
            output_path.write_bytes(b"\x00" * 100)
            return output_path, "dry_run"

        # EDTalk 主路徑
        return self._render_edtalk(
            composite_image, audio_path, output_path,
            exp_type=exp_type,
        )

    def _render_edtalk(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        exp_type: str = "neutral",
    ) -> tuple[Path, str]:
        """
        透過 EDTalk subprocess 渲染對嘴動畫。

        EDTalk 特點：
        - 原生支援 8 種情緒標籤（--exp_type）
        - VRAM ~2.4GB（比 SadTalker 省 50%）
        - 執行速度接近即時（10 秒影片 ~11 秒推論）
        """
        _logger.info(
            "開始 EDTalk 渲染（exp_type=%s）", exp_type,
        )

        # 前置 VRAM 清理
        self._pre_launch_cleanup()

        # 處理非 ASCII 路徑（EDTalk 可能不支援中文路徑）
        ascii_img = to_ascii_temp(composite_image)
        ascii_audio = to_ascii_temp(audio_path)

        try:
            # 檢查 EDTalk 環境
            if not self._edtalk_python.exists():
                raise FileNotFoundError(
                    f"EDTalk venv Python 不存在：{self._edtalk_python}"
                )
            if not self._edtalk_demo.exists():
                raise FileNotFoundError(
                    f"EDTalk demo 腳本不存在：{self._edtalk_demo}"
                )

            # EDTalk 輸出到暫存路徑（res/ 目錄下）
            edtalk_output = self.edtalk_dir / "res" / f"singer_{output_path.stem}.mp4"
            edtalk_output.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                str(self._edtalk_python),
                str(self._edtalk_demo),
                "--source_path", str(ascii_img),
                "--audio_driving_path", str(ascii_audio),
                "--pose_driving_path", str(self._pose_video),
                "--exp_type", exp_type,
                "--save_path", str(edtalk_output),
            ]

            _logger.info("EDTalk 命令：%s", " ".join(cmd))

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._RENDER_TIMEOUT,
                cwd=str(self.edtalk_dir),
            )

            if result.returncode != 0:
                _logger.error(
                    "EDTalk 推論失敗（exit=%d）：%s",
                    result.returncode,
                    result.stderr[-500:] if result.stderr else "無 stderr",
                )
                raise RuntimeError(
                    f"EDTalk 推論失敗（exit={result.returncode}）"
                )

            # 確認輸出影片存在
            if not edtalk_output.exists():
                raise RuntimeError(
                    f"EDTalk 未產出影片：{edtalk_output}"
                )

            # 搬移到目標路徑
            if output_path.exists():
                output_path.unlink()
            shutil.move(str(edtalk_output), str(output_path))

            size_mb = output_path.stat().st_size / (1024 ** 2)
            _logger.info(
                "EDTalk 渲染完成：%s（%.2f MB, exp_type=%s）",
                output_path, size_mb, exp_type,
            )
            return output_path, "edtalk"

        except subprocess.TimeoutExpired:
            _logger.error("EDTalk 推論超時（>%ds）", self._RENDER_TIMEOUT)
            raise RuntimeError(
                f"EDTalk 推論超時（>{self._RENDER_TIMEOUT}s）"
            )

        finally:
            # 清理暫存 ASCII 路徑
            cleanup_temp(ascii_img)
            cleanup_temp(ascii_audio)

    def _pre_launch_cleanup(self) -> None:
        """
        EDTalk 啟動前的 VRAM 清理。

        確保 ComfyUI SDXL 模型已卸載、rembg 殘留已清理，
        讓 EDTalk 能獨佔 GPU。
        """
        from src.singer_agent.vram_monitor import (
            free_comfyui_models, force_cleanup, log_vram, check_vram_safety,
        )

        _logger.info("EDTalk 前置清理：卸載 ComfyUI 模型 + 清理 VRAM")
        free_comfyui_models(
            getattr(config, "COMFYUI_URL", "http://localhost:8188")
        )
        force_cleanup()
        log_vram("EDTalk 啟動前")
        check_vram_safety("EDTalk 啟動前")

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
