# -*- coding: utf-8 -*-
"""Singer Agent — 專案狀態持久化

將 MVProject 儲存為 JSON 檔案，追蹤流程狀態。
"""

import json
import logging
from pathlib import Path

from .config import PROJECTS_DIR, SPECS_DIR
from .models import MVProject, SongSpec

logger = logging.getLogger(__name__)


def save_project(project: MVProject) -> None:
    """儲存 MV 專案狀態

    Args:
        project: MV 專案物件
    """
    filepath = PROJECTS_DIR / f"{project.project_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
    logger.debug("專案已儲存: %s", filepath)


def load_project(project_id: str) -> MVProject:
    """載入 MV 專案

    Args:
        project_id: 專案 ID

    Returns:
        MV 專案物件

    Raises:
        FileNotFoundError: 找不到專案檔案
    """
    filepath = PROJECTS_DIR / f"{project_id}.json"
    if not filepath.exists():
        raise FileNotFoundError(f"找不到專案: {project_id}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return MVProject.from_dict(data)


def save_spec(spec: SongSpec, project_id: str) -> None:
    """儲存歌曲規格書

    Args:
        spec: 歌曲規格書
        project_id: 專案 ID
    """
    filepath = SPECS_DIR / f"{project_id}_spec.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(spec.to_dict(), f, ensure_ascii=False, indent=2)
    logger.debug("規格書已儲存: %s", filepath)


def list_projects() -> list[MVProject]:
    """列出所有 MV 專案

    Returns:
        按建立時間排序的專案列表（最新的在前）
    """
    projects = []
    for filepath in sorted(PROJECTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            projects.append(MVProject.from_dict(data))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("載入專案失敗 %s: %s", filepath.name, e)
    return projects
