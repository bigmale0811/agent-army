# 讀書 Agent v2 詳細架構 Codemap

**最後更新**: 2026-03-04
**版本**: v2.1（含來源探索 + AI Weekly）
**主要特性**: 暢銷書 → YouTube 搜尋 → 字幕擷取 → Gemini 整理 → Telegram 發送

---

## 核心流程圖

```
┌─────────────────────────────────────────────────────────────┐
│                     讀書 Agent v2 主流程                      │
└─────────────────────────────────────────────────────────────┘

入口 (runner.py)
  │
  ├─→ /start 歡迎訊息 (telegram_bot_handler.py)
  │
  ├─→ /weekly 完整蒐集
  │   ├─→ 【可選】來源探索 (source_discovery.py) — 自動檢查是否該執行
  │   ├─→ 暢銷書爬蟲 (bestseller_scraper.py)
  │   │   ├─ 博客來 (books.com.tw)
  │   │   ├─ 誠品 (eslite.com)
  │   │   ├─ 金石堂 (kingstone.com.tw)
  │   │   └─ Amazon (amazon.com)
  │   │   → 結果：Book[] (去重 + 跨平台合併)
  │   │
  │   ├─→ YouTube 搜尋 (youtube_searcher.py)
  │   │   ├─ 中文書 → "{書名} 說書"
  │   │   ├─ 英文書 → "{書名} book summary review"
  │   │   └─ 篩選：≥5 分鐘影片，最多 5 個/本書
  │   │   → 結果：Video[] (含 title, url, channel_name, duration)
  │   │
  │   ├─→ 字幕擷取 (transcript_extractor.py)
  │   │   ├─ YouTubeTranscriptApi 呼叫
  │   │   ├─ 語言優先順序：zh-TW > zh-Hant > zh > zh-Hans（中文）
  │   │   │                 en > en-US > en-GB（英文）
  │   │   └─ 清理：移除 [Music]、[掌聲] 等雜訊標記，正規化空白
  │   │   → 結果：Video.transcript 已填充
  │   │
  │   ├─→ Gemini 深度整理 (content_analyzer.py)
  │   │   ├─ 輸入：video.transcript
  │   │   ├─ 處理：
  │   │   │  ├─ 中文影片：分析後 → key_points_original + key_points_zh
  │   │   │  └─ 英文影片：分析 → key_points_original，翻譯 → key_points_zh
  │   │   ├─ 批次延遲：2.0 秒/部（避免 API 限流）
  │   │   └─ 異常處理：失敗影片自動略過，不阻斷流程
  │   │   → 結果：Video.key_points_zh + key_points_original
  │   │
  │   ├─→ 自訂頻道追蹤 (runner.py)
  │   │   ├─ 讀取 custom_channels.json
  │   │   ├─ 舊版 YouTubeClient (RSS) 取得新影片
  │   │   └─ 重複：字幕擷取 + Gemini 整理
  │   │   → 結果：custom_videos[] (已整理)
  │   │
  │   ├─→ AI Weekly 蒐集 (ai_weekly.py)
  │   │   ├─ 固定 AI 頻道 RSS 監控
  │   │   ├─ 關鍵字搜尋（7 個搜尋主題）
  │   │   ├─ 字幕擷取 + Gemini 分析
  │   │   └─ 搜尋範圍：weekly → 7 天，initial → 30 天
  │   │   → 結果：ai_videos[] (已整理)
  │   │
  │   ├─→ 儲存影片 (storage.py)
  │   │   └─ 寫入 data/reading_agent/videos/YYYY-MM-DD.json
  │   │
  │   ├─→ 產生報告 (reporter.py)
  │   │   ├─ 暢銷書段落（每本書一則訊息）
  │   │   ├─ 自訂頻道段落（若有新影片）
  │   │   ├─ AI Weekly 段落（獨立分組）
  │   │   └─ 自動分段：超過 4096 字元則切割
  │   │   → 結果：segments[] (已格式化的 Telegram 訊息)
  │   │
  │   └─→ 發送 Telegram (telegram_sender.py)
  │       └─ 若非 dry-run 模式，發送所有分段（延遲 1.5 秒）
  │
  ├─→ /bot 互動模式 (telegram_bot_handler.py)
  │   ├─ /videos — 列出最近蒐集影片
  │   ├─ /books — 抓取暢銷書排行榜
  │   ├─ /channels — 列出追蹤頻道
  │   ├─ /add <url> — 新增自訂頻道
  │   ├─ /remove <名稱> — 移除自訂頻道
  │   ├─ /analyze <url> — 直接分析某影片
  │   ├─ /discover — 探索推薦新頻道（含確認/拒絕按鈕）
  │   ├─ /weekly — 觸發背景蒐集
  │   ├─ /ai — 觸發 AI Weekly
  │   ├─ /collect — 完整蒐集 + 完成通知
  │   └─ /start、/help — 顯示說明
  │
  ├─→ /ai-weekly 獨立執行
  │   └─ 重複：AI 蒐集 → 儲存 → 產生報告 → 發送
  │
  └─→ /analyze-url <url> 直接分析
      └─ 字幕 → Gemini 整理 → 發送單則訊息
```

