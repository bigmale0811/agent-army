# -*- coding: utf-8 -*-
"""Rich 輸出工具模組 — 提供統一的終端輸出格式。

所有 CLI 指令共用的 Rich 顯示函式，確保輸出風格一致。
使用純 ASCII 符號避免 Windows cp950 編碼問題。

包含：
- print_success/error/info/warning：簡單訊息輸出函式
- DisplayManager：實作 ProgressCallback 的 Rich 終端顯示管理器
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from rich.console import Console

if TYPE_CHECKING:
    from agentforge.core.engine import PipelineResult
    from agentforge.steps.base import StepOutput

# 在 Windows 下使用 UTF-8 或 fallback 到 legacy console
# 確保 Rich 不使用 emoji shortcode（cp950 無法編碼）
console = Console(emoji=False)


def print_success(message: str) -> None:
    """顯示成功訊息（綠色）。"""
    console.print(f"[bold green][OK] {message}[/bold green]")


def print_error(message: str) -> None:
    """顯示錯誤訊息（紅色）。"""
    console.print(f"[bold red][ERROR] {message}[/bold red]")


def print_info(message: str) -> None:
    """顯示資訊訊息（藍色）。"""
    console.print(f"[bold blue][INFO] {message}[/bold blue]")


def print_warning(message: str) -> None:
    """顯示警告訊息（黃色）。"""
    console.print(f"[bold yellow][WARN] {message}[/bold yellow]")


class DisplayManager:
    """Pipeline 執行進度的 Rich 終端顯示管理器。

    實作 ProgressCallback 協定，將步驟進度即時顯示在終端機上。
    使用 ASCII 符號確保 Windows 相容性。
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        verbose: bool = False,
    ) -> None:
        """初始化 DisplayManager。

        Args:
            console: Rich Console 實例（可選，預設使用模組級別的 console）。
            verbose: 若為 True，顯示步驟輸出的詳細內容。
        """
        self._console = console or globals()["console"]
        self._verbose = verbose

    def on_step_start(
        self,
        step_index: int,
        total_steps: int,
        step_name: str,
    ) -> None:
        """顯示步驟開始的進度訊息。

        Args:
            step_index: 目前步驟索引（從 0 起算）。
            total_steps: 總步驟數。
            step_name: 步驟名稱。
        """
        step_num = step_index + 1
        self._console.print(
            f"[bold blue][{step_num}/{total_steps}] Running step: {step_name}[/bold blue]"
        )

    def on_step_complete(
        self,
        step_index: int,
        step_name: str,
        output: "StepOutput",
        elapsed_seconds: float,
    ) -> None:
        """顯示步驟完成的結果訊息。

        Args:
            step_index: 完成的步驟索引。
            step_name: 步驟名稱。
            output: 步驟執行結果。
            elapsed_seconds: 步驟耗時（秒）。
        """
        elapsed_str = f"{elapsed_seconds:.2f}s"

        if output.success:
            self._console.print(
                f"[bold green]  [OK] {step_name} ({elapsed_str})[/bold green]"
            )
            if self._verbose and output.output:
                self._console.print(f"  [dim]{output.output[:200]}[/dim]")
        else:
            self._console.print(
                f"[bold red]  [FAIL] {step_name} ({elapsed_str})[/bold red]"
            )
            if output.error:
                self._console.print(f"  [red]{output.error}[/red]")

    def on_pipeline_complete(self, result: "PipelineResult") -> None:
        """顯示 Pipeline 完成的彙整訊息。

        Args:
            result: 完整的 Pipeline 執行結果。
        """
        total_str = f"{result.total_seconds:.2f}s"
        step_count = len(result.steps)

        if result.success:
            self._console.print(
                f"\n[bold green][DONE] Agent '{result.agent_name}' completed "
                f"({step_count} steps, {total_str})[/bold green]"
            )
        else:
            # 找出失敗的步驟
            failed = [s for s in result.steps if not s.output.success]
            failed_names = ", ".join(s.step_name for s in failed)
            self._console.print(
                f"\n[bold red][FAIL] Agent '{result.agent_name}' failed "
                f"at step(s): {failed_names} ({total_str})[/bold red]"
            )

        if result.total_cost_usd > 0:
            self._console.print(
                f"[dim]  Total API cost: ${result.total_cost_usd:.6f} USD[/dim]"
            )
