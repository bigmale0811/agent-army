"""Progress Reporter — 進度回報"""
from __future__ import annotations
import click
from slot_cloner.pipeline.context import PipelineContext


class ProgressReporter:
    """CLI 進度回報器（Sprint 1 簡化版，Sprint 4 換成 Rich）"""

    def start(self, game_name: str, url: str) -> None:
        """開始執行"""
        click.echo("=" * 60)
        click.echo(f"[Slot Cloner] {game_name}")
        click.echo(f"URL: {url}")
        click.echo("=" * 60)

    def phase(self, phase_name: str) -> None:
        """進入新 Phase"""
        click.echo(f"\n>> Phase: {phase_name}")

    def complete(self, context: PipelineContext) -> None:
        """Pipeline 完成"""
        click.echo("\n" + "=" * 60)
        click.echo("Clone 完成！")
        click.echo(f"輸出目錄: {context.output_dir}")
        click.echo("=" * 60)

    def error(self, message: str) -> None:
        """錯誤"""
        click.echo(f"\n[ERROR] {message}", err=True)
