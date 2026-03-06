"""
Stock Analyzer 配置管理

管理 LLM、資料源、輸出路徑等配置。
支援 .env 環境變數覆蓋預設值。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 載入 .env 環境變數
load_dotenv()

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 報告輸出目錄
REPORTS_DIR = PROJECT_ROOT / "reports"

# 資料快取目錄
DATA_CACHE_DIR = PROJECT_ROOT / "data" / "stock_analyzer" / "cache"


@dataclass(frozen=True)
class LLMConfig:
    """LLM 模型配置（不可變）"""

    provider: str = "ollama"
    deep_think_model: str = "qwen3:14b"
    quick_think_model: str = "qwen3:14b"
    backend_url: str = "http://localhost:11434/v1"
    # 備援雲端 LLM（可選）
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None


@dataclass(frozen=True)
class AnalysisConfig:
    """分析流程配置（不可變）"""

    # 辯論輪數
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    max_recur_limit: int = 100
    # 分析師開關
    enable_market_analyst: bool = True
    enable_news_analyst: bool = True
    enable_fundamentals_analyst: bool = True
    enable_social_analyst: bool = True


@dataclass(frozen=True)
class DataConfig:
    """資料源配置（不可變）"""

    # 資料供應商
    stock_vendor: str = "yfinance"
    indicators_vendor: str = "yfinance"
    fundamentals_vendor: str = "yfinance"
    news_vendor: str = "yfinance"


@dataclass(frozen=True)
class StockAnalyzerConfig:
    """Stock Analyzer 總配置（不可變）"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    data: DataConfig = field(default_factory=DataConfig)
    reports_dir: Path = REPORTS_DIR
    data_cache_dir: Path = DATA_CACHE_DIR

    def to_trading_agents_config(self) -> dict:
        """轉換為 TradingAgents 的配置格式"""
        # TradingAgents 需要 project_dir 來定位內部資源
        ta_project_dir = str(
            Path(__file__).parent.parent.parent
            / "vendor" / "TradingAgents" / "tradingagents"
        )
        return {
            "project_dir": ta_project_dir,
            "llm_provider": self.llm.provider,
            "deep_think_llm": self.llm.deep_think_model,
            "quick_think_llm": self.llm.quick_think_model,
            "backend_url": self.llm.backend_url,
            "google_thinking_level": None,
            "openai_reasoning_effort": None,
            "max_debate_rounds": self.analysis.max_debate_rounds,
            "max_risk_discuss_rounds": self.analysis.max_risk_discuss_rounds,
            "max_recur_limit": self.analysis.max_recur_limit,
            "results_dir": str(self.reports_dir),
            "data_cache_dir": str(self.data_cache_dir),
            "data_vendors": {
                "core_stock_apis": self.data.stock_vendor,
                "technical_indicators": self.data.indicators_vendor,
                "fundamental_data": self.data.fundamentals_vendor,
                "news_data": self.data.news_vendor,
            },
            "tool_vendors": {},
        }


def load_config() -> StockAnalyzerConfig:
    """
    從環境變數載入配置，未設定則使用預設值。

    環境變數：
        STOCK_LLM_PROVIDER: LLM 供應商（預設 ollama）
        STOCK_LLM_MODEL: LLM 模型（預設 qwen3:14b）
        STOCK_LLM_URL: LLM 端點（預設 http://localhost:11434/v1）
        STOCK_REPORTS_DIR: 報告輸出目錄
    """
    llm_config = LLMConfig(
        provider=os.getenv("STOCK_LLM_PROVIDER", "ollama"),
        deep_think_model=os.getenv("STOCK_LLM_MODEL", "qwen3:14b"),
        quick_think_model=os.getenv("STOCK_LLM_MODEL", "qwen3:14b"),
        backend_url=os.getenv(
            "STOCK_LLM_URL", "http://localhost:11434/v1"
        ),
    )

    reports_dir = Path(os.getenv("STOCK_REPORTS_DIR", str(REPORTS_DIR)))

    return StockAnalyzerConfig(
        llm=llm_config,
        reports_dir=reports_dir,
    )
