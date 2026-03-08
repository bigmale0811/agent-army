# -*- coding: utf-8 -*-
"""
Singer Agent Telegram Bot 啟動腳本。

Usage:
    python scripts/run_singer_bot.py

環境變數（.env 自動載入）：
    SINGER_BOT_TOKEN — Telegram Bot API Token
    SINGER_CHAT_ID   — 允許使用的 Telegram 使用者 ID（逗號分隔）
"""
import logging
import sys
from pathlib import Path

# 確保專案根目錄在 sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.singer_agent.bot import create_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

_logger = logging.getLogger(__name__)


def main() -> None:
    """啟動 Singer Bot polling。"""
    _logger.info("正在啟動 Singer Agent Telegram Bot...")

    try:
        app = create_application()
    except ValueError as exc:
        _logger.error("啟動失敗：%s", exc)
        sys.exit(1)

    _logger.info("Bot 啟動成功，開始 polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
