"""Config Generator 測試"""
import json
from slot_cloner.builder.config_generator import ConfigGenerator
from slot_cloner.models.game import GameModel, GameConfig, GridConfig
from slot_cloner.models.symbol import SymbolConfig, PaytableEntry, PaytableConfig
from slot_cloner.models.enums import GameType, SymbolType


def _make_model() -> GameModel:
    symbols = (
        SymbolConfig(id="anubis", name="Anubis", symbol_type=SymbolType.REGULAR, payouts={8: 1.0}),
        SymbolConfig(id="wild", name="Wild", symbol_type=SymbolType.WILD),
    )
    config = GameConfig(
        name="test-game",
        game_type=GameType.CASCADE,
        grid=GridConfig(cols=6, rows=5),
        symbols=symbols,
        paytable=PaytableConfig(
            entries=(PaytableEntry(symbol_id="anubis", min_count=8, payout_multiplier=1.0),),
        ),
        rtp=96.89,
    )
    return GameModel(config=config)


class TestConfigGenerator:
    def test_generate_file(self, tmp_path):
        gen = ConfigGenerator()
        model = _make_model()
        path = gen.generate(model, tmp_path / "game-config.json")
        assert path.exists()

    def test_json_structure(self, tmp_path):
        gen = ConfigGenerator()
        model = _make_model()
        path = gen.generate(model, tmp_path / "game-config.json")
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["game"]["name"] == "test-game"
        assert data["game"]["type"] == "cascade"
        assert data["game"]["grid"]["cols"] == 6
        assert data["game"]["rtp"] == 96.89

    def test_symbols_in_config(self, tmp_path):
        gen = ConfigGenerator()
        model = _make_model()
        path = gen.generate(model, tmp_path / "game-config.json")
        data = json.loads(path.read_text(encoding="utf-8"))

        assert len(data["symbols"]) == 2
        assert data["symbols"][0]["id"] == "anubis"
        assert data["symbols"][1]["type"] == "wild"

    def test_features_in_config(self, tmp_path):
        gen = ConfigGenerator()
        model = _make_model()
        path = gen.generate(model, tmp_path / "game-config.json")
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["features"]["cascade"]["enabled"] is True
        assert data["features"]["wild"]["enabled"] is True
        assert data["features"]["multiplier"]["values"] == [2, 3, 5, 10, 25, 50, 100, 500]

    def test_paytable_in_config(self, tmp_path):
        gen = ConfigGenerator()
        model = _make_model()
        path = gen.generate(model, tmp_path / "game-config.json")
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["paytable"]["minClusterSize"] == 8
        assert len(data["paytable"]["entries"]) == 1
