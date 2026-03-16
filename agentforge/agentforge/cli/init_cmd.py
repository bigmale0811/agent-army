# -*- coding: utf-8 -*-
"""agentforge init 指令 — 初始化新的 AgentForge 專案。

在指定路徑建立完整的專案目錄結構，包含設定檔與範例 Agent。
"""

import shutil
from pathlib import Path

import click

from agentforge.utils.display import print_error, print_info, print_success


def _get_templates_dir() -> Path:
    """取得模板目錄的絕對路徑。"""
    return Path(__file__).resolve().parent.parent / "templates"


@click.command("init")
@click.argument("name")
def init_command(name: str) -> None:
    """初始化新的 AgentForge 專案。

    NAME: 專案名稱（支援巢狀路徑，如 parent/my-project）。
    """
    project_path = Path(name)

    # 檢查目錄是否已存在
    if project_path.exists():
        print_error(
            f"目錄 '{name}' 已存在！"
            f" 請選擇其他名稱，或刪除後再試。"
        )
        raise SystemExit(1)

    templates_dir = _get_templates_dir()

    try:
        # 建立專案目錄結構（含父目錄）
        project_path.mkdir(parents=True, exist_ok=False)
        agents_dir = project_path / "agents"
        agents_dir.mkdir()
        dot_dir = project_path / ".agentforge"
        dot_dir.mkdir()

        # 複製模板檔案
        shutil.copy2(
            templates_dir / "agentforge.yaml",
            project_path / "agentforge.yaml",
        )
        shutil.copy2(
            templates_dir / "example.yaml",
            agents_dir / "example.yaml",
        )

        # 顯示建立的檔案清單
        print_success(f"專案 '{name}' 初始化完成！")
        print_info("已建立以下檔案：")
        created_files = [
            project_path / "agentforge.yaml",
            agents_dir / "example.yaml",
            dot_dir,
        ]
        for item in created_files:
            # 用相對路徑顯示，比較乾淨
            click.echo(f"  {item}")

        click.echo()
        print_info(f"開始使用：cd {name} && agentforge list")

    except OSError as exc:
        print_error(f"建立專案失敗：{exc}")
        raise SystemExit(1) from exc
