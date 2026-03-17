# -*- coding: utf-8 -*-
"""CredentialManager 測試。

測試通行證管理器：
- Gemini API key 格式驗證
- OpenAI API key 格式驗證
- 儲存 / 讀取通行證
- 建立 .gitignore
"""

from pathlib import Path

import pytest
import yaml

from agentforge.setup.credential import CredentialManager


class TestValidateGeminiKey:
    """validate_gemini_key 測試群組。"""

    def setup_method(self) -> None:
        self.manager = CredentialManager()

    def test_validate_gemini_key_valid(self) -> None:
        """有效的 Gemini key — 以 AIza 開頭，長度 >= 30 — 回傳 True。"""
        valid_key = "AIza" + "X" * 30  # 長度 34
        assert self.manager.validate_gemini_key(valid_key) is True

    def test_validate_gemini_key_invalid_prefix(self) -> None:
        """不以 AIza 開頭 — 回傳 False。"""
        assert self.manager.validate_gemini_key("sk-" + "X" * 30) is False

    def test_validate_gemini_key_too_short(self) -> None:
        """長度不足 30 — 回傳 False。"""
        assert self.manager.validate_gemini_key("AIzaXXX") is False

    def test_validate_gemini_key_empty(self) -> None:
        """空字串 — 回傳 False。"""
        assert self.manager.validate_gemini_key("") is False


class TestValidateOpenAIKey:
    """validate_openai_key 測試群組。"""

    def setup_method(self) -> None:
        self.manager = CredentialManager()

    def test_validate_openai_key_valid(self) -> None:
        """有效的 OpenAI key — 以 sk- 開頭，長度 >= 20 — 回傳 True。"""
        valid_key = "sk-" + "X" * 20  # 長度 23
        assert self.manager.validate_openai_key(valid_key) is True

    def test_validate_openai_key_invalid_prefix(self) -> None:
        """不以 sk- 開頭 — 回傳 False。"""
        assert self.manager.validate_openai_key("AIza" + "X" * 20) is False

    def test_validate_openai_key_too_short(self) -> None:
        """長度不足 20 — 回傳 False。"""
        assert self.manager.validate_openai_key("sk-short") is False

    def test_validate_openai_key_empty(self) -> None:
        """空字串 — 回傳 False。"""
        assert self.manager.validate_openai_key("") is False


class TestSaveCredentials:
    """save_credentials 測試群組。"""

    def setup_method(self) -> None:
        self.manager = CredentialManager()

    def test_save_credentials_gemini(self, tmp_path: Path) -> None:
        """儲存 Gemini 通行證後可正確讀取。"""
        api_key = "AIza" + "X" * 30
        self.manager.save_credentials(tmp_path, "gemini", api_key)

        cred_file = tmp_path / ".agentforge" / "credentials.yaml"
        assert cred_file.is_file()

        content = yaml.safe_load(cred_file.read_text(encoding="utf-8"))
        assert content["provider"] == "gemini"
        assert content["api_key"] == api_key

    def test_save_credentials_claude_code(self, tmp_path: Path) -> None:
        """儲存 Claude-code 通行證 — 不需要 api_key 欄位。"""
        self.manager.save_credentials(tmp_path, "claude-code")

        cred_file = tmp_path / ".agentforge" / "credentials.yaml"
        assert cred_file.is_file()

        content = yaml.safe_load(cred_file.read_text(encoding="utf-8"))
        assert content["provider"] == "claude-code"
        # claude-code 不存 api_key，或 api_key 為空
        assert content.get("api_key", "") == ""

    def test_save_credentials_creates_gitignore(self, tmp_path: Path) -> None:
        """.gitignore 應被建立並包含 credentials.yaml。"""
        self.manager.save_credentials(tmp_path, "gemini", "AIza" + "X" * 30)

        gitignore_path = tmp_path / ".gitignore"
        assert gitignore_path.is_file()
        content = gitignore_path.read_text(encoding="utf-8")
        assert "credentials.yaml" in content

    def test_save_credentials_appends_gitignore(self, tmp_path: Path) -> None:
        """若 .gitignore 已存在，應附加而非覆蓋。"""
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

        self.manager.save_credentials(tmp_path, "gemini", "AIza" + "X" * 30)

        content = gitignore_path.read_text(encoding="utf-8")
        assert "*.pyc" in content
        assert "credentials.yaml" in content

    def test_save_credentials_ollama_no_key(self, tmp_path: Path) -> None:
        """Ollama 不需要 api_key，存入時 api_key 為空字串。"""
        self.manager.save_credentials(tmp_path, "ollama")

        cred_file = tmp_path / ".agentforge" / "credentials.yaml"
        content = yaml.safe_load(cred_file.read_text(encoding="utf-8"))
        assert content["provider"] == "ollama"
        assert content.get("api_key", "") == ""


class TestLoadCredentials:
    """load_credentials 測試群組。"""

    def setup_method(self) -> None:
        self.manager = CredentialManager()

    def test_load_credentials_missing(self, tmp_path: Path) -> None:
        """credentials.yaml 不存在 — 回傳空 dict。"""
        result = self.manager.load_credentials(tmp_path)
        assert result == {}

    def test_load_credentials_after_save(self, tmp_path: Path) -> None:
        """儲存後再讀取應正確。"""
        api_key = "AIza" + "X" * 30
        self.manager.save_credentials(tmp_path, "gemini", api_key)
        result = self.manager.load_credentials(tmp_path)
        assert result["provider"] == "gemini"
        assert result["api_key"] == api_key
