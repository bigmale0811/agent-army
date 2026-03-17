# -*- coding: utf-8 -*-
"""AuthMiddleware 測試套件。

驗證 Telegram 使用者白名單驗證中介層的所有情境。
全部使用 Mock，不依賴真實 Telegram SDK。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# 不直接 import telegram，透過模組路徑取用
from agentforge.telegram.auth import AuthMiddleware


class TestAuthMiddlewareAllowedUser:
    """白名單使用者通過驗證測試。"""

    @pytest.mark.asyncio
    async def test_allowed_user_passes(self) -> None:
        """白名單內的使用者應通過驗證並呼叫 handler。"""
        auth = AuthMiddleware(allowed_users={123, 456})
        called = []

        async def handler(update, context):
            called.append(update.effective_user.id)

        wrapped = auth.wrap(handler)

        # 建立 mock update
        update = MagicMock()
        update.effective_user.id = 123
        update.message = MagicMock()

        await wrapped(update, MagicMock())
        assert called == [123]

    @pytest.mark.asyncio
    async def test_denied_user_blocked(self) -> None:
        """白名單外的使用者應被拒絕，handler 不被呼叫。"""
        auth = AuthMiddleware(allowed_users={100, 200})
        called = []

        async def handler(update, context):
            called.append("called")

        wrapped = auth.wrap(handler)

        # 建立不在白名單的 user
        update = MagicMock()
        update.effective_user.id = 999
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        await wrapped(update, MagicMock())

        # handler 不應被呼叫
        assert called == []
        # 應回覆拒絕訊息
        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args[0]
        assert "沒有權限" in args[0]

    @pytest.mark.asyncio
    async def test_empty_whitelist_allows_all(self) -> None:
        """空白名單應允許所有使用者（不限制）。"""
        auth = AuthMiddleware(allowed_users=set())
        called = []

        async def handler(update, context):
            called.append(update.effective_user.id)

        wrapped = auth.wrap(handler)

        update = MagicMock()
        update.effective_user.id = 99999
        update.message = MagicMock()

        await wrapped(update, MagicMock())
        # 空白名單不限制，handler 應被呼叫
        assert called == [99999]

    @pytest.mark.asyncio
    async def test_no_effective_user_blocked(self) -> None:
        """update.effective_user 為 None 時，有白名單設定應拒絕。"""
        auth = AuthMiddleware(allowed_users={123})
        called = []

        async def handler(update, context):
            called.append("called")

        wrapped = auth.wrap(handler)

        # effective_user 為 None
        update = MagicMock()
        update.effective_user = None
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        await wrapped(update, MagicMock())
        # user_id 會是 0，不在白名單，handler 不應被呼叫
        assert called == []

    @pytest.mark.asyncio
    async def test_no_message_on_denied_no_crash(self) -> None:
        """update.message 為 None 時拒絕不應 crash。"""
        auth = AuthMiddleware(allowed_users={100})
        called = []

        async def handler(update, context):
            called.append("called")

        wrapped = auth.wrap(handler)

        update = MagicMock()
        update.effective_user.id = 999
        update.message = None  # 沒有 message

        # 不應拋出例外
        await wrapped(update, MagicMock())
        assert called == []

    @pytest.mark.asyncio
    async def test_handler_return_value_preserved(self) -> None:
        """通過驗證的 handler 回傳值應被保留。"""
        auth = AuthMiddleware(allowed_users={123})

        async def handler(update, context):
            return "handler_result"

        wrapped = auth.wrap(handler)

        update = MagicMock()
        update.effective_user.id = 123
        update.message = MagicMock()

        result = await wrapped(update, MagicMock())
        assert result == "handler_result"
