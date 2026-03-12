"""Plugin Registry 測試"""
import pytest
from slot_cloner.plugins.base import BaseAdapter
from slot_cloner.plugins.registry import PluginRegistry
from slot_cloner.plugins.generic.adapter import GenericAdapter
from slot_cloner.models.game import GameFingerprint, GameModel, GameConfig
from slot_cloner.models.asset import AssetBundle
from slot_cloner.models.enums import GameType


class FakeATGAdapter(BaseAdapter):
    """測試用假 ATG Adapter"""

    @staticmethod
    def can_handle(url, fingerprint=None):
        return "godeebxp.com" in url

    @property
    def name(self):
        return "fake_atg"

    async def recon(self, url, **kwargs):
        return GameFingerprint(url=url, provider="atg")

    async def scrape(self, fingerprint, **kwargs):
        return AssetBundle()

    async def reverse(self, fingerprint, assets, **kwargs):
        return GameModel(config=GameConfig(name="test", game_type=GameType.CASCADE))


class FakePGAdapter(BaseAdapter):
    """測試用假 PG Soft Adapter"""

    @staticmethod
    def can_handle(url, fingerprint=None):
        return "pgsoft.com" in url

    @property
    def name(self):
        return "fake_pg"

    async def recon(self, url, **kwargs):
        return GameFingerprint(url=url, provider="pg_soft")

    async def scrape(self, fingerprint, **kwargs):
        return AssetBundle()

    async def reverse(self, fingerprint, assets, **kwargs):
        return GameModel(config=GameConfig(name="test", game_type=GameType.CASCADE))


class TestPluginRegistry:
    def test_register(self):
        registry = PluginRegistry()
        registry.register(FakeATGAdapter)
        assert len(registry.adapters) == 1

    def test_no_duplicate(self):
        registry = PluginRegistry()
        registry.register(FakeATGAdapter)
        registry.register(FakeATGAdapter)
        assert len(registry.adapters) == 1

    def test_find_atg(self):
        registry = PluginRegistry()
        registry.register(FakeATGAdapter)
        adapter = registry.find_adapter("https://play.godeebxp.com/game")
        assert adapter.name == "fake_atg"

    def test_find_pg(self):
        registry = PluginRegistry()
        registry.register(FakeATGAdapter)
        registry.register(FakePGAdapter)
        adapter = registry.find_adapter("https://demo.pgsoft.com/game")
        assert adapter.name == "fake_pg"

    def test_fallback_to_generic(self):
        registry = PluginRegistry()
        registry.register(FakeATGAdapter)
        adapter = registry.find_adapter("https://unknown-provider.com/game")
        assert isinstance(adapter, GenericAdapter)

    def test_empty_registry_fallback(self):
        registry = PluginRegistry()
        adapter = registry.find_adapter("https://any.com")
        assert isinstance(adapter, GenericAdapter)