---

## 模組詳解

### 1. runner.py (775 行)
**責任**: CLI 入口 + 流程協調

**主要函數**:
| 函數 | 行數 | 用途 |
|------|------|------|
| `_run_v2_collect(mode, dry_run)` | 70-220 | v2 主流程協調 |
| `_check_custom_channels(mode)` | 227-274 | 自訂頻道追蹤 |
| `_run_analyze_url(url, dry_run)` | 281-361 | 直接分析影片 |
| `_run_list_books()` | 431-455 | 列出暢銷書 |
| `_run_ai_weekly(dry_run)` | 462-526 | AI Weekly 獨立執行 |
| `_run_v1_collect(mode, dry_run)` | 533-583 | 舊版相容（保留） |
| `main()` / `argparse` | 649-774 | CLI 解析與分派 |

**關鍵變數**:
- `BestsellerScraper()` — 暢銷書爬蟲例示
- `YouTubeSearcher()` — YouTube 搜尋引擎
- `TranscriptExtractor()` — 字幕擷取器
- `ContentAnalyzer()` — Gemini 分析器
- `ReportGenerator()` — 報告產生器
- `TelegramSender()` — Telegram 發送端

---

### 2. telegram_bot_handler.py (1026 行)
**責任**: Telegram Bot 互動、指令處理、結果回覆

**核心類別**: `TelegramBotHandler`

**12 個指令方法**:
| 方法 | 類型 | 功能 |
|------|------|------|
| `cmd_start()` / `cmd_help()` | 同步 | 顯示歡迎 + 指令說明 |
| `cmd_videos()` | 非同步 | 讀 JSON 列出最近影片 |
| `cmd_books()` | 非同步 | 呼叫 BestsellerScraper 顯示排行榜 |
| `cmd_channels()` | 非同步 | 讀 channels.json 展示頻道 |
| `cmd_weekly()` | 非同步 | 背景啟動 `_run_v2_collect()` |
| `cmd_ai()` | 非同步 | 背景啟動 `_run_ai_weekly()` |
| `cmd_collect()` | 非同步 | 完整蒐集 + 完成通知 |
| `cmd_add()` | 非同步 | 新增頻道到 channels.json |
| `cmd_remove()` | 非同步 | 移除頻道 |
| `cmd_analyze()` | 非同步 | 背景分析 YouTube URL |
| `cmd_discover()` | 非同步 | 背景執行來源探索 + Inline Keyboard 投票 |
| `handle_discover_callback()` | 非同步 | 處理探索結果確認/拒絕 |

**安全機制**:
- `_is_authorized(update)` — 驗證 chat_id，防止未授權存取
- 所有指令前檢查授權，失敗則回覆「未授權」

**訊息分段**:
- `_split_message()` — 按 4096 字元上限分割，保持段落完整
- `_send_long_message()` — 逐段發送超長訊息

**資源檔案讀寫**:
- `_load_channels_file()` — 讀 channels.json
- `_save_channels_file()` — 寫 channels.json
- `_extract_channel_name_from_url()` — 解析 YouTube 頻道名
- `_is_youtube_url()` — 驗證 YouTube URL 格式
- `_extract_video_id()` — 從 URL 提取 11 位影片 ID

**背景任務**:
- `_collect_task()` — 完整蒐集，完成後主動回覆
- `_analyze_video_task()` — 影片分析，完成後發送結果
- `_discover_sources_task()` — 來源探索，完成後發送候選清單

---

### 3. models.py (331 行)
**責任**: 資料結構定義

**核心類別**:

