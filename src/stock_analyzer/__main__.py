"""
Stock Analyzer CLI 入口

用法：
    python -m stock_analyzer analyze <ticker> [--date DATE] [--verbose]
    python -m stock_analyzer analyze 2330.TW
    python -m stock_analyzer analyze BTC-USD --date 2026-03-01
    python -m stock_analyzer analyze 2330.TW 0050.TW AAPL GC=F
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """建立 CLI 參數解析器"""
    parser = argparse.ArgumentParser(
        prog="stock_analyzer",
        description="Stock Analyzer - 綜合投資分析工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # analyze 命令
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="分析投資標的",
    )
    analyze_parser.add_argument(
        "tickers",
        nargs="+",
        help="股票代號（如 2330.TW, BTC, AAPL, GC=F）",
    )
    analyze_parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="分析日期（YYYY-MM-DD），預設今天",
    )
    analyze_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="報告輸出目錄",
    )
    analyze_parser.add_argument(
        "--llm-provider",
        type=str,
        default=None,
        help="LLM 供應商（ollama/openai/anthropic）",
    )
    analyze_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM 模型名稱",
    )
    analyze_parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細輸出",
    )
    analyze_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模擬執行（不實際呼叫 LLM）",
    )

    return parser


def format_report_summary(report) -> str:
    """格式化報告摘要（終端輸出用）"""
    lines = [
        "",
        f"{'=' * 60}",
        f"  Stock Analyzer Report: {report.display_name}",
        f"  Date: {report.date}",
        f"  Asset Type: {report.asset_type.value}",
        f"{'=' * 60}",
        "",
    ]

    if report.market_report:
        lines.append("[Technical Analysis]")
        # 只取前 500 字
        lines.append(report.market_report[:500])
        lines.append("")

    if report.news_report:
        lines.append("[News Analysis]")
        lines.append(report.news_report[:500])
        lines.append("")

    if report.fundamentals_report:
        lines.append("[Fundamental Analysis]")
        lines.append(report.fundamentals_report[:500])
        lines.append("")

    if report.final_decision:
        lines.append("[Final Decision]")
        lines.append(report.final_decision)
        lines.append("")

    lines.append(f"{'=' * 60}")
    return "\n".join(lines)


def save_report(report, output_dir: Path) -> Path:
    """儲存報告為 Markdown 檔案"""
    output_dir.mkdir(parents=True, exist_ok=True)
    # 檔名：ticker_date.md
    safe_ticker = report.ticker.replace("=", "_").replace("-", "_")
    filename = f"{safe_ticker}_{report.date}.md"
    filepath = output_dir / filename

    content = f"""# {report.display_name} Analysis Report

**Date**: {report.date}
**Asset Type**: {report.asset_type.value}
**Ticker**: {report.ticker}

---

## Technical Analysis (Market Report)

{report.market_report or '_No data_'}

---

## News Analysis

{report.news_report or '_No data_'}

---

## Fundamental Analysis

{report.fundamentals_report or '_No data_'}

---

## Sentiment Analysis

{report.sentiment_report or '_No data_'}

---

## Investment Plan

{report.investment_plan or '_No data_'}

---

## Final Decision

{report.final_decision or '_No decision_'}
"""
    filepath.write_text(content, encoding="utf-8")
    return filepath


def main():
    """CLI 主入口"""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "analyze":
        # Dry-run 模式：只解析 ticker，不呼叫 LLM
        if args.dry_run:
            from .utils.ticker_resolver import resolve_ticker

            print("=== DRY RUN MODE ===")
            for ticker_input in args.tickers:
                resolved = resolve_ticker(ticker_input)
                print(
                    f"  {resolved.raw_input} -> "
                    f"{resolved.ticker} "
                    f"({resolved.asset_type.value})"
                )
            print("=== DRY RUN COMPLETE ===")
            sys.exit(0)

        # 正式分析
        from .config import StockAnalyzerConfig, LLMConfig, load_config
        from .main import StockAnalyzer

        config = load_config()

        # 覆蓋 CLI 參數
        if args.llm_provider or args.model:
            llm_config = LLMConfig(
                provider=args.llm_provider or config.llm.provider,
                deep_think_model=args.model or config.llm.deep_think_model,
                quick_think_model=args.model or config.llm.quick_think_model,
                backend_url=config.llm.backend_url,
            )
            config = StockAnalyzerConfig(
                llm=llm_config,
                reports_dir=Path(args.output_dir) if args.output_dir else config.reports_dir,
            )

        analyzer = StockAnalyzer(config=config)

        for ticker_input in args.tickers:
            print(f"\nAnalyzing: {ticker_input} ...")
            report = analyzer.analyze(ticker_input, date=args.date)

            # 終端輸出摘要
            print(format_report_summary(report))

            # 儲存 Markdown 報告
            output_dir = Path(args.output_dir) if args.output_dir else config.reports_dir
            filepath = save_report(report, output_dir)
            print(f"Report saved: {filepath}")


if __name__ == "__main__":
    main()
