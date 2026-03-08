# -*- coding: utf-8 -*-
"""
DEV-11: 影片合成模組。

VideoRenderer 提供：
- SadTalker 主路徑（subprocess 呼叫對嘴動畫）
- FFmpeg 靜態降級（靜態圖片 + 音訊合成影片）
- 非 ASCII 路徑自動處理（透過 path_utils）
"""
import logging
import shutil
import subprocess
import time
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
        # SadTalker 使用自己的 venv（含 torch 等依賴）
        self._sadtalker_python = self.sadtalker_dir / "venv" / "Scripts" / "python.exe"

    def render(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        dry_run: bool = False,
        expression_scale: float = 1.0,
    ) -> tuple[Path, str]:
        """
        渲染影片。

        Args:
            composite_image: 合成圖片路徑
            audio_path: 音訊檔案路徑
            output_path: 輸出影片路徑
            dry_run: True 時建立佔位檔
            expression_scale: SadTalker 表情幅度（0.0~2.0）
                預設 1.0，低於 1.0 降低表情強度（適合悲傷），
                高於 1.0 放大表情（適合歡樂）

        Returns:
            (輸出路徑, 渲染模式) — 模式為 "sadtalker"、"ffmpeg_static" 或 "dry_run"
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            _logger.info("dry_run 模式：建立佔位影片檔")
            output_path.write_bytes(b"\x00" * 100)
            return output_path, "dry_run"

        # 直接執行 SadTalker，失敗時讓錯誤傳播（不自動降級 FFmpeg）
        return self._render_sadtalker(
            composite_image, audio_path, output_path,
            expression_scale=expression_scale,
        )

    # 輪詢間隔（秒）與穩定判定次數
    _POLL_INTERVAL: int = 10
    _STABLE_CHECKS: int = 3  # 檔案大小連續穩定 3 次（30 秒）視為完成
    _RENDER_TIMEOUT: int = 3600  # 最長等待 1 小時

    def _render_sadtalker(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        expression_scale: float = 1.0,
    ) -> tuple[Path, str]:
        """
        透過 SadTalker subprocess 渲染對嘴動畫。

        使用 Popen + 輪詢策略：啟動 SadTalker 後持續偵測 mp4 產出，
        一旦檔案穩定（大小不再變化）就強制結束 process。
        這能避免 SadTalker 在 cleanup 階段掛住的問題。

        expression_scale 控制 3DMM 表情幅度：
        - < 1.0：壓抑表情（適合悲傷、低落情緒）
        - = 1.0：原始表情
        - > 1.0：放大表情（適合歡樂、興奮情緒）
        """
        _logger.info(
            "開始 SadTalker 渲染（expression_scale=%.2f）",
            expression_scale,
        )

        # 前置 VRAM 清理：確保 ComfyUI / rembg 已釋放 VRAM
        self._pre_launch_cleanup()

        # 處理非 ASCII 路徑（SadTalker 不支援中文路徑）
        ascii_img = to_ascii_temp(composite_image)
        ascii_audio = to_ascii_temp(audio_path)

        process: subprocess.Popen | None = None
        try:
            # 使用 SadTalker 自己的 venv Python（含 torch 等依賴）
            python_bin = str(self._sadtalker_python)
            if not self._sadtalker_python.exists():
                raise FileNotFoundError(
                    f"SadTalker venv Python 不存在：{python_bin}"
                )

            # result_dir 必須用絕對路徑，因為 cwd 會切到 SadTalker 目錄
            result_dir = output_path.parent.resolve()
            abs_result_dir = str(result_dir)

            cmd = [
                python_bin,
                str(self.sadtalker_dir / "inference.py"),
                "--driven_audio", str(ascii_audio),
                "--source_image", str(ascii_img),
                "--result_dir", abs_result_dir,
                "--still",        # 靜態模式（頭不亂動，只動嘴巴與表情）
                "--preprocess", "full",  # 全臉預處理
                "--verbose",      # 跳過 shutil.rmtree 清理（避免卡死）
            ]

            # 動態調整表情幅度（情緒映射驅動）
            # expression_scale 控制 SadTalker 3DMM 表情係數
            if expression_scale != 1.0:
                cmd.extend([
                    "--expression_scale",
                    f"{expression_scale:.2f}",
                ])
                _logger.info(
                    "SadTalker 表情幅度：%.2f（%s）",
                    expression_scale,
                    "壓抑" if expression_scale < 1.0 else "放大",
                )

            # 記錄啟動前已存在的 mp4（避免誤判舊檔案）
            pre_existing = set(result_dir.glob("*.mp4"))
            for subdir in result_dir.iterdir():
                if subdir.is_dir():
                    pre_existing.update(subdir.glob("*.mp4"))

            _logger.info("啟動 SadTalker（Popen + 輪詢模式）")
            # SadTalker 用相對路徑讀取 checkpoints，必須在其目錄下執行
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(self.sadtalker_dir),
            )

            found_mp4 = self._poll_for_mp4(
                process, result_dir, pre_existing,
            )

            # 確保 process 已終止
            self._terminate_process(process)

            if not found_mp4:
                raise RuntimeError(
                    f"SadTalker 在 {self._RENDER_TIMEOUT} 秒內未產出影片"
                )

            # 搬移產出檔案到目標路徑
            if found_mp4 != output_path:
                if output_path.exists():
                    output_path.unlink()
                shutil.move(str(found_mp4), str(output_path))

            _logger.info("SadTalker 渲染完成：%s", output_path)
            return output_path, "sadtalker"

        except Exception:
            # 異常時確保 process 被清理
            if process is not None and process.poll() is None:
                self._terminate_process(process)
            raise

        finally:
            # 清理暫存 ASCII 路徑
            cleanup_temp(ascii_img)
            cleanup_temp(ascii_audio)

    def _poll_for_mp4(
        self,
        process: subprocess.Popen,
        result_dir: Path,
        pre_existing: set[Path],
    ) -> Path | None:
        """
        輪詢 result_dir，偵測新產出的 mp4 檔案。

        掃描 result_dir 及其子目錄，忽略啟動前已存在的檔案。
        當 mp4 檔案大小連續穩定 _STABLE_CHECKS 次，視為渲染完成。

        Args:
            process: SadTalker subprocess
            result_dir: 輸出目錄
            pre_existing: 啟動前已存在的 mp4 路徑集合

        Returns:
            找到的 mp4 路徑，或 None（超時）
        """
        start_time = time.monotonic()
        last_size: int = -1
        stable_count: int = 0

        while time.monotonic() - start_time < self._RENDER_TIMEOUT:
            # 如果 process 自然退出，最後再掃一次就結束
            retcode = process.poll()
            if retcode is not None:
                if retcode != 0:
                    raise subprocess.CalledProcessError(retcode, process.args)
                # Process 正常退出，做最後掃描
                mp4 = self._find_new_mp4(result_dir, pre_existing)
                if mp4:
                    _logger.info("SadTalker 正常退出，找到：%s", mp4)
                    return mp4
                return None

            # 輪詢：尋找新的 mp4
            mp4 = self._find_new_mp4(result_dir, pre_existing)

            if mp4:
                current_size = mp4.stat().st_size
                elapsed = int(time.monotonic() - start_time)

                if current_size > 0 and current_size == last_size:
                    stable_count += 1
                    _logger.info(
                        "mp4 檔案穩定 %d/%d（%d bytes，已耗時 %ds）",
                        stable_count, self._STABLE_CHECKS,
                        current_size, elapsed,
                    )
                    if stable_count >= self._STABLE_CHECKS:
                        _logger.info(
                            "偵測到穩定 mp4：%s（%d bytes，耗時 %ds）",
                            mp4, current_size, elapsed,
                        )
                        return mp4
                else:
                    stable_count = 0
                    last_size = current_size
            else:
                elapsed = int(time.monotonic() - start_time)
                if elapsed % 60 < self._POLL_INTERVAL:
                    _logger.info("等待 SadTalker 產出...（已耗時 %ds）", elapsed)

            time.sleep(self._POLL_INTERVAL)

        return None

    @staticmethod
    def _find_new_mp4(
        result_dir: Path,
        pre_existing: set[Path],
    ) -> Path | None:
        """
        在 result_dir 及其子目錄中尋找最新的 mp4（排除已存在檔案）。

        優先回傳 result_dir 根目錄的檔案（SadTalker 最終產出位置），
        其次回傳子目錄中的檔案（中間產出）。
        """
        # 先查根目錄（SadTalker shutil.move 的最終位置）
        root_mp4s = sorted(
            (p for p in result_dir.glob("*.mp4") if p not in pre_existing),
            key=lambda p: p.stat().st_mtime,
        )
        if root_mp4s:
            return root_mp4s[-1]

        # 再查子目錄（SadTalker 時間戳子目錄內的中間產出）
        for subdir in sorted(result_dir.iterdir(), reverse=True):
            if not subdir.is_dir():
                continue
            sub_mp4s = sorted(
                (p for p in subdir.glob("*.mp4") if p not in pre_existing),
                key=lambda p: p.stat().st_mtime,
            )
            if sub_mp4s:
                return sub_mp4s[-1]

        return None

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        """安全終止 subprocess：先 terminate，再 kill。"""
        if process.poll() is not None:
            return
        _logger.info("終止 SadTalker process（pid=%d）", process.pid)
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            _logger.warning("terminate 超時，強制 kill")
            process.kill()
            process.wait(timeout=10)

    def _pre_launch_cleanup(self) -> None:
        """
        SadTalker 啟動前的 VRAM 清理。

        確保 ComfyUI SDXL 模型已卸載、rembg 殘留已清理，
        讓 SadTalker 能獨佔 GPU 的 12GB VRAM。
        """
        from src.singer_agent.vram_monitor import (
            free_comfyui_models, force_cleanup, log_vram, check_vram_safety,
        )

        _logger.info("SadTalker 前置清理：卸載 ComfyUI 模型 + 清理 VRAM")
        # 卸載 ComfyUI SDXL（如果還在）
        free_comfyui_models(
            getattr(config, "COMFYUI_URL", "http://localhost:8188")
        )
        # gc + empty_cache
        force_cleanup()
        # 記錄清理後的 VRAM 狀態
        log_vram("SadTalker 啟動前")
        # 安全檢查
        check_vram_safety("SadTalker 啟動前")

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
