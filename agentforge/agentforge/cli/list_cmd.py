# -*- coding: utf-8 -*-
"""agentforge list 指令 — 列出當前專案的所有 Agent 定義。

掃描 agents/ 目錄，解析 YAML 並以 Rich 表格呈現。
"""

from pathlib import Path
from typing import Any

import click
import yaml
from rich.table import Table

from agentforge.utils.display import console, print_info, print_warning


def _parse_agent_yaml(file_path: Path) -> dict[str, Any] | None:
    """安全解析單一 Agent YAML 檔案。

    Args:
        file_path: YAML 檔案路徑。

    Returns:
        解析後的 dict，或 None（若解析失敗）。
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return data
        return None
    except (yaml.YAMLError, OSError):
        # 無效的 YAML 或讀取失敗，靜默跳過
        return None


@click.command("list")
def list_command() -> None:
    """列出當前專案中的所有 Agent 定義。

    掃描 ./agents/ 目錄下的所有 .yaml 檔案並以表格呈現。
    """
    agents_dir = Path("agents")

    # 檢查 agents 目錄是否存在
    if not agents_dir.is_dir():
        print_warning(
            "找不到 agents/ 目錄。"
            " 請先執行 [bold]agentforge init <name>[/bold] 初始化專案。"
        )
        return

    # 掃描所有 YAML 檔案
    yaml_files = sorted(agents_dir.glob("*.yaml")) + sorted(
        agents_dir.glob("*.yml")
    )

    if not yaml_files:
        print_info(
            "agents/ 目錄中沒有找到任何 Agent 定義。"
            " 可用 YAML 格式在 agents/ 目錄下建立 Agent。"
        )
        return

    # 建立 Rich 表格
    table = Table(
        title="Agent 清單",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Name", style="bold white", min_width=15)
    table.add_column("Description", style="dim", min_width=30)
    table.add_column("Steps", justify="center", style="green", min_width=6)

    agent_count = 0
    for yaml_file in yaml_files:
        data = _parse_agent_yaml(yaml_file)
        if data is None:
            # 無效 YAML，跳過不崩潰
            continue

        name = data.get("name", yaml_file.stem)
        description = data.get("description", "-")
        steps = data.get("steps", [])
        step_count = len(steps) if isinstance(steps, list) else 0

        table.add_row(name, description, str(step_count))
        agent_count += 1

    if agent_count == 0:
        print_info("agents/ 目錄中沒有有效的 Agent 定義。")
        return

    console.print(table)
    print_info(f"共 {agent_count} 個 Agent")
