"""Config 設定測試"""
from pathlib import Path
from slot_cloner.config.settings import SlotClonerSettings, load_settings


class TestSlotClonerSettings:
    def test_defaults(self):
        settings = SlotClonerSettings()
        assert settings.headless is True
        assert settings.max_retries == 3
        assert settings.log_level == "INFO"

    def test_custom(self):
        settings = SlotClonerSettings(headless=False, max_retries=5)
        assert settings.headless is False
        assert settings.max_retries == 5


class TestLoadSettings:
    def test_default_settings(self):
        settings = load_settings()
        assert isinstance(settings, SlotClonerSettings)

    def test_missing_file(self):
        settings = load_settings(Path("/nonexistent/config.yaml"))
        assert isinstance(settings, SlotClonerSettings)
