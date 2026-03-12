"""遊戲核心模型測試"""
import pytest
from pydantic import ValidationError
from slot_cloner.models.enums import GameType, ConfidenceLevel
from slot_cloner.models.game import (
    GridConfig, GameFingerprint, GameConfig, GameModel,
)


class TestGridConfig:
    def test_defaults(self):
        grid = GridConfig()
        assert grid.cols == 6
        assert grid.rows == 5

    def test_custom(self):
        grid = GridConfig(cols=5, rows=3)
        assert grid.cols == 5

    def test_frozen(self):
        grid = GridConfig()
        with pytest.raises(ValidationError):
            grid.cols = 10


class TestGameFingerprint:
    def test_create(self, sample_fingerprint):
        assert sample_fingerprint.framework == "pixi"
        assert sample_fingerprint.provider == "atg"
        assert sample_fingerprint.canvas_detected is True

    def test_websocket_urls(self, sample_fingerprint):
        assert len(sample_fingerprint.websocket_urls) == 1
        assert "socket.godeebxp.com" in sample_fingerprint.websocket_urls[0]

    def test_frozen(self, sample_fingerprint):
        with pytest.raises(ValidationError):
            sample_fingerprint.framework = "phaser"

    def test_json_roundtrip(self, sample_fingerprint):
        data = sample_fingerprint.model_dump_json()
        restored = GameFingerprint.model_validate_json(data)
        assert restored.framework == sample_fingerprint.framework


class TestGameConfig:
    def test_create(self, sample_game_config):
        assert sample_game_config.name == "storm-of-seth"
        assert sample_game_config.game_type == GameType.CASCADE
        assert sample_game_config.rtp == 96.89

    def test_symbols(self, sample_game_config):
        assert len(sample_game_config.symbols) == 4

    def test_grid(self, sample_game_config):
        assert sample_game_config.grid.cols == 6
        assert sample_game_config.grid.rows == 5

    def test_frozen(self, sample_game_config):
        with pytest.raises(ValidationError):
            sample_game_config.name = "changed"

    def test_json_roundtrip(self, sample_game_config):
        data = sample_game_config.model_dump_json()
        restored = GameConfig.model_validate_json(data)
        assert restored.name == sample_game_config.name
        assert len(restored.symbols) == len(sample_game_config.symbols)


class TestGameModel:
    def test_create(self, sample_game_config, sample_fingerprint):
        model = GameModel(
            config=sample_game_config,
            fingerprint=sample_fingerprint,
            confidence_map={"paytable": ConfidenceLevel.HIGH},
        )
        assert model.config.name == "storm-of-seth"
        assert model.fingerprint.provider == "atg"

    def test_minimal(self, sample_game_config):
        model = GameModel(config=sample_game_config)
        assert model.fingerprint is None
        assert model.assets is None

    def test_frozen(self, sample_game_config):
        model = GameModel(config=sample_game_config)
        with pytest.raises(ValidationError):
            model.config = sample_game_config
