# -*- coding: utf-8 -*-
"""Telegram 訊息格式化工具（DEV-08）。

將 AgentForge 資料結構轉換為適合 Telegram 顯示的文字訊息。
遵循 Telegram 4096 字元長度限制。
"""

from __future__ import annotations


class TelegramFormatter:
    """將 AgentForge 資料格式化為 Telegram 訊息。

    所有方法回傳純文字字串，可直接傳給 Telegram API 發送。
    超過 4096 字元的內容會自動截斷並附加提示。
    """

    # Telegram 單則訊息最大字元數
    MAX_LENGTH: int = 4096
    # 相容別名：測試與 bot.py 使用此名稱
    MAX_MESSAGE_LENGTH: int = 4096

    def format_welcome(self) -> str:
        """歡迎訊息。

        Returns:
            包含「歡迎」字樣的歡迎文字。
        """
        return (
            "歡迎使用 AgentForge Bot！\n"
            "\n"
            "我可以幫你在手機上遠端操控 AI Agent 執行流程。\n"
            "\n"
            "輸入 /help 查看所有可用指令。"
        )

    def format_help(self) -> str:
        """指令說明。

        Returns:
            包含所有可用指令說明的文字。
        """
        return (
            "AgentForge Bot 指令說明\n"
            "\n"
            "/start  — 顯示歡迎訊息\n"
            "/help   — 顯示此說明\n"
            "/list   — 列出所有可用的 Agent\n"
            "/run <agent>  — 執行指定的 Agent\n"
            "/status — 顯示執行統計儀表板\n"
            "\n"
            "範例：/run my-agent"
        )

    def format_agent_list(self, agents: list[dict]) -> str:
        """格式化 Agent 清單。

        Args:
            agents: Agent 資訊列表，每個元素包含：
                    - name (str)：Agent 名稱
                    - description (str)：描述
                    - steps (int)：步驟數量

        Returns:
            格式化後的 Agent 清單文字。
        """
        if not agents:
            return "目前沒有可用的 Agent。\n請先在 agents/ 目錄下建立 YAML 定義檔。"

        lines: list[str] = ["可用的 Agent 清單：\n"]
        for agent in agents:
            name = agent.get("name", "（未命名）")
            description = agent.get("description", "無描述")
            steps = agent.get("steps", 0)
            lines.append(f"• {name}（{steps} 步驟）")
            lines.append(f"  {description}")

        lines.append(f"\n共 {len(agents)} 個 Agent")
        return self._truncate("\n".join(lines))

    def format_run_start(self, agent_name: str) -> str:
        """回傳「正在執行」提示訊息（舊版相容介面）。

        Args:
            agent_name: 要執行的 Agent 名稱。

        Returns:
            執行中提示文字。
        """
        return self.format_run_started(agent_name)

    def format_run_started(self, agent_name: str) -> str:
        """回傳「正在執行」提示訊息。

        Args:
            agent_name: 要執行的 Agent 名稱。

        Returns:
            含有 ⏳ 和 agent_name 的執行中提示文字。
        """
        return f"⏳ 正在執行 {agent_name}，完成後會通知你..."

    def format_run_result(
        self,
        agent_name: str,
        success: bool,
        steps_summary: list[dict] | None = None,
        elapsed: float = 0.0,
        cost: float = 0.0,
        *,
        # 舊版相容參數
        duration: float | None = None,
        steps: list[dict] | None = None,
        output: str = "",
    ) -> str:
        """格式化執行結果。

        Args:
            agent_name: Agent 名稱。
            success: 執行是否成功。
            steps_summary: 步驟執行結果列表，每個元素包含：
                           - name (str)：步驟名稱
                           - success (bool)：是否成功
                           - elapsed (float)：耗時（秒）
            elapsed: 執行耗時（秒）。
            cost: 費用（USD）。
            duration: 舊版相容參數，等同於 elapsed。
            steps: 舊版相容參數，等同於 steps_summary。
            output: 執行輸出內容（選填）。

        Returns:
            格式化後的執行結果文字。
        """
        # 舊版相容處理
        if duration is not None:
            elapsed = duration
        actual_steps = steps_summary or steps

        status_icon = "成功" if success else "失敗"
        status_emoji = "✅" if success else "❌"
        lines: list[str] = [
            f"{status_emoji} Agent 執行{status_icon}：{agent_name}",
            f"耗時：{elapsed:.2f} 秒",
            f"費用：${cost:.4f} USD",
        ]

        # 附加步驟明細（若有）
        if actual_steps:
            lines.append("\n步驟執行結果：")
            for step in actual_steps:
                step_name = step.get("name", "（未命名）")
                step_ok = step.get("success", False)
                # 支援 elapsed 和 duration 兩個 key
                step_dur = step.get("elapsed", step.get("duration", 0.0))
                step_icon = "OK" if step_ok else "FAIL"
                lines.append(f"  [{step_icon}] {step_name}（{step_dur:.1f}s）")

        # 附加輸出內容（若有）
        if output:
            lines.append("\n輸出內容：")
            lines.append(output)

        return self._truncate("\n".join(lines))

    def format_status(self, stats: list[dict]) -> str:
        """格式化執行統計。

        Args:
            stats: Agent 統計列表，每個元素包含：
                   - name (str)：Agent 名稱
                   - runs (int)：執行次數
                   - success (int)：成功次數
                   - cost (float)：累積費用（USD）

        Returns:
            格式化後的統計文字。
        """
        if not stats:
            return "尚無執行記錄。\n請先執行 /run <agent> 開始使用。"

        lines: list[str] = ["AgentForge 執行統計\n"]
        total_runs = 0
        total_cost = 0.0

        for item in stats:
            # 支援 "agent" 和 "name" 兩種 key（相容不同呼叫端）
            name = item.get("agent", item.get("name", "（未知）"))
            runs = item.get("runs", 0)
            success = item.get("success", 0)
            cost = item.get("cost", 0.0)
            fail = runs - success
            rate = (success / runs * 100) if runs > 0 else 0.0

            lines.append(f"• {name}")
            lines.append(f"  執行 {runs} 次 | 成功 {success} | 失敗 {fail} | 成功率 {rate:.1f}%")
            lines.append(f"  費用 ${cost:.6f} USD")

            total_runs += runs
            total_cost += cost

        lines.append(f"\n合計：{len(stats)} 個 Agent，{total_runs} 次執行，${total_cost:.6f} USD")
        return self._truncate("\n".join(lines))

    def _truncate(self, text: str) -> str:
        """超過 MAX_MESSAGE_LENGTH 字元時截斷並附加提示。

        Args:
            text: 原始文字。

        Returns:
            符合長度限制的文字。
        """
        if len(text) <= self.MAX_MESSAGE_LENGTH:
            return text

        # 截斷並附加提示（保留提示的空間）
        suffix = "...（訊息過長已截斷）"
        cutoff = self.MAX_MESSAGE_LENGTH - len(suffix)
        return text[:cutoff] + suffix
