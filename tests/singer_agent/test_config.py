# -*- coding: utf-8 -*-
"""
DEV-2: config.py 單元測試
測試路徑常數、子目錄結構、環境變數讀取與預設值。
"""
import os
import pytest
from pathlib import Path


# ─────────────────────────────────────────────────
# 路徑常數測試
# ─────────────────────────────────────────────────

class TestDataDirPaths:
    """測試 DATA_DIR 及各子目錄路徑常數。"""

    def test_data_dir_is_path_type(self):
        """DATA_DIR 必須為 Path 型別。"""
        from src.singer_agent.config import DATA_DIR
        assert isinstance(DATA_DIR, Path)

    def test_data_dir_value(self):
        """DATA_DIR 應指向 data/singer_agent。"""
        from src.singer_agent.config import DATA_DIR
        # 僅比較路徑尾端，避免絕對路徑差異
        assert DATA_DIR.parts[-1] == "singer_agent"
        assert DATA_DIR.parts[-2] == "data"

    def test_character_dir_is_path(self):
        """CHARACTER_DIR 必須為 Path 型別。"""
        from src.singer_agent.config import CHARACTER_DIR
        assert isinstance(CHARACTER_DIR, Path)

    def test_character_dir_under_data_dir(self):
        """CHARACTER_DIR 應為 DATA_DIR 的子目錄。"""
        from src.singer_agent.config import DATA_DIR, CHARACTER_DIR
        assert str(CHARACTER_DIR).startswith(str(DATA_DIR))

    def test_inbox_dir_is_path(self):
        """INBOX_DIR 必須為 Path 型別。"""
        from src.singer_agent.config import INBOX_DIR
        assert isinstance(INBOX_DIR, Path)

    def test_inbox_dir_name(self):
        """INBOX_DIR 目錄名稱應為 inbox。"""
        from src.singer_agent.config import INBOX_DIR
        assert INBOX_DIR.name == "inbox"

    def test_backgrounds_dir_name(self):
        """BACKGROUNDS_DIR 目錄名稱應為 backgrounds。"""
        from src.singer_agent.config import BACKGROUNDS_DIR
        assert BACKGROUNDS_DIR.name == "backgrounds"

    def test_composites_dir_name(self):
        """COMPOSITES_DIR 目錄名稱應為 composites。"""
        from src.singer_agent.config import COMPOSITES_DIR
        assert COMPOSITES_DIR.name == "composites"

    def test_videos_dir_name(self):
        """VIDEOS_DIR 目錄名稱應為 videos。"""
        from src.singer_agent.config import VIDEOS_DIR
        assert VIDEOS_DIR.name == "videos"

    def test_specs_dir_name(self):
        """SPECS_DIR 目錄名稱應為 specs。"""
        from src.singer_agent.config import SPECS_DIR
        assert SPECS_DIR.name == "specs"

    def test_projects_dir_name(self):
        """PROJECTS_DIR 目錄名稱應為 projects。"""
        from src.singer_agent.config import PROJECTS_DIR
        assert PROJECTS_DIR.name == "projects"

    def test_all_subdirs_are_paths(self):
        """所有子目錄常數均為 Path 型別。"""
        from src.singer_agent import config
        subdirs = [
            config.CHARACTER_DIR,
            config.INBOX_DIR,
            config.BACKGROUNDS_DIR,
            config.COMPOSITES_DIR,
            config.VIDEOS_DIR,
            config.SPECS_DIR,
            config.PROJECTS_DIR,
        ]
        for d in subdirs:
            assert isinstance(d, Path), f"{d} is not a Path"

    def test_all_subdirs_under_data_dir(self):
        """所有子目錄應在 DATA_DIR 之下。"""
        from src.singer_agent import config
        subdirs = [
            config.CHARACTER_DIR,
            config.INBOX_DIR,
            config.BACKGROUNDS_DIR,
            config.COMPOSITES_DIR,
            config.VIDEOS_DIR,
            config.SPECS_DIR,
            config.PROJECTS_DIR,
        ]
        for d in subdirs:
            assert str(d).startswith(str(config.DATA_DIR)), \
                f"{d} is not under DATA_DIR={config.DATA_DIR}"

    def test_character_image_path(self):
        """CHARACTER_IMAGE 應為 CHARACTER_DIR / avatar.png。"""
        from src.singer_agent.config import CHARACTER_DIR, CHARACTER_IMAGE
        assert isinstance(CHARACTER_IMAGE, Path)
        assert CHARACTER_IMAGE == CHARACTER_DIR / "avatar.png"
        assert CHARACTER_IMAGE.name == "avatar.png"


