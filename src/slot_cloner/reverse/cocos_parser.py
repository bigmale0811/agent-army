"""Cocos Creator 場景解析器 — 從 Cocos 引擎的序列化 JSON 中提取遊戲資源映射

Cocos Creator 的 JSON 場景檔案使用 UUID 引用系統：
- 每個物件有 __type__ 和 _name 屬性
- 參考其他物件時使用 __uuid__ 或 @XXXX 格式
- 常見類型：cc.SpriteFrame, cc.Texture2D, cc.Node, cc.Sprite

此解析器的目標：
1. 從場景 JSON 中提取 SpriteFrame 定義
2. 建立 symbol name → image asset 的映射關係
3. 辨識可能的遊戲符號（基於命名慣例和位置）
"""
from __future__ import annotations
import logging
import re
from typing import Any
from slot_cloner.models.symbol import SymbolConfig
from slot_cloner.models.enums import SymbolType

logger = logging.getLogger(__name__)

# 常見的老虎機符號名稱模式（支援多語系和代號）
SYMBOL_NAME_PATTERNS = [
    # 直接命名
    re.compile(r"symbol[_\-]?(\d+)", re.IGNORECASE),
    re.compile(r"sym[_\-]?(\d+)", re.IGNORECASE),
    re.compile(r"icon[_\-]?(\d+)", re.IGNORECASE),
    # 高價值符號（埃及神話主題）
    re.compile(r"(horus|anubis|seth|ra|osiris|isis|eye|scarab|ankh)", re.IGNORECASE),
    # 通用 slot 符號
    re.compile(r"(wild|scatter|bonus|free.?spin|multiplier)", re.IGNORECASE),
    # 撲克牌符號
    re.compile(r"\b(A|K|Q|J|10|9)\b"),
    # 圖片資源名稱模式
    re.compile(r"slot[_\-]?img[_\-]?(\d+)", re.IGNORECASE),
    re.compile(r"reel[_\-]?symbol[_\-]?(\d+)", re.IGNORECASE),
]

# Cocos Creator 常見的序列化類型
COCOS_SPRITE_TYPES = {
    "cc.SpriteFrame", "cc.Sprite", "cc.SpriteComponent",
    "cc.Texture2D", "cc.ImageAsset",
}
COCOS_NODE_TYPE = "cc.Node"


