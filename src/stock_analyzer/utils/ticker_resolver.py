"""
Ticker 代號解析器

自動辨識投資標的類型（台股、美股、加密貨幣、黃金等），
並轉換為 yfinance 相容的 ticker 格式。
"""

import re
from dataclasses import dataclass
from enum import Enum


class AssetType(Enum):
    """投資標的類型"""

    TW_STOCK = "tw_stock"          # 台股個股
    TW_ETF = "tw_etf"             # 台股 ETF
    US_STOCK = "us_stock"          # 美股
    CRYPTO = "crypto"              # 加密貨幣
    COMMODITY = "commodity"        # 大宗商品（黃金、原油等）
    FUND = "fund"                  # 基金
    UNKNOWN = "unknown"


# 常見台股 ETF 代號（4 位數字，00 開頭）
TW_ETF_PREFIXES = {"00", "006", "007", "008"}

# 常見加密貨幣代號
CRYPTO_SYMBOLS = {
    "BTC", "ETH", "SOL", "ADA", "DOT", "AVAX", "MATIC",
    "DOGE", "SHIB", "XRP", "BNB", "LINK", "UNI", "AAVE",
}

# 常見商品期貨代號
COMMODITY_SYMBOLS = {
    "GC=F": "黃金",
    "SI=F": "白銀",
    "CL=F": "原油",
    "NG=F": "天然氣",
}

# 台股代號快捷對照表（方便使用者輸入）
TW_STOCK_ALIASES = {
    "台積電": "2330.TW",
    "鴻海": "2317.TW",
    "聯發科": "2454.TW",
    "台達電": "2308.TW",
    "中華電": "2412.TW",
    "元大50": "0050.TW",
    "元大高股息": "0056.TW",
}


@dataclass(frozen=True)
class ResolvedTicker:
    """解析後的 Ticker 資訊（不可變）"""

    raw_input: str        # 使用者原始輸入
    ticker: str           # yfinance 格式的 ticker
    asset_type: AssetType  # 標的類型
    display_name: str     # 顯示名稱


def resolve_ticker(raw_input: str) -> ResolvedTicker:
    """
    解析使用者輸入的股票代號，轉換為 yfinance 格式。

    支援格式：
        - 台股：2330, 2330.TW, 台積電
        - 美股：AAPL, MSFT
        - 加密貨幣：BTC, BTC-USD
        - 商品：GC=F, gold, 黃金
        - ETF：0050, 0050.TW

    Args:
        raw_input: 使用者輸入的代號

    Returns:
        ResolvedTicker: 解析結果
    """
    cleaned = raw_input.strip()

    # 中文別名對照
    if cleaned in TW_STOCK_ALIASES:
        ticker = TW_STOCK_ALIASES[cleaned]
        return ResolvedTicker(
            raw_input=cleaned,
            ticker=ticker,
            asset_type=AssetType.TW_STOCK,
            display_name=f"{cleaned} ({ticker})",
        )

    # 黃金/商品中文
    commodity_aliases = {"黃金": "GC=F", "gold": "GC=F", "白銀": "SI=F", "silver": "SI=F", "原油": "CL=F", "oil": "CL=F"}
    if cleaned.lower() in commodity_aliases:
        ticker = commodity_aliases[cleaned.lower()]
        return ResolvedTicker(
            raw_input=cleaned,
            ticker=ticker,
            asset_type=AssetType.COMMODITY,
            display_name=f"{cleaned} ({ticker})",
        )

    # 商品期貨代號（含 =F）
    if cleaned.upper() in COMMODITY_SYMBOLS:
        return ResolvedTicker(
            raw_input=cleaned,
            ticker=cleaned.upper(),
            asset_type=AssetType.COMMODITY,
            display_name=f"{COMMODITY_SYMBOLS[cleaned.upper()]} ({cleaned.upper()})",
        )

    # 加密貨幣（BTC → BTC-USD）
    upper = cleaned.upper()
    if upper in CRYPTO_SYMBOLS:
        ticker = f"{upper}-USD"
        return ResolvedTicker(
            raw_input=cleaned,
            ticker=ticker,
            asset_type=AssetType.CRYPTO,
            display_name=f"{upper} ({ticker})",
        )
    if re.match(r"^[A-Z]{2,5}-USD$", upper):
        symbol = upper.split("-")[0]
        if symbol in CRYPTO_SYMBOLS:
            return ResolvedTicker(
                raw_input=cleaned,
                ticker=upper,
                asset_type=AssetType.CRYPTO,
                display_name=f"{symbol} ({upper})",
            )

    # 台股（純數字，4-6 位）
    if re.match(r"^\d{4,6}$", cleaned):
        ticker = f"{cleaned}.TW"
        # 判斷是 ETF 還是個股
        asset_type = AssetType.TW_ETF if cleaned.startswith("00") else AssetType.TW_STOCK
        return ResolvedTicker(
            raw_input=cleaned,
            ticker=ticker,
            asset_type=asset_type,
            display_name=f"{cleaned} ({ticker})",
        )

    # 已含 .TW 後綴
    if cleaned.upper().endswith(".TW") or cleaned.upper().endswith(".TWO"):
        ticker = cleaned.upper()
        code = ticker.split(".")[0]
        asset_type = AssetType.TW_ETF if code.startswith("00") else AssetType.TW_STOCK
        return ResolvedTicker(
            raw_input=cleaned,
            ticker=ticker,
            asset_type=asset_type,
            display_name=ticker,
        )

    # 美股（純英文字母，1-5 位）
    if re.match(r"^[A-Za-z]{1,5}$", cleaned):
        ticker = cleaned.upper()
        return ResolvedTicker(
            raw_input=cleaned,
            ticker=ticker,
            asset_type=AssetType.US_STOCK,
            display_name=ticker,
        )

    # 無法辨識，原樣返回
    return ResolvedTicker(
        raw_input=cleaned,
        ticker=cleaned,
        asset_type=AssetType.UNKNOWN,
        display_name=cleaned,
    )
