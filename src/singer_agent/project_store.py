# -*- coding: utf-8 -*-
"""
DEV-5: 專案儲存管理。

將 ProjectState 序列化為 JSON 檔案並支援還原。
功能：
- save()：將 ProjectState 寫入 JSON（ensure_ascii=False 保留中文）
- load()：從 JSON 還原 ProjectState
- list_projects()：列出所有專案，按 created_at 降冪排序
"""
import json
import logging
from pathlib import Path
from typing import Optional

from src.singer_agent import config
from src.singer_agent.models import ProjectState

_logger = logging.getLogger(__name__)


class ProjectStore:
    """
    專案持久化儲存。

    每個 ProjectState 序列化為一個 JSON 檔案，
    檔名格式為 {project_id}.json。

    Args:
        projects_dir: 儲存目錄，預設為 config.PROJECTS_DIR
    """

    def __init__(self, projects_dir: Optional[Path] = None) -> None:
        self.projects_dir = projects_dir or config.PROJECTS_DIR

    def save(self, state: ProjectState) -> Path:
        """
        將 ProjectState 序列化並寫入 JSON 檔案。

        自動建立目錄（若不存在），中文字元直接寫入（非 \\uXXXX 跳脫）。

        Args:
            state: 要儲存的專案狀態

        Returns:
            寫入的 JSON 檔案路徑
        """
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.projects_dir / f"{state.project_id}.json"
        data = state.to_dict()
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path

    def load(self, project_id: str) -> ProjectState:
        """
        從 JSON 檔案還原 ProjectState。

        Args:
            project_id: 專案 ID

        Returns:
            還原的 ProjectState 實例

        Raises:
            FileNotFoundError: 找不到指定 project_id 的檔案
        """
        # 防止路徑穿越攻擊：確保解析後路徑仍在 projects_dir 內
        file_path = (self.projects_dir / f"{project_id}.json").resolve()
        projects_dir_resolved = self.projects_dir.resolve()
        if not str(file_path).startswith(str(projects_dir_resolved)):
            raise ValueError(f"非法的 project_id：'{project_id}'")
        if not file_path.exists():
            raise FileNotFoundError(
                f"找不到專案 '{project_id}'：{file_path} 不存在"
            )
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return ProjectState.from_dict(data)

    def list_projects(self) -> list[ProjectState]:
        """
        列出所有已儲存的專案，按 created_at 降冪排序（最新在前）。

        非 JSON 檔案會被忽略，損壞的 JSON 也會被跳過。

        Returns:
            ProjectState 列表，按建立時間降冪排序
        """
        if not self.projects_dir.exists():
            return []

        projects: list[ProjectState] = []
        for file_path in self.projects_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                projects.append(ProjectState.from_dict(data))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                _logger.warning("跳過損壞的專案檔案 %s：%s", file_path, exc)
                continue

        # 按 created_at 降冪排序（最新在前）
        projects.sort(key=lambda p: p.created_at, reverse=True)
        return projects
