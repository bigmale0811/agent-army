# 開發計畫

> 本文件由 Phase 2: PLAN 產出，需使用者確認後才進入開發階段。
> 輸入：`01_spec.md` + `02_architecture.md`

## 基本資訊

| 欄位 | 內容 |
|------|------|
| 功能名稱 | Singer Agent — 虛擬歌手 MV 自動產出系統 |
| 企劃 | planner agent |
| 建立日期 | 2026-03-06 |
| 預估開發項目數 | 14 項 |

## 開發項目

### DEV-1: 資料模型（models.py）

| 欄位 | 內容 |
|------|------|
| 說明 | 定義所有核心 dataclass：SongResearch、SongSpec、CopySpec、PrecheckResult、ProjectState、PipelineRequest。包含 to_dict() / from_dict() 序列化。frozen dataclass（不可變）。無外部依賴。 |
| 涉及檔案 | `src/singer_agent/models.py`、`src/singer_agent/__init__.py`、`tests/singer_agent/test_models.py` |
| 依賴 | 無（第一個開發） |
| 驗收標準 | AC-2, AC-3, AC-7, AC-13 |

### DEV-2: 設定模組（config.py）

| 欄位 | 內容 |
|------|------|
| 說明 | 路徑常數（DATA_DIR 等）、工具路徑（SadTalker、FFmpeg、ComfyUI URL）、環境變數讀取（TELEGRAM_BOT_TOKEN 等）。python-dotenv 載入 .env。 |
| 涉及檔案 | `src/singer_agent/config.py`、`tests/singer_agent/test_config.py` |
| 依賴 | 無（與 DEV-1 平行） |
| 驗收標準 | AC-1, AC-14 |

### DEV-3: 路徑工具（path_utils.py）

| 欄位 | 內容 |
|------|------|
| 說明 | to_ascii_temp()（非 ASCII → 暫存 ASCII 路徑）、cleanup_temp()、ensure_dir()、safe_stem()（中文歌名轉安全檔名） |
| 涉及檔案 | `src/singer_agent/path_utils.py`、`tests/singer_agent/test_path_utils.py` |
| 依賴 | DEV-2 |
| 驗收標準 | AC-14 |

### DEV-4: Ollama 客戶端（ollama_client.py）

| 欄位 | 內容 |
|------|------|
| 說明 | OllamaClient：generate()、is_available()、chat()。HTTP timeout、OllamaUnavailableError。 |
| 涉及檔案 | `src/singer_agent/ollama_client.py`、`tests/singer_agent/test_ollama_client.py` |
| 依賴 | DEV-2 |
| 驗收標準 | AC-12 |

### DEV-5: 專案儲存（project_store.py）

| 欄位 | 內容 |
|------|------|
| 說明 | ProjectStore：save()、load()、list_projects()。JSON 持久化，UTF-8 編碼。 |
| 涉及檔案 | `src/singer_agent/project_store.py`、`tests/singer_agent/test_project_store.py` |
| 依賴 | DEV-1, DEV-2 |
| 驗收標準 | AC-13, AC-14 |

### DEV-6: 歌曲研究（researcher.py）

| 欄位 | 內容 |
|------|------|
| 說明 | SongResearcher.research() → SongResearch。結構化 prompt、JSON schema 驗證、dry_run stub。 |
| 涉及檔案 | `src/singer_agent/researcher.py`、`tests/singer_agent/test_researcher.py` |
| 依賴 | DEV-1, DEV-4 |
| 驗收標準 | AC-2, AC-12 |

### DEV-7: 文案產出（copywriter.py）

| 欄位 | 內容 |
|------|------|
| 說明 | Copywriter.write() → CopySpec。YouTube 標題/描述/tags、dry_run stub。 |
| 涉及檔案 | `src/singer_agent/copywriter.py`、`tests/singer_agent/test_copywriter.py` |
| 依賴 | DEV-1, DEV-4 |
| 驗收標準 | AC-3 |

### DEV-8: 背景生成（background_gen.py）

| 欄位 | 內容 |
|------|------|
| 說明 | BackgroundGenerator.generate()。ComfyUI SDXL 主路徑 + PIL 純色降級。1920×1080。 |
| 涉及檔案 | `src/singer_agent/background_gen.py`、`tests/singer_agent/test_background_gen.py` |
| 依賴 | DEV-2, DEV-3 |
| 驗收標準 | AC-4, AC-5 |

### DEV-9: 角色合成（compositor.py）

| 欄位 | 內容 |
|------|------|
| 說明 | Compositor：remove_background()（rembg 去背 RGBA）+ composite()（PIL 底部置中）。 |
| 涉及檔案 | `src/singer_agent/compositor.py`、`tests/singer_agent/test_compositor.py` |
| 依賴 | DEV-2, DEV-3 |
| 驗收標準 | AC-6 |

### DEV-10: 品質預檢（precheck.py）

| 欄位 | 內容 |
|------|------|
| 說明 | QualityPrecheck.run() → PrecheckResult。圖片/音訊/磁碟/SadTalker/FFmpeg 檢查 + Gemini 選配。 |
| 涉及檔案 | `src/singer_agent/precheck.py`、`tests/singer_agent/test_precheck.py` |
| 依賴 | DEV-1, DEV-2, DEV-3 |
| 驗收標準 | AC-7, AC-12 |

### DEV-11: 影片合成（video_renderer.py）

| 欄位 | 內容 |
|------|------|
| 說明 | VideoRenderer.render() → (Path, render_mode)。SadTalker + ASCII 暫存路徑 / FFmpeg 降級。 |
| 涉及檔案 | `src/singer_agent/video_renderer.py`、`tests/singer_agent/test_video_renderer.py` |
| 依賴 | DEV-2, DEV-3 |
| 驗收標準 | AC-8, AC-9, AC-14 |

