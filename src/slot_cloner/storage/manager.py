"""Storage Manager — 管理輸出目錄結構"""
from __future__ import annotations
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# AC-5 定義的標準輸出目錄結構
OUTPUT_DIRS = (
    "assets/images",
    "assets/sprites",
    "assets/audio",
    "assets/fonts",
    "analysis",
    "analysis/screenshots",
    "game",
    "game/src",
    "game/dist",
)


class StorageManager:
    """輸出目錄管理器"""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def setup(self) -> Path:
        """建立標準輸出目錄結構，回傳根目錄"""
        for subdir in OUTPUT_DIRS:
            path = self._base_dir / subdir
            path.mkdir(parents=True, exist_ok=True)
            logger.debug("建立目錄: %s", path)
        logger.info("輸出目錄已建立: %s", self._base_dir)
        return self._base_dir

    def get_path(self, *parts: str) -> Path:
        """取得輸出目錄下的路徑"""
        return self._base_dir / Path(*parts)

    def images_dir(self) -> Path:
        return self._base_dir / "assets" / "images"

    def sprites_dir(self) -> Path:
        return self._base_dir / "assets" / "sprites"

    def audio_dir(self) -> Path:
        return self._base_dir / "assets" / "audio"

    def analysis_dir(self) -> Path:
        return self._base_dir / "analysis"

    def game_dir(self) -> Path:
        return self._base_dir / "game"

    def verify_structure(self) -> bool:
        """驗證輸出目錄結構是否完整"""
        for subdir in OUTPUT_DIRS:
            if not (self._base_dir / subdir).is_dir():
                return False
        return True
