# 架構設計書 — Singer Agent（虛擬歌手 MV 自動產出系統）

> Phase 1: ARCHITECT 產出，需使用者確認後才進入開發計畫階段。
> 輸入：`docs/features/singer-agent/01_spec.md`

## 基本資訊

| 欄位 | 內容 |
|------|------|
| 功能名稱 | Singer Agent — 虛擬歌手 MV 自動產出系統 |
| 架構師 | architect agent |
| 建立日期 | 2026-03-06 |

## 系統架構總覽

```
┌─────────────────────────────────────────────────────────────────┐
│                        Entry Points                             │
│                                                                 │
│  python -m src.singer_agent          Telegram Bot               │
│       (cli.py)                       (bot.py)                   │
│         │                                │                      │
│         └──────────────┬─────────────────┘                      │
│                        │ PipelineRequest                        │
└────────────────────────┼────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    pipeline.py (Pipeline)                        │
│                                                                 │
│  progress_callback: Callable[[int, str], None]                  │
│  dry_run: bool                                                  │
│  queue: asyncio.Queue  (序列化，避免 GPU 衝突)                    │
│                                                                 │
│  Step 1 ──► Step 2 ──► Step 3 ──► Step 4                        │
│  researcher  song_spec  copywriter  background_gen              │
│                                                                 │
│  Step 5 ──► Step 6 ──► Step 7 ──► Step 8                        │
│  compositor  precheck  video_renderer  project_store            │
└─────────────────────────────────────────────────────────────────┘
         │               │               │               │
┌────────▼───────┐ ┌─────▼──────┐ ┌──────▼─────┐ ┌──────▼──────┐
│ ollama_client  │ │  src/llm/  │ │ path_utils │ │   config    │
│ (QWen3 14B)    │ │(Gemini 視覺)│ │(ASCII 路徑) │ │ (常數/路徑)  │
└────────────────┘ └────────────┘ └────────────┘ └─────────────┘
         │
┌────────▼────────────────────────────────────────────────────────┐
│                      Data Layer                                 │
│  models.py (SongSpec, ProjectState, PrecheckResult, CopySpec)   │
│  project_store.py  (JSON → data/singer_agent/projects/)         │
└─────────────────────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────────┐
│                   External Services                             │
│  Ollama:11434   ComfyUI:8188   SadTalker (subprocess)           │
│  FFmpeg (subprocess)   rembg (Python)   Gemini Vision API       │
└─────────────────────────────────────────────────────────────────┘
```

## 模組拆分

| 模組 | 檔案 | 職責 | 依賴 |
|------|------|------|------|
| Entry: CLI | `cli.py` | argparse 入口；--title, --artist, --audio, --dry-run, --auto, --list | pipeline, project_store, config |
| Entry: Bot | `bot.py` | Telegram Bot handler；授權閘門；接收 MP3 + caption；佇列管線 | pipeline, project_store, config |
| Entry: Main | `__main__.py` | `python -m src.singer_agent` 路由 | cli |
| Pipeline | `pipeline.py` | 8 步管線編排器；progress_callback 注入；dry_run 傳遞；例外捕獲不閃退 | 所有 step 模組 |
| Step 1 | `researcher.py` | Ollama/LLM 歌曲風格分析 → SongResearch | ollama_client, models |
| Step 2 | `song_spec.py` | metadata + SongResearch → SongSpec | models, project_store |
| Step 3 | `copywriter.py` | Ollama/LLM → YouTube title/description/tags | ollama_client, models |
| Step 4 | `background_gen.py` | ComfyUI SDXL 背景 / PIL 純色備援 | config, models, path_utils |
| Step 5 | `compositor.py` | rembg 去背 + PIL 合成（底部置中） | config, path_utils |
| Step 6 | `precheck.py` | 圖片/音訊/工具檢查 + Gemini Vision 選配 | src/llm, models |
| Step 7 | `video_renderer.py` | SadTalker subprocess / FFmpeg 靜態備援 | path_utils, config, models |
| Step 8 | `project_store.py` | ProjectState JSON 持久化 | models |
| Models | `models.py` | 所有 dataclass（無外部依賴） | 無 |
| Ollama | `ollama_client.py` | HTTP wrapper for Ollama /api/generate | requests |
| Path | `path_utils.py` | ASCII 暫存路徑（SadTalker 用） | config |
| Config | `config.py` | 路徑常數、工具路徑、env vars | pathlib, dotenv |

