"""符號與賠率相關資料模型"""
from pydantic import BaseModel, ConfigDict
from slot_cloner.models.enums import SymbolType, ConfidenceLevel


class SymbolConfig(BaseModel):
    """單一符號的設定"""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    symbol_type: SymbolType = SymbolType.REGULAR
    image_name: str = ""
    # 賠率：key 是組合數量，value 是賠率倍數
    payouts: dict[int, float] = {}


class PaytableEntry(BaseModel):
    """賠率表的單一條目"""
    model_config = ConfigDict(frozen=True)

    symbol_id: str
    min_count: int
    payout_multiplier: float
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class PaytableConfig(BaseModel):
    """完整賠率表"""
    model_config = ConfigDict(frozen=True)

    entries: tuple[PaytableEntry, ...] = ()
    min_cluster_size: int = 8  # 消除型：最小連接數
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