class CocosCreatorParser:
    """Cocos Creator 場景 JSON 解析器

    從 Cocos Creator 的序列化格式中提取遊戲符號資訊。
    """

    def extract_symbols_from_configs(
        self,
        raw_configs: dict[str, object],
    ) -> list[SymbolConfig]:
        """從所有已擷取的 JSON 設定檔中搜尋符號定義

        Args:
            raw_configs: {filename: json_data} 的字典

        Returns:
            找到的 SymbolConfig 列表
        """
        all_symbols: list[SymbolConfig] = []
        sprite_frames: dict[str, str] = {}  # uuid → name
        texture_map: dict[str, str] = {}    # uuid → filename

        for filename, config in raw_configs.items():
            if not isinstance(config, (dict, list)):
                continue

            # 解析 Cocos Creator 場景檔案
            cocos_items = self._flatten_cocos_data(config)

            # 第一輪：建立 UUID → name 映射
            for item in cocos_items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("__type__", "")

                # SpriteFrame 定義
                if item_type in COCOS_SPRITE_TYPES:
                    name = item.get("_name", item.get("name", ""))
                    uuid = item.get("_uuid", item.get("__uuid__", ""))
                    if name:
                        sprite_frames[uuid] = name
                        if uuid:
                            texture_map[uuid] = name

                # Node 名稱（可能包含符號資訊）
                if item_type == COCOS_NODE_TYPE:
                    name = item.get("_name", "")
                    if name and self._is_symbol_name(name):
                        symbol = self._create_symbol_from_node(item, name, filename)
                        if symbol:
                            all_symbols.append(symbol)

            # 第二輪：從 sprite frame 名稱中提取符號
            for uuid, name in sprite_frames.items():
                if self._is_symbol_name(name):
                    symbol = self._create_symbol_from_sprite(name, filename)
                    if symbol and not any(s.id == symbol.id for s in all_symbols):
                        all_symbols.append(symbol)

        # 第三輪：暴力搜尋 — 從所有 JSON 的字串值中找符號關鍵字
        if not all_symbols:
            all_symbols = self._brute_force_search(raw_configs)

        logger.info(
            "Cocos Creator 解析: %d 個 sprite frames, %d 個符號",
            len(sprite_frames), len(all_symbols),
        )
        return all_symbols

    def extract_asset_map(
        self,
        raw_configs: dict[str, object],
    ) -> dict[str, str]:
        """提取 Cocos Creator 的 asset UUID → 檔案路徑映射

        用於 Cocos 的 config.json（asset bundle 設定）
        """
        asset_map: dict[str, str] = {}

        for filename, config in raw_configs.items():
            if not isinstance(config, dict):
                continue

            # Cocos Creator config.json 格式：
            # {"paths": {"uuid1": ["path", "type"], ...}}
            paths = config.get("paths")
            if isinstance(paths, dict):
                for uuid_key, path_info in paths.items():
                    if isinstance(path_info, list) and len(path_info) >= 1:
                        asset_map[uuid_key] = str(path_info[0])
                    elif isinstance(path_info, str):
                        asset_map[uuid_key] = path_info

            # 替代格式：{"versions": {"import": [...], "native": [...]}}
            versions = config.get("versions")
            if isinstance(versions, dict):
                for category, items in versions.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                uuid = item.get("uuid", "")
                                path = item.get("path", "")
                                if uuid and path:
                                    asset_map[uuid] = path

        return asset_map

    def _flatten_cocos_data(self, data: Any) -> list[dict]:
        """將 Cocos Creator 場景資料攤平為物件列表

        Cocos 場景 JSON 通常是一個大 list，每個元素是一個序列化物件。
        也可能是巢狀 dict 結構。
        """
        items: list[dict] = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    items.append(item)
                    # 遞迴搜尋巢狀結構（限制深度）
                    items.extend(self._extract_nested_objects(item, depth=0))
        elif isinstance(data, dict):
            items.append(data)
            items.extend(self._extract_nested_objects(data, depth=0))

        return items

    def _extract_nested_objects(
        self, obj: dict, depth: int, max_depth: int = 10,
    ) -> list[dict]:
        """遞迴提取巢狀字典中的物件"""
        if depth > max_depth:
            return []
        results: list[dict] = []
        for value in obj.values():
            if isinstance(value, dict) and "__type__" in value:
                results.append(value)
                results.extend(self._extract_nested_objects(value, depth + 1, max_depth))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "__type__" in item:
                        results.append(item)
                        results.extend(self._extract_nested_objects(item, depth + 1, max_depth))
        return results

    @staticmethod
    def _is_symbol_name(name: str) -> bool:
        """判斷名稱是否像遊戲符號"""
        return any(pattern.search(name) for pattern in SYMBOL_NAME_PATTERNS)

    @staticmethod
    def _detect_symbol_type(name: str) -> SymbolType:
        """從名稱推斷符號類型"""
        name_lower = name.lower()
        if "wild" in name_lower:
            return SymbolType.WILD
        if "scatter" in name_lower:
            return SymbolType.SCATTER
        if "bonus" in name_lower:
            return SymbolType.BONUS
        if "multiplier" in name_lower or "mult" in name_lower:
            return SymbolType.MULTIPLIER
        return SymbolType.REGULAR

    def _create_symbol_from_node(
        self, node: dict, name: str, source_file: str,
    ) -> SymbolConfig | None:
        """從 Cocos Node 物件建構 SymbolConfig"""
        # 嘗試從 node 的子元件中找到關聯的 sprite
        components = node.get("_components", [])
        image_name = ""
        for comp in components if isinstance(components, list) else []:
            if isinstance(comp, dict):
                sprite_frame = comp.get("_spriteFrame", comp.get("spriteFrame", ""))
                if sprite_frame:
                    # UUID 引用格式
                    image_name = str(sprite_frame).replace("@", "")
                    break

        return SymbolConfig(
            id=name.lower().replace(" ", "_"),
            name=name,
            symbol_type=self._detect_symbol_type(name),
            image_name=image_name or f"{name}.png",
        )

    def _create_symbol_from_sprite(
        self, name: str, source_file: str,
    ) -> SymbolConfig | None:
        """從 SpriteFrame 名稱建構 SymbolConfig"""
        return SymbolConfig(
            id=name.lower().replace(" ", "_").replace("-", "_"),
            name=name,
            symbol_type=self._detect_symbol_type(name),
            image_name=f"{name}.png",
        )

    def _brute_force_search(
        self, raw_configs: dict[str, object],
    ) -> list[SymbolConfig]:
        """暴力搜尋：從所有 JSON 值中找符號關鍵字

        最低可信度，但可在其他方法都失敗時提供線索。
        """
        found_names: set[str] = set()
        symbols: list[SymbolConfig] = []

        for filename, config in raw_configs.items():
            text = str(config)
            for pattern in SYMBOL_NAME_PATTERNS:
                for match in pattern.finditer(text):
                    name = match.group(0)
                    if len(name) >= 2 and name not in found_names:
                        found_names.add(name)

        # 從找到的名稱建立符號（最多 30 個，避免雜訊）
        for name in sorted(found_names)[:30]:
            symbols.append(SymbolConfig(
                id=name.lower().replace(" ", "_").replace("-", "_"),
                name=name,
                symbol_type=self._detect_symbol_type(name),
                image_name=f"{name}.png",
            ))

        if symbols:
            logger.info("暴力搜尋找到 %d 個疑似符號名稱", len(symbols))

        return symbols