## 技術選型

| 決策 | 選擇 | 理由 | 替代方案 |
|------|------|------|---------|
| LLM（研究+文案） | Ollama QWen3 14B 本地 | 節省費用；速度快；已安裝 | src/llm/ 雲端（環境變數切換） |
| 圖片生成 | ComfyUI SDXL REST API | 已安裝；GPU 加速；1920×1080 | PIL 純色背景（降級方案） |
| 去背 | rembg U2-Net | Python native；效果好 | OpenCV 背景分割（精度差） |
| 圖片合成 | Pillow PIL | 穩定；依賴少；RGBA 支援 | OpenCV（過重） |
| 對嘴動畫 | SadTalker subprocess | 已安裝；GPU CUDA | FFmpeg 靜態迴圈（降級方案） |
| 影片備援 | FFmpeg subprocess | 已安裝；跨平台 | moviepy（依賴鏈複雜） |
| Bot | python-telegram-bot v20+ | async 支援；文件完整 | Telethon（過重） |
| 視覺審查 | Gemini Vision API 選配 | 多模態評估搭配度 | CLIP（需額外模型） |
| 狀態持久化 | JSON 檔案 | 零依賴；簡單可讀 | SQLite（overkill） |
| 非 ASCII 路徑 | 暫存 ASCII 路徑 + 複製回 | 最低侵入性 | 修改 SadTalker（不可行） |

## 介面定義

### models.py — 核心資料結構

```python
@dataclass(frozen=True)
class SongResearch:
    genre: str                     # "ballad"
    mood: str                      # "romantic, nostalgic"
    visual_style: str              # "Pastel Watercolor"
    color_palette: list[str]       # ["soft_pink", "light_blue"]
    background_prompt: str         # SDXL 英文提示詞
    outfit_prompt: str             # 服裝描述（未來 F-11）
    scene_description: str         # 繁中場景描述
    research_summary: str          # 繁中研究摘要

@dataclass
class SongSpec:
    title: str
    artist: str
    language: str
    research: SongResearch
    created_at: str
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "SongSpec": ...

@dataclass(frozen=True)
class CopySpec:
    title: str
    description: str
    tags: list[str]

@dataclass(frozen=True)
class PrecheckResult:
    passed: bool
    checks: dict[str, bool]
    warnings: list[str]
    gemini_score: int | None
    gemini_feedback: str

@dataclass
class ProjectState:
    project_id: str
    source_audio: str
    status: str                    # "running" | "completed" | "failed"
    metadata: dict
    song_spec: SongSpec | None
    copy_spec: CopySpec | None
    background_image: str
    composite_image: str
    precheck_result: PrecheckResult | None
    final_video: str
    render_mode: str               # "sadtalker" | "ffmpeg_static"
    error_message: str
    created_at: str
    completed_at: str
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "ProjectState": ...
```

### pipeline.py — 管線編排器

```python
ProgressCallback = Callable[[int, str], None]

@dataclass
class PipelineRequest:
    audio_path: Path
    title: str
    artist: str
    language: str = ""
    genre_hint: str = ""
    mood_hint: str = ""
    notes: str = ""

class Pipeline:
    def __init__(self, character_image: Path,
                 progress_callback: ProgressCallback | None = None,
                 dry_run: bool = False) -> None: ...

    def run(self, request: PipelineRequest) -> ProjectState:
        """同步 8 步管線。任何步驟例外被捕獲，不閃退。"""

    async def arun(self, request: PipelineRequest) -> ProjectState:
        """非同步版本，供 Telegram Bot 使用。"""
```

### 各步驟模組核心介面

