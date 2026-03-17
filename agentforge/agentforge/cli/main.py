# -*- coding: utf-8 -*-
"""AgentForge CLI 入口 — Click 框架主群組。

註冊所有子指令：init, list, run, status, setup, gui, telegram。
"""

import sys

import click

from agentforge import __version__
from agentforge.cli.init_cmd import init_command
from agentforge.cli.list_cmd import list_command
from agentforge.cli.run_cmd import run_command
from agentforge.cli.setup_cmd import setup_command
from agentforge.cli.status_cmd import status_command
from agentforge.cli.telegram_cmd import telegram_command


@click.group()
@click.version_option(version=__version__, prog_name="agentforge")
def cli() -> None:
    """AgentForge — 企業 AI Agent 即服務平台。

    用 YAML 定義 AI Agent，一行指令執行，自帶三級自動修復。
    """


@click.command("gui")
@click.option("--dry-run", is_flag=True, help="模擬執行，不實際寫入檔案")
def gui_command(dry_run: bool) -> None:
    """啟動圖形介面安裝精靈 — 適合不熟悉終端機的使用者。

    \b
        agentforge gui              # 啟動 GUI 安裝精靈
        agentforge gui --dry-run    # 模擬執行（不寫入檔案）
    """
    from agentforge.setup.gui_wizard import _launch_gui
    _launch_gui(dry_run=dry_run)


# 註冊子指令
cli.add_command(init_command)
cli.add_command(list_command)
cli.add_command(run_command)
cli.add_command(setup_command)
cli.add_command(status_command)
cli.add_command(telegram_command)
cli.add_command(gui_command)
