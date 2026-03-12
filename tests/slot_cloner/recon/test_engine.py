"""Recon Engine 測試"""
from slot_cloner.recon.engine import ReconEngine
from slot_cloner.models.enums import GameType


class TestReconEngine:
    def test_detect_provider_atg(self):
        assert ReconEngine._detect_provider("https://play.godeebxp.com/game") == "atg"

    def test_detect_provider_unknown(self):
        assert ReconEngine._detect_provider("https://unknown.com") == "unknown"

    def test_detect_game_type_cascade(self):
        url = "https://example.com?gt=slot-erase-any-times-1"
        assert ReconEngine._detect_game_type(url) == GameType.CASCADE

    def test_detect_game_type_ways(self):
        url = "https://example.com?gt=ways-to-win"
        assert ReconEngine._detect_game_type(url) == GameType.WAYS

    def test_detect_game_type_default(self):
        assert ReconEngine._detect_game_type("https://example.com") == GameType.CASCADE
