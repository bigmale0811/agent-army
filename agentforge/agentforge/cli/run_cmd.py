# -*- coding: utf-8 -*-
"""agentforge run 指令 — 執行指定的 Agent。

從 agents/ 目錄載入 Agent YAML 定義，透過 PipelineEngine 執行所有步驟，
並以 Rich 輸出即時顯示進度。
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from agentforge.core.engine import PipelineEngine
from agentforge.llm.router import LLMRouter
from agentforge.schema import (
    AgentForgeValidationError,
    load_agent_def,
    load_global_config,
)
from agentforge.utils.display import DisplayManager, print_error, print_info


def _find_agent_yaml(agents_dir: Path, agent_name: str) -> Path | None:
    """在 agents 目錄中搜尋 Agent YAML 檔案。

    依序嘗試 <name>.yaml 和 <name>.yml 兩種副檔名。

    Args:
        agents_dir: agents 目錄路徑。
        agent_name: Agent 名稱（不含副檔名）。

    Returns:
        找到的 Path 物件；若未找到則回傳 None。
    """
    for ext in (".yaml", ".yml"):
        candidate = agents_dir / f"{agent_name}{ext}"
        if candidate.exists():
            return candidate
    return None


@click.command("run")
@click.argument("agent")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="模擬執行模式：顯示執行計畫但不實際執行。",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="顯示每個步驟的詳細輸出內容。",
)
def run_command(agent: str, dry_run: bool, verbose: bool) -> None:
    """執行指定的 Agent。

    AGENT: 要執行的 Agent 名稱（對應 agents/ 下的 YAML 檔名）。
    """
    # 以目前工作目錄為基礎尋找設定檔
    cwd = Path.cwd()
    config_path = cwd / "agentforge.yaml"
    agents_dir = cwd / "agents"

    # 1. 載入全域設定
    try:
        global_config = load_global_config(config_path)
    except AgentForgeValidationError as exc:
        print_error(f"無法載入全域設定：{exc}")
        sys.exit(1)

    # 2. 尋找 Agent YAML 檔案
    agent_path = _find_agent_yaml(agents_dir, agent)
    if agent_path is None:
        print_error(
            f"找不到 Agent '{agent}' 的定義檔案。"
            f"請確認 {agents_dir}/{agent}.yaml 是否存在。"
        )
        sys.exit(1)

    # 3. 載入 Agent 定義
    try:
        agent_def = load_agent_def(agent_path)
    except AgentForgeValidationError as exc:
        print_error(f"Agent 定義驗證失敗：{exc}")
        sys.exit(1)

    if dry_run:
        print_info(f"[DRY-RUN] Simulating agent '{agent}' (no real operations)")

    # 4. 建立執行元件
    router = LLMRouter(global_config)
    display = DisplayManager(verbose=verbose)
    engine = PipelineEngine(router=router, callback=display)

    # 5. 執行 Pipeline
    result = engine.execute(agent_def, dry_run=dry_run)

    # 6. 依結果設定退出碼
    sys.exit(0 if result.success else 1)
