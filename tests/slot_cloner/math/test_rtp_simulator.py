"""RTP 模擬器單元測試"""
import pytest
from slot_cloner.math.rtp_simulator import RTPSimulator, RTPResult
from slot_cloner.models.game import GameConfig, GridConfig
from slot_cloner.models.symbol import SymbolConfig, PaytableConfig, PaytableEntry
from slot_cloner.models.feature import (
    FeaturesConfig, WildConfig, ScatterConfig,
    CascadeConfig, MultiplierConfig, FreeSpinConfig,
)
from slot_cloner.models.enums import GameType, SymbolType, ConfidenceLevel


@pytest.fixture
def sample_config() -> GameConfig:
    """建立簡化的測試用 GameConfig"""
    return GameConfig(
        name="test-game",
        game_type=GameType.CASCADE,
        grid=GridConfig(cols=6, rows=5),
        symbols=[
            SymbolConfig(id="sym_a", name="A", symbol_type=SymbolType.REGULAR, payouts={"8": 1, "12": 3, "20": 10}),
            SymbolConfig(id="sym_b", name="B", symbol_type=SymbolType.REGULAR, payouts={"8": 0.5, "12": 2}),
            SymbolConfig(id="sym_c", name="C", symbol_type=SymbolType.REGULAR, payouts={"8": 0.3, "12": 1}),
            SymbolConfig(id="wild", name="Wild", symbol_type=SymbolType.WILD, payouts={}),
            SymbolConfig(id="scatter", name="Scatter", symbol_type=SymbolType.SCATTER, payouts={}),
        ],
        paytable=PaytableConfig(
            min_cluster_size=8,
            entries=[
                PaytableEntry(symbol_id="sym_a", min_count=8, payout_multiplier=1.0, confidence=ConfidenceLevel.HIGH),
                PaytableEntry(symbol_id="sym_b", min_count=8, payout_multiplier=0.5, confidence=ConfidenceLevel.HIGH),
                PaytableEntry(symbol_id="sym_c", min_count=8, payout_multiplier=0.3, confidence=ConfidenceLevel.HIGH),
            ],
        ),
        features=FeaturesConfig(
            wild=WildConfig(enabled=True, symbol_id="wild"),
            scatter=ScatterConfig(enabled=True, symbol_id="scatter", trigger_count=4, free_spins_awarded=15),
            cascade=CascadeConfig(enabled=True, min_cluster_size=8),
            multiplier=MultiplierConfig(enabled=False),
            free_spin=FreeSpinConfig(enabled=True, base_spins=15),
        ),
    )


def test_simulate_returns_result(sample_config: GameConfig):
    """模擬應回傳 RTPResult"""
    sim = RTPSimulator(sample_config, seed=42)
    result = sim.simulate(num_spins=1000, bet=1.0)
    assert isinstance(result, RTPResult)
    assert result.total_spins == 1000
    assert result.total_wagered == 1000.0


def test_rtp_in_reasonable_range(sample_config: GameConfig):
    """RTP 應在合理範圍內 (10%~200%)"""
    sim = RTPSimulator(sample_config, seed=123)
    result = sim.simulate(num_spins=10000, bet=1.0)
    assert 10 < result.rtp_percent < 200


def test_hit_rate_positive(sample_config: GameConfig):
    """中獎率應大於 0"""
    sim = RTPSimulator(sample_config, seed=456)
    result = sim.simulate(num_spins=5000, bet=1.0)
    assert result.hit_rate > 0


def test_deterministic_with_seed(sample_config: GameConfig):
    """相同 seed 應產出相同結果"""
    sim1 = RTPSimulator(sample_config, seed=789)
    sim2 = RTPSimulator(sample_config, seed=789)
    r1 = sim1.simulate(num_spins=1000, bet=1.0)
    r2 = sim2.simulate(num_spins=1000, bet=1.0)
    assert r1.rtp_percent == r2.rtp_percent
    assert r1.total_won == r2.total_won


def test_symbol_hit_counts_populated(sample_config: GameConfig):
    """符號命中統計應有資料"""
    sim = RTPSimulator(sample_config, seed=101)
    result = sim.simulate(num_spins=5000, bet=1.0)
    assert len(result.symbol_hit_counts) > 0


def test_cascade_depth_positive(sample_config: GameConfig):
    """平均 cascade 深度應大於 0"""
    sim = RTPSimulator(sample_config, seed=202)
    result = sim.simulate(num_spins=5000, bet=1.0)
    assert result.avg_cascade_depth > 0
