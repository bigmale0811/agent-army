"""分析報告建構器 — 產出 Markdown 報告 + 結構化 JSON"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from slot_cloner.models.game import GameModel, GameConfig
from slot_cloner.models.enums import ConfidenceLevel

logger = logging.getLogger(__name__)


class ReportBuilder:
    """分析報告建構器

    從 GameModel 產出：
    1. report.md — 完整 Markdown 分析報告
    2. paytable.json — 結構化賠率表
    3. symbols.json — 符號定義
    4. rules.json — 遊戲規則
    """

    def build(self, game_model: GameModel, output_dir: Path) -> Path:
        """建構完整分析報告

        Args:
            game_model: 逆向分析產出的遊戲模型
            output_dir: 輸出目錄（analysis/）

        Returns:
            report.md 的路徑
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        config = game_model.config

        # 產出 JSON 檔案
        self._write_json(output_dir / "paytable.json", self._paytable_to_dict(config))
        self._write_json(output_dir / "symbols.json", self._symbols_to_dict(config))
        self._write_json(output_dir / "rules.json", self._rules_to_dict(config))

        # 產出 Markdown 報告
        report_path = output_dir / "report.md"
        report_content = self._build_markdown(game_model)
        report_path.write_text(report_content, encoding="utf-8")

        logger.info("報告已產出: %s", report_path)
        return report_path

    def _build_markdown(self, model: GameModel) -> str:
        """建構 Markdown 報告"""
        config = model.config
        fp = model.fingerprint
        lines = []

        # 標題
        lines.append(f"# {config.display_name or config.name} — 遊戲分析報告\n")
        lines.append(f"> 自動產出 by Slot Cloner\n")

        # 概覽
        lines.append("## 1. 遊戲概覽\n")
        lines.append(f"| 項目 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 遊戲名稱 | {config.display_name or config.name} |")
        lines.append(f"| 遊戲類型 | {config.game_type.value} |")
        lines.append(f"| 棋盤大小 | {config.grid.cols} x {config.grid.rows} |")
        if config.rtp > 0:
            lines.append(f"| RTP | {config.rtp}% |")
        if config.max_multiplier > 0:
            lines.append(f"| 最大倍率 | x{config.max_multiplier:,.0f} |")
        if fp:
            lines.append(f"| 遊戲框架 | {fp.framework} |")
            lines.append(f"| 供應商 | {fp.provider} |")
        lines.append("")

        # 符號清單
        lines.append("## 2. 符號清單\n")
        if config.symbols:
            lines.append("| ID | 名稱 | 類型 | 賠率 |")
            lines.append("|-----|------|------|------|")
            for sym in config.symbols:
                payouts_str = ", ".join(f"{k}個={v}x" for k, v in sorted(sym.payouts.items()))
                lines.append(f"| {sym.id} | {sym.name} | {sym.symbol_type.value} | {payouts_str or '-'} |")
        else:
            lines.append("*無法提取符號資訊*\n")
        lines.append("")

        # 賠率表
        lines.append("## 3. 賠率表\n")
        if config.paytable.entries:
            lines.append(f"最小消除數: {config.paytable.min_cluster_size}\n")
            lines.append("| 符號 | 最少數量 | 倍率 | 可信度 |")
            lines.append("|------|---------|------|--------|")
            for entry in config.paytable.entries:
                lines.append(
                    f"| {entry.symbol_id} | {entry.min_count} | {entry.payout_multiplier}x | {entry.confidence.value} |"
                )
        else:
            lines.append("*無法提取賠率表*\n")
        lines.append("")

        # 特殊機制
        lines.append("## 4. 特殊機制\n")
        features = config.features
        lines.append(f"- **Wild**: {'啟用' if features.wild.enabled else '停用'}")
        if features.wild.enabled:
            lines.append(f"  - 替代所有符號: {'是' if features.wild.substitutes_all else '否'}")
            lines.append(f"  - 例外: {', '.join(features.wild.except_symbols)}")
        lines.append(f"- **Scatter**: {'啟用' if features.scatter.enabled else '停用'}")
        if features.scatter.enabled:
            lines.append(f"  - 觸發數量: {features.scatter.trigger_count}")
            lines.append(f"  - Free Spin 數: {features.scatter.free_spins_awarded}")
        lines.append(f"- **Cascade**: {'啟用' if features.cascade.enabled else '停用'}")
        if features.cascade.enabled:
            lines.append(f"  - 最小消除: {features.cascade.min_cluster_size}")
        lines.append(f"- **乘數**: {'啟用' if features.multiplier.enabled else '停用'}")
        if features.multiplier.enabled:
            lines.append(f"  - 可能值: {', '.join(str(v) + 'x' for v in features.multiplier.values)}")
            lines.append(f"  - Cascade 累積: {'是' if features.multiplier.accumulate_in_cascade else '否'}")
        lines.append("")

        # 可信度摘要
        lines.append("## 5. 分析可信度\n")
        if model.confidence_map:
            lines.append("| 項目 | 可信度 |")
            lines.append("|------|--------|")
            for key, level in model.confidence_map.items():
                emoji = {"high": "高", "medium": "中", "low": "低"}.get(
                    level.value if isinstance(level, ConfidenceLevel) else level, "未知"
                )
                lines.append(f"| {key} | {emoji} ({level.value if isinstance(level, ConfidenceLevel) else level}) |")
        lines.append("")

        # 技術架構
        if fp:
            lines.append("## 6. 技術架構\n")
            lines.append(f"- URL: `{fp.url}`")
            lines.append(f"- 框架: {fp.framework}")
            lines.append(f"- Canvas: {'有' if fp.canvas_detected else '無'}")
            lines.append(f"- WebGL: {'有' if fp.webgl_detected else '無'}")
            if fp.websocket_urls:
                lines.append(f"- WebSocket: {', '.join(fp.websocket_urls)}")
            lines.append("")

        # 資源清單
        if model.assets:
            lines.append("## 7. 資源清單\n")
            lines.append(f"| 類型 | 數量 |")
            lines.append(f"|------|------|")
            lines.append(f"| 圖片 | {len(model.assets.images)} |")
            lines.append(f"| 音效 | {len(model.assets.audio)} |")
            lines.append(f"| Sprite Sheet | {len(model.assets.sprites)} |")
            lines.append(f"| 設定檔 | {len(model.assets.raw_configs)} |")
            lines.append("")

            if model.assets.images:
                lines.append("### 圖片資源\n")
                for img in model.assets.images[:20]:  # 最多顯示 20 個
                    lines.append(f"- `{img.name}` ({img.mime_type})")
                if len(model.assets.images) > 20:
                    lines.append(f"- ... 及其他 {len(model.assets.images) - 20} 個")
                lines.append("")

            if model.assets.audio:
                lines.append("### 音效資源\n")
                for aud in model.assets.audio:
                    lines.append(f"- `{aud.name}` ({aud.mime_type})")
                lines.append("")

        # 資料來源與可靠性
        lines.append("## 8. 分析方法論\n")
        lines.append("本報告透過以下自動化逆向工程層次產出：\n")
        lines.append("| 層次 | 方法 | 可靠性 |")
        lines.append("|------|------|--------|")
        lines.append("| Layer 1 | 設定檔直接解析 | ⭐⭐⭐ 最高 |")
        lines.append("| Layer 2 | WebSocket 訊息攔截 | ⭐⭐⭐ 高 |")
        lines.append("| Layer 3 | JavaScript 靜態分析 | ⭐⭐ 中 |")
        lines.append("| Layer 4 | 視覺 OCR 辨識 | ⭐ 低 |")
        lines.append("")
        lines.append("> 各項數據旁的可信度標記來自分析引擎的自動評估。")
        lines.append("> 標記為「低」可信度的項目建議人工覆核。\n")

        return "\n".join(lines)

    @staticmethod
    def _paytable_to_dict(config: GameConfig) -> dict:
        """賠率表轉為 dict"""
        return {
            "min_cluster_size": config.paytable.min_cluster_size,
            "entries": [
                {
                    "symbol_id": e.symbol_id,
                    "min_count": e.min_count,
                    "payout_multiplier": e.payout_multiplier,
                    "confidence": e.confidence.value,
                }
                for e in config.paytable.entries
            ],
        }

    @staticmethod
    def _symbols_to_dict(config: GameConfig) -> list:
        """符號轉為 dict list"""
        return [
            {
                "id": s.id,
                "name": s.name,
                "type": s.symbol_type.value,
                "image": s.image_name,
                "payouts": s.payouts,
            }
            for s in config.symbols
        ]

    @staticmethod
    def _rules_to_dict(config: GameConfig) -> dict:
        """遊戲規則轉為 dict"""
        return {
            "game_type": config.game_type.value,
            "grid": {"cols": config.grid.cols, "rows": config.grid.rows},
            "features": {
                "wild": {"enabled": config.features.wild.enabled},
                "scatter": {
                    "enabled": config.features.scatter.enabled,
                    "trigger_count": config.features.scatter.trigger_count,
                },
                "cascade": {
                    "enabled": config.features.cascade.enabled,
                    "min_cluster_size": config.features.cascade.min_cluster_size,
                },
                "multiplier": {
                    "enabled": config.features.multiplier.enabled,
                    "values": list(config.features.multiplier.values),
                },
                "free_spin": {
                    "enabled": config.features.free_spin.enabled,
                    "base_spins": config.features.free_spin.base_spins,
                },
            },
            "rtp": config.rtp,
            "max_multiplier": config.max_multiplier,
        }

    @staticmethod
    def _write_json(path: Path, data: object) -> None:
        """寫入 JSON 檔案"""
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
