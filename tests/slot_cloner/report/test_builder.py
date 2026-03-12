"""Report Builder 測試"""
import json
from pathlib import Path
from slot_cloner.report.builder import ReportBuilder
from slot_cloner.models.game import GameModel, GameConfig, GameFingerprint, GridConfig
from slot_cloner.models.symbol import SymbolConfig, PaytableEntry, PaytableConfig
from slot_cloner.models.enums import GameType, SymbolType, ConfidenceLevel


def _make_game_model() -> GameModel:
    """建立測試用 GameModel"""
    symbols = (
        SymbolConfig(id="anubis", name="Anubis", symbol_type=SymbolType.REGULAR, payouts={8: 1.0, 10: 2.5}),
        SymbolConfig(id="wild", name="Wild", symbol_type=SymbolType.WILD),
        SymbolConfig(id="scatter", name="Scatter", symbol_type=SymbolType.SCATTER),
    )
    paytable = PaytableConfig(
        entries=(
            PaytableEntry(symbol_id="anubis", min_count=8, payout_multiplier=1.0, confidence=ConfidenceLevel.HIGH),
            PaytableEntry(symbol_id="anubis", min_count=10, payout_multiplier=2.5, confidence=ConfidenceLevel.HIGH),
        ),
        min_cluster_size=8,
    )
    config = GameConfig(
        name="storm-of-seth",
        display_name="Storm of Seth",
        game_type=GameType.CASCADE,
        grid=GridConfig(cols=6, rows=5),
        symbols=symbols,
        paytable=paytable,
        rtp=96.89,
        max_multiplier=51000.0,
    )
    fingerprint = GameFingerprint(
        url="https://play.godeebxp.com/test",
        framework="pixi",
        provider="atg",
        canvas_detected=True,
    )
    return GameModel(
        config=config,
        fingerprint=fingerprint,
        confidence_map={"paytable": ConfidenceLevel.HIGH, "symbols": ConfidenceLevel.MEDIUM},
    )


class TestReportBuilder:
    def test_build_creates_files(self, tmp_path):
        builder = ReportBuilder()
        model = _make_game_model()
        report_path = builder.build(model, tmp_path)

        assert report_path.exists()
        assert (tmp_path / "paytable.json").exists()
        assert (tmp_path / "symbols.json").exists()
        assert (tmp_path / "rules.json").exists()

    def test_markdown_content(self, tmp_path):
        builder = ReportBuilder()
        model = _make_game_model()
        report_path = builder.build(model, tmp_path)

        content = report_path.read_text(encoding="utf-8")
        assert "Storm of Seth" in content
        assert "cascade" in content
        assert "96.89" in content
        assert "Anubis" in content
        assert "Wild" in content

    def test_paytable_json(self, tmp_path):
        builder = ReportBuilder()
        model = _make_game_model()
        builder.build(model, tmp_path)

        data = json.loads((tmp_path / "paytable.json").read_text(encoding="utf-8"))
        assert data["min_cluster_size"] == 8
        assert len(data["entries"]) == 2

    def test_symbols_json(self, tmp_path):
        builder = ReportBuilder()
        model = _make_game_model()
        builder.build(model, tmp_path)

        data = json.loads((tmp_path / "symbols.json").read_text(encoding="utf-8"))
        assert len(data) == 3
        assert data[0]["id"] == "anubis"

    def test_rules_json(self, tmp_path):
        builder = ReportBuilder()
        model = _make_game_model()
        builder.build(model, tmp_path)

        data = json.loads((tmp_path / "rules.json").read_text(encoding="utf-8"))
        assert data["game_type"] == "cascade"
        assert data["grid"]["cols"] == 6
        assert data["features"]["cascade"]["enabled"] is True
