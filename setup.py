#!/usr/bin/env python3
"""Agent Army Setup Wizard — 互動式安裝精靈入口。

使用方式：
    python setup.py                     # 完整安裝精靈
    python setup.py --add-cloud-models  # 只設定雲端模型
    python setup.py --add-github        # 只設定 GitHub CLI
    python setup.py --add-ollama        # 只設定 Ollama
    python setup.py --add-telegram      # 只設定 Telegram Bot
    python setup.py --verify            # 只驗證安裝結果
    python setup.py --path /path/to/project  # 指定專案路徑
"""

import argparse
import sys
from pathlib import Path


def main() -> None:
    """Setup Wizard 入口。"""
    parser = argparse.ArgumentParser(
        description="🤖 Agent Army Setup Wizard",
        prog="python setup.py",
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="專案路徑（預設互動式詢問）",
    )
    parser.add_argument(
        "--add-cloud-models",
        action="store_true",
        help="只設定雲端模型 API",
    )
    parser.add_argument(
        "--add-ollama",
        action="store_true",
        help="只設定本地 Ollama",
    )
    parser.add_argument(
        "--add-github",
        action="store_true",
        help="只設定 GitHub CLI",
    )
    parser.add_argument(
        "--add-telegram",
        action="store_true",
        help="只設定 Telegram Bot",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="只驗證安裝結果",
    )

    args = parser.parse_args()

    # 單步模式
    if args.add_cloud_models:
        from setup.cloud_models import setup_cloud_models
        from setup.wizard import _enable_ansi_windows, print_banner

        _enable_ansi_windows()
        print_banner()
        context = {"project_path": args.path or Path.cwd()}
        setup_cloud_models(context)
        return

    if args.add_ollama:
        from setup.ollama import setup_ollama
        from setup.wizard import _enable_ansi_windows, print_banner

        _enable_ansi_windows()
        print_banner()
        context = {"project_path": args.path or Path.cwd()}
        setup_ollama(context)
        return

    if args.add_github:
        from setup.github_cli import setup_github_cli
        from setup.wizard import _enable_ansi_windows, print_banner

        _enable_ansi_windows()
        print_banner()
        context = {"project_path": args.path or Path.cwd()}
        setup_github_cli(context)
        return

    if args.add_telegram:
        from setup.telegram import setup_telegram
        from setup.wizard import _enable_ansi_windows, print_banner

        _enable_ansi_windows()
        print_banner()
        context = {"project_path": args.path or Path.cwd()}
        setup_telegram(context)
        return

    if args.verify:
        from setup.verify import run_verification
        from setup.wizard import _enable_ansi_windows, print_banner

        _enable_ansi_windows()
        print_banner()
        context = {"project_path": args.path or Path.cwd()}
        run_verification(context)
        return

    # 完整精靈模式
    from setup.wizard import run_wizard

    run_wizard(project_path=args.path)


if __name__ == "__main__":
    main()
