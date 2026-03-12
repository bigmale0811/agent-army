"""Game Builder 測試"""
import json
from pathlib import Path
from slot_cloner.builder.engine import GameBuilder
from slot_cloner.models.game import GameModel, GameConfig
from slot_cloner.models.enums import GameType


def _make_model() -> GameModel:
    return GameModel(config=GameConfig(name="test", game_type=GameType.CASCADE))


class TestGameBuilder:
    def test_build_creates_game_dir(self, tmp_path):
        builder = GameBuilder(skip_npm=True)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        output_dir = tmp_path / "output"

        game_dir = builder.build(_make_model(), assets_dir, output_dir)
        assert game_dir.exists()
        assert (game_dir / "index.html").exists()

    def test_build_creates_config(self, tmp_path):
        builder = GameBuilder(skip_npm=True)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        output_dir = tmp_path / "output"

        game_dir = builder.build(_make_model(), assets_dir, output_dir)
        config_path = game_dir / "game-config.json"
        assert config_path.exists()

        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["game"]["name"] == "test"

    def test_build_copies_assets(self, tmp_path):
        builder = GameBuilder(skip_npm=True)
        assets_dir = tmp_path / "assets" / "images"
        assets_dir.mkdir(parents=True)
        (assets_dir / "symbol.png").write_bytes(b"fake png")

        output_dir = tmp_path / "output"
        game_dir = builder.build(_make_model(), tmp_path / "assets", output_dir)

        copied = game_dir / "public" / "assets" / "images" / "symbol.png"
        assert copied.exists()

    def test_html_content(self, tmp_path):
        builder = GameBuilder(skip_npm=True)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        output_dir = tmp_path / "output"

        game_dir = builder.build(_make_model(), assets_dir, output_dir)
        html = (game_dir / "index.html").read_text(encoding="utf-8")
        assert "Slot Clone" in html
        # 完整模板使用 module script 載入
        assert "game-container" in html

    def test_template_has_package_json(self, tmp_path):
        """驗證完整 PixiJS 模板已複製"""
        builder = GameBuilder(skip_npm=True)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        output_dir = tmp_path / "output"

        game_dir = builder.build(_make_model(), assets_dir, output_dir)
        assert (game_dir / "package.json").exists()
        assert (game_dir / "src" / "main.ts").exists()
        assert (game_dir / "src" / "Game.ts").exists()
        assert (game_dir / "src" / "math" / "PaytableEngine.ts").exists()
        assert (game_dir / "src" / "slot" / "CascadeGrid.ts").exists()
