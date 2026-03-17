# -*- coding: utf-8 -*-
"""agentforge setup 子指令 — 互動式安裝精靈 CLI 入口。

此模組提供 `agentforge setup` 指令，透過互動式精靈
引導使用者一步步完成 AgentForge 的初始設定。

支援選項：
- --dry-run：模擬執行，不實際寫入任何檔案
- --auto：全自動模式，所有選擇使用預設值（適合 CI/CD 或測試）
"""

import sys

import click

from agentforge.setup.wizard import SetupWizard


@click.command("setup")
@click.option("--dry-run", is_flag=True, help="模擬執行，不實際寫入檔案")
@click.option("--auto", is_flag=True, help="全自動模式，使用預設值（適合測試）")
@click.option("--gui", is_flag=True, help="啟動圖形介面安裝精靈")
def setup_command(dry_run: bool, auto: bool, gui: bool) -> None:
    """互動式安裝精靈 — 一步步帶你完成 AgentForge 設定。

    如果你是第一次使用 AgentForge，執行此指令開始設定。
    精靈會引導你選擇 AI 服務、設定通行證、並建立設定檔。

    範例用法：

    \b
        agentforge setup              # 終端機互動式設定
        agentforge setup --gui        # 圖形介面安裝精靈
        agentforge setup --dry-run    # 模擬執行（不寫入檔案）
        agentforge setup --auto       # 全自動（使用預設值）
    """
    if gui:
        from agentforge.setup.gui_wizard import _launch_gui
        _launch_gui(dry_run=dry_run)
        return

    wizard = SetupWizard(dry_run=dry_run, auto=auto)
    success = wizard.run()
    sys.exit(0 if success else 1)
