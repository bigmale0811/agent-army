"""Config Generator — 從 GameModel 產出 PixiJS 引擎用的 game-config.json"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from slot_cloner.models.game import GameModel

logger = logging.getLogger(__name__)


class ConfigGenerator:
    """遊戲設定產生器

    將 Python 端的 GameModel 轉換為 TypeScript PixiJS 引擎用的 game-config.json。
    """

    def generate(self, game_model: GameModel, output_path: Path) -> Path:
        """產出 game-config.json

        Args:
            game_model: 逆向分析產出的遊戲模型
            output_path: JSON 檔案輸出路徑

        Returns:
            產出的 JSON 檔案路徑
        """
        config = game_model.config
        game_config = {
            "game": {
                "name": config.name,
                "displayName": config.display_name or config.name,
                "type": config.game_type.value,
                "grid": {
                    "cols": config.grid.cols,
                    "rows": config.grid.rows,
                },
                "rtp": config.rtp,
                "maxMultiplier": config.max_multiplier,
                "minBet": config.min_bet,
                "maxBet": config.max_bet,
            },
            "symbols": [
                {
                    "id": sym.id,
                    "name": sym.name,
                    "type": sym.symbol_type.value,
                    "image": sym.image_name or f"{sym.id}.png",
                    "payouts": {str(k): v for k, v in sym.payouts.items()},
                }
                for sym in config.symbols
            ],
            "paytable": {
                "minClusterSize": config.paytable.min_cluster_size,
                "entries": [
                    {
                        "symbolId": entry.symbol_id,
                        "minCount": entry.min_count,
                        "multiplier": entry.payout_multiplier,
                    }
                    for entry in config.paytable.entries
                ],
            },
            "features": {
                "wild": {
                    "enabled": config.features.wild.enabled,
                    "symbolId": config.features.wild.symbol_id,
                    "substitutesAll": config.features.wild.substitutes_all,
                    "exceptSymbols": list(config.features.wild.except_symbols),
                },
                "scatter": {
                    "enabled": config.features.scatter.enabled,
                    "symbolId": config.features.scatter.symbol_id,
                    "triggerCount": config.features.scatter.trigger_count,
                    "freeSpinsAwarded": config.features.scatter.free_spins_awarded,
                },
                "cascade": {
                    "enabled": config.features.cascade.enabled,
                    "minClusterSize": config.features.cascade.min_cluster_size,
                    "fillFromTop": config.features.cascade.fill_from_top,
                },
                "multiplier": {
                    "enabled": config.features.multiplier.enabled,
                    "values": list(config.features.multiplier.values),
                    "accumulateInCascade": config.features.multiplier.accumulate_in_cascade,
                },
                "freeSpin": {
                    "enabled": config.features.free_spin.enabled,
                    "baseSpins": config.features.free_spin.base_spins,
                    "retriggerEnabled": config.features.free_spin.retrigger_enabled,
                    "retriggerSpins": config.features.free_spin.retrigger_spins,
                },
            },
            "assets": {
                "basePath": "./assets/",
                "imagesPath": "./assets/images/",
                "audioPath": "./assets/audio/",
                "spritesPath": "./assets/sprites/",
            },
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(game_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("game-config.json 已產出: %s", output_path)
        return output_path
