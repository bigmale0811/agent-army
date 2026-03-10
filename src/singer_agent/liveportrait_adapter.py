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