#### Book (暢銷書)
```python
@dataclass
class Book:
    title: str              # 書名
    author: str = ""        # 作者
    language: str = "zh"    # 語言（zh/en）
    sources: list[str] = [] # 來源平台列表
    rank: int = 0           # 排名
    isbn: str = ""          # ISBN
    cover_url: str = ""     # 封面 URL
    category: str = ""      # 分類
    collected_at: str = ""  # 蒐集時間（ISO 格式）
```
特殊方法：
- `__eq__()` — 按正規化書名判等（去空格、轉小寫）
- `__hash__()` — 支援集合去重
- `to_dict()` / `from_dict()` — JSON 序列化

#### Video (YouTube 影片)
```python
@dataclass
class Video:
    title: str              # 影片標題
    url: str                # YouTube URL
    channel_name: str       # 頻道名
    channel_id: str         # 頻道 ID
    published_at: str       # 發布日期
    description: str = ""   # 影片描述
    category: str = "general"  # 分類
    video_id: str = ""      # 影片 ID
    duration_seconds: int = 0   # 長度（秒）
    # v2 新增
    transcript: str = ""    # 完整字幕
    key_points_original: str = ""   # 原語言重點
    key_points_zh: str = ""         # 中文重點
    language: str = "zh"    # 影片語言
    book_title: str = ""    # 關聯的書名
```

#### ReadingReport (報告資料)
```python
@dataclass
class ReadingReport:
    period_start: str       # 報告起始日
    period_end: str         # 報告結束日
    videos: list[Video] = []    # 影片列表
    mode: str = "weekly"    # 執行模式
    generated_at: str = ""  # 產生時間
```
統計方法：
- `total_count` — 影片總數
- `channel_counts` — 各頻道計數
- `category_counts` — 各分類計數
- `get_videos_by_channel()` — 篩選指定頻道

#### DiscoveredSource (來源探索)
```python
@dataclass
class DiscoveredSource:
    name: str               # 來源名稱
    url: str                # 主要 URL
    source_type: str = "youtube_channel"  # 類型
    category: str = "general"              # 分類
    language: str = "zh"    # 語言
    score: float = 0.0      # Gemini 評分
    reason: str = ""        # 推薦理由
    status: str = "pending" # 審核狀態（pending/approved/rejected）
    discovered_at: str = "" # 發現時間
    metadata: dict = {}     # 額外資訊
```

---

### 4. config.py (340 行)
**責任**: 全域設定、環境變數載入、常數定義

**環境變數**:
```python
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")      # 舊版 Bot
READING_BOT_TOKEN = os.getenv("READING_BOT_TOKEN")        # 讀書專用 Bot
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")              # Gemini API
```

**路徑設定**:
```python
DATA_DIR = _PROJECT_ROOT / "data" / "reading_agent"
VIDEOS_DIR = DATA_DIR / "videos"            # 影片快取
REPORTS_DIR = DATA_DIR / "reports"          # 報告存檔
CHANNELS_FILE = DATA_DIR / "channels.json"  # 預設頻道
CUSTOM_CHANNELS_FILE = DATA_DIR / "custom_channels.json"  # 自訂頻道
```

**暢銷書來源**:
```python
BESTSELLER_SOURCES = {
    "books_com_tw": {"name": "博客來", "url": "...", "language": "zh"},
    "eslite": {"name": "誠品", "url": "...", "language": "zh"},
    "kingstone": {"name": "金石堂", "url": "...", "language": "zh"},
    "amazon": {"name": "Amazon", "url": "...", "language": "en"},
}
BESTSELLER_TOP_N = 20  # 每個來源抓前 20 名
```

**YouTube 搜尋**:
```python
MIN_VIDEO_DURATION = 300   # 最短 5 分鐘
MAX_SEARCH_RESULTS = 5     # 每本書最多 5 個結果
SEARCH_KEYWORDS_ZH = "{book_title} 說書"
SEARCH_KEYWORDS_EN = "{book_title} book summary review"
```

**頻道分類** (BOOK_CATEGORIES):
```python
{
    "business": {"name": "商業管理", "icon": "💼"},
    "self_help": {"name": "自我成長", "icon": "🌱"},
    "science": {"name": "科學新知", "icon": "🔬"},
    "philosophy": {"name": "哲學思辨", "icon": "🤔"},
    ... 共 11 個分類
}
```

