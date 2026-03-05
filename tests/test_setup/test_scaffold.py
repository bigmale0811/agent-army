"""測試 scaffold 模組 — 驗證專案初始化的正確性。"""

import json
from pathlib import Path

import pytest


class TestGenerateEnvTemplate:
    """_generate_env_template 函式測試。"""

    def test_creates_env_file(self, tmp_path):
        """在空目錄建立 .env 模板。"""
        from setup.scaffold import _generate_env_template

        _generate_env_template(tmp_path)

        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" in content
        assert "DEEPSEEK_API_KEY" in content
        assert "DEFAULT_LLM_PROVIDER" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        """不覆蓋已存在的 .env。"""
        from setup.scaffold import _generate_env_template

        env_file = tmp_path / ".env"
        env_file.write_text("MY_EXISTING=value", encoding="utf-8")

        _generate_env_template(tmp_path)

        assert env_file.read_text(encoding="utf-8") == "MY_EXISTING=value"


class TestCreateDirectories:
    """_create_directories 函式測試。"""

    def test_creates_all_required_dirs(self, tmp_path):
        """建立所有必要的目錄。"""
        from setup.scaffold import _create_directories

        _create_directories(tmp_path)

        required = [
            ".claude/rules/common",
            ".claude/rules/python",
            "scripts/hooks",
            "data/memory/sessions",
            "config",
            "src",
            "tests",
        ]
        for d in required:
            assert (tmp_path / d).is_dir(), f"目錄 {d} 未建立"


class TestInitMemory:
    """_init_memory 函式測試。"""

    def test_creates_memory_files(self, tmp_path):
        """建立記憶系統檔案。"""
        from setup.scaffold import _init_memory

        _init_memory(tmp_path)

        assert (tmp_path / "data" / "memory" / "active_context.md").exists()
        assert (tmp_path / "data" / "memory" / "decisions.md").exists()
        assert (tmp_path / "data" / "memory" / "sessions").is_dir()

    def test_does_not_overwrite_existing_memory(self, tmp_path):
        """不覆蓋已存在的記憶檔案。"""
        from setup.scaffold import _init_memory

        memory_dir = tmp_path / "data" / "memory"
        memory_dir.mkdir(parents=True)
        active = memory_dir / "active_context.md"
        active.write_text("# 我的記憶", encoding="utf-8")

        _init_memory(tmp_path)

        assert active.read_text(encoding="utf-8") == "# 我的記憶"


class TestGenerateSettingsJson:
    """_generate_settings_json 函式測試。"""

    def test_creates_valid_json(self, tmp_path):
        """產生有效的 settings.json。"""
        from setup.scaffold import _generate_settings_json

        _generate_settings_json(tmp_path)

        settings_path = tmp_path / ".claude" / "settings.json"
        assert settings_path.exists()

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "hooks" in settings
        assert "SessionStart" in settings["hooks"]
        assert "PreCompact" in settings["hooks"]
        assert "SessionEnd" in settings["hooks"]

    def test_hooks_use_correct_paths(self, tmp_path):
        """hooks 路徑指向正確的 scripts/hooks 目錄。"""
        from setup.scaffold import _generate_settings_json

        _generate_settings_json(tmp_path)

        settings_path = tmp_path / ".claude" / "settings.json"
        content = settings_path.read_text(encoding="utf-8")

        hooks_path = str(tmp_path / "scripts" / "hooks").replace("\\", "/")
        assert hooks_path in content


class TestGenerateGitignore:
    """_generate_gitignore 函式測試。"""

    def test_creates_gitignore(self, tmp_path):
        """產生 .gitignore。"""
        from setup.scaffold import _generate_gitignore

        _generate_gitignore(tmp_path)

        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert ".env" in content
        assert "__pycache__" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        """不覆蓋已存在的 .gitignore。"""
        from setup.scaffold import _generate_gitignore

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("my-custom-ignore", encoding="utf-8")

        _generate_gitignore(tmp_path)

        assert gitignore.read_text(encoding="utf-8") == "my-custom-ignore"


class TestGenerateClaudeMd:
    """_generate_claude_md 函式測試。"""

    def test_creates_claude_md(self, tmp_path):
        """產生 CLAUDE.md。"""
        from setup.scaffold import _generate_claude_md

        context = {
            "project_name": "test-project",
            "language": "python",
        }
        _generate_claude_md(tmp_path, context)

        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert "test-project" in content