```python
# researcher.py
class SongResearcher:
    def research(self, title, artist, ..., dry_run=False) -> SongResearch: ...

# background_gen.py
class BackgroundGenerator:
    def generate(self, prompt, output_path, dry_run=False) -> Path: ...

# compositor.py
class Compositor:
    def remove_background(self, character_path, output_path, dry_run=False) -> Path: ...
    def composite(self, background_path, character_nobg_path, output_path, ...) -> Path: ...

# precheck.py
class QualityPrecheck:
    def run(self, composite_image, audio_path, song_spec, dry_run=False) -> PrecheckResult: ...

# video_renderer.py
class VideoRenderer:
    def render(self, composite_image, audio_path, output_path, dry_run=False) -> tuple[Path, str]: ...

# ollama_client.py
class OllamaClient:
    def generate(self, prompt, **kwargs) -> str: ...
    def is_available(self) -> bool: ...

# project_store.py
class ProjectStore:
    def save(self, state: ProjectState) -> Path: ...
    def load(self, project_id: str) -> ProjectState: ...
    def list_projects(self) -> list[ProjectState]: ...
```

## 資料流

```
使用者（Telegram / CLI）
  │ PipelineRequest(audio_path, title, artist, ...)
  ▼
Pipeline.run()
  ├─ Step 1: researcher.research() → SongResearch
  ├─ Step 2: song_spec.build() → SongSpec → specs/<id>.json
  ├─ Step 3: copywriter.write() → CopySpec
  ├─ Step 4: background_gen.generate() → backgrounds/<id>.png
  │          [降級] PIL 純色背景
  ├─ Step 5: compositor.remove_bg() + composite() → composites/<id>.png
  ├─ Step 6: precheck.run() → PrecheckResult
  │          passed=False → status="failed" + 錯誤訊息
  ├─ Step 7: video_renderer.render() → videos/<id>.mp4
  │          [降級] FFmpeg 靜態模式
  └─ Step 8: project_store.save() → projects/<id>.json
             status="completed"
```

## 風險評估

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| Ollama 未啟動 | Step 1/3 失敗 | is_available() 前置檢查；錯誤訊息含 `ollama serve` 指令；中止不閃退 |
| ComfyUI 超時/離線 | Step 4 無背景 | 自動降級 PIL 純色（AC-5）；超時 120s |
| SadTalker 失敗 | Step 7 無影片 | ASCII 暫存路徑 → 捕獲 subprocess → 降級 FFmpeg（AC-9） |
| 非 ASCII 路徑 | SadTalker 崩潰 | path_utils 集中處理（AC-14） |
| 多個 MP3 同時觸發 | GPU OOM | asyncio.Queue 序列化；回覆「排隊中」 |
| Gemini 無 Key | Step 6 審查跳過 | 偵測 key 存在；無則跳過不影響 passed |
| 磁碟空間不足 | Step 7 寫檔失敗 | precheck 加入空間檢查（> 5GB） |
| MP3 損壞 | Step 7 失敗 | precheck 用 ffprobe 驗證格式 |

## 架構決策記錄

### ADR-001: Pipeline 以 ProjectState 貫穿所有步驟
- 單一可變物件傳遞，每步更新欄位
- 任何步驟失敗都能保存已完成部分

### ADR-002: OllamaClient 獨立模組，不重用 src/llm/
- src/llm/ 需 API key，不支援 Ollama 無 key 模式
- 環境變數 SINGER_LLM_PROVIDER 可切換雲端 LLM

### ADR-003: Telegram Bot 用 asyncio.Queue 序列化管線
- 避免多個 SadTalker 並行競爭 VRAM
- 使用者收到排隊順序回饋

## 目錄結構

```
src/singer_agent/
├── __init__.py
├── __main__.py          # python -m src.singer_agent 入口
├── cli.py               # argparse CLI
├── bot.py               # Telegram Bot handlers
├── pipeline.py          # 8 步管線編排器
├── models.py            # 所有 dataclass
├── config.py            # 路徑常數、env vars
├── ollama_client.py     # Ollama HTTP wrapper
├── path_utils.py        # ASCII 暫存路徑工具
├── project_store.py     # JSON 持久化
├── researcher.py        # Step 1: 歌曲研究
├── song_spec.py         # Step 2: SongSpec 建立
├── copywriter.py        # Step 3: YouTube 文案
├── background_gen.py    # Step 4: 背景生成
├── compositor.py        # Step 5: 去背 + 合成
├── precheck.py          # Step 6: 品質預檢
└── video_renderer.py    # Step 7: 影片合成
```

---

**使用者確認：** [ ] 已確認架構設計，可進入 Phase 2 開發計畫階段
