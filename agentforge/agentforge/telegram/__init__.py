# -*- coding: utf-8 -*-
"""AgentForge Telegram Bot 模組。

python-telegram-bot 為選配依賴：pip install agentforge[telegram]

此模組提供：
- AuthMiddleware：白名單驗證
- TelegramFormatter：訊息格式化
- BotHandlers：指令處理器
- AgentForgeBot：Bot 主類別
"""

try:
    from agentforge.telegram.auth import AuthMiddleware
    from agentforge.telegram.bot import AgentForgeBot
    from agentforge.telegram.formatter import TelegramFormatter
    from agentforge.telegram.handlers import BotHandlers

    __all__ = [
        "AuthMiddleware",
        "TelegramFormatter",
        "BotHandlers",
        "AgentForgeBot",
    ]
except ImportError:
    # python-telegram-bot 未安裝時，模組仍可匯入，但功能不可用
    __all__ = []
