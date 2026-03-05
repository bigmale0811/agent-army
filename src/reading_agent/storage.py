# -*- coding: utf-8 -*-
"""讀書 Agent — 資料儲存模組

將蒐集到的影片和產生的報告以 JSON 格式儲存到本地檔案系統。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from .config import VIDEOS_DIR, REPORTS_DIR
from .models import Video, ReadingReport

logger = logging.getLogger(__name__)


class VideoStorage:
    """影片資料儲存

    將影片資料以日期分檔儲存為 JSON。
    支援合併（同日期多次蒐集不重複）和日期範圍查詢。
    """

    def __init__(self, base_dir: Path = VIDEOS_DIR):
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save_videos(self, videos: list[Video], date_str: str = "") -> Path:
        """儲存影片資料

        Args:
            videos: 影片列表
            date_str: 日期字串（預設為今天）

        Returns:
            儲存的檔案路徑
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        file_path = self._base_dir / f"{date_str}.json"

        # 如果已有同日檔案，合併（以 URL 去重）
        existing_videos: list[Video] = []
        if file_path.exists():
            existing_videos = self._load_file(file_path)

        # 合併去重
        url_set = {v.url for v in existing_videos}
        merged = list(existing_videos)
        new_count = 0
        for video in videos:
            if video.url not in url_set:
                merged.append(video)
                url_set.add(video.url)
                new_count += 1

        # 寫入 JSON
        data = [v.to_dict() for v in merged]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            "儲存 %d 部影片（新增 %d 部）到 %s",
            len(merged), new_count, file_path.name,
        )
        return file_path

    def load_videos(self, date_str: str) -> list[Video]:
        """載入指定日期的影片"""
        file_path = self._base_dir / f"{date_str}.json"
        if not file_path.exists():
            return []
        return self._load_file(file_path)

    def get_all_urls(self) -> set[str]:
        """取得所有已儲存的影片 URL（用於去重）"""
        urls: set[str] = set()
        for json_file in self._base_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    if "url" in item:
                        urls.add(item["url"])
            except (json.JSONDecodeError, OSError):
                continue
        return urls

    def _load_file(self, file_path: Path) -> list[Video]:
        """從 JSON 檔案載入影片列表"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Video.from_dict(item) for item in data]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("載入 %s 失敗: %s", file_path, e)
            return []


class ReportStorage:
    """報告儲存"""

    def __init__(self, base_dir: Path = REPORTS_DIR):
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: ReadingReport) -> Path:
        """儲存報告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self._base_dir / f"report_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info("報告已儲存: %s", file_path.name)
        return file_path

    def load_report(self, file_path: Path) -> ReadingReport:
        """載入報告"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ReadingReport.from_dict(data)
