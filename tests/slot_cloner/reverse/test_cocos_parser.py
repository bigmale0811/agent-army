"""Cocos Creator 場景解析器測試"""
import pytest
from slot_cloner.reverse.cocos_parser import CocosCreatorParser
from slot_cloner.models.enums import SymbolType


class TestCocosCreatorParser:
    """Cocos Creator JSON 解析基礎功能"""

    def setup_method(self):
        self.parser = CocosCreatorParser()

    def test_extract_symbols_from_sprite_frames(self):
        """從 SpriteFrame 定義提取符號"""
        configs = {
            "scene.json": [
                {"__type__": "cc.SpriteFrame", "_name": "symbol_01", "_uuid": "abc123"},
                {"__type__": "cc.SpriteFrame", "_name": "symbol_02", "_uuid": "def456"},
                {"__type__": "cc.SpriteFrame", "_name": "background", "_uuid": "ghi789"},
            ]
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        symbol_names = {s.name for s in symbols}
        assert "symbol_01" in symbol_names
        assert "symbol_02" in symbol_names
        # background 不是符號名稱
        assert "background" not in symbol_names

    def test_extract_symbols_from_nodes(self):
        """從 Node 名稱提取符號"""
        configs = {
            "scene.json": [
                {
                    "__type__": "cc.Node",
                    "_name": "wild",
                    "_components": [
                        {"_spriteFrame": "@frame001"}
                    ],
                },
                {
                    "__type__": "cc.Node",
                    "_name": "scatter",
                    "_components": [],
                },
            ]
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        assert len(symbols) >= 2
        names = {s.name for s in symbols}
        assert "wild" in names
        assert "scatter" in names

    def test_detect_wild_type(self):
        """正確偵測 Wild 符號類型"""
        configs = {
            "scene.json": [
                {"__type__": "cc.SpriteFrame", "_name": "wild_symbol", "_uuid": "w1"},
            ]
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        wild = next((s for s in symbols if "wild" in s.name.lower()), None)
        assert wild is not None
        assert wild.symbol_type == SymbolType.WILD

    def test_detect_scatter_type(self):
        """正確偵測 Scatter 符號類型"""
        configs = {
            "scene.json": [
                {"__type__": "cc.SpriteFrame", "_name": "scatter_bonus", "_uuid": "s1"},
            ]
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        scatter = next((s for s in symbols if "scatter" in s.name.lower()), None)
        assert scatter is not None
        assert scatter.symbol_type == SymbolType.SCATTER

    def test_empty_configs(self):
        """空設定檔回傳空列表"""
        symbols = self.parser.extract_symbols_from_configs({})
        assert symbols == []

    def test_non_cocos_json(self):
        """非 Cocos Creator 格式的 JSON 正常處理（不崩潰）"""
        configs = {
            "random.json": {"key": "value", "nested": {"a": 1}},
            "list.json": [1, 2, 3],
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        assert isinstance(symbols, list)


class TestBruteForceSearch:
    """暴力搜尋模式測試"""

    def setup_method(self):
        self.parser = CocosCreatorParser()

    def test_brute_force_finds_symbol_patterns(self):
        """暴力搜尋能從字串中找到符號模式"""
        configs = {
            "data.json": {
                "assets": ["symbol_1.png", "symbol_2.png", "symbol_3.png"],
                "other": "background.png",
            }
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        assert len(symbols) >= 3

    def test_brute_force_finds_card_symbols(self):
        """暴力搜尋能找到撲克牌符號"""
        configs = {
            "game.json": {
                "reels": "A K Q J 10 9 wild scatter",
            }
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        names = {s.name for s in symbols}
        assert "wild" in names or "scatter" in names

    def test_brute_force_limit(self):
        """暴力搜尋結果不超過 30 個"""
        # 製造大量符號名稱
        configs = {
            "huge.json": {
                f"symbol_{i}": f"value_{i}" for i in range(100)
            }
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        assert len(symbols) <= 30


class TestAssetMap:
    """Cocos Creator asset 映射功能測試"""

    def setup_method(self):
        self.parser = CocosCreatorParser()

    def test_extract_paths_format(self):
        """從 Cocos config.json 的 paths 格式提取映射"""
        configs = {
            "config.json": {
                "paths": {
                    "abc123": ["textures/symbol_01", 1],
                    "def456": ["textures/symbol_02", 1],
                    "ghi789": ["audio/bgm", 2],
                }
            }
        }

        asset_map = self.parser.extract_asset_map(configs)
        assert asset_map["abc123"] == "textures/symbol_01"
        assert asset_map["def456"] == "textures/symbol_02"
        assert asset_map["ghi789"] == "audio/bgm"

    def test_empty_config(self):
        """空設定檔回傳空映射"""
        asset_map = self.parser.extract_asset_map({})
        assert asset_map == {}

    def test_non_config_format(self):
        """非 config 格式的 JSON 回傳空映射"""
        configs = {"random.json": {"key": "value"}}
        asset_map = self.parser.extract_asset_map(configs)
        assert asset_map == {}


class TestNestedCocosStructures:
    """Cocos Creator 巢狀結構解析"""

    def setup_method(self):
        self.parser = CocosCreatorParser()

    def test_nested_sprite_frames(self):
        """巢狀結構中的 SpriteFrame 也能被提取"""
        configs = {
            "scene.json": {
                "root": {
                    "__type__": "cc.Node",
                    "_name": "root",
                    "children": [
                        {
                            "__type__": "cc.SpriteFrame",
                            "_name": "icon_01",
                            "_uuid": "nested_uuid",
                        }
                    ],
                }
            }
        }

        symbols = self.parser.extract_symbols_from_configs(configs)
        names = {s.name for s in symbols}
        assert "icon_01" in names

    def test_deeply_nested_no_crash(self):
        """深度巢狀不會造成 stack overflow"""
        # 建造 15 層巢狀結構
        data: dict = {"__type__": "cc.Node", "_name": "level_0"}
        current = data
        for i in range(1, 15):
            child = {"__type__": "cc.Node", "_name": f"level_{i}"}
            current["child"] = child
            current = child
        # 最深層放一個符號
        current["sprite"] = {
            "__type__": "cc.SpriteFrame",
            "_name": "symbol_deep",
            "_uuid": "deep_uuid",
        }

        configs = {"deep.json": data}
        # 不應該崩潰
        symbols = self.parser.extract_symbols_from_configs(configs)
        assert isinstance(symbols, list)
