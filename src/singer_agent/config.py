# -*- coding: utf-8 -*-
"""Singer Agent — 設定模組

管理所有環境變數、路徑、預設值。
遵循 reading_agent / japan_intel 的 config 模式。
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# === 載入環境變數 ===
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# === Telegram 設定 ===
# 優先使用 Singer Agent 專用 Bot，未設定時降級為共用 Bot
SINGER_BOT_TOKEN = os.getenv("SINGER_BOT_TOKEN", "")
SINGER_CHAT_ID = os.getenv("SINGER_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Ollama 設定（Qwen3 14B 本地推論）===
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# === Gemini API（備用，供較複雜的分析任務）===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# === 路徑設定 ===
DATA_DIR = _PROJECT_ROOT / "data" / "singer_agent"
INBOX_DIR = DATA_DIR / "inbox"           # 使用者放入 MP3 的資料夾
PROCESSING_DIR = DATA_DIR / "processing"  # 處理中的檔案
COMPLETED_DIR = DATA_DIR / "completed"    # 已完成的檔案
SPECS_DIR = DATA_DIR / "specs"            # SongSpec JSON 輸出
IMAGES_DIR = DATA_DIR / "images"          # 生成的圖片
VIDEOS_DIR = DATA_DIR / "videos"          # 生成的影片
PROJECTS_DIR = DATA_DIR / "projects"      # MVProject 狀態追蹤

# 確保目錄存在
for _dir in [INBOX_DIR, PROCESSING_DIR, COMPLETED_DIR, SPECS_DIR,
             IMAGES_DIR, VIDEOS_DIR, PROJECTS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# === 虛擬角色設定 ===
# 角色圖片路徑（使用者需自行放置）
CHARACTER_IMAGE = DATA_DIR / "character" / "avatar.png"
CHARACTER_DIR = DATA_DIR / "character"
CHARACTER_DIR.mkdir(parents=True, exist_ok=True)

# === SadTalker 設定（唱歌模式：對嘴動畫 + 身體搖擺）===
SADTALKER_DIR = Path(os.getenv("SADTALKER_DIR", r"D:\Projects\SadTalker"))
SADTALKER_PYTHON = os.getenv(
    "SADTALKER_PYTHON",
    str(SADTALKER_DIR / "venv" / "Scripts" / "python.exe"),
)
SADTALKER_EXPRESSION_SCALE = float(os.getenv("SADTALKER_EXPRESSION_SCALE", "1.3"))
SADTALKER_POSE_STYLE = int(os.getenv("SADTALKER_POSE_STYLE", "1"))
SADTALKER_SIZE = int(os.getenv("SADTALKER_SIZE", "256"))
SADTALKER_TIMEOUT = int(os.getenv("SADTALKER_TIMEOUT", "600"))  # 秒
SADTALKER_BODY_MOTION = os.getenv("SADTALKER_BODY_MOTION", "true").lower() == "true"

# === ComfyUI 設定（v0.3 AI 背景圖生成）===
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")
COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
COMFYUI_CHECKPOINT = os.getenv(
    "COMFYUI_CHECKPOINT", "sd_xl_base_1.0.safetensors"
)
COMFYUI_TIMEOUT = int(os.getenv("COMFYUI_TIMEOUT", "300"))  # 秒
COMFYUI_DEFAULT_STEPS = int(os.getenv("COMFYUI_DEFAULT_STEPS", "25"))
COMFYUI_DEFAULT_CFG = float(os.getenv("COMFYUI_DEFAULT_CFG", "7.0"))
COMFYUI_NEGATIVE_PROMPT = (
    "person, human, character, face, text, watermark, signature, "
    "blurry, low quality, worst quality, jpeg artifacts"
)

# === 圖片合成設定（v0.3）===
COMPOSITE_CHARACTER_SCALE = float(
    os.getenv("COMPOSITE_CHARACTER_SCALE", "0.85")
)  # 角色高度占背景的比例
COMPOSITE_POSITION = os.getenv("COMPOSITE_POSITION", "bottom_center")

# === 預檢 Agent 設定（v0.3）===
PRECHECK_GEMINI_ENABLED = os.getenv(
    "PRECHECK_GEMINI_ENABLED", "true"
).lower() == "true"
PRECHECK_MIN_FACE_RATIO = float(
    os.getenv("PRECHECK_MIN_FACE_RATIO", "0.02")
)  # 人臉面積至少占圖片 2%
PRECHECK_MAX_AUDIO_DURATION = int(
    os.getenv("PRECHECK_MAX_AUDIO_DURATION", "600")
)  # 音檔最長 10 分鐘

# === v0.3 新增目錄 ===
BACKGROUNDS_DIR = DATA_DIR / "backgrounds"
COMPOSITES_DIR = DATA_DIR / "composites"
for _dir2 in [BACKGROUNDS_DIR, COMPOSITES_DIR]:
    _dir2.mkdir(parents=True, exist_ok=True)

# === 音樂分析設定 ===
# librosa 相關參數
AUDIO_SAMPLE_RATE = 22050       # 取樣率
AUDIO_HOP_LENGTH = 512          # hop length for feature extraction
AUDIO_N_MFCC = 13               # MFCC 係數數量

# === File Watcher 設定 ===
WATCHER_POLL_INTERVAL = 2.0     # 監控輪詢間隔（秒）
SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}

# === 歌曲風格分類 ===
MUSIC_GENRES = {
    "pop": {"name": "流行", "icon": "🎵"},
    "rock": {"name": "搖滾", "icon": "🎸"},
    "ballad": {"name": "抒情", "icon": "💕"},
    "electronic": {"name": "電子", "icon": "🎛️"},
    "rnb": {"name": "R&B", "icon": "🎤"},
    "jazz": {"name": "爵士", "icon": "🎷"},
    "classical": {"name": "古典", "icon": "🎻"},
    "folk": {"name": "民謠", "icon": "🪕"},
    "hip_hop": {"name": "嘻哈", "icon": "🎧"},
    "anime": {"name": "動漫", "icon": "🌸"},
    "chinese_pop": {"name": "華語流行", "icon": "🏮"},
    "other": {"name": "其他", "icon": "🎶"},
}

# === 情緒分類 ===
MOOD_CATEGORIES = {
    "happy": {"name": "歡快", "color_tone": "warm, bright, yellow, orange"},
    "sad": {"name": "憂傷", "color_tone": "cool, blue, muted, rain"},
    "energetic": {"name": "活力", "color_tone": "vibrant, red, neon, dynamic"},
    "calm": {"name": "平靜", "color_tone": "pastel, green, nature, soft light"},
    "romantic": {"name": "浪漫", "color_tone": "pink, sunset, warm glow, petals"},
    "dark": {"name": "黑暗", "color_tone": "dark, purple, shadow, night"},
    "epic": {"name": "史詩", "color_tone": "grand, gold, sky, dramatic lighting"},
    "nostalgic": {"name": "懷舊", "color_tone": "sepia, vintage, warm filter"},
}

# === YouTube 設定 ===
YOUTUBE_CLIENT_SECRETS = DATA_DIR / "client_secrets.json"
YOUTUBE_TOKEN_FILE = DATA_DIR / "youtube_token.json"
YOUTUBE_DEFAULT_CATEGORY = "10"  # Music category
YOUTUBE_DEFAULT_PRIVACY = "private"  # 預設先設為私人，手動確認後再公開

# === HTTP 設定 ===
REQUEST_TIMEOUT = 60    # 請求超時（秒），影片生成可能較久
MAX_RETRIES = 3         # 最大重試次數
