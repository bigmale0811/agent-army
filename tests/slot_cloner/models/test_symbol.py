"""符號與賠率模型測試"""
import pytest
from pydantic import ValidationError
from slot_cloner.models.enums import SymbolType, ConfidenceLevel
from slot_cloner.models.symbol import SymbolConfig, PaytableEntry, PaytableConfig


class TestSymbolConfig:
    def test_create_regular(self, sample_symbol):
        assert sample_symbol.id == "anubis"
        assert sample_symbol.symbol_type == SymbolType.REGULAR

    def test_create_wild(self):
        wild = SymbolConfig(id="wild", name="Wild", symbol_type=SymbolType.WILD)
        assert wild.symbol_type == SymbolType.WILD

    def test_payouts(self, sample_symbol):
        assert sample_symbol.payouts[8] == 1.0
        assert sample_symbol.payouts[12] == 10.0

    def test_frozen(self, sample_symbol):
        with pytest.raises(ValidationError):
            sample_symbol.id = "changed"

    def test_json_roundtrip(self, sample_symbol):
        data = sample_symbol.model_dump_json()
        restored = SymbolConfig.model_validate_json(data)
        assert restored == sample_symbol


class TestPaytableEntry:
    def test_create(self):
        entry = PaytableEntry(
            symbol_id="anubis",
            min_count=8,
            payout_multiplier=1.0,
            confidence=ConfidenceLevel.HIGH,
        )
        assert entry.payout_multiplier == 1.0

    def test_default_confidence(self):
        entry = PaytableEntry(symbol_id="x", min_count=5, payout_multiplier=2.0)
        assert entry.confidence == ConfidenceLevel.MEDIUM


class TestPaytableConfig:
    def test_create_with_entries(self):
        entries = (
            PaytableEntry(symbol_id="a", min_count=8, payout_multiplier=1.0),
            PaytableEntry(symbol_id="a", min_count=10, payout_multiplier=2.5),
        )
        pt = PaytableConfig(entries=entries, min_cluster_size=8)
        assert len(pt.entries) == 2
        assert pt.min_cluster_size == 8

    def test_empty_paytable(self):
        pt = PaytableConfig()
        assert len(pt.entries) == 0
