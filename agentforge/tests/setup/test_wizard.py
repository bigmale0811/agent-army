# -*- coding: utf-8 -*-
"""SetupWizard 測試。

測試安裝精靈的完整流程：
- --auto 模式自動完成
- --dry-run 不產生檔案
- provider 選擇邏輯
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentforge.setup.wizard import SetupWizard


class TestWizardAutoMode:
    """--auto 模式測試。"""

    def test_wizard_auto_mode(self, tmp_path: Path) -> None:
        """--auto 模式應完整跑通並回傳 True。"""
        wizard = SetupWizard(dry_run=True, auto=True)
        # auto + dry_run 不需要任何輸入
        result = wizard.run()
        assert result is True

    def test_wizard_dry_run_no_files(self, tmp_path: Path) -> None:
        """--dry-run 不應在 tmp_path 產生任何實際檔案。"""
        wizard = SetupWizard(dry_run=True, auto=True)
        wizard._state.project_path = tmp_path

        wizard.run()

        # dry_run 模式不應建立 agentforge.yaml
        assert not (tmp_path / "agentforge.yaml").exists()

    def test_wizard_auto_dry_run_combined(self, tmp_path: Path) -> None:
        """--auto --dry-run 合併使用應成功。"""
        wizard = SetupWizard(dry_run=True, auto=True)
        result = wizard.run()
        assert result is True


class TestWizardChooseProvider:
    """_step_choose_provider 測試。"""

    def test_wizard_choose_provider_gemini(self) -> None:
        """輸入 '1' 應選擇 gemini provider。"""
        wizard = SetupWizard(dry_run=True, auto=False)

        with patch("click.prompt", return_value="1"):
            result = wizard._step_choose_provider()

        assert result is True
        assert wizard._state.provider == "gemini"

    def test_wizard_choose_provider_claude(self) -> None:
        """輸入 '2' 應選擇 claude-code provider。"""
        wizard = SetupWizard(dry_run=True, auto=False)

        with patch("click.prompt", return_value="2"):
            result = wizard._step_choose_provider()

        assert result is True
        assert wizard._state.provider == "claude-code"

    def test_wizard_choose_provider_openai(self) -> None:
        """輸入 '3' 應選擇 openai provider。"""
        wizard = SetupWizard(dry_run=True, auto=False)

        with patch("click.prompt", return_value="3"):
            result = wizard._step_choose_provider()

        assert result is True
        assert wizard._state.provider == "openai"

    def test_wizard_choose_provider_ollama(self) -> None:
        """輸入 '4' 應選擇 ollama provider。"""
        wizard = SetupWizard(dry_run=True, auto=False)

        with patch("click.prompt", return_value="4"):
            result = wizard._step_choose_provider()

        assert result is True
        assert wizard._state.provider == "ollama"

    def test_wizard_auto_mode_selects_gemini(self) -> None:
        """auto 模式應自動選擇 gemini。"""
        wizard = SetupWizard(dry_run=True, auto=True)
        result = wizard._step_choose_provider()

        assert result is True
        assert wizard._state.provider == "gemini"


class TestWizardConfigureCredential:
    """_step_configure_credential 測試。"""

    def test_wizard_auto_mode_skips_validation(self) -> None:
        """auto 模式應跳過所有驗證，直接成功。"""
        wizard = SetupWizard(dry_run=True, auto=True)
        wizard._state.provider = "gemini"

        result = wizard._step_configure_credential()
        assert result is True

    def test_wizard_gemini_valid_key(self) -> None:
        """Gemini provider 輸入有效 key — 回傳 True。"""
        wizard = SetupWizard(dry_run=True, auto=False)
        wizard._state.provider = "gemini"

        valid_key = "AIza" + "X" * 30
        with patch("click.prompt", return_value=valid_key):
            result = wizard._step_configure_credential()

        assert result is True
        assert wizard._state.api_key == valid_key

    def test_wizard_ollama_checks_installation(self) -> None:
        """ollama provider — 偵測 ollama 是否安裝。"""
        wizard = SetupWizard(dry_run=True, auto=False)
        wizard._state.provider = "ollama"

        with patch.object(wizard._detector, "check_ollama", return_value=(True, "qwen3:14b")):
            result = wizard._step_configure_credential()

        assert result is True
