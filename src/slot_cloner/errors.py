"""統一的錯誤類別定義 — 所有 Pipeline 錯誤的基類

錯誤層級：
- SlotClonerError (base)
  ├── PipelineError (Pipeline 執行錯誤)
  │   ├── ReconError (偵察失敗)
  │   ├── ScrapeError (資源擷取失敗)
  │   ├── ReverseError (逆向分析失敗)
  │   ├── BuildError (構建遊戲失敗)
  │   └── CheckpointError (Checkpoint 讀寫失敗)
  ├── AdapterError (Adapter 錯誤)
  ├── ConfigError (設定檔錯誤)
  └── ValidationError (資料驗證錯誤)
"""


class SlotClonerError(Exception):
    """所有 Slot Cloner 錯誤的基類"""

    def __init__(self, message: str, details: str | None = None) -> None:
        self.details = details
        super().__init__(message)


class PipelineError(SlotClonerError):
    """Pipeline 執行過程中的錯誤"""

    def __init__(self, phase: str, message: str, details: str | None = None) -> None:
        self.phase = phase
        super().__init__(f"[{phase}] {message}", details)


class ReconError(PipelineError):
    """偵察階段錯誤（如瀏覽器啟動失敗、頁面載入超時）"""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__("recon", message, details)


class ScrapeError(PipelineError):
    """資源擷取錯誤（如網路中斷、MIME type 無法辨識）"""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__("scrape", message, details)


class ReverseError(PipelineError):
    """逆向分析錯誤（如 JS 解析失敗、WS 資料格式異常）"""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__("reverse", message, details)


class BuildError(PipelineError):
    """遊戲構建錯誤（如 npm build 失敗、模板缺失）"""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__("build", message, details)


class CheckpointError(PipelineError):
    """Checkpoint 讀寫錯誤"""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__("checkpoint", message, details)


class AdapterError(SlotClonerError):
    """Adapter 相關錯誤（如找不到合適的 Adapter）"""
    pass


class ConfigError(SlotClonerError):
    """設定檔相關錯誤（如 YAML 解析失敗、必要欄位缺失）"""
    pass


class ValidationError(SlotClonerError):
    """資料驗證錯誤（如不合法的 URL、不合法的遊戲設定）"""
    pass


# --- 輸入驗證工具函數 ---

_ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str) -> None:
    """驗證 URL 是否安全（防 SSRF / local file exfiltration）

    Raises:
        ValidationError: URL 不合法
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValidationError(f"不允許的 URL scheme: {parsed.scheme!r}")
    if not parsed.netloc:
        raise ValidationError("URL 必須包含主機名稱")


def sanitize_name(name: str) -> str:
    """清理遊戲名稱（防 path traversal）

    Returns:
        安全的名稱字串（僅含英數字、底線、連字號）

    Raises:
        ValidationError: 名稱清理後為空
    """
    import re
    clean = re.sub(r"[^\w\-]", "_", name)
    clean = clean.strip("._")
    if not clean:
        raise ValidationError(f"不合法的遊戲名稱: {name!r}")
    return clean[:64]
