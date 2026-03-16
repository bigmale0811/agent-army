# -*- coding: utf-8 -*-
"""agentforge status 指令 — 顯示執行歷史與成本統計儀表板。

從 .agentforge/tracker.db 讀取 TaskTracker 的 SQLite 記錄，
以 Rich 表格呈現各 Agent 的執行次數、成功率與總費用。
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from agentforge.core.task_tracker import TaskTracker
from agentforge.utils.display import print_info, print_warning

# 預設資料庫路徑（相對於工作目錄）
_DEFAULT_DB = Path(".agentforge") / "tracker.db"


def _find_tracker_db(cwd: Path) -> Path | None:
    """在工作目錄尋找 tracker.db。

    Args:
        cwd: 工作目錄路徑。

    Returns:
        資料庫路徑，若不存在則回傳 None。
    """
    db_path = cwd / _DEFAULT_DB
    if db_path.exists():
        return db_path
    return None


def _render_status_table(tracker: TaskTracker, console: Console) -> None:
    """用 Rich 表格顯示所有 Agent 的執行統計。

    Args:
        tracker: 已開啟的 TaskTracker 實例。
        console: Rich Console 輸出目標。
    """
    stats_list = tracker.get_all_stats()

    if not stats_list:
        print_info("資料庫存在但尚無執行記錄。")
        return

    table = Table(
        title="AgentForge 執行統計",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Agent 名稱", style="bold", min_width=20)
    table.add_column("執行次數", justify="right")
    table.add_column("成功次數", justify="right", style="green")
    table.add_column("失敗次數", justify="right", style="red")
    table.add_column("成功率", justify="right")
    table.add_column("總費用 (USD)", justify="right", style="yellow")

    # 按成功率高低排序（降序）
    for stats in sorted(stats_list, key=lambda s: s.agent_name):
        success_rate_str = f"{stats.success_rate:.1f}%"
        cost_str = f"${stats.total_cost_usd:.6f}"

        # 成功率顏色：綠色 >= 80%, 黃色 >= 50%, 紅色 < 50%
        if stats.success_rate >= 80.0:
            rate_style = "[bold green]"
        elif stats.success_rate >= 50.0:
            rate_style = "[bold yellow]"
        else:
            rate_style = "[bold red]"

        table.add_row(
            stats.agent_name,
            str(stats.total_runs),
            str(stats.success_count),
            str(stats.fail_count),
            f"{rate_style}{success_rate_str}[/]",
            cost_str,
        )

    console.print(table)

    # 顯示彙整行
    total_runs = sum(s.total_runs for s in stats_list)
    total_cost = sum(s.total_cost_usd for s in stats_list)
    console.print(
        f"[dim]共 {len(stats_list)} 個 Agent，{total_runs} 次執行，"
        f"累積費用 ${total_cost:.6f} USD[/dim]"
    )


@click.command("status")
@click.option(
    "--db",
    "db_path",
    default=None,
    help="指定 tracker.db 路徑（預設：.agentforge/tracker.db）",
    type=click.Path(exists=False),
)
def status_command(db_path: str | None) -> None:
    """顯示 AgentForge 執行歷史與成本統計儀表板。

    從 .agentforge/tracker.db 讀取執行記錄，
    以表格形式顯示各 Agent 的統計資料。
    """
    console = Console(emoji=False)
    cwd = Path.cwd()

    # 決定資料庫路徑
    if db_path is not None:
        resolved_db = Path(db_path)
    else:
        resolved_db = _find_tracker_db(cwd)

    # 資料庫不存在時顯示提示訊息
    if resolved_db is None or not resolved_db.exists():
        print_warning("尚無執行記錄。請先執行 agentforge run <agent-name>。")
        return

    tracker = None
    try:
        tracker = TaskTracker(resolved_db)
        _render_status_table(tracker, console)
    except Exception as exc:  # noqa: BLE001
        # 資料庫讀取失敗（可能損壞）
        from agentforge.utils.display import print_error
        print_error(f"無法讀取執行記錄：{exc}")
        raise SystemExit(1) from exc
    finally:
        if tracker is not None:
            tracker.close()
