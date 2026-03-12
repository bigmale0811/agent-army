"""列舉類型測試"""
from slot_cloner.models.enums import GameType, ConfidenceLevel, PipelinePhase, SymbolType


class TestGameType:
    def test_cascade_value(self):
        assert GameType.CASCADE.value == "cascade"

    def test_all_types(self):
        assert len(GameType) == 4

    def test_string_comparison(self):
        assert GameType.CASCADE == "cascade"


class TestConfidenceLevel:
    def test_high_value(self):
        assert ConfidenceLevel.HIGH.value == "high"

    def test_ordering(self):
        levels = [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]
        assert len(levels) == 3


class TestPipelinePhase:
    def test_all_phases(self):
        assert len(PipelinePhase) == 7

    def test_order(self):
        phases = list(PipelinePhase)
        assert phases[0] == PipelinePhase.INIT
        assert phases[-1] == PipelinePhase.DONE


class TestSymbolType:
    def test_regular(self):
        assert SymbolType.REGULAR.value == "regular"

    def test_all_types(self):
        expected = {"regular", "wild", "scatter", "bonus", "multiplier"}
        actual = {s.value for s in SymbolType}
        assert actual == expected
