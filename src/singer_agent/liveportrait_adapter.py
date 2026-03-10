# -*- coding: utf-8 -*-
"""
LivePortrait subprocess 適配器（V3.0）。

負責：
- 透過 subprocess 呼叫 LivePortrait retarget 腳本
- 將表情參數以 JSON 傳遞給 retarget 腳本
- 管理暫存檔案生命週期
- 回傳帶表情的中間圖片路徑

不直接載入任何 GPU 模型（零 VRAM 佔用）。
subprocess 結束後 VRAM 由 OS 強制回收。
"""

import json
import logging
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from src.singer_agent import config
from src.singer_agent.audio_preprocessor import LivePortraitExpression
from src.singer_agent.path_utils import to_ascii_temp, cleanup_temp

_logger = logging.getLogger(__name__)

# 批量 retarget 的預設幀率（後續可被 MuseTalk 直接讀取）
_DEFAULT_MOTION_FPS: int = 10


class LivePortraitAdapter:
    """
    LivePortrait subprocess 適配器。

    透過 subprocess 呼叫 retarget 腳本（在 LivePortrait venv 中執行），
    對源圖套用表情參數，產出帶表情的中間圖片。

    Args:
        liveportrait_dir: LivePortrait 安裝目錄
        python_bin: LivePortrait venv Python 路徑
        retarget_script: retarget 腳本路徑
    """

    # 推論超時（秒）— 含首次 ONNX warmup 可能需要較長時間
    _RETARGET_TIMEOUT: int = 420

    def __init__(
        self,
        liveportrait_dir: Path | None = None,
        python_bin: Path | None = None,
        retarget_script: Path | None = None,
    ) -> None:
        self.liveportrait_dir = liveportrait_dir or config.LIVEPORTRAIT_DIR
        self._python_bin = python_bin or config.LIVEPORTRAIT_PYTHON
        self._retarget_script = retarget_script or config.LIVEPORTRAIT_RETARGET_SCRIPT

    def retarget(
        self,
        source_image: Path,
        expression: LivePortraitExpression,
        output_dir: Path,
    ) -> Path:
        """
        對源圖套用表情參數，產出帶表情的中間圖片。

        Args:
            source_image: 角色源圖（臉部肖像，任意尺寸）
            expression: LivePortrait 表情參數集
            output_dir: 中間產物輸出目錄

        Returns:
            帶表情的中間圖片路徑（PNG）

        Raises:
            FileNotFoundError: LivePortrait venv/腳本不存在
            RuntimeError: LivePortrait 推論失敗或超時
        """
        # 環境檢查
        if not self._python_bin.exists():
            raise FileNotFoundError(
                f"LivePortrait venv Python 不存在：{self._python_bin}"
            )
        if not self._retarget_script.exists():
            raise FileNotFoundError(
                f"LivePortrait retarget 腳本不存在：{self._retarget_script}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        # 處理非 ASCII 路徑
        ascii_img = to_ascii_temp(source_image)

        # 建構 JSON 配置
        retarget_config = {
            "source": str(ascii_img).replace("\\", "/"),
            "output_dir": str(output_dir).replace("\\", "/"),
            **asdict(expression),
        }

        config_path = output_dir / "retarget_config.json"
        config_path.write_text(
            json.dumps(retarget_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        _logger.info(
            "LivePortrait retarget 開始：source=%s, expression=%s",
            source_image.name, expression,
        )

        cmd = [
            str(self._python_bin),
            str(self._retarget_script),
            "--config", str(config_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._RETARGET_TIMEOUT,
                cwd=str(self.liveportrait_dir),
            )
        except subprocess.TimeoutExpired:
            _logger.error(
                "LivePortrait retarget 超時（>%ds）", self._RETARGET_TIMEOUT,
            )
            raise RuntimeError(
                f"LivePortrait retarget 超時（>{self._RETARGET_TIMEOUT}s）"
            )
        finally:
            cleanup_temp(ascii_img)

        if result.returncode != 0:
            _logger.error(
                "LivePortrait retarget 失敗（exit=%d）：%s",
                result.returncode,
                result.stderr[-500:] if result.stderr else "無 stderr",
            )
            raise RuntimeError(
                f"LivePortrait retarget 失敗（exit={result.returncode}）"
            )

        # 尋找產出 PNG
        output_image = output_dir / "retargeted.png"
        if not output_image.exists():
            # 嘗試找任何 PNG 檔案
            pngs = list(output_dir.glob("*.png"))
            if not pngs:
                raise RuntimeError(
                    f"LivePortrait retarget 未產出圖片（搜尋：{output_dir}）"
                )
            output_image = pngs[0]

        _logger.info(
            "LivePortrait retarget 完成：%s（%.1f KB）",
            output_image, output_image.stat().st_size / 1024,
        )
        return output_image

    def retarget_video(
        self,
        source_image: Path,
        frames: list[LivePortraitExpression],
        output_dir: Path,
        fps: int = _DEFAULT_MOTION_FPS,
    ) -> Path:
        """
        批量 retarget：生成帶自然動態的 MP4 影片。

        每幀使用不同的表情參數（blink/eyebrow/head/eye），
        產出帶自然人體微動的影片。

        Args:
            source_image: 角色源圖（臉部肖像）
            frames: 逐幀 LivePortraitExpression 列表
            output_dir: 中間產物輸出目錄
            fps: 影片幀率（預設 10fps）

        Returns:
            帶動態的 MP4 影片路徑

        Raises:
            FileNotFoundError: LivePortrait venv/腳本不存在
            RuntimeError: LivePortrait 推論失敗或超時
        """
        # 環境檢查
        if not self._python_bin.exists():
            raise FileNotFoundError(
                f"LivePortrait venv Python 不存在：{self._python_bin}"
            )
        if not self._retarget_script.exists():
            raise FileNotFoundError(
                f"LivePortrait retarget 腳本不存在：{self._retarget_script}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        # 處理非 ASCII 路徑
        ascii_img = to_ascii_temp(source_image)

        # 建構批量 JSON 配置
        frames_dicts = [asdict(f) for f in frames]
        batch_config = {
            "source": str(ascii_img).replace("\\", "/"),
            "output_dir": str(output_dir).replace("\\", "/"),
            "mode": "batch",
            "fps": fps,
            "frames": frames_dicts,
        }

        config_path = output_dir / "retarget_batch_config.json"
        config_path.write_text(
            json.dumps(batch_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        _logger.info(
            "LivePortrait 批量 retarget 開始：%d 幀 @ %dfps（%.1fs 影片），"
            "source=%s",
            len(frames), fps, len(frames) / fps, source_image.name,
        )

        cmd = [
            str(self._python_bin),
            str(self._retarget_script),
            "--config", str(config_path),
        ]

        # 批量模式超時：模型載入 + 每幀 ~0.2s
        batch_timeout = 600 + len(frames) * 1

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=batch_timeout,
                cwd=str(self.liveportrait_dir),
            )
        except subprocess.TimeoutExpired:
            _logger.error(
                "LivePortrait 批量 retarget 超時（>%ds，%d 幀）",
                batch_timeout, len(frames),
            )
            raise RuntimeError(
                f"LivePortrait 批量 retarget 超時"
                f"（>{batch_timeout}s，{len(frames)} 幀）"
            )
        finally:
            cleanup_temp(ascii_img)

        # 記錄 subprocess 輸出（含進度資訊）
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-10:]:
                _logger.debug("LP stdout: %s", line)
        if result.returncode != 0:
            _logger.error(
                "LivePortrait 批量 retarget 失敗（exit=%d）：%s",
                result.returncode,
                result.stderr[-500:] if result.stderr else "無 stderr",
            )
            raise RuntimeError(
                f"LivePortrait 批量 retarget 失敗"
                f"（exit={result.returncode}）"
            )

        # 尋找產出 MP4
        output_video = output_dir / "motion.mp4"
        if not output_video.exists():
            mp4s = list(output_dir.glob("*.mp4"))
            if not mp4s:
                raise RuntimeError(
                    f"LivePortrait 批量 retarget 未產出影片"
                    f"（搜尋：{output_dir}）"
                )
            output_video = mp4s[0]

        size_mb = output_video.stat().st_size / (1024 ** 2)
        _logger.info(
            "LivePortrait 批量 retarget 完成：%s（%.1f MB，%d 幀）",
            output_video, size_mb, len(frames),
        )
        return output_video
