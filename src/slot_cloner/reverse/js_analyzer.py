"""JS 靜態分析器 — 從混淆的 JS 中提取遊戲配置（Layer 3）"""
from __future__ import annotations
import re
import logging
import jsbeautifier

logger = logging.getLogger(__name__)


class JSAnalyzer:
    """JavaScript 靜態分析器

    Layer 3 逆向策略：下載 JS bundle，美化後用正則搜尋關鍵配置。
    注意：ATG 的 JS 可能嚴重混淆，此分析器是「盡力而為」。
    """

    def analyze(self, js_code: str) -> dict:
        """分析 JS 程式碼，提取遊戲相關配置

        Args:
            js_code: 原始或混淆的 JavaScript 程式碼

        Returns:
            提取到的配置資訊
        """
        # 先美化
        beautified = self._beautify(js_code)

        result = {
            "paytable_candidates": self._find_paytable(beautified),
            "symbol_candidates": self._find_symbols(beautified),
            "grid_size": self._find_grid_size(beautified),
            "rtp_candidates": self._find_rtp(beautified),
            "framework_hints": self._find_framework(beautified),
        }

        non_empty = sum(1 for v in result.values() if v)
        logger.info("JS 分析完成：找到 %d 項有效資訊", non_empty)
        return result

    @staticmethod
    def _beautify(js_code: str) -> str:
        """美化 JS 程式碼"""
        opts = jsbeautifier.default_options()
        opts.indent_size = 2
        return jsbeautifier.beautify(js_code, opts)

    @staticmethod
    def _find_paytable(code: str) -> list[dict]:
        """搜尋賠率表相關的物件字面值"""
        results = []
        # 搜尋包含數字陣列的模式（像是 [8, 1.0, 10, 2.5, 12, 10.0]）
        pattern = r'(?:paytable|payout|pay_table|payTable)\s*[:=]\s*(\{[^}]{10,}\}|\[[^\]]{10,}\])'
        for match in re.finditer(pattern, code, re.IGNORECASE):
            results.append({"raw": match.group(0)[:500], "position": match.start()})
        return results

    @staticmethod
    def _find_symbols(code: str) -> list[str]:
        """搜尋符號定義"""
        symbols = set()
        # 搜尋像 "wild", "scatter", "bonus" 等常見符號名稱
        pattern = r'["\'](\w*(?:wild|scatter|bonus|multiplier|free.?spin)\w*)["\']'
        for match in re.finditer(pattern, code, re.IGNORECASE):
            symbols.add(match.group(1))
        return sorted(symbols)

    @staticmethod
    def _find_grid_size(code: str) -> dict | None:
        """搜尋棋盤大小"""
        # 搜尋 rows/cols 或 reels/rows 的定義
        patterns = [
            r'(?:cols|columns|reels)\s*[:=]\s*(\d+)',
            r'(?:rows)\s*[:=]\s*(\d+)',
        ]
        cols = rows = None
        for i, pat in enumerate(patterns):
            match = re.search(pat, code, re.IGNORECASE)
            if match:
                if i == 0:
                    cols = int(match.group(1))
                else:
                    rows = int(match.group(1))
        if cols or rows:
            return {"cols": cols, "rows": rows}
        return None

    @staticmethod
    def _find_rtp(code: str) -> list[float]:
        """搜尋 RTP 值"""
        results = []
        pattern = r'(?:rtp|return.?to.?player)\s*[:=]\s*([\d.]+)'
        for match in re.finditer(pattern, code, re.IGNORECASE):
            try:
                val = float(match.group(1))
                if 75 <= val <= 99:  # RTP 合理範圍
                    results.append(val)
            except ValueError:
                pass
        return results

    @staticmethod
    def _find_framework(code: str) -> list[str]:
        """偵測使用的遊戲框架"""
        frameworks = []
        if "PIXI" in code or "pixi" in code:
            frameworks.append("pixi")
        if "Phaser" in code:
            frameworks.append("phaser")
        if "cc.director" in code or "cc.game" in code:
            frameworks.append("cocos")
        return frameworks