# ─────────────────────────────────────────────────
# 工具路徑測試
# ─────────────────────────────────────────────────

class TestToolPaths:
    """測試工具路徑常數（SADTALKER_DIR、FFMPEG_BIN 等）。"""

    def test_sadtalker_dir_is_path(self):
        """SADTALKER_DIR 必須為 Path 型別。"""
        from src.singer_agent.config import SADTALKER_DIR
        assert isinstance(SADTALKER_DIR, Path)

    def test_ffmpeg_bin_is_path(self):
        """FFMPEG_BIN 必須為 Path 型別。"""
        from src.singer_agent.config import FFMPEG_BIN
        assert isinstance(FFMPEG_BIN, Path)

    def test_comfyui_url_is_string(self):
        """COMFYUI_URL 必須為字串。"""
        from src.singer_agent.config import COMFYUI_URL
        assert isinstance(COMFYUI_URL, str)

    def test_comfyui_url_default(self, monkeypatch):
        """COMFYUI_URL 未設置環境變數時預設為 http://localhost:8188。"""
        monkeypatch.delenv("COMFYUI_URL", raising=False)
        # 重新載入模組以套用環境變數
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.COMFYUI_URL == "http://localhost:8188"

    def test_ollama_url_is_string(self):
        """OLLAMA_URL 必須為字串。"""
        from src.singer_agent.config import OLLAMA_URL
        assert isinstance(OLLAMA_URL, str)

    def test_ollama_url_default(self, monkeypatch):
        """OLLAMA_URL 未設置環境變數時預設為 http://localhost:11434。"""
        monkeypatch.delenv("OLLAMA_URL", raising=False)
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.OLLAMA_URL == "http://localhost:11434"

    def test_comfyui_url_from_env(self, monkeypatch):
        """COMFYUI_URL 可透過環境變數覆寫。"""
        monkeypatch.setenv("COMFYUI_URL", "http://custom-host:9999")
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.COMFYUI_URL == "http://custom-host:9999"

    def test_ollama_url_from_env(self, monkeypatch):
        """OLLAMA_URL 可透過環境變數覆寫。"""
        monkeypatch.setenv("OLLAMA_URL", "http://remote:11434")
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.OLLAMA_URL == "http://remote:11434"

    def test_sadtalker_dir_from_env(self, monkeypatch, tmp_path):
        """SADTALKER_DIR 可透過環境變數覆寫。"""
        custom_path = str(tmp_path / "SadTalker")
        monkeypatch.setenv("SADTALKER_DIR", custom_path)
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.SADTALKER_DIR == Path(custom_path)

    def test_ffmpeg_bin_from_env(self, monkeypatch, tmp_path):
        """FFMPEG_BIN 可透過環境變數覆寫。"""
        custom_ffmpeg = str(tmp_path / "ffmpeg.exe")
        monkeypatch.setenv("FFMPEG_BIN", custom_ffmpeg)
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.FFMPEG_BIN == Path(custom_ffmpeg)


# ─────────────────────────────────────────────────
# Telegram 設定測試
# ─────────────────────────────────────────────────

