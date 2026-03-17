# -*- coding: utf-8 -*-
"""Telegram 白名單驗證中介層（DEV-07）。

僅允許在白名單中的使用者 ID 存取 Bot 功能。
空白名單模式下允許所有人存取（開發用途）。
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    pass


class AuthMiddleware:
    """Telegram 白名單驗證。

    使用 Telegram user_id（整數）進行身分驗證。
    空白名單代表不限制任何人（適合個人使用情境）。

    Examples:
        >>> auth = AuthMiddleware({123456789})
        >>> auth.is_authorized(123456789)
        True
        >>> auth.is_authorized(999999999)
        False
    """

    def __init__(self, allowed_users: set[int]) -> None:
        """初始化白名單驗證器。

        Args:
            allowed_users: 允許存取的 Telegram user_id 集合。
                           空集合代表允許所有人。
        """
        # 使用 frozenset 確保不可變性
        self._allowed: frozenset[int] = frozenset(allowed_users)

    def is_authorized(self, user_id: int) -> bool:
        """檢查使用者是否在白名單中。

        空白名單 = 允許所有人（適合個人 Bot 或測試用途）。

        Args:
            user_id: 要驗證的 Telegram user_id。

        Returns:
            True 代表允許存取；False 代表拒絕存取。
        """
        # 空白名單模式：開放給所有人
        if not self._allowed:
            return True
        return user_id in self._allowed

    def wrap(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """包裝 async handler，驗證身分後才執行。

        若使用者未在白名單，回傳「沒有權限」訊息並終止處理。

        Args:
            handler: 要包裝的 async handler 函式。

        Returns:
            包裝後的 async handler。
        """

        @wraps(handler)
        async def wrapper(update: Any, context: Any) -> Any:
            # 取得使用者 ID（若無法取得則預設為 0，視為未授權）
            user_id: int = 0
            if update.effective_user is not None:
                user_id = update.effective_user.id

            if not self.is_authorized(user_id):
                # 僅在有 message 時才回覆（避免 None 呼叫）
                if update.message is not None:
                    await update.message.reply_text("抱歉，你沒有權限使用這個機器人。")
                return None

            return await handler(update, context)

        return wrapper
