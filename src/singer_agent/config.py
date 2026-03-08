# -*- coding: utf-8 -*-
"""
Singer Agent 設定模組。

載入路徑常數、工具路徑及環境變數。
優先讀取 .env 檔案，再從系統環境變數讀取，最後使用預設值。
"""
import os
from pathlib import Path

# 嘗試載入 .env 檔案（python-dotenv 選配，未安裝時略過）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─────────────────────────────────────────────────
# 資料目錄結構
# ─────────────────────────────────────────────────

# 主資料目錄（相對路徑，工作目錄為專案根目錄時正確）
DATA_DIR = Path("data/singer_agent")

# 各功能子目錄
CHARACTER_DIR = DATA_DIR / "character"      # 角色圖片目錄
INBOX_DIR = DATA_DIR / "inbox"              # 待處理音訊檔案目錄
BACKGROUNDS_DIR = DATA_DIR / "backgrounds"  # 生成的背景圖目錄
COMPOSITES_DIR = DATA_DIR / "composites"    # 合成後的角色圖目錄
VIDEOS_DIR = DATA_DIR / "videos"            # 產出 MV 目錄
SPECS_DIR = DATA_DIR / "specs"              # SongSpec JSON 目錄
PROJECTS_DIR = DATA_DIR / "projects"        # ProjectState JSON 目錄

# 角色圖片路徑（固定檔名）
CHARACTER_IMAGE = CHARACTER_DIR / "avatar.png"


# ─────────────────────────────────────────────────
# 工具路徑（從環境變數讀取，含預設值）
# ─────────────────────────────────────────────────

# SadTalker 安裝目錄（V1.0 遺留，V2.0 已棄用）
SADTALKER_DIR = Path(os.environ.get("SADTALKER_DIR", "D:/Projects/SadTalker"))

# EDTalk 安裝目錄（V2.0 核心影片引擎）
EDTALK_DIR = Path(os.environ.get("EDTALK_DIR", "D:/Projects/EDTalk"))
# EDTalk 虛擬環境 Python（含 torch + cu128）
EDTALK_PYTHON = EDTALK_DIR / "edtalk_env" / "Scripts" / "python.exe"
# EDTalk demo 腳本（支援 --exp_type 情緒標籤）
EDTALK_DEMO_SCRIPT = EDTALK_DIR / "demo_EDTalk_A_using_predefined_exp_weights.py"
# EDTalk 預設姿態影片
EDTALK_POSE_VIDEO = EDTALK_DIR / "test_data" / "pose_source1.mp4"

# FFmpeg 執行檔路徑（用於影片靜態合成降級）
FFMPEG_BIN = Path(os.environ.get("FFMPEG_BIN", "ffmpeg"))

# ComfyUI REST API URL（用於 SDXL 背景生成）
COMFYUI_URL: str = os.environ.get("COMFYUI_URL", "http://localhost:8188")

# Ollama API URL（用於本地 LLM 推理）
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")


# ─────────────────────────────────────────────────
# Telegram Bot 設定
# ─────────────────────────────────────────────────

# Telegram Bot API Token（從 @BotFather 取得）
# 優先使用 SINGER_BOT_TOKEN，與主 Bot 分開管理
TELEGRAM_BOT_TOKEN: str = os.environ.get(
    "SINGER_BOT_TOKEN",
    os.environ.get("TELEGRAM_BOT_TOKEN", ""),
)


def _parse_user_ids(raw: str) -> list[int]:
    """
    將逗號分隔的使用者 ID 字串解析為 list[int]。
    支援 ID 前後有空白的格式，如 "123 , 456 , 789"。

    :param raw: 逗號分隔的 ID 字串
    :return: 整數 ID 列表，空字串時回傳空列表
    """
    if not raw.strip():
        return []
    ids: list[int] = []
    for uid in raw.split(","):
        uid = uid.strip()
        if not uid:
            continue
        # 驗證每個 ID 是否為合法整數，提供清楚的錯誤訊息
        if not uid.lstrip("-").isdigit():
            raise ValueError(
                f"ALLOWED_USER_IDS 包含無效的 ID：'{uid}'。"
                "請確認為純整數，以逗號分隔。"
            )
        ids.append(int(uid))
    return ids


# 允許使用 Telegram Bot 的使用者 ID 列表
# 優先使用 SINGER_CHAT_ID，與主 Bot 分開管理
ALLOWED_USER_IDS: list[int] = _parse_user_ids(
    os.environ.get(
        "SINGER_CHAT_ID",
        os.environ.get("ALLOWED_USER_IDS", ""),
    )
)


# ─────────────────────────────────────────────────
# LLM / AI 服務設定
# ─────────────────────────────────────────────────

# Gemini Vision API Key（用於品質預檢視覺評分，選配）
# 空字串表示未設置，precheck.py 會跳過 Gemini 評分
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# LLM Provider 選擇（"ollama" 或 "gemini"）
# 預設使用本地 Ollama，節省費用
SINGER_LLM_PROVIDER: str = os.environ.get("SINGER_LLM_PROVIDER", "ollama")