**AI Weekly 設定**:
- `AI_SEARCH_TOPICS` — 7 個搜尋主題（中英文）
- `_DEFAULT_AI_CHANNELS` — 預設 AI 頻道列表（6 個）

**來源探索設定**:
```python
DISCOVERY_MIN_SCORE = 60.0              # 評分門檻
DISCOVERY_MAX_CANDIDATES = 10           # 候選上限
DISCOVERY_INTERVAL_DAYS = 30            # 自動探索週期
```

**工具函數**:
- `load_channels()` — 載入預設或自訂頻道
- `load_ai_channels()` — 載入 AI 頻道列表

---

### 5. bestseller_scraper.py (200+ 行)
**責任**: 四平台暢銷書爬蟲

**類別**: `BestsellerScraper`

**主要方法**:
| 方法 | 用途 |
|------|------|
| `async scrape_all()` | 並行抓取 4 個平台 + 去重 + 合併 |
| `async scrape_books_com_tw()` | 博客來爬蟲 |
| `async scrape_eslite()` | 誠品爬蟲 |
| `async scrape_kingstone()` | 金石堂爬蟲 |
| `async scrape_amazon()` | Amazon 爬蟲 |

**爬蟲特點**:
- 使用 httpx 非同步客戶端，並行抓取
- 模擬真實瀏覽器 User-Agent
- BeautifulSoup4 解析 HTML
- 自動重試 3 次（MAX_RETRIES）
- 單一平台失敗不阻斷整體流程
- 正規化書名去重，跨平台合併來源

**去重邏輯** (models.Book):
- `Book.__eq__()` — 按正規化書名判等
- `Book.__hash__()` — 支援 set() 去重
- 結果：`set(books)` 自動合併同名書籍

---

### 6. youtube_searcher.py (150+ 行)
**責任**: YouTube 影片搜尋

**類別**: `YouTubeSearcher`

**主要方法**:
| 方法 | 用途 |
|------|------|
| `async search_all_books(books)` | 批次搜尋多本書 |
| `async search_one_book(book)` | 搜尋單本書 |
| `_build_search_query(book)` | 依語言建立關鍵字 |

**搜尋邏輯**:
- 中文書 → `"{書名} 說書"`
- 英文書 → `"{書名} book summary review"`
- 使用 youtubesearchpython 的 VideosSearch
- 篩選條件：duration ≥ 300 秒（5 分鐘）
- 每本書最多取 5 個結果
- 批次延遲 1.5 秒

**相容性修補**:
- youtubesearchpython 1.6.x 與 httpx 0.28+ 相容性問題
- 自動移除已過時的 `proxies` 參數

---

### 7. transcript_extractor.py (150+ 行)
**責任**: YouTube 字幕擷取與清理

**類別**: `TranscriptExtractor`

**主要方法**:
| 方法 | 用途 |
|------|------|
| `async extract_batch(videos)` | 批次擷取字幕 |
| `async _extract_one(video)` | 單部影片擷取 |
| `_clean_transcript(text)` | 清理雜訊 |

**語言優先順序** (LANGUAGE_PRIORITY):
```python
"zh": ["zh-TW", "zh-Hant", "zh", "zh-Hans"]
"en": ["en", "en-US", "en-GB"]
```

**清理規則**:
- 移除 `[Music]`、`[Applause]` 等非語音標記
- 移除 `[音樂]`、`[掌聲]` 等中文標記
- 正規化多餘空白（2 個以上空格/換行 → 1 個）
- 使用 youtube_transcript_api 0.6.x API

**批次處理**:
- asyncio.to_thread 包裝同步呼叫
- 每部影片延遲 1.5 秒（避免 IP 被限制）

---

### 8. content_analyzer.py (150+ 行)
**責任**: Gemini 深度內容分析

**類別**: `ContentAnalyzer`

**主要方法**:
| 方法 | 用途 |
|------|------|
| `async analyze_batch(videos)` | 批次分析 |
| `async _analyze_one(video)` | 單部影片分析 |
| `_detect_language(text)` | 偵測內容語言 |

**分析邏輯**:
1. 偵測字幕語言（zh 或 en）
2. 中文影片 → 直接分析，結果填 key_points_original 和 key_points_zh
3. 英文影片 → 分析 → key_points_original，翻譯 → key_points_zh
4. 無字幕影片 → 使用影片描述進行分析（降級）

