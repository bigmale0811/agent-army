"""列舉類型定義"""
from enum import Enum


class GameType(str, Enum):
    """遊戲類型"""
    CASCADE = "cascade"      # 消除型（如戰神賽特）
    CLASSIC = "classic"      # 傳統 Payline
    WAYS = "ways"            # Ways to Win
    CLUSTER = "cluster"      # Cluster Pays


class ConfidenceLevel(str, Enum):
    """分析可信度"""
    HIGH = "high"        # 從設定檔直接取得
    MEDIUM = "medium"    # 從 WS 攔截推斷
    LOW = "low"          # 從 OCR 或猜測


class PipelinePhase(str, Enum):
    """Pipeline 階段"""
    INIT = "init"
    RECON = "recon"
    SCRAPE = "scrape"
    REVERSE = "reverse"
    REPORT = "report"
    BUILD = "build"
    DONE = "done"


class SymbolType(str, Enum):
    """符號類型"""
    REGULAR = "regular"
    WILD = "wild"
    SCATTER = "scatter"
    BONUS = "bonus"
    MULTIPLIER = "multiplier"
