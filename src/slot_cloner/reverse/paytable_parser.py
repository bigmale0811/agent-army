"""賠率表解析器 — 從各種來源建構結構化賠率表"""
from __future__ import annotations
import logging
from typing import Any
from slot_cloner.models.symbol import SymbolConfig, PaytableEntry, PaytableConfig
from slot_cloner.models.enums import SymbolType, ConfidenceLevel

logger = logging.getLogger(__name__)


class PaytableParser:
    """賠率表解析器

    從 WS 訊息、JS 分析、或 OCR 結果中建構 PaytableConfig。
    """

    def parse_from_ws_config(
        self,
        ws_config: dict[str, Any],
    ) -> tuple[tuple[SymbolConfig, ...], PaytableConfig]:
        """從 WS 遊戲配置解析賠率表

        嘗試多種已知格式，回傳 (symbols, paytable)
        """
        symbols = self._extract_symbols(ws_config)
        entries = self._extract_entries(ws_config, symbols)

        paytable = PaytableConfig(
            entries=tuple(entries),
            min_cluster_size=self._detect_min_cluster(ws_config),
            confidence=ConfidenceLevel.MEDIUM,
        )

        logger.info("解析完成: %d 個符號, %d 條賠率", len(symbols), len(entries))
        return tuple(symbols), paytable

    def parse_from_raw(
        self,
        symbols_data: list[dict],
        payouts_data: list[dict] | dict,
    ) -> tuple[tuple[SymbolConfig, ...], PaytableConfig]:
        """從原始資料建構賠率表（手動提供）"""
        symbols = []
        entries = []

        for sd in symbols_data:
            sym_type = self._detect_symbol_type(sd.get("name", ""), sd.get("type", ""))
            symbol = SymbolConfig(
                id=str(sd.get("id", sd.get("name", "unknown"))),
                name=sd.get("name", "Unknown"),
                symbol_type=sym_type,
                image_name=sd.get("image", ""),
                payouts=sd.get("payouts", {}),
            )
            symbols.append(symbol)

            # 從 payouts 建構 entries
            for count, multiplier in symbol.payouts.items():
                entries.append(PaytableEntry(
                    symbol_id=symbol.id,
                    min_count=int(count),
                    payout_multiplier=float(multiplier),
                    confidence=ConfidenceLevel.HIGH,
                ))

        paytable = PaytableConfig(entries=tuple(entries))
        return tuple(symbols), paytable

    def _extract_symbols(self, config: dict) -> list[SymbolConfig]:
        """從遊戲配置提取符號"""
        symbols = []
        # 搜尋可能的符號定義位置
        for key in ("symbols", "symbolList", "symbol_list", "symbolConfig"):
            if key in config and isinstance(config[key], (list, dict)):
                raw = config[key]
                if isinstance(raw, dict):
                    raw = list(raw.values())
                for item in raw:
                    if isinstance(item, dict):
                        sym = self._parse_single_symbol(item)
                        if sym:
                            symbols.append(sym)
                break

        return symbols

    def _parse_single_symbol(self, data: dict) -> SymbolConfig | None:
        """解析單一符號"""
        sym_id = str(data.get("id", data.get("symbolId", data.get("name", ""))))
        if not sym_id:
            return None

        name = data.get("name", data.get("displayName", sym_id))
        sym_type = self._detect_symbol_type(name, data.get("type", ""))

        payouts = {}
        for key in ("payouts", "payout", "pay", "wins"):
            if key in data and isinstance(data[key], dict):
                payouts = {int(k): float(v) for k, v in data[key].items()}
                break

        return SymbolConfig(
            id=sym_id,
            name=name,
            symbol_type=sym_type,
            payouts=payouts,
        )

    def _extract_entries(self, config: dict, symbols: list[SymbolConfig]) -> list[PaytableEntry]:
        """從配置提取賠率條目"""
        entries = []
        for symbol in symbols:
            for count, multiplier in symbol.payouts.items():
                entries.append(PaytableEntry(
                    symbol_id=symbol.id,
                    min_count=count,
                    payout_multiplier=multiplier,
                    confidence=ConfidenceLevel.MEDIUM,
                ))
        return entries

    @staticmethod
    def _detect_symbol_type(name: str, type_hint: str = "") -> SymbolType:
        """偵測符號類型"""
        combined = f"{name} {type_hint}".lower()
        if "wild" in combined:
            return SymbolType.WILD
        if "scatter" in combined:
            return SymbolType.SCATTER
        if "bonus" in combined:
            return SymbolType.BONUS
        if "multiplier" in combined or "mult" in combined:
            return SymbolType.MULTIPLIER
        return SymbolType.REGULAR

    @staticmethod
    def _detect_min_cluster(config: dict) -> int:
        """偵測最小消除連接數"""
        for key in ("minCluster", "min_cluster", "minMatch", "clusterSize"):
            if key in config:
                try:
                    return int(config[key])
                except (ValueError, TypeError):
                    pass
        return 8  # 預設值（戰神賽特標準）
