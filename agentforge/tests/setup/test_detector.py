# -*- coding: utf-8 -*-
"""EnvironmentDetector 測試。

測試環境偵測器的所有情境：
- claude CLI 已安裝 / 未安裝
- ollama 已安裝並執行中 / 未安裝
- 設定檔存在 / 不存在
- Python 版本偵測
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentforge.setup.detector import EnvironmentDetector


class TestCheckClaudeCli:
    """check_claude_cli 測試群組。"""

    def setup_method(self) -> None:
        self.detector = EnvironmentDetector()

    def test_check_claude_cli_found(self) -> None:
        """偵測到 claude CLI — 回傳 (True, version_string)。"""
        mock_result = MagicMock()
        mock_result.stdout = "claude 1.2.3\n"
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/claude"), \
             patch("subprocess.run", return_value=mock_result):
            found, version = self.detector.check_claude_cli()

        assert found is True
        assert "1.2.3" in version

    def test_check_claude_cli_not_found(self) -> None:
        """未偵測到 claude CLI — 回傳 (False, msg)。"""
        with patch("shutil.which", return_value=None):
            found, msg = self.detector.check_claude_cli()

        assert found is False
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_check_claude_cli_subprocess_fails(self) -> None:
        """claude CLI 存在但執行失敗 — 回傳 (False, msg)。"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("shutil.which", return_value="/usr/local/bin/claude"), \
             patch("subprocess.run", return_value=mock_result):
            found, msg = self.detector.check_claude_cli()

        assert found is False


class TestCheckOllama:
    """check_ollama 測試群組。"""

    def setup_method(self) -> None:
        self.detector = EnvironmentDetector()

    def test_check_ollama_found(self) -> None:
        """偵測到 ollama 且執行中 — 回傳 (True, version_string)。"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "NAME\nqwen3:14b\n"

        with patch("shutil.which", return_value="/usr/local/bin/ollama"), \
             patch("subprocess.run", return_value=mock_result):
            found, info = self.detector.check_ollama()

        assert found is True
        assert isinstance(info, str)

    def test_check_ollama_not_found(self) -> None:
        """未偵測到 ollama — 回傳 (False, msg)。"""
        with patch("shutil.which", return_value=None):
            found, msg = self.detector.check_ollama()

        assert found is False
        assert isinstance(msg, str)

    def test_check_ollama_not_running(self) -> None:
        """ollama 已安裝但未執行中 — 回傳 (False, msg)。"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("shutil.which", return_value="/usr/local/bin/ollama"), \
             patch("subprocess.run", return_value=mock_result):
            found, msg = self.detector.check_ollama()

        assert found is False


class TestCheckExistingConfig:
    """check_existing_config 測試群組。"""

    def setup_method(self) -> None:
        self.detector = EnvironmentDetector()

    def test_check_existing_config_exists(self, tmp_path: Path) -> None:
        """目錄中有 agentforge.yaml — 回傳 True。"""
        (tmp_path / "agentforge.yaml").write_text("default_model: gemini/gemini-2.0-flash")
        assert self.detector.check_existing_config(tmp_path) is True

    def test_check_existing_config_missing(self, tmp_path: Path) -> None:
        """目錄中無 agentforge.yaml — 回傳 False。"""
        assert self.detector.check_existing_config(tmp_path) is False


class TestCheckPythonVersion:
    """check_python_version 測試群組。"""

    def setup_method(self) -> None:
        self.detector = EnvironmentDetector()

    def test_check_python_version(self) -> None:
        """偵測 Python 版本 — 至少回傳 (True, version_string)（測試環境 >= 3.10）。"""
        found, version = self.detector.check_python_version()
        assert isinstance(found, bool)
        assert isinstance(version, str)
        assert len(version) > 0

    def test_check_python_version_returns_version_string(self) -> None:
        """版本字串格式應包含數字。"""
        _, version = self.detector.check_python_version()
        # 格式如 "3.12.8" 或 "Python 3.12.8"
        assert any(char.isdigit() for char in version)
