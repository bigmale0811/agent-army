"""CLI 入口 — Click 命令列介面

支援互動模式和持久化瀏覽器 profile，解決 Token 認證問題。
"""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
import click
from slot_cloner.pipeline.context import PipelineContext
from slot_cloner.pipeline.orchestrator import PipelineOrchestrator, PHASE_ORDER
from slot_cloner.storage.manager import StorageManager
from slot_cloner.config.settings import load_settings
from slot_cloner.models.enums import PipelinePhase
from slot_cloner.progress.reporter import ProgressReporter
from slot_cloner.plugins.registry import PluginRegistry
from slot_cloner.plugins.atg.adapter import ATGAdapter


def _build_orchestrator(
    registry: PluginRegistry,
    url: str,
    output_dir: Path,
    *,
    interactive: bool = False,
    browser_profile: str | None = None,
) -> PipelineOrchestrator:
    """建構 Pipeline，將各 Phase handler 連接到 Orchestrator"""
    from slot_cloner.report.builder import ReportBuilder
    from slot_cloner.builder.engine import GameBuilder

    adapter = registry.find_adapter(url)
    report_builder = ReportBuilder()
    game_builder = GameBuilder(skip_npm=True)  # MVP 先跳過 npm build

    # 傳遞互動模式和瀏覽器 profile 給 Adapter
    scrape_kwargs: dict = {"output_dir": output_dir}
    if interactive:
        scrape_kwargs["interactive"] = True
    if browser_profile:
        scrape_kwargs["browser_profile"] = browser_profile

    async def recon_handler(ctx: PipelineContext) -> PipelineContext:
        """Phase 1: 偵察"""
        fingerprint = await adapter.recon(ctx.url)
        return ctx.model_copy(update={"fingerprint": fingerprint})

    async def scrape_handler(ctx: PipelineContext) -> PipelineContext:
        """Phase 2: 資源擷取（統一 Session — 同時攔截 WS）"""
        assets = await adapter.scrape(ctx.fingerprint, **scrape_kwargs)
        return ctx.model_copy(update={"assets": assets})

    async def reverse_handler(ctx: PipelineContext) -> PipelineContext:
        """Phase 3: 逆向分析（使用 Scraper 預捕獲的 WS 資料）"""
        game_model = await adapter.reverse(ctx.fingerprint, ctx.assets)
        return ctx.model_copy(update={"game_model": game_model})

    async def report_handler(ctx: PipelineContext) -> PipelineContext:
        """Phase 4: 產出報告"""
        analysis_dir = ctx.output_dir / "analysis"
        report_builder.build(ctx.game_model, analysis_dir)
        return ctx

    async def build_handler(ctx: PipelineContext) -> PipelineContext:
        """Phase 5: 建置遊戲"""
        assets_dir = ctx.output_dir / "assets"
        game_builder.build(ctx.game_model, assets_dir, ctx.output_dir)
        return ctx

    orchestrator = PipelineOrchestrator()
    orchestrator.register(PipelinePhase.RECON, recon_handler)
    orchestrator.register(PipelinePhase.SCRAPE, scrape_handler)
    orchestrator.register(PipelinePhase.REVERSE, reverse_handler)
    orchestrator.register(PipelinePhase.REPORT, report_handler)
    orchestrator.register(PipelinePhase.BUILD, build_handler)

    return orchestrator


@click.group()
@click.version_option(version="0.1.0")
def main():
    """老虎機遊戲 Clone & 生產線工具"""
    pass


@main.command()
@click.argument("url", required=False, default=None)
@click.option("--name", required=True, help="遊戲名稱")
@click.option("--output", default="./output", help="輸出目錄", type=click.Path())
@click.option("--dry-run", is_flag=True, help="乾跑模式（不執行實際操作）")
@click.option("--skip-build", is_flag=True, help="跳過遊戲重建")
@click.option("--resume", is_flag=True, help="從上次斷點續傳")
@click.option("--adapter", default=None, help="強制指定 Adapter（如 atg）")
@click.option(
    "--phases",
    default=None,
    help="只執行指定 Phase（逗號分隔，如 recon,scrape）",
)
@click.option("--verbose", is_flag=True, help="顯示詳細日誌")
@click.option("--interactive", is_flag=True, help="互動模式（開啟可見瀏覽器，可手動處理認證）")
@click.option("--browser-profile", default=None, help="瀏覽器 profile 路徑（保留 Cookie/Session）", type=click.Path())
@click.option(
    "--demo",
    default=None,
    help="ATG Demo 模式（自動從官網取得新鮮 Token，如 --demo storm-of-seth）",
)
def clone(
    url: str | None,
    name: str,
    output: str,
    dry_run: bool,
    skip_build: bool,
    resume: bool,
    adapter: str | None,
    phases: str | None,
    verbose: bool,
    interactive: bool,
    browser_profile: str | None,
    demo: str | None,
) -> None:
    """Clone 一個老虎機遊戲

    範例：
      python -m slot_cloner clone https://play.example.com/game --name my-game
      python -m slot_cloner clone --demo storm-of-seth --name seth  # 自動取得 Demo URL
      python -m slot_cloner clone URL --name my-game --interactive  # 互動模式處理認證
    """
    # 設定 logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s | %(name)s | %(message)s")
    cli_logger = logging.getLogger("slot_cloner.cli")

    # Demo 模式：自動從 ATG 官網取得新鮮 Token URL
    if demo:
        from slot_cloner.plugins.atg.demo_launcher import get_demo_url

        cli_logger.info("🎮 Demo 模式: 從 ATG 官網取得 %s 的新鮮 Token...", demo)
        url = asyncio.run(get_demo_url(game=demo))
        cli_logger.info("✅ Demo URL: %s", url[:80] + "...")

    if not url:
        raise click.UsageError("必須提供 URL 或使用 --demo 指定遊戲名稱")

    if interactive:
        cli_logger.info("🎮 互動模式已啟用 — 瀏覽器將以可見方式開啟")
    if browser_profile:
        cli_logger.info("📂 瀏覽器 profile: %s", browser_profile)

    # 解析 phases 參數
    target_phases = None
    if phases:
        try:
            target_phases = tuple(PipelinePhase(p.strip()) for p in phases.split(","))
        except ValueError as e:
            raise click.BadParameter(f"無效的 Phase: {e}") from e

    if skip_build and target_phases is None:
        target_phases = tuple(p for p in PHASE_ORDER if p != PipelinePhase.BUILD)

    # 建立輸出目錄
    output_path = Path(output) / name
    storage = StorageManager(output_path)

    reporter = ProgressReporter()
    reporter.start(name, url)

    if not dry_run:
        storage.setup()

    # 建立 Pipeline Context
    context = PipelineContext(
        url=url,
        game_name=name,
        output_dir=output_path,
        dry_run=dry_run,
    )

    # 建立 Plugin Registry
    registry = PluginRegistry()
    registry.register(ATGAdapter)

    # 建立並執行 Pipeline（傳遞互動模式和瀏覽器 profile）
    orchestrator = _build_orchestrator(
        registry, url, output_path,
        interactive=interactive,
        browser_profile=browser_profile,
    )

    try:
        result = asyncio.run(orchestrator.run(context, phases=target_phases))
        reporter.complete(result)
    except Exception as e:
        reporter.error(str(e))
        raise click.ClickException(str(e)) from e
