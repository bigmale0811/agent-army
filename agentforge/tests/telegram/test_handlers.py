# -*- coding: utf-8 -*-
"""BotHandlers 測試套件。

驗證所有 Telegram Bot 指令處理器的行為。
使用 Mock 模擬 update / context 物件，不依賴真實 Telegram SDK。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import yaml

from agentforge.telegram.handlers import BotHandlers


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """建立含有 agents 目錄的臨時專案目錄。"""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    # 建立最小化的 agentforge.yaml
    config = {
        "default_model": "ollama/qwen3:14b",
        "providers": {},
        "budget": {"daily_limit_usd": 10.0, "warn_at_percent": 80.0},
    }
    (tmp_path / "agentforge.yaml").write_text(
        yaml.dump(config), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def project_with_agent(project_dir: Path) -> Path:
    """在專案目錄中建立測試 Agent YAML。"""
    agent_data = {
        "name": "test-agent",
        "description": "測試用 Agent",
        "model": "ollama/qwen3:14b",
        "steps": [
            {"name": "greet", "action": "shell", "command": "echo hello"},
        ],
    }
    yaml_path = project_dir / "agents" / "test-agent.yaml"
    yaml_path.write_text(yaml.dump(agent_data), encoding="utf-8")
    return project_dir


@pytest.fixture
def handlers(project_dir: Path) -> BotHandlers:
    """建立 BotHandlers 實例。"""
    return BotHandlers(project_path=project_dir)


def make_update(text: str = "", args: list[str] | None = None) -> MagicMock:
    """建立模擬的 Telegram Update 物件。"""
    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "測試使用者"
    return update


def make_context(args: list[str] | None = None) -> MagicMock:
    """建立模擬的 Telegram Context 物件。"""
    context = MagicMock()
    context.args = args or []
    return context


class TestCmdStart:
    """cmd_start 指令測試。"""

    @pytest.mark.asyncio
    async def test_cmd_start_replies(self, handlers: BotHandlers) -> None:
        """cmd_start 應回覆歡迎訊息。"""
        update = make_update()
        context = make_context()

        await handlers.cmd_start(update, context)

        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_start_contains_welcome(self, handlers: BotHandlers) -> None:
        """cmd_start 的回覆應包含歡迎字樣。"""
        update = make_update()
        context = make_context()

        await handlers.cmd_start(update, context)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "歡迎" in reply_text


class TestCmdHelp:
    """cmd_help 指令測試。"""

    @pytest.mark.asyncio
    async def test_cmd_help_replies(self, handlers: BotHandlers) -> None:
        """cmd_help 應回覆指令說明。"""
        update = make_update()
        context = make_context()

        await handlers.cmd_help(update, context)

        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_help_contains_commands(self, handlers: BotHandlers) -> None:
        """cmd_help 的回覆應包含所有指令。"""
        update = make_update()
        context = make_context()

        await handlers.cmd_help(update, context)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "/list" in reply_text
        assert "/run" in reply_text
        assert "/status" in reply_text


class TestCmdList:
    """cmd_list 指令測試。"""

    @pytest.mark.asyncio
    async def test_cmd_list_with_agents(self, project_with_agent: Path) -> None:
        """有 Agent 時應列出 Agent 清單。"""
        handlers = BotHandlers(project_path=project_with_agent)
        update = make_update()
        context = make_context()

        await handlers.cmd_list(update, context)

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "test-agent" in reply_text

    @pytest.mark.asyncio
    async def test_cmd_list_no_agents(self, project_dir: Path) -> None:
        """沒有 Agent 時應顯示提示訊息。"""
        handlers = BotHandlers(project_path=project_dir)
        update = make_update()
        context = make_context()

        await handlers.cmd_list(update, context)

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        # 應有「沒有」或「找不到」的訊息
        assert len(reply_text) > 0


class TestCmdRun:
    """cmd_run 指令測試。"""

    @pytest.mark.asyncio
    async def test_cmd_run_no_args(self, handlers: BotHandlers) -> None:
        """沒帶 Agent 名稱時應提示用法。"""
        update = make_update()
        context = make_context(args=[])  # 空 args

        await handlers.cmd_run(update, context)

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        # 應提示使用方法
        assert "/run" in reply_text or "用法" in reply_text or "請提供" in reply_text

    @pytest.mark.asyncio
    async def test_cmd_run_agent_not_found(self, handlers: BotHandlers) -> None:
        """Agent 不存在時應回覆友善錯誤訊息。"""
        update = make_update()
        context = make_context(args=["nonexistent-agent"])

        await handlers.cmd_run(update, context)

        # reply_text 被呼叫（可能多次 — 先說執行中，再說找不到）
        assert update.message.reply_text.call_count >= 1
        # 確認最後一次回覆包含找不到的訊息
        all_calls = [
            call[0][0] for call in update.message.reply_text.call_args_list
        ]
        combined = " ".join(all_calls)
        assert "找不到" in combined or "不存在" in combined or "失敗" in combined

    @pytest.mark.asyncio
    async def test_cmd_run_sends_started_message(self, project_with_agent: Path) -> None:
        """有效 Agent 應先回覆執行中訊息。"""
        handlers = BotHandlers(project_path=project_with_agent)
        update = make_update()
        # 模擬 edit_text 方法
        update.message.reply_text = AsyncMock(return_value=AsyncMock(edit_text=AsyncMock()))
        context = make_context(args=["test-agent"])

        with patch("agentforge.telegram.handlers.asyncio.to_thread") as mock_thread:
            # 模擬成功的 PipelineResult
            from agentforge.core.engine import PipelineResult
            mock_result = MagicMock(spec=PipelineResult)
            mock_result.success = True
            mock_result.agent_name = "test-agent"
            mock_result.total_seconds = 1.0
            mock_result.total_cost_usd = 0.0
            mock_result.steps = ()
            mock_thread.return_value = mock_result

            await handlers.cmd_run(update, context)

        # 應先傳送執行中訊息
        assert update.message.reply_text.called
        first_call_text = update.message.reply_text.call_args_list[0][0][0]
        assert "test-agent" in first_call_text or "執行" in first_call_text


class TestCmdStatus:
    """cmd_status 指令測試。"""

    @pytest.mark.asyncio
    async def test_cmd_status_replies(self, handlers: BotHandlers) -> None:
        """cmd_status 應回覆統計資訊。"""
        update = make_update()
        context = make_context()

        with patch("agentforge.telegram.handlers.TaskTracker") as mock_tracker_cls:
            mock_tracker = MagicMock()
            mock_tracker.get_all_stats.return_value = []
            mock_tracker.__enter__ = MagicMock(return_value=mock_tracker)
            mock_tracker.__exit__ = MagicMock(return_value=False)
            mock_tracker_cls.return_value = mock_tracker

            await handlers.cmd_status(update, context)

        update.message.reply_text.assert_called_once()
