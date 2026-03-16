# -*- coding: utf-8 -*-
"""AgentForge 測試共用 fixtures。"""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """建立臨時 AgentForge 專案目錄。"""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    agents_dir = project_dir / "agents"
    agents_dir.mkdir()
    forge_dir = project_dir / ".agentforge"
    forge_dir.mkdir()
    return project_dir
