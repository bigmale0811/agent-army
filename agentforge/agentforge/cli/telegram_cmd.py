# -*- coding: utf-8 -*-
"""agentforge telegram 指令 — 啟動 Telegram Bot（DEV-11）。

從 agentforge.yaml 讀取 telegram 設定，建立 AgentForgeBot 並以
Polling 模式啟動。需要安裝選配依賴：pip install agentforge[telegram]
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from agentforge.schema import AgentForgeValidationError, load_global_config
from agentforge.utils.display import print_error, print_info


@click.command("telegram")
def telegram_command() -> None:
    """啟動 Telegram Bot — 在手機上遠端操控 AgentForge。

    從目前工作目錄的 agentforge.yaml 讀取 telegram 設定，
    並以 Polling 模式啟動 Bot。

    必要設定（agentforge.yaml）：
        telegram:
          bot_token: "YOUR_BOT_TOKEN"
          allowed_users: [123456789]  # 留空表示不限制使用者
    """
    # 1. 以目前工作目錄尋找 agentforge.yaml
    cwd = Path.cwd()
    config_path = cwd / "agentforge.yaml"

    # 2. 載入全域設定
    try:
        global_config = load_global_config(config_path)
    except AgentForgeValidationError as exc:
        print_error(f"無法載入設定：{exc}")
        sys.exit(1)

    # 3. 檢查 telegram 設定是否存在
    if global_config.telegram is None:
        print_error(
            "agentforge.yaml 中缺少 telegram 設定。\n"
            "請加入以下設定：\n"
            "\n"
            "telegram:\n"
            "  bot_token: \"YOUR_BOT_TOKEN\"\n"
            "  allowed_users: []  # 留空表示允許所有人"
        )
        sys.exit(1)

    # 4. 檢查 bot_token 是否有效
    telegram_cfg = global_config.telegram
    if not telegram_cfg.bot_token or not telegram_cfg.bot_token.strip():
        print_error(
            "telegram.bot_token 未設定或為空。\n"
            "請前往 Telegram 向 @BotFather 申請 Bot Token，\n"
            "並填入 agentforge.yaml 的 telegram.bot_token 欄位。"
        )
        sys.exit(1)

    # 5. 建立 AgentForgeBot 並啟動
    from agentforge.telegram.bot import AgentForgeBot

    try:
        bot = AgentForgeBot(
            bot_token=telegram_cfg.bot_token,
            allowed_users=list(telegram_cfg.allowed_users),
            project_path=cwd,
        )
    except ValueError as exc:
        print_error(str(exc))
        sys.exit(1)

    print_info(
        f"AgentForge Telegram Bot 正在啟動...\n"
        f"白名單使用者：{'不限制' if not telegram_cfg.allowed_users else telegram_cfg.allowed_users}\n"
        f"按 Ctrl+C 停止。"
    )

    try:
        bot.start()
    except ImportError as exc:
        print_error(str(exc))
        sys.exit(1)
    except KeyboardInterrupt:
        print_info("Telegram Bot 已停止。")
