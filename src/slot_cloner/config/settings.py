"""設定管理 — YAML 設定檔 + 預設值"""
from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, ConfigDict


class SlotClonerSettings(BaseModel):
    """工具設定"""
    model_config = ConfigDict(frozen=True)

    output_dir: Path = Path("./output")
    browser_timeout_ms: int = 60000
    page_load_timeout_ms: int = 30000
    max_retries: int = 3
    log_level: str = "INFO"
    # Playwright 設定
    headless: bool = True
    slow_mo: int = 0  # 毫秒，用於除錯


def load_settings(config_path: Path | None = None) -> SlotClonerSettings:
    """載入設定，支援 YAML 覆寫

    優先級：YAML 檔 > 環境變數 > 預設值
    """
    if config_path and config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return SlotClonerSettings(**data)
        except Exception:
            pass
    return SlotClonerSettings()
