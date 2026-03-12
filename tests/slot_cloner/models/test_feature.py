"""遊戲特殊機制模型測試"""
import pytest
from pydantic import ValidationError
from slot_cloner.models.feature import (
    WildConfig, ScatterConfig, CascadeConfig,
    MultiplierConfig, FreeSpinConfig, FeaturesConfig,
)


class TestWildConfig:
    def test_defaults(self):
        wild = WildConfig()
        assert wild.enabled is True
        assert wild.substitutes_all is True
        assert "scatter" in wild.except_symbols

    def test_frozen(self):
        wild = WildConfig()
        with pytest.raises(ValidationError):
            wild.enabled = False


class TestScatterConfig:
    def test_defaults(self):
        scatter = ScatterConfig()
        assert scatter.trigger_count == 4
        assert scatter.free_spins_awarded == 15


class TestCascadeConfig:
    def test_defaults(self):
        cascade = CascadeConfig()
        assert cascade.min_cluster_size == 8
        assert cascade.fill_from_top is True


class TestMultiplierConfig:
    def test_defaults(self):
        mult = MultiplierConfig()
        assert 500 in mult.values
        assert mult.accumulate_in_cascade is True

    def test_custom_values(self):
        mult = MultiplierConfig(values=(2, 5, 10))
        assert len(mult.values) == 3


class TestFreeSpinConfig:
    def test_defaults(self):
        fs = FreeSpinConfig()
        assert fs.base_spins == 15
        assert fs.retrigger_enabled is True


class TestFeaturesConfig:
    def test_defaults(self):
        features = FeaturesConfig()
        assert features.wild.enabled is True
        assert features.cascade.enabled is True
        assert features.multiplier.enabled is True

    def test_custom(self):
        features = FeaturesConfig(
            wild=WildConfig(enabled=False),
            cascade=CascadeConfig(min_cluster_size=5),
        )
        assert features.wild.enabled is False
        assert features.cascade.min_cluster_size == 5

    def test_frozen(self):
        features = FeaturesConfig()
        with pytest.raises(ValidationError):
            features.wild = WildConfig(enabled=False)
