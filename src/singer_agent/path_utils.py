# -*- coding: utf-8 -*-
"""
Singer Agent 路徑工具模組（DEV-3）。

解決 SadTalker 不支援非 ASCII 路徑的問題：
將含中文或特殊字元的路徑複製到暫存 ASCII 路徑後再處理。
"""
import hashlib
import shutil
import tempfile
import time
from pathlib import Path


def to_ascii_temp(original: Path, suffix: str = "") -> Path:
    """
    將非 ASCII 路徑的檔案複製到純 ASCII 暫存路徑後回傳。

    SadTalker subprocess 無法處理含中文的路徑，
    此函式產生一個全 ASCII 的暫存檔案路徑，
    並把原始內容複製過去。

    :param original: 原始檔案路徑（可含中文或任意 Unicode）
    :param suffix: 附加到暫存檔名 stem 的後綴字串（如 "_work"）
    :return: 暫存 ASCII 路徑（已存在於磁碟）
    """
    # 取得副檔名
    ext = original.suffix

    # 取得系統暫存目錄（全 ASCII 路徑）
    temp_dir = Path(tempfile.gettempdir())

    # 用 timestamp + hash 產生唯一且純 ASCII 的檔名
    timestamp = int(time.time() * 1000)
    # 用原始路徑的 hash 作為識別碼，避免碰撞
    hash_part = hashlib.md5(str(original).encode("utf-8")).hexdigest()[:8]
    stem = f"singer_{timestamp}_{hash_part}{suffix}"

    # 組合最終路徑
    temp_path = temp_dir / f"{stem}{ext}"

    # 複製原始檔案到暫存路徑
    shutil.copy2(str(original), str(temp_path))

    return temp_path


def cleanup_temp(path: Path) -> None:
    """
    刪除暫存檔案，若不存在則靜默略過。

    用於清理 to_ascii_temp() 產生的暫存檔案。

    :param path: 要刪除的路徑
    :return: None
    """
    try:
        path.unlink()
    except FileNotFoundError:
        # 檔案不存在時靜默略過，符合 DEV-3 規格
        pass


def ensure_dir(path: Path) -> Path:
    """
    若目錄不存在則建立（含所有父目錄），然後回傳原始 path。

    等同於 mkdir -p，用於確保輸出目錄存在。

    :param path: 要確保存在的目錄路徑
    :return: 與輸入相同的 path 物件
    """
    # parents=True 允許建立巢狀目錄，exist_ok=True 已存在時不報錯
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_stem(title: str) -> str:
    """
    將任意字串（含中文、emoji、特殊字元）轉換為 ASCII 安全的檔名 stem。

    使用 SHA-256 hash 的前 12 碼確保唯一性，
    加上 timestamp 提供時間可讀性。

    中文歌名如「月亮代表我的心」會轉換為 "singer_<hash>_<ts>" 格式。

    :param title: 原始標題字串（可含任意 Unicode）
    :return: ASCII 安全的檔名 stem（無副檔名、無非法字元）
    """
    if not title or not title.strip():
        # 空字串後備：使用 timestamp
        return f"singer_untitled_{int(time.time())}"

    # 嘗試保留 ASCII 英數字元
    ascii_parts = []
    for char in title:
        if char.isascii() and (char.isalnum() or char in "-_"):
            ascii_parts.append(char)
        elif char in " \t":
            ascii_parts.append("_")
        # 非 ASCII 字元跳過（如中文）

    # 用 hash 確保唯一性
    hash_part = hashlib.md5(title.encode("utf-8")).hexdigest()[:12]

    if ascii_parts:
        # 有 ASCII 部分：用來當前綴，再加 hash
        ascii_prefix = "".join(ascii_parts)[:20].strip("_")
        if ascii_prefix:
            return f"{ascii_prefix}_{hash_part}"

    # 完全無 ASCII 可用部分（如純中文）：直接用 hash
    return f"singer_{hash_part}"
