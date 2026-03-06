"""
Stock Analyzer 主邏輯

封裝 TradingAgentsGraph，提供簡潔的分析介面。
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import StockAnalyzerConfig, load_config
from .utils.ticker_resolver import AssetType, ResolvedTicker, resolve_ticker


@dataclass(frozen=True)
class AnalysisReport:
    """分析報告（不可變）"""

    ticker: str
    display_name: str
    asset_type: AssetType
    date: str
    market_report: str
    news_report: str
    fundamentals_report: str
    sentiment_report: str
    investment_plan: str
    final_decision: str
    raw_state: dict


def clean_thinking_tags(text: Optional[str]) -> Optional[str]:
    """
    清除 QWen3 等模型輸出的思考鏈雜訊。

    部分本地 LLM（如 QWen3）會在回應中夾帶 <think>...</think> 區塊，
    這些屬於模型的內部推理過程，不應出現在最終報告中。

    假設輸入為典型 LLM 輸出長度，非對抗性輸入。

    Args:
        text: 原始文字（可能包含 think 標籤，或 None）

    Returns:
        清理後的文字，若輸入為 None 則回傳 None
    """
    if text is None:
        return None
    if not text:
        return text
    # 第一步：移除完整的 <think>...</think> 區塊（含多行內容）
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # 第二步：移除所有殘留的未閉合 <think> 或 </think> 標籤（合併為單一 regex）
    cleaned = re.sub(r"</?think>", "", cleaned)
    # 清除開頭多餘空行與 Windows \r\n 換行殘留
    cleaned = cleaned.lstrip("\r\n")
    return cleaned


class StockAnalyzer:
    """
    綜合投資分析工具

    基於 TradingAgents 多代理人框架，結合技術分析、新聞情緒、
    基本面分析，產出綜合投資建議。

    使用範例：
        analyzer = StockAnalyzer()
        report = analyzer.analyze("2330.TW")
        print(report.final_decision)
    """

    def __init__(
        self,
        config: Optional[StockAnalyzerConfig] = None,
    ):
        """
        初始化分析器

        Args:
            config: 配置物件，None 則從環境變數載入
        """
        self.config = config or load_config()
        self._graph = None

    def _ensure_graph(self):
        """延遲初始化 TradingAgentsGraph（避免載入時就連 LLM）"""
        if self._graph is not None:
            return

        # 確保快取目錄存在
        self.config.data_cache_dir.mkdir(parents=True, exist_ok=True)
        self.config.reports_dir.mkdir(parents=True, exist_ok=True)

        # 設定 PYTHONIOENCODING 避免 Windows CP950 問題
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

        from tradingagents.graph.trading_graph import TradingAgentsGraph

        ta_config = self.config.to_trading_agents_config()
        self._graph = TradingAgentsGraph(
            debug=True,
            config=ta_config,
        )

    def analyze(
        self,
        ticker_input: str,
        date: Optional[str] = None,
    ) -> AnalysisReport:
        """
        分析單一投資標的

        Args:
            ticker_input: 股票代號（支援台股代號、中文名、加密貨幣等）
            date: 分析日期（YYYY-MM-DD），預設今天

        Returns:
            AnalysisReport: 分析結果

        Raises:
            ValueError: ticker 無法解析
            ConnectionError: Ollama 連線失敗
        """
        # 解析 ticker
        resolved = resolve_ticker(ticker_input)

        # 預設日期為今天
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # 初始化 LangGraph
        self._ensure_graph()

        # 執行分析（捕獲 LLM 連線與回傳異常）
        try:
            state, decision = self._graph.propagate(
                resolved.ticker, date
            )
        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(
                f"TradingAgents 分析失敗 ({resolved.ticker}): {e}"
            ) from e

        if not isinstance(state, dict):
            raise ValueError(
                f"TradingAgents 回傳非預期的 state 類型: {type(state)}"
            )

        # 封裝報告（修正 key 名稱 + 清除 LLM 思考鏈雜訊）
        return AnalysisReport(
            ticker=resolved.ticker,
            display_name=resolved.display_name,
            asset_type=resolved.asset_type,
            date=date,
            market_report=clean_thinking_tags(
                state.get("market_report", "")
            ),
            news_report=clean_thinking_tags(
                state.get("news_report", "")
            ),
            fundamentals_report=clean_thinking_tags(
                state.get("fundamentals_report", "")
            ),
            sentiment_report=clean_thinking_tags(
                state.get("sentiment_report", "")
            ),
            investment_plan=clean_thinking_tags(
                state.get("investment_plan", "")
            ),
            final_decision=clean_thinking_tags(decision or ""),
            raw_state=dict(state) if state else {},
        )

    def analyze_batch(
        self,
        tickers: list[str],
        date: Optional[str] = None,
    ) -> list[AnalysisReport]:
        """
        批次分析多個投資標的

        Args:
            tickers: 股票代號列表
            date: 分析日期

        Returns:
            list[AnalysisReport]: 各標的的分析結果
        """
        results = []
        for ticker in tickers:
            report = self.analyze(ticker, date)
            results.append(report)
        return results