**Gemini Prompt 結構**:
```
【中文影片】：
- 完整聆聽後，提取所有核心知識點
- 用繁體中文，Markdown 格式

【英文影片】：
- 分析並用英文輸出重點
- 再翻譯為繁體中文

設計原則：
- 「重點整理」而非摘要（完整、詳細）
- 如有未來應用、延伸閱讀等，加在末尾
```

**批次處理**:
- 批次延遲 2.0 秒/部
- 失敗影片自動略過（not_available 狀態）
- 異常日誌記錄但不中斷

**使用模型**:
- `gemini-2.5-flash` — 快速、節省 token

---

### 9. reporter.py (250+ 行)
**責任**: 報告產生與格式化

**類別**: `ReportGenerator`

**主要方法**:
| 方法 | 用途 |
|------|------|
| `generate(report, summary)` | v1 報告產生（舊版） |
| `generate_v2(books, videos_dict, custom_videos)` | v2 報告（以書籍為主） |
| `generate_ai_weekly(videos)` | AI Weekly 報告 |
| `_split_message(text)` | 4096 字元分段 |

**v2 報告格式** (generate_v2):
```
📚 暢銷書說書整理
📅 2026-03-04

【第 1 本】《書名》— 作者
🎯 關鍵重點
  ... (key_points_zh)

📺 來源影片
  · 頻道名 - 影片標題
  · 更多...

━━━━━━━

【第 2 本】...

[自訂頻道區塊]
[AI Weekly 區塊]

🤖 Agent Army ｜ 讀書 Agent v2
```

**分段邏輯**:
- 每本書獨立為一段
- 超過 4096 字元時按換行符切割
- 保持段落完整性

---

### 10. telegram_sender.py
**責任**: Telegram 訊息發送

**類別**: `TelegramSender`

**主要方法**:
| 方法 | 用途 |
|------|------|
| `async send_segments(segments)` | 發送分段訊息 |
| `async send_report(report, summary)` | 發送完整報告（舊版） |
| `async test_connection()` | 測試連線 |

**發送機制**:
- 使用 python-telegram-bot v20+ 的 async API
- 每段訊息發送延遲 1.5 秒（TELEGRAM_SEND_DELAY）
- 支援 Markdown 格式
- 禁用網頁預覽

---

### 11. storage.py (40+ 行)
**責任**: 影片與報告的 JSON 持久化

**類別**: `VideoStorage`

**主要方法**:
| 方法 | 用途 |
|------|------|
| `save_videos(videos, date_str)` | 按日期存檔影片 |
| `load_videos(date_str)` | 載入指定日期影片 |
| `load_videos_by_date_range(start, end)` | 日期範圍查詢 |

**儲存結構**:
```
data/reading_agent/videos/
├── 2026-03-04.json  ← [Video.to_dict(), ...]
├── 2026-03-03.json
└── ...
```

---

### 12. ai_weekly.py
**責任**: AI 相關影片蒐集

**類別**: `AIWeeklyCollector`

**流程**:
1. 監控預設 AI 頻道（6 個 RSS）
2. 按 7 個搜尋主題進行 YouTube 搜尋
3. 去重合併
4. 字幕擷取 + Gemini 分析
5. 回傳已整理的 Video[]

---

### 13. source_discovery.py
**責任**: 自動探索推薦新頻道與書評網站

**類別**: `SourceDiscovery`

**流程**:
1. 搜尋 YouTube 說書頻道（中英文關鍵字）
2. 掃描已知書評網站
3. Gemini 評分 + 推薦理由
4. 儲存候選至 discovered_sources.json
5. Telegram Bot 中展示 Inline Keyboard 供確認/拒絕

**自動觸發**:
- 每 30 天自動執行一次（_run_v2_collect 中 discover_if_due）

---

## 資料流向圖

```
Book (暢銷書)
├─ title, author, language
├─ sources[], rank, isbn, cover_url, category
└─ collected_at

    ↓ YouTube 搜尋

Video (初始影片資訊)
├─ title, url, channel_name, channel_id, published_at
├─ description, category, video_id
├─ thumbnail, duration_seconds
└─ collected_at

    ↓ 字幕擷取

Video (含字幕)
├─ [上述欄位]
└─ transcript (完整字幕)

    ↓ Gemini 分析

Video (含重點整理)
├─ [上述欄位]
├─ key_points_original (原語言)
├─ key_points_zh (中文翻譯)
├─ language (zh/en)
└─ book_title (關聯書籍)

    ↓ 產生報告

ReportGenerator.generate_v2()
├─ 按書籍分組
├─ 每本書一段訊息
├─ 自動分段（4096 字元上限）
└─ segments[] (已格式化)

    ↓ 發送 Telegram

TelegramSender.send_segments()
└─ 逐段發送（延遲 1.5 秒）
```

