# Agent Army Codemaps 索引

**最後更新**: 2026-03-04
**目的**: 提供整個專案的架構地圖，幫助快速定位代碼與瞭解系統設計

---

## 文件導航

### 總體層級

| 文件 | 內容 | 適合對象 |
|------|------|---------|
| **[architecture.md](architecture.md)** | 三大模組總體架構、檔案結構、設定管理 | 新開發者入門、架構設計 |
| **[reading-agent.md](reading-agent.md)** | 讀書 Agent v2 完整 Codemap、流程圖、模組詳解 | 讀書 Agent 開發者 |

---

## 核心模組速查表

### 讀書 Agent v2 (src/reading_agent/)

**最重要的模組**，主要特性：暢銷書→YouTube 搜尋→字幕擷取→Gemini 整理→Telegram 發送

| 檔案 | 行數 | 用途 | 優先級 |
|------|------|------|--------|
| **runner.py** | 775 | CLI 入口 + 流程協調 | ⭐⭐⭐ 必讀 |
| **telegram_bot_handler.py** | 1026 | 12 個 Telegram 指令 | ⭐⭐⭐ |
| **models.py** | 331 | Book、Video、ReadingReport 資料結構 | ⭐⭐⭐ |
| **config.py** | 340 | 設定、常數、頻道定義 | ⭐⭐⭐ |
| **bestseller_scraper.py** | 200+ | 暢銷書爬蟲（4 平台） | ⭐⭐ |
| **youtube_searcher.py** | 150+ | YouTube 影片搜尋 | ⭐⭐ |
| **transcript_extractor.py** | 150+ | 字幕擷取與清理 | ⭐⭐ |
| **content_analyzer.py** | 150+ | Gemini 深度分析 | ⭐⭐ |
| **reporter.py** | 250+ | 報告產生與格式化 | ⭐⭐ |
| **telegram_sender.py** | — | Telegram 訊息發送 | ⭐ |
| **storage.py** | 40+ | JSON 持久化 | ⭐ |
| **ai_weekly.py** | — | AI 相關影片蒐集 | ⭐ |
| **source_discovery.py** | — | 自動推薦新頻道 | ⭐ |

**關鍵資料流**:
```
Book → YouTube 搜尋 → Video (基本資訊)
  ↓ 字幕擷取
  → Video (含 transcript)
  ↓ Gemini 分析
  → Video (含 key_points_zh + key_points_original)
  ↓ 報告產生
  → segments[] (分段 Telegram 訊息)
  ↓ 發送
  → Telegram 使用者
```

---

### 日本博弈資訊蒐集 (src/japan_intel/)

