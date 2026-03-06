# -*- coding: utf-8 -*-
"""
DEV-10: 品質預檢模組。

QualityPrecheck 在影片渲染前執行多項檢查：
- 合成圖片是否存在
- 音訊檔案是否存在
- 磁碟空間是否足夠（>= 1GB）
- 可選 Gemini Vision API 評分
"""
import logging
import shutil
from pathlib import Path

from src.singer_agent import config
from src.singer_agent.models import PrecheckResult, SongSpec

_logger = logging.getLogger(__name__)

# 最低磁碟空間需求（1 GB）
_MIN_DISK_FREE_BYTES = 1 * 1024 * 1024 * 1024


class QualityPrecheck:
    """
    品質預檢器。

    在管線的 Step 6 執行，確保所有素材就位、
    系統資源充足後才進入耗時的影片渲染步驟。
    """

    def run(
        self,
        composite_image: Path,
        audio_path: Path,
        song_spec: SongSpec | None = None,
        dry_run: bool = False,
    ) -> PrecheckResult:
        """
        執行品質預檢。

        Args:
            composite_image: 合成圖片路徑
            audio_path: 音訊檔案路徑
            song_spec: 歌曲規格（用於 Gemini 評分，可選）
            dry_run: True 時回傳全通過的結果

        Returns:
            PrecheckResult 結構化結果
        """
        if dry_run:
            _logger.info("dry_run 模式：回傳全通過的 PrecheckResult")
            return PrecheckResult(
                passed=True,
                checks={
                    "image_exists": True,
                    "audio_exists": True,
                    "disk_space": True,
                },
                warnings=[],
                gemini_score=None,
                gemini_feedback="",
            )

        checks: dict[str, bool] = {}
        warnings: list[str] = []

        # 檢查圖片存在
        checks["image_exists"] = composite_image.exists()
        if not checks["image_exists"]:
            warnings.append(f"合成圖片不存在：{composite_image}")

        # 檢查音訊存在
        checks["audio_exists"] = audio_path.exists()
        if not checks["audio_exists"]:
            warnings.append(f"音訊檔案不存在：{audio_path}")

        # 檢查磁碟空間
        try:
            usage = shutil.disk_usage(composite_image.parent)
            checks["disk_space"] = usage.free >= _MIN_DISK_FREE_BYTES
            if not checks["disk_space"]:
                free_gb = usage.free / (1024 ** 3)
                warnings.append(f"磁碟空間不足：{free_gb:.1f} GB（需 >= 1 GB）")
        except OSError as exc:
            checks["disk_space"] = False
            warnings.append(f"無法檢查磁碟空間：{exc}")

        # Gemini 視覺評分（可選）
        gemini_score: int | None = None
        gemini_feedback = ""
        if config.GEMINI_API_KEY:
            _logger.debug("Gemini API key 存在，但本版本暫不呼叫")
            # 未來版本實作 Gemini Vision 評分
        else:
            _logger.debug("無 Gemini API key，跳過視覺評分")

        # 整體判定：所有 checks 都必須為 True
        passed = all(checks.values())

        _logger.info("預檢結果：%s（%s）", "通過" if passed else "失敗", checks)
        return PrecheckResult(
            passed=passed,
            checks=checks,
            warnings=warnings,
            gemini_score=gemini_score,
            gemini_feedback=gemini_feedback,
        )