---

## 設定檔結構

### channels.json (預設頻道)
```json
[
  {
    "channel_id": "UCxxx",
    "name": "文森說書",
    "url": "https://www.youtube.com/@vincentshuoshu",
    "category": "general",
    "description": "每週介紹一本好書"
  },
  ...
]
```

### custom_channels.json (使用者自訂)
```json
[
  {
    "channel_id": "UCyyy",
    "name": "自訂頻道",
    "url": "https://...",
    "category": "general",
    "description": "使用者透過 /add 新增"
  }
]
```

### discovered_sources.json (探索結果)
```json
[
  {
    "name": "頻道名",
    "url": "https://...",
    "source_type": "youtube_channel",
    "category": "general",
    "language": "zh",
    "score": 85.5,
    "reason": "Gemini 推薦理由（繁體中文）",
    "status": "pending|approved|rejected",
    "discovered_at": "2026-03-04T...",
    "metadata": {
      "update_frequency": "high|medium|low",
      "recent_titles": ["影片標題 1", "影片標題 2"]
    }
  }
]
```

---

## Telegram Bot 互動指令清單

| 指令 | 用途 | 耗時 | 參數 |
|------|------|------|------|
| `/start`、`/help` | 顯示歡迎 + 指令列表 | 快 | 無 |
| `/videos` | 列出最近蒐集影片 | 快 | 無 |
| `/books` | 顯示暢銷書排行榜 | 中（爬蟲） | 無 |
| `/channels` | 列出追蹤頻道 | 快 | 無 |
| `/weekly` | 背景執行完整蒐集 | 慢（5-10 分） | 無 |
| `/ai` | 背景執行 AI Weekly | 慢（3-5 分） | 無 |
| `/collect` | 完整蒐集 + 完成通知 | 慢 | `[dry]`（可選） |
| `/add <url>` | 新增自訂頻道 | 快 | YouTube 頻道 URL |
| `/remove <名稱>` | 移除自訂頻道 | 快 | 頻道名稱 |
| `/analyze <url>` | 分析指定 YouTube 影片 | 慢（2-3 分） | YouTube 影片 URL |
| `/discover` | 探索推薦新頻道 | 慢（2-3 分） | 無（結果含按鈕） |

---

## 開發指南

### 新增 Telegram 指令
1. 在 `telegram_bot_handler.py` 新增 `async def cmd_xxx()`
2. 實現指令邏輯
3. 在 `run()` 方法註冊 `CommandHandler("xxx", self.cmd_xxx)`

### 修改暢銷書來源
1. 編輯 `config.py` 的 `BESTSELLER_SOURCES`
2. 在 `bestseller_scraper.py` 實現 `async scrape_xxx()` 方法

### 擴展 Gemini 分析
1. 編輯 `content_analyzer.py` 的 Prompt 模板
2. 調整 `_analyze_one()` 邏輯

### 新增頻道分類
1. 編輯 `config.py` 的 `BOOK_CATEGORIES` 或 `AI_CATEGORIES`
2. 更新 `telegram_bot_handler.py` 的分類展示邏輯

---

## 常見問題排查

### Q: 字幕擷取失敗？
A: 檢查 YouTube 影片是否有字幕，嘗試變更 `LANGUAGE_PRIORITY` 或升級 youtube_transcript_api

### Q: Gemini 分析超時？
A: 增加 `_BATCH_DELAY`，或檢查 GEMINI_API_KEY 額度

### Q: Telegram 發送失敗？
A: 驗證 READING_BOT_TOKEN / READING_CHAT_ID（或降級至 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID）

### Q: 暢銷書爬蟲被限流？
A: 增加 `REQUEST_DELAY`，或改用代理

---

## 相關檔案與資源

- [整體系統架構](architecture.md)
- CLAUDE.md — 開發規則與 Agent 調度
- data/reading_agent/ — 執行時資料目錄
- requirements.txt — Python 依賴清單
