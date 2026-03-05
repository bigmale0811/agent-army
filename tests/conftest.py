"""pytest 全域配置 - 自定義 markers 和命令列選項"""

import pytest


def pytest_configure(config):
    """註冊自定義 markers"""
    config.addinivalue_line("markers", "slow: 需要等待遊戲倒數的慢速測試")


def pytest_addoption(parser):
    """加入 --run-slow 選項"""
    parser.addoption("--run-slow", action="store_true", default=False, help="執行慢速測試")


def pytest_collection_modifyitems(config, items):
    """未指定 --run-slow 時自動跳過 @pytest.mark.slow 測試"""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="需要 --run-slow 才會執行")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
