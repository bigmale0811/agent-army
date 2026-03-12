"""共用測試 fixture"""
import pytest
from pathlib import Path
from slot_cloner.models import (
    GameType, ConfidenceLevel, SymbolType,
    SymbolConfig, PaytableEntry, PaytableConfig,
    WildConfig, ScatterConfig, CascadeConfig, MultiplierConfig,
    FreeSpinConfig, FeaturesConfig,
    GridConfig, GameConfig, GameFingerprint, GameModel,
    ImageAsset, AudioAsset, SpriteFrame, SpriteSheet, AssetBundle,
)


@pytest.fixture
def sample_symbol():
    """範例符號"""
    return SymbolConfig(
        id="anubis",
        name="Anubis",
        symbol_type=SymbolType.REGULAR,
        image_name="anubis.png",
        payouts={8: 1.0, 10: 2.5, 12: 10.0},
    )


@pytest.fixture
def sample_game_config():
    """範例遊戲設定（戰神賽特風格）"""
    symbols = (
        SymbolConfig(id="anubis", name="Anubis", symbol_type=SymbolType.REGULAR, payouts={8: 1.0, 10: 2.5, 12: 10.0}),
        SymbolConfig(id="eye_of_ra", name="Eye of Ra", symbol_type=SymbolType.REGULAR, payouts={8: 0.5, 10: 1.5, 12: 5.0}),
        SymbolConfig(id="wild", name="Wild", symbol_type=SymbolType.WILD),
        SymbolConfig(id="scatter", name="Scatter", symbol_type=SymbolType.SCATTER),
    )
    paytable = PaytableConfig(
        entries=(
            PaytableEntry(symbol_id="anubis", min_count=8, payout_multiplier=1.0),
            PaytableEntry(symbol_id="anubis", min_count=10, payout_multiplier=2.5),
            PaytableEntry(symbol_id="anubis", min_count=12, payout_multiplier=10.0),
        ),
        min_cluster_size=8,
    )
    return GameConfig(
        name="storm-of-seth",
        display_name="Storm of Seth",
        game_type=GameType.CASCADE,
        grid=GridConfig(cols=6, rows=5),
        symbols=symbols,
        paytable=paytable,
        rtp=96.89,
        max_multiplier=51000.0,
    )


@pytest.fixture
def sample_fingerprint():
    """範例技術指紋"""
    return GameFingerprint(
        url="https://play.godeebxp.com/egames/test",
        framework="pixi",
        provider="atg",
        game_type=GameType.CASCADE,
        canvas_detected=True,
        webgl_detected=True,
        websocket_urls=("wss://socket.godeebxp.com",),
    )


@pytest.fixture
def sample_asset_bundle(tmp_path):
    """範例資源包"""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake png")
    return AssetBundle(
        images=(ImageAsset(name="test", path=img_path),),
    )
