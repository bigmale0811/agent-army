# -*- coding: utf-8 -*-
"""AgentForge Telegram Bot 主類別（DEV-10）。

採用 Polling 模式運行，適合開發與個人使用。
延遲 import python-telegram-bot（選配依賴），避免模組載入時出錯。
"""

from __future__ import annotations

from pathlib import Path


class AgentForgeBot:
    """AgentForge Telegram Bot。

    以 Polling 模式接收 Telegram 訊息，調用 BotHandlers 處理指令。
    需要安裝選配依賴：pip install agentforge[telegram]

    Attributes:
        _token: Telegram Bot API Token。
        _allowed: 白名單使用者 ID 集合。
        _project_path: AgentForge 專案根目錄路徑。
    """

    def __init__(
        self,
        bot_token: str,
        allowed_users: list[int],
        project_path: Path,
    ) -> None:
        """初始化 Bot。

        Args:
            bot_token: Telegram Bot API Token（由 @BotFather 取得）。
            allowed_users: 白名單使用者 ID 串列，空串列代表不限制。
            project_path: AgentForge 專案根目錄路徑。

        Raises:
            ValueError: bot_token 為空或純空白字串。
        """
        # 驗證 Token 不可為空
        if not bot_token or not bot_token.strip():
            raise ValueError(
                "未設定 Telegram Bot Token。\n"
                "請先執行 agentforge setup 設定 Bot Token，\n"
                "或在 agentforge.yaml 的 telegram.bot_token 填入 Token。"
            )

        self._token: str = bot_token
        # 轉換為 set 確保 O(1) 查詢效能
        self._allowed: set[int] = set(allowed_users)
        self._project_path: Path = project_path

    def start(self) -> None:
        """啟動 Bot（blocking，Polling 模式）。

        延遲 import python-telegram-bot，僅在呼叫此方法時才需要套件。
        若套件未安裝，拋出友善的 ImportError 提示安裝步驟。

        Raises:
            ImportError: python-telegram-bot 未安裝。
        """
        # 延遲 import：只有在實際啟動時才需要 telegram 套件
        try:
            from telegram.ext import Application, CommandHandler
        except ImportError as exc:
            raise ImportError(
                "需要安裝 Telegram 套件：pip install agentforge[telegram]\n"
                "或直接安裝：pip install python-telegram-bot>=21.0"
            ) from exc

        from agentforge.telegram.auth import AuthMiddleware
        from agentforge.telegram.handlers import BotHandlers

        # 建立 Application
        app = Application.builder().token(self._token).build()

        # 建立中介層與處理器
        auth = AuthMiddleware(self._allowed)
        handlers = BotHandlers(self._project_path)

        # 註冊所有指令（全部套上白名單驗證）
        app.add_handler(CommandHandler("start", auth.wrap(handlers.cmd_start)))
        app.add_handler(CommandHandler("help", auth.wrap(handlers.cmd_help)))
        app.add_handler(CommandHandler("list", auth.wrap(handlers.cmd_list)))
        app.add_handler(CommandHandler("run", auth.wrap(handlers.cmd_run)))
        app.add_handler(CommandHandler("status", auth.wrap(handlers.cmd_status)))

        # 啟動 Polling（blocking）
        app.run_polling()
