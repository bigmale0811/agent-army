# -*- coding: utf-8 -*-
"""全域設定 (agentforge.yaml) 的 Pydantic v2 模型。

此模組定義了 AgentForge 平台的全域設定結構，包括：
- LLMProviderConfig：LLM Provider 連線設定
- BudgetConfig：預算控管設定
- TelegramConfig：Telegram Bot 設定（可選）
- GlobalConfig：頂層全域設定（彙整所有子設定）

所有模型皆為 frozen（不可變）。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LLMProviderConfig(BaseModel):
    """LLM Provider 連線設定。

    Attributes:
        api_key_env: 存放 API Key 的環境變數名稱（如 OPENAI_API_KEY）。
        base_url: Provider API 的 base URL。
    """

    model_config = ConfigDict(frozen=True)

    api_key_env: str = ""  # 環境變數名稱
    base_url: str | None = None  # API base URL


class BudgetConfig(BaseModel):
    """預算控管設定。

    Attributes:
        daily_limit_usd: 每日預算上限（美元）。
        warn_at_percent: 使用量達此百分比時發出警告。
    """

    model_config = ConfigDict(frozen=True)

    daily_limit_usd: float = 10.0  # 每日預算上限（USD）
    warn_at_percent: float = 80.0  # 警告閾值百分比


class TelegramConfig(BaseModel):
    """Telegram Bot 設定。

    Attributes:
        bot_token: Telegram Bot API Token（由 @BotFather 取得）。
        allowed_users: 允許使用 Bot 的 Telegram User ID 白名單，空串列表示不限制。
    """

    model_config = ConfigDict(frozen=True)

    bot_token: str = ""  # Telegram Bot API Token
    allowed_users: list[int] = []  # User ID 白名單（空串列 = 不限制）


class GlobalConfig(BaseModel):
    """AgentForge 全域設定。

    對應 agentforge.yaml 的頂層結構。

    Attributes:
        default_model: 預設 LLM 模型（格式：provider/model-name）。
        providers: 各 LLM Provider 的連線設定。
        budget: 預算控管設定。
        telegram: Telegram Bot 設定（可選，不設定則不啟用 Telegram）。
    """

    model_config = ConfigDict(frozen=True)

    default_model: str = "openai/gpt-4o-mini"  # 預設模型
    providers: dict[str, LLMProviderConfig] = {}  # Provider 設定
    budget: BudgetConfig = BudgetConfig()  # 預算設定
    telegram: TelegramConfig | None = None  # Telegram Bot 設定（可選）
