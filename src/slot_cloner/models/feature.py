"""遊戲特殊機制資料模型"""
from pydantic import BaseModel, ConfigDict
from slot_cloner.models.enums import ConfidenceLevel


class WildConfig(BaseModel):
    """Wild 符號設定"""
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    symbol_id: str = "wild"
    substitutes_all: bool = True  # 是否替代所有符號
    except_symbols: tuple[str, ...] = ("scatter", "bonus")
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class ScatterConfig(BaseModel):
    """Scatter 符號設定"""
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    symbol_id: str = "scatter"
    trigger_count: int = 4  # 觸發 Free Spin 所需數量
    free_spins_awarded: int = 15
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class CascadeConfig(BaseModel):
    """消除（Cascade）機制設定"""
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    min_cluster_size: int = 8  # 最小消除連接數
    # 消除後新符號從上方掉落填充
    fill_from_top: bool = True
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class MultiplierConfig(BaseModel):
    """乘數機制設定"""
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    values: tuple[int, ...] = (2, 3, 5, 10, 25, 50, 100, 500)
    # 乘數在同一輪 cascade 中累積
    accumulate_in_cascade: bool = True
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class FreeSpinConfig(BaseModel):
    """Free Spin 設定"""
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    base_spins: int = 15
    retrigger_enabled: bool = True
    retrigger_spins: int = 5
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class FeaturesConfig(BaseModel):
    """所有遊戲特殊機制的集合"""
    model_config = ConfigDict(frozen=True)

    wild: WildConfig = WildConfig()
    scatter: ScatterConfig = ScatterConfig()
    cascade: CascadeConfig = CascadeConfig()
    multiplier: MultiplierConfig = MultiplierConfig()
    free_spin: FreeSpinConfig = FreeSpinConfig()
