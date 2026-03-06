# -*- coding: utf-8 -*-
"""
Singer Agent CLI 進入點。

允許使用 `python -m singer_agent` 執行 CLI。
"""
import sys

from src.singer_agent.cli import main

if __name__ == "__main__":
    sys.exit(main())
