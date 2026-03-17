# -*- coding: utf-8 -*-
"""WizardController 測試 — GUI 安裝精靈的業務邏輯。

只測試 WizardController，不需要 tkinter。
涵蓋：導航控制、Provider 選擇、API Key 驗證、
連線測試委派、設定檔寫入、dry-run 模式。
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from agentforge.setup.gui_wizard import PROVIDERS, WizardController


class TestWizardControllerNavigation:
    """導航控制測試群組。"""

    def test_initial_step_is_1(self) -> None:
        """初始步驟應為 1。"""
        ctrl = WizardController()
        assert ctrl.state.current_step == 1

    def test_cannot_go_next_without_provider(self) -> None:
        """未選擇 provider 時不能前進。"""
        ctrl = WizardController()
        ok, reason = ctrl.can_go_next()
        assert ok is False
        assert len(reason) > 0

    def test_go_next_from_step1_with_provider(self) -> None:
        """選擇 provider 後可從 step 1 前進到 step 2。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ok, _ = ctrl.can_go_next()
        assert ok is True
        new_step = ctrl.go_next()
        assert new_step == 2

    def test_go_back_from_step2(self) -> None:
        """從 step 2 退回 step 1。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ctrl.go_next()
        new_step = ctrl.go_back()
        assert new_step == 1

    def test_cannot_go_back_from_step1(self) -> None:
        """step 1 退回仍為 step 1。"""
        ctrl = WizardController()
        new_step = ctrl.go_back()
        assert new_step == 1

    def test_full_navigation_forward(self) -> None:
        """可以從 step 1 一路前進到 step 4。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ctrl.state.api_key = "AIza" + "X" * 30

        assert ctrl.go_next() == 2  # step 1 → 2
        assert ctrl.go_next() == 3  # step 2 → 3
        assert ctrl.go_next() == 4  # step 3 → 4

    def test_cannot_go_past_step4(self) -> None:
        """step 4 無法再前進。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ctrl.state.api_key = "AIza" + "X" * 30
        ctrl.go_next()  # → 2
        ctrl.go_next()  # → 3
        ctrl.go_next()  # → 4
        assert ctrl.go_next() == 4  # 不變


class TestWizardControllerProviders:
    """Provider 選擇邏輯測試群組。"""

    def test_select_gemini(self) -> None:
        """選擇 gemini 時 model 應自動設定。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        assert ctrl.state.provider == "gemini"
        assert ctrl.state.model == "gemini/gemini-2.0-flash"

    def test_select_claude_code(self) -> None:
        """選擇 claude-code。"""
        ctrl = WizardController()
        ctrl.select_provider("claude-code")
        assert ctrl.state.provider == "claude-code"
        assert ctrl.state.model == "claude-code/sonnet"

    def test_select_openai(self) -> None:
        """選擇 openai。"""
        ctrl = WizardController()
        ctrl.select_provider("openai")
        assert ctrl.state.provider == "openai"
        assert ctrl.state.model == "openai/gpt-4o-mini"

    def test_select_ollama(self) -> None:
        """選擇 ollama。"""
        ctrl = WizardController()
        ctrl.select_provider("ollama")
        assert ctrl.state.provider == "ollama"
        assert ctrl.state.model == "ollama/qwen3:14b"

    def test_select_invalid_provider_ignored(self) -> None:
        """無效 provider 應被忽略。"""
        ctrl = WizardController()
        ctrl.select_provider("nonexistent")
        assert ctrl.state.provider == ""

    def test_gemini_needs_key(self) -> None:
        """gemini 需要 API Key。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        assert ctrl.needs_api_key() is True

    def test_openai_needs_key(self) -> None:
        """openai 需要 API Key。"""
        ctrl = WizardController()
        ctrl.select_provider("openai")
        assert ctrl.needs_api_key() is True

    def test_claude_no_key(self) -> None:
        """claude-code 不需要 API Key。"""
        ctrl = WizardController()
        ctrl.select_provider("claude-code")
        assert ctrl.needs_api_key() is False

    def test_ollama_no_key(self) -> None:
        """ollama 不需要 API Key。"""
        ctrl = WizardController()
        ctrl.select_provider("ollama")
        assert ctrl.needs_api_key() is False

    def test_all_providers_defined(self) -> None:
        """PROVIDERS 應包含 4 個 provider。"""
        assert len(PROVIDERS) == 4
        assert "gemini" in PROVIDERS
        assert "claude-code" in PROVIDERS
        assert "openai" in PROVIDERS
        assert "ollama" in PROVIDERS


class TestWizardControllerValidation:
    """API Key 驗證測試群組。"""

    def test_gemini_key_valid(self) -> None:
        """有效的 Gemini key。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ok, msg = ctrl.validate_api_key("AIza" + "X" * 30)
        assert ok is True

    def test_gemini_key_invalid(self) -> None:
        """無效的 Gemini key。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ok, msg = ctrl.validate_api_key("bad-key")
        assert ok is False
        assert len(msg) > 0

    def test_openai_key_valid(self) -> None:
        """有效的 OpenAI key。"""
        ctrl = WizardController()
        ctrl.select_provider("openai")
        ok, msg = ctrl.validate_api_key("sk-" + "X" * 20)
        assert ok is True

    def test_openai_key_invalid(self) -> None:
        """無效的 OpenAI key。"""
        ctrl = WizardController()
        ctrl.select_provider("openai")
        ok, msg = ctrl.validate_api_key("invalid")
        assert ok is False

    def test_step2_cannot_advance_without_key(self) -> None:
        """Gemini 在 step 2 時無 key 不能前進。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ctrl.go_next()  # → step 2
        ok, _ = ctrl.can_go_next()
        assert ok is False  # 沒有 key

    def test_step2_can_advance_with_key(self) -> None:
        """Gemini 在 step 2 有 key 可以前進。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ctrl.go_next()  # → step 2
        ctrl.state.api_key = "AIza" + "X" * 30
        ok, _ = ctrl.can_go_next()
        assert ok is True

    def test_step2_claude_can_advance_without_key(self) -> None:
        """claude-code 在 step 2 不需要 key 即可前進。"""
        ctrl = WizardController()
        ctrl.select_provider("claude-code")
        ctrl.go_next()  # → step 2
        ok, _ = ctrl.can_go_next()
        assert ok is True


class TestWizardControllerConnectionTest:
    """連線測試委派測試群組。"""

    def test_gemini_connection_format_only(self) -> None:
        """Gemini 連線測試只做格式驗證。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ctrl.state.api_key = "AIza" + "X" * 30
        ok, msg = ctrl.run_connection_test()
        assert ok is True
        assert "通過" in msg

    def test_gemini_no_key_fails(self) -> None:
        """Gemini 無 key 連線測試失敗。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ok, msg = ctrl.run_connection_test()
        assert ok is False

    def test_claude_delegates_to_detector(self) -> None:
        """Claude 連線測試委派給 detector。"""
        ctrl = WizardController()
        ctrl.select_provider("claude-code")
        with patch.object(
            ctrl._detector, "check_claude_cli", return_value=(True, "claude 1.0")
        ):
            ok, msg = ctrl.run_connection_test()
        assert ok is True

    def test_ollama_delegates_to_detector(self) -> None:
        """Ollama 連線測試委派給 detector。"""
        ctrl = WizardController()
        ctrl.select_provider("ollama")
        with patch.object(
            ctrl._detector, "check_ollama", return_value=(True, "qwen3:14b")
        ):
            ok, msg = ctrl.run_connection_test()
        assert ok is True

    def test_openai_connection_format_only(self) -> None:
        """OpenAI 連線測試只做格式驗證。"""
        ctrl = WizardController()
        ctrl.select_provider("openai")
        ctrl.state.api_key = "sk-" + "X" * 20
        ok, msg = ctrl.run_connection_test()
        assert ok is True

    def test_step3_always_can_advance(self) -> None:
        """Step 3 連線測試不強制通過，可以前進。"""
        ctrl = WizardController()
        ctrl.select_provider("gemini")
        ctrl.state.api_key = "AIza" + "X" * 30
        ctrl.go_next()  # → 2
        ctrl.go_next()  # → 3
        ok, _ = ctrl.can_go_next()
        assert ok is True


class TestWizardControllerDryRun:
    """dry-run 模式測試群組。"""

    def test_dry_run_flag(self) -> None:
        """dry_run 旗標正確設定。"""
        ctrl = WizardController(dry_run=True)
        assert ctrl.state.dry_run is True

    def test_dry_run_no_files_created(self, tmp_path: Path) -> None:
        """dry-run 不應建立任何檔案。"""
        ctrl = WizardController(dry_run=True, project_path=tmp_path)
        ctrl.select_provider("gemini")
        ctrl.state.api_key = "AIza" + "X" * 30
        ctrl.write_all_config()
        assert not (tmp_path / "agentforge.yaml").exists()

    def test_normal_mode_creates_files(self, tmp_path: Path) -> None:
        """非 dry-run 應建立設定檔。"""
        ctrl = WizardController(dry_run=False, project_path=tmp_path)
        ctrl.select_provider("gemini")
        ctrl.state.api_key = "AIza" + "X" * 30
        files = ctrl.write_all_config()
        assert (tmp_path / "agentforge.yaml").exists()
        assert len(files) > 0


class TestWizardControllerProjectPath:
    """專案路徑測試群組。"""

    def test_custom_project_path(self, tmp_path: Path) -> None:
        """可自訂專案路徑。"""
        ctrl = WizardController(project_path=tmp_path)
        assert ctrl.state.project_path == tmp_path

    def test_default_project_path_is_cwd(self) -> None:
        """預設路徑為當前工作目錄。"""
        ctrl = WizardController()
        assert ctrl.state.project_path == Path.cwd()
