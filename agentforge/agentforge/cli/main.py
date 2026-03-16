# -*- coding: utf-8 -*-
"""AgentForge CLI 入口 — Click 框架主群組。

註冊所有子指令：init, list, run, status。
"""

import click

from agentforge import __version__
from agentforge.cli.init_cmd import init_command
from agentforge.cli.list_cmd import list_command
from agentforge.cli.run_cmd import run_command
from agentforge.cli.status_cmd import status_command


@click.group()
@click.version_option(version=__version__, prog_name="agentforge")
def cli() -> None:
    """AgentForge — 企業 AI Agent 即服務平台。

    用 YAML 定義 AI Agent，一行指令執行，自帶三級自動修復。
    """


# 註冊子指令
cli.add_command(init_command)
cli.add_command(list_command)
cli.add_command(run_command)
cli.add_command(status_command)
