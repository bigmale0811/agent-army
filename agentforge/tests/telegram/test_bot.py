# -*- coding: utf-8 -*-
"""AgentForgeBot 測試套件。

驗證 Bot 主類別的初始化邏輯和啟動前的驗證。
不依賴真實 Telegram SDK（全部 mock）。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agentforge.telegram.bot import AgentForgeBot


class TestAgentForgeBotInit:
    """AgentForgeBot 初始化測試。"""

    def test_bot_init_no_token_raises_value_error(self, tmp_path: Path) -> None:
        """空 token 應拋出 ValueError 且包含提示訊息。"""
        with pytest.raises(ValueError) as exc_info:
            AgentForgeBot(
                bot_token="",
                allowed_users=[],
                project_path=tmp_path,
            )
        assert "Token" in str(exc_info.value) or "token" in str(exc_info.value).lower()

    def test_bot_init_valid_no_error(self, tmp_path: Path) -> None:
        """有效參數應可正常初始化，不拋出例外。"""
        bot = AgentForgeBot(
            bot_token="valid_token_123",
            allowed_users=[100, 200],
            project_path=tmp_path,
        )
        assert bot is not None

    def test_bot_init_stores_token(self, tmp_path: Path) -> None:
        """初始化後應儲存 token。"""
        bot = AgentForgeBot(
            bot_token="my_test_token",
            allowed_users=[],
            project_path=tmp_path,
        )
        assert bot._token == "my_test_token"

    def test_bot_init_converts_allowed_users_to_set(self, tmp_path: Path) -> None:
        """初始化後 allowed_users 應轉換為 set。"""
        bot = AgentForgeBot(
            bot_token="token_abc",
            allowed_users=[111, 222, 333],
            project_path=tmp_path,
        )
        assert isinstance(bot._allowed, set)
        assert bot._allowed == {111, 222, 333}

    def test_bot_init_stores_project_path(self, tmp_path: Path) -> None:
        """初始化後應儲存 project_path。"""
        bot = AgentForgeBot(
            bot_token="some_token",
            allowed_users=[],
            project_path=tmp_path,
        )
        assert bot._project_path == tmp_path

    def test_bot_init_empty_allowed_users_ok(self, tmp_path: Path) -> None:
        """空的 allowed_users 串列應可正常初始化（不限制使用者）。"""
        bot = AgentForgeBot(
            bot_token="any_token",
            allowed_users=[],
            project_path=tmp_path,
        )
        assert bot._allowed == set()

    def test_bot_init_whitespace_token_raises(self, tmp_path: Path) -> None:
        """純空白 token 應被視為無效並拋出 ValueError。"""
        with pytest.raises(ValueError):
            AgentForgeBot(
                bot_token="   ",
                allowed_users=[],
                project_path=tmp_path,
            )


class TestAgentForgeBotStart:
    """AgentForgeBot.start() 測試。"""

    def test_bot_no_telegram_package_raises_import_error(self, tmp_path: Path) -> None:
        """python-telegram-bot 未安裝時應拋出 ImportError 並提示安裝指令。"""
        bot = AgentForgeBot(
            bot_token="valid_token",
            allowed_users=[],
            project_path=tmp_path,
        )

        # 模擬 telegram.ext 不可用
        with patch.dict("sys.modules", {"telegram": None, "telegram.ext": None}):
            with pytest.raises((ImportError, TypeError)):
                bot.start()

    def test_bot_start_calls_run_polling(self, tmp_path: Path) -> None:
        """start() 應呼叫 Application.run_polling()。"""
        bot = AgentForgeBot(
            bot_token="valid_token",
            allowed_users=[100],
            project_path=tmp_path,
        )

        # 模擬整個 telegram.ext 模組
        mock_app = MagicMock()
        mock_app_instance = MagicMock()
        mock_app_instance.run_polling = MagicMock()
        mock_app.builder.return_value.token.return_value.build.return_value = mock_app_instance

        mock_ext = MagicMock()
        mock_ext.Application = mock_app
        mock_ext.CommandHandler = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "telegram": MagicMock(),
            "telegram.ext": mock_ext,
        }):
            bot.start()

        mock_app_instance.run_polling.assert_called_once()