### DEV-12: 管線編排器（pipeline.py）

| 欄位 | 內容 |
|------|------|
| 說明 | Pipeline.run() 同步 8 步 + arun() 非同步。progress_callback 注入。try/except 不閃退。song_spec 建構整合。 |
| 涉及檔案 | `src/singer_agent/pipeline.py`、`src/singer_agent/song_spec.py`、`tests/singer_agent/test_pipeline.py` |
| 依賴 | DEV-1 ~ DEV-11 全部 |
| 驗收標準 | AC-1, AC-8, AC-12, AC-13 |

### DEV-13: CLI 入口點（cli.py + __main__.py）

| 欄位 | 內容 |
|------|------|
| 說明 | argparse：--title, --artist, --audio, --dry-run, --auto, --list。呼叫 Pipeline.run()。 |
| 涉及檔案 | `src/singer_agent/cli.py`、`src/singer_agent/__main__.py`、`tests/singer_agent/test_cli.py` |
| 依賴 | DEV-12, DEV-5 |
| 驗收標準 | AC-1, AC-13 |

### DEV-14: Telegram Bot 入口點（bot.py）

| 欄位 | 內容 |
|------|------|
| 說明 | python-telegram-bot v20+ async。授權閘門、MP3 handler、asyncio.Queue 佇列、進度回調。 |
| 涉及檔案 | `src/singer_agent/bot.py`、`tests/singer_agent/test_bot.py` |
| 依賴 | DEV-12, DEV-5 |
| 驗收標準 | AC-10, AC-11, AC-12 |

## 開發順序

```
批次 A（平行，無依賴）：
  DEV-1 (models)  ║  DEV-2 (config)

批次 B（依賴批次 A）：
  DEV-3 (path_utils)  ║  DEV-4 (ollama)  ║  DEV-5 (project_store)

批次 C（平行，依賴批次 A+B）：
  DEV-6 (researcher)  ║  DEV-7 (copywriter)  ║  DEV-8 (background_gen)
  DEV-9 (compositor)  ║  DEV-10 (precheck)   ║  DEV-11 (video_renderer)

批次 D（等批次 C 全部完成）：
  DEV-12 (pipeline)

批次 E（平行，依賴 DEV-12）：
  DEV-13 (cli)  ║  DEV-14 (bot)
```

### 建議執行順序（循序）

```
DEV-1 → DEV-2 → DEV-3 → DEV-4 → DEV-5
→ DEV-6 → DEV-7 → DEV-8 → DEV-9 → DEV-10
→ DEV-11 → DEV-12 → DEV-13 → DEV-14
```

## 測試策略

| 層級 | 涵蓋範圍 | 目標覆蓋率 | 工具 |
|------|---------|-----------|------|
| 單元測試 | 每個模組核心函式（mock 外部依賴） | 80%+ | pytest + unittest.mock |
| 整合測試 | FFmpeg 靜態合成、PIL 圖片、JSON 持久化 | 80%+ | pytest + tmp_path |
| E2E 測試 | --dry-run --auto 全流程 | 所有 AC | subprocess.run |

### AC 對應表

| AC | 測試類型 | 測試模組 |
|----|---------|---------|
| AC-1 | E2E | test_cli.py |
| AC-2 | 單元 | test_researcher.py |
| AC-3 | 單元 | test_copywriter.py |
| AC-4 | 整合 | test_background_gen.py |
| AC-5 | 單元 | test_background_gen.py |
| AC-6 | 單元 | test_compositor.py |
| AC-7 | 單元 | test_precheck.py |
| AC-8 | 整合 | test_video_renderer.py |
| AC-9 | 單元 | test_video_renderer.py |
| AC-10 | E2E | test_bot.py |
| AC-11 | E2E | test_bot.py |
| AC-12 | E2E | test_pipeline.py |
| AC-13 | 單元 | test_project_store.py + test_cli.py |
| AC-14 | 整合 | test_path_utils.py + test_video_renderer.py |

## 測試檔案結構

```
tests/singer_agent/
├── conftest.py           # 共用 fixtures（tmp_path, stub MP3, stub PNG）
├── test_models.py        # DEV-1
├── test_config.py        # DEV-2
├── test_path_utils.py    # DEV-3
├── test_ollama_client.py # DEV-4
├── test_project_store.py # DEV-5
├── test_researcher.py    # DEV-6
├── test_copywriter.py    # DEV-7
├── test_background_gen.py# DEV-8
├── test_compositor.py    # DEV-9
├── test_precheck.py      # DEV-10
├── test_video_renderer.py# DEV-11
├── test_pipeline.py      # DEV-12
├── test_cli.py           # DEV-13（含 E2E subprocess）
└── test_bot.py           # DEV-14
```

## 風險與依賴

| 項目 | 風險 | 應對 |
|------|------|------|
| DEV-8 | ComfyUI workflow JSON schema 複雜 | 先 mock TDD，整合測試標記 @pytest.mark.integration |
| DEV-9 | rembg 首次需下載 U2-Net 模型 170MB | dry_run 不呼叫 rembg；CI 用 mock |
| DEV-11 | SadTalker subprocess 介面須確認 | 整合標記 @pytest.mark.sadtalker；先實作 FFmpeg 降級 |
| DEV-12 | 8 步串接邊界條件多 | 全部 mock 做單元測試 |
| DEV-14 | Telegram API token 需真實申請 | mock Telegram；E2E 標記 @pytest.mark.telegram |
| DEV-6/7 | Ollama JSON 回傳不穩定 | retry 3 次 + fallback stub |

---

**使用者確認：** [ ] 已確認開發計畫，可進入開發階段
