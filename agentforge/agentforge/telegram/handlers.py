# -*- coding: utf-8 -*-
"""Telegram Bot 指令處理器（DEV-09）。

每個指令對應一個 async 方法。
使用 asyncio.to_thread 在背景執行同步的 PipelineEngine，
避免阻塞 Telegram 的 event loop。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentforge.core.task_tracker import TaskTracker
from agentforge.telegram.formatter import TelegramFormatter

if TYPE_CHECKING:
    pass


class BotHandlers:
    """Telegram Bot 指令處理器集合。

    封裝所有 /start、/help、/list、/run、/status 的處理邏輯。
    不直接依賴 python-telegram-bot 型別，以利測試。
    """

    def __init__(self, project_path: Path) -> None:
        """初始化處理器。

        Args:
            project_path: AgentForge 專案根目錄路徑，
                          用於尋找 agentforge.yaml 和 agents/ 目錄。
        """
        self._project_path = project_path
        self._formatter = TelegramFormatter()

    async def cmd_start(self, update: Any, context: Any) -> None:
        """處理 /start 指令 — 回覆歡迎訊息。

        Args:
            update: Telegram Update 物件。
            context: Telegram CallbackContext 物件。
        """
        await update.message.reply_text(self._formatter.format_welcome())

    async def cmd_help(self, update: Any, context: Any) -> None:
        """處理 /help 指令 — 回覆指令說明。

        Args:
            update: Telegram Update 物件。
            context: Telegram CallbackContext 物件。
        """
        await update.message.reply_text(self._formatter.format_help())

    async def cmd_list(self, update: Any, context: Any) -> None:
        """處理 /list 指令 — 列出所有可用的 Agent。

        掃描 project_path/agents/*.yaml，格式化後回覆清單。

        Args:
            update: Telegram Update 物件。
            context: Telegram CallbackContext 物件。
        """
        agents = self._scan_agents()
        await update.message.reply_text(
            self._formatter.format_agent_list(agents)
        )

    async def cmd_run(self, update: Any, context: Any) -> None:
        """處理 /run <agent> 指令 — 執行指定的 Agent。

        執行流程：
        1. 驗證 args 是否含有 agent 名稱
        2. 尋找 agent 定義檔案
        3. 先回覆「⏳ 正在執行...」
        4. 用 asyncio.to_thread 在背景執行 PipelineEngine
        5. 完成後 edit_text 推送結果

        Args:
            update: Telegram Update 物件。
            context: Telegram CallbackContext 物件（context.args 含參數）。
        """
        # 驗證是否有提供 agent 名稱
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "請提供 Agent 名稱。\n用法：/run <agent-name>"
            )
            return

        agent_name = args[0]

        # 尋找 agent 定義檔案
        agent_path = self._find_agent_yaml(agent_name)
        if agent_path is None:
            await update.message.reply_text(
                f"找不到 Agent '{agent_name}'。\n"
                f"請用 /list 查看可用的 Agent 清單。"
            )
            return

        # 先回覆執行中訊息
        sent_msg = await update.message.reply_text(
            self._formatter.format_run_started(agent_name)
        )

        # 在背景執行（不阻塞 event loop）
        try:
            result = await asyncio.to_thread(
                self._run_agent_sync, agent_path
            )
        except Exception as exc:  # noqa: BLE001
            # 任何非預期例外都以友善訊息回報
            await sent_msg.edit_text(
                f"❌ 執行 '{agent_name}' 時發生錯誤：{exc}"
            )
            return

        # 整理步驟摘要
        steps_summary = [
            {
                "name": step.step_name,
                "success": step.output.success,
                "elapsed": step.elapsed_seconds,
            }
            for step in result.steps
        ]

        # 推送執行結果
        result_text = self._formatter.format_run_result(
            agent_name=result.agent_name,
            success=result.success,
            steps_summary=steps_summary,
            elapsed=result.total_seconds,
            cost=result.total_cost_usd,
        )
        await sent_msg.edit_text(result_text)

    async def cmd_status(self, update: Any, context: Any) -> None:
        """處理 /status 指令 — 顯示執行統計儀表板。

        從 TaskTracker 讀取統計，格式化後回覆。

        Args:
            update: Telegram Update 物件。
            context: Telegram CallbackContext 物件。
        """
        stats = self._get_stats()
        await update.message.reply_text(
            self._formatter.format_status(stats)
        )

    # ── 私有輔助方法 ──────────────────────────────────────────

    def _scan_agents(self) -> list[dict]:
        """掃描 agents/ 目錄，回傳 Agent 資訊列表。

        Returns:
            每個元素含 name、description、steps 的 dict 列表。
        """
        from agentforge.schema.validator import AgentForgeValidationError, load_agent_def

        agents_dir = self._project_path / "agents"
        if not agents_dir.exists():
            return []

        result: list[dict] = []
        for yaml_file in sorted(agents_dir.glob("*.yaml")):
            try:
                agent_def = load_agent_def(yaml_file)
                result.append({
                    "name": agent_def.name,
                    "description": agent_def.description or "",
                    "steps": len(agent_def.steps),
                })
            except (AgentForgeValidationError, Exception):
                # 跳過無法解析的 YAML 檔案
                result.append({
                    "name": yaml_file.stem,
                    "description": "（解析失敗）",
                    "steps": 0,
                })

        return result

    def _find_agent_yaml(self, agent_name: str) -> Path | None:
        """在 agents/ 目錄尋找 agent YAML 檔案。

        Args:
            agent_name: Agent 名稱（不含副檔名）。

        Returns:
            找到的 Path；未找到則回傳 None。
        """
        agents_dir = self._project_path / "agents"
        for ext in (".yaml", ".yml"):
            candidate = agents_dir / f"{agent_name}{ext}"
            if candidate.exists():
                return candidate
        return None

    def _run_agent_sync(self, agent_path: Path) -> Any:
        """同步執行 Agent（在 thread 中呼叫）。

        Args:
            agent_path: Agent YAML 檔案路徑。

        Returns:
            PipelineResult 執行結果。
        """
        from agentforge.core.engine import PipelineEngine
        from agentforge.llm.router import LLMRouter
        from agentforge.schema.validator import load_agent_def, load_global_config

        # 載入設定
        config_path = self._project_path / "agentforge.yaml"
        global_config = load_global_config(config_path)
        agent_def = load_agent_def(agent_path)

        # 建立並執行 Pipeline
        router = LLMRouter(global_config)
        engine = PipelineEngine(router=router)
        return engine.execute(agent_def)

    def _get_stats(self) -> list[dict]:
        """從 TaskTracker 取得統計資料。

        Returns:
            每個元素含 agent、runs、success、cost 的 dict 列表。
        """
        db_path = self._project_path / ".agentforge" / "tasks.db"

        # 若資料庫不存在，回傳空列表
        if not db_path.exists():
            return []

        with TaskTracker(db_path) as tracker:
            all_stats = tracker.get_all_stats()
            return [
                {
                    "agent": s.agent_name,
                    "runs": s.total_runs,
                    "success": s.success_count,
                    "cost": s.total_cost_usd,
                }
                for s in all_stats
            ]