| 檔案 | 用途 |
|------|------|
| runner.py | CLI 入口 |
| collector.py | 多源資訊蒐集 |
| sources/*.py | 爬蟲模組（Google News、日本媒體等） |
| reporter.py、telegram_sender.py | 報告 + 發送 |

---

### 百家樂遊戲引擎 (src/game/)

| 檔案 | 用途 |
|------|------|
| baccarat_engine.py | 核心發牌邏輯 |
| shoe.py | 牌靴管理 |
| hand.py | 手牌點數計算 |
| card.py | 撲克牌資料 |

---

### WebSocket API (src/api/)

| 檔案 | 用途 |
|------|------|
| ws_handler.py | 遊戲實時推送 |
| session.py | 會話管理 |
| models.py | 通訊資料結構 |

---

## 快速查找

### 「我想...」查詢表

| 需求 | 查看檔案 | 關鍵函數/類別 |
|------|---------|-------------|
| 新增 Telegram 指令 | telegram_bot_handler.py | `cmd_xxx()` + `run()` |
| 修改暢銷書來源 | config.py + bestseller_scraper.py | BESTSELLER_SOURCES + scrape_xxx() |
| 調整 Gemini 分析 | content_analyzer.py | ContentAnalyzer.analyze_batch() |
| 新增 AI Weekly 頻道 | config.py | _DEFAULT_AI_CHANNELS |
| 新增頻道分類 | config.py | BOOK_CATEGORIES |
| 修改報告格式 | reporter.py | ReportGenerator.generate_v2() |
| 修改字幕清理規則 | transcript_extractor.py | _NOISE_PATTERN |
| 查看最近蒐集的影片 | storage.py | VideoStorage.load_videos() |
| 調整 Telegram 訊息分段 | reporter.py / telegram_bot_handler.py | _split_message() |
| 修改 YouTube 搜尋邏輯 | youtube_searcher.py | YouTubeSearcher._build_search_query() |

---

## CLI 命令速查

### 讀書 Agent v2

```bash
# 完整蒐集（暢銷書 → YouTube → 字幕 → 整理 → 發送）
python -m src.reading_agent --mode weekly

# 首次蒐集（範圍更大，包含 30 天前內容）
python -m src.reading_agent --mode initial

# 只蒐集不發送 Telegram
python -m src.reading_agent --mode weekly --dry-run

# 直接分析某個 YouTube 影片
python -m src.reading_agent --analyze-url <url>

# AI Weekly 蒐集
python -m src.reading_agent --ai-weekly

# 啟動 Telegram Bot（長駐 polling）
python -m src.reading_agent --bot

# 列出暢銷書
python -m src.reading_agent --list-books

# 列出追蹤頻道
python -m src.reading_agent --list-channels

# 新增自訂頻道
python -m src.reading_agent --add-channel <url>

# 測試 Telegram 連線
python -m src.reading_agent --test-telegram
```

### Telegram Bot 指令（需啟動 `--bot` 模式）

| 指令 | 用途 | 耗時 |
|------|------|------|
| `/start`、`/help` | 幫助 | 瞬間 |
| `/videos` | 列出最近蒐集影片 | 瞬間 |
| `/books` | 暢銷書排行榜 | 1-2 分 |
| `/channels` | 追蹤頻道列表 | 瞬間 |
| `/weekly` | 背景執行蒐集 | 5-10 分 |
| `/ai` | AI Weekly 蒐集 | 3-5 分 |
| `/collect` | 完整蒐集 + 通知 | 5-10 分 |
| `/add <url>` | 新增頻道 | 瞬間 |
| `/remove <名稱>` | 移除頻道 | 瞬間 |
| `/analyze <url>` | 分析影片 | 2-3 分 |
| `/discover` | 探索推薦頻道 | 2-3 分 |

---

## 環境變數清單

```bash
# Telegram（必需至少一組）
TELEGRAM_BOT_TOKEN=           # 舊版 Bot（通用）
TELEGRAM_CHAT_ID=             # 舊版 Chat ID

READING_BOT_TOKEN=            # 讀書 Agent 專用 Bot（優先）
READING_CHAT_ID=              # 讀書 Agent Chat ID

# Gemini
GEMINI_API_KEY=               # Google Gemini API Key（必需）

# YouTube（可選，預設免鑰）
YOUTUBE_API_KEY=              # YouTube API Key
```

---

## 配置檔案速查

### 讀書 Agent

| 檔案 | 位置 | 用途 |
|------|------|------|
| channels.json | data/reading_agent/ | 預設說書頻道列表 |
| custom_channels.json | data/reading_agent/ | 使用者自訂頻道 |
| ai_channels.json | data/reading_agent/ | AI Weekly 頻道列表 |
| discovered_sources.json | data/reading_agent/discovery/ | 來源探索候選 |
| videos/*.json | data/reading_agent/videos/ | 日期別影片快取（YYYY-MM-DD.json） |

---

## 資料結構一覽

### Book（暢銷書）
- title, author, language
- sources[], rank, isbn, cover_url, category
- collected_at

### Video（YouTube 影片）
- title, url, channel_name, channel_id, published_at
- description, category, video_id, thumbnail, duration_seconds
- **[v2 新增]** transcript, key_points_original, key_points_zh, language, book_title

### ReadingReport（報告）
- period_start, period_end, videos[], mode, generated_at
- 統計方法：total_count, channel_counts, category_counts

### DiscoveredSource（探索候選）
- name, url, source_type, category, language
- score, reason, status, discovered_at, metadata

---

## 常用開發工作流

### 1. 新增 Telegram 指令

**檔案**: src/reading_agent/telegram_bot_handler.py

```python
async def cmd_mycommand(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """新指令說明"""
    if not self._is_authorized(update):
        await update.message.reply_text("未授權的存取。")
        return

    # 實現邏輯
    await update.message.reply_text("回覆訊息")
```

在 `run()` 方法中註冊：
```python
app.add_handler(CommandHandler("mycommand", self.cmd_mycommand))
```

---

### 2. 修改暢銷書爬蟲

**檔案**: src/reading_agent/config.py

編輯 BESTSELLER_SOURCES 以新增或修改平台。

**檔案**: src/reading_agent/bestseller_scraper.py

實現 `async scrape_xxx()` 方法，並在 `scrape_all()` 中並行呼叫。

---

### 3. 調整 Gemini 分析

**檔案**: src/reading_agent/content_analyzer.py

編輯 Prompt 模板和 `_analyze_one()` 邏輯。

---

### 4. 擴展資料模型

**檔案**: src/reading_agent/models.py

新增 @dataclass 或欄位，記得實現 `to_dict()` / `from_dict()`。

---

## 效能優化提示

| 項目 | 建議 | 相關檔案 |
|------|------|---------|
| 爬蟲速度 | 調整 REQUEST_DELAY (預設 1.5 秒) | config.py |
| Gemini token 用量 | 考慮使用 gemini-1.5-flash，或調整分析深度 | content_analyzer.py |
| Telegram 發送速度 | 調整 TELEGRAM_SEND_DELAY (預設 1.5 秒) | config.py |
| YouTube 搜尋 | 考慮增加 MAX_SEARCH_RESULTS，或改用 API | youtube_searcher.py |
| 字幕擷取 | 升級 youtube_transcript_api | requirements.txt |

---

## 故障排除

| 症狀 | 可能原因 | 檢查項目 |
|------|--------|---------|
| "GEMINI_API_KEY 未設定" | 環境變數未載入 | .env 檔案 |
| "Bot 連線失敗" | Token 或 Chat ID 錯誤 | TELEGRAM_BOT_TOKEN / READING_BOT_TOKEN |
| "字幕擷取失敗" | 影片無字幕或 YouTubeTranscriptApi 版本不符 | youtube_transcript_api 版本 |
| "Gemini 分析超時" | API 限流或網路問題 | 增加 _BATCH_DELAY，檢查額度 |
| "爬蟲被限流" | 請求過於頻繁 | 增加 REQUEST_DELAY |

---

## 相關文件

- CLAUDE.md — 開發規則與 Agent 調度策略
- SECRETARY.md — 專案進度與版本管理
- requirements.txt — Python 依賴清單
- tests/ — 單元測試

---

## 貢獻指南

1. 開啟 Feature Branch
2. 閱讀相關 Codemap（本索引 + 詳細文件）
3. 新增程式碼 + 測試
4. 更新相關 Codemap 文件
5. Commit + Push + PR

**重要**: 所有新功能必須更新對應的 Codemap 文件。

---

**最後更新**: 2026-03-04
**Codemap 版本**: 1.0
**下一次計劃更新**: 加入 Japan Intel 與 Game 詳細 Codemap
