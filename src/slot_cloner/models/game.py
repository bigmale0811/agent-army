"""遊戲核心資料模型"""
from pydantic import BaseModel, ConfigDict, Field
from slot_cloner.models.enums import GameType, ConfidenceLevel
from slot_cloner.models.symbol import SymbolConfig, PaytableConfig
from slot_cloner.models.feature import FeaturesConfig
from slot_cloner.models.asset import AssetBundle


class GridConfig(BaseModel):
    """遊戲棋盤設定"""
    model_config = ConfigDict(frozen=True)

    cols: int = 6
    rows: int = 5


class GameFingerprint(BaseModel):
    """遊戲技術指紋（Recon 階段產出）"""
    model_config = ConfigDict(frozen=True)

    url: str
    framework: str = "unknown"  # pixi, phaser, cocos, unknown
    provider: str = "unknown"   # atg, pg_soft, pragmatic, unknown
    game_type: GameType = GameType.CASCADE
    canvas_detected: bool = False
    webgl_detected: bool = False
    websocket_urls: tuple[str, ...] = ()
    js_bundle_urls: tuple[str, ...] = ()
    extra: dict[str, object] = Field(default_factory=dict)


class GameConfig(BaseModel):
    """完整遊戲設定（逆向分析產出）"""
    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str = ""
    game_type: GameType = GameType.CASCADE
    grid: GridConfig = GridConfig()
    symbols: tuple[SymbolConfig, ...] = ()
    paytable: PaytableConfig = PaytableConfig()
    features: FeaturesConfig = FeaturesConfig()
    rtp: float = 0.0  # 理論 RTP（如有取得）
    max_multiplier: float = 0.0
    min_bet: float = 1.0
    max_bet: float = 1000.0


class GameModel(BaseModel):
    """完整遊戲模型（Pipeline 最終產出）"""
    model_config = ConfigDict(frozen=True)

    config: GameConfig
    fingerprint: GameFingerprint | None = None
    assets: AssetBundle | None = None
    # 各資料項的可信度
    confidence_map: dict[str, ConfidenceLevel] = Field(default_factory=dict)
    # 原始 WS 訊息（用於除錯）
    raw_ws_messages: tuple[dict, ...] = ()