class TestTelegramConfig:
    """測試 Telegram Bot 相關環境變數讀取。"""

    def test_telegram_bot_token_from_env(self, monkeypatch):
        """TELEGRAM_BOT_TOKEN 可從環境變數讀取（SINGER_BOT_TOKEN 不存在時 fallback）。"""
        import importlib
        import unittest.mock as mock
        import src.singer_agent.config as cfg_module
        # 攔截 os.environ.get：SINGER_BOT_TOKEN 回傳預設值，模擬未設定
        original_get = os.environ.get

        def patched_get(key, *args):
            if key == "SINGER_BOT_TOKEN":
                return args[0] if args else ""
            if key == "TELEGRAM_BOT_TOKEN":
                return "1234567890:test_token_abc"
            return original_get(key, *args)

        with mock.patch("os.environ.get", side_effect=patched_get):
            with mock.patch("dotenv.load_dotenv"):
                importlib.reload(cfg_module)
        assert cfg_module.TELEGRAM_BOT_TOKEN == "1234567890:test_token_abc"

    def test_telegram_bot_token_default_empty(self, monkeypatch):
        """兩個 token 變數都未設置時預設為空字串。"""
        import importlib
        import unittest.mock as mock
        import src.singer_agent.config as cfg_module
        # 攔截 os.environ.get 讓 token 相關 key 回傳空字串
        original_get = os.environ.get

        def patched_get(key, default=""):
            if key in ("TELEGRAM_BOT_TOKEN", "SINGER_BOT_TOKEN"):
                return default
            return original_get(key, default)

        with mock.patch("os.environ.get", side_effect=patched_get):
            with mock.patch("dotenv.load_dotenv"):
                importlib.reload(cfg_module)
        assert cfg_module.TELEGRAM_BOT_TOKEN == ""

    def test_allowed_user_ids_from_env(self, monkeypatch):
        """ALLOWED_USER_IDS 逗號分隔字串應解析為 list[int]（SINGER_CHAT_ID 不存在時 fallback）。"""
        import importlib
        import unittest.mock as mock
        monkeypatch.delenv("SINGER_CHAT_ID", raising=False)
        monkeypatch.setenv("ALLOWED_USER_IDS", "123456789,987654321,111222333")
        import src.singer_agent.config as cfg_module
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(cfg_module)
        assert cfg_module.ALLOWED_USER_IDS == [123456789, 987654321, 111222333]

    def test_allowed_user_ids_single(self, monkeypatch):
        """ALLOWED_USER_IDS 只有一個 ID 時正確解析。"""
        import importlib
        import unittest.mock as mock
        monkeypatch.delenv("SINGER_CHAT_ID", raising=False)
        monkeypatch.setenv("ALLOWED_USER_IDS", "123456789")
        import src.singer_agent.config as cfg_module
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(cfg_module)
        assert cfg_module.ALLOWED_USER_IDS == [123456789]

    def test_allowed_user_ids_empty_default(self, monkeypatch):
        """兩個 ID 變數都未設置時預設為空 list。"""
        import importlib
        import unittest.mock as mock
        monkeypatch.delenv("SINGER_CHAT_ID", raising=False)
        monkeypatch.delenv("ALLOWED_USER_IDS", raising=False)
        import src.singer_agent.config as cfg_module
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(cfg_module)
        assert cfg_module.ALLOWED_USER_IDS == []

    def test_allowed_user_ids_is_list_of_int(self, monkeypatch):
        """ALLOWED_USER_IDS 解析結果每個元素必須為 int 型別。"""
        import importlib
        import unittest.mock as mock
        monkeypatch.delenv("SINGER_CHAT_ID", raising=False)
        monkeypatch.setenv("ALLOWED_USER_IDS", "100,200,300")
        import src.singer_agent.config as cfg_module
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(cfg_module)
        assert all(isinstance(uid, int) for uid in cfg_module.ALLOWED_USER_IDS)

    def test_allowed_user_ids_with_spaces(self, monkeypatch):
        """ALLOWED_USER_IDS 逗號周圍有空白時也能正確解析。"""
        import importlib
        import unittest.mock as mock
        monkeypatch.delenv("SINGER_CHAT_ID", raising=False)
        monkeypatch.setenv("ALLOWED_USER_IDS", "123 , 456 , 789")
        import src.singer_agent.config as cfg_module
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(cfg_module)
        assert cfg_module.ALLOWED_USER_IDS == [123, 456, 789]


# ─────────────────────────────────────────────────
# Gemini / LLM 設定測試
# ─────────────────────────────────────────────────

class TestLLMConfig:
    """測試 Gemini API 及 LLM Provider 設定。"""

    def test_gemini_api_key_from_env(self, monkeypatch):
        """GEMINI_API_KEY 可從環境變數讀取。"""
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-xyz")
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.GEMINI_API_KEY == "test-gemini-key-xyz"

    def test_gemini_api_key_default_empty(self, monkeypatch):
        """GEMINI_API_KEY 未設置時預設為空字串（同時攔截 dotenv 載入）。"""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        import importlib
        import unittest.mock as mock
        import src.singer_agent.config as cfg_module
        with mock.patch("dotenv.load_dotenv"):
            importlib.reload(cfg_module)
        assert cfg_module.GEMINI_API_KEY == ""

    def test_singer_llm_provider_default(self, monkeypatch):
        """SINGER_LLM_PROVIDER 未設置時預設為 'ollama'。"""
        monkeypatch.delenv("SINGER_LLM_PROVIDER", raising=False)
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.SINGER_LLM_PROVIDER == "ollama"

    def test_singer_llm_provider_from_env(self, monkeypatch):
        """SINGER_LLM_PROVIDER 可透過環境變數覆寫。"""
        monkeypatch.setenv("SINGER_LLM_PROVIDER", "gemini")
        import importlib
        import src.singer_agent.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.SINGER_LLM_PROVIDER == "gemini"

    def test_singer_llm_provider_is_string(self):
        """SINGER_LLM_PROVIDER 必須為字串型別。"""
        from src.singer_agent.config import SINGER_LLM_PROVIDER
        assert isinstance(SINGER_LLM_PROVIDER, str)
