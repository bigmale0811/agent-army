# 架構設計：老虎機遊戲 Clone & 生產線工具

> **Feature**: slot-clone-pipeline
> **Stage**: 🟡 Stage 2 架構設計
> **日期**: 2026-03-12
> **設計者**: Architect Agent (Opus)

---

## 1. 系統架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLI 入口 (Click)                           │
│              python -m slot_cloner clone <URL> --name <NAME>    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Pipeline Orchestrator                         │
│              (狀態機 + 斷點續傳 + 進度回報)                       │
│                                                                  │
│  Phase 1        Phase 2        Phase 3        Phase 4   Phase 5 │
│  ┌────────┐   ┌──────────┐   ┌──────────┐   ┌──────┐  ┌─────┐ │
│  │ Recon  │──▶│  Asset   │──▶│ Reverse  │──▶│Report│─▶│Build│ │
│  │ Engine │   │ Scraper  │   │ Engine   │   │      │  │     │ │
│  └────────┘   └──────────┘   └──────────┘   └──────┘  └─────┘ │
│       │            │              │                        │     │
│       ▼            ▼              ▼                        ▼     │
│  [偵察結果]   [資源檔案]     [遊戲模型]              [HTML5遊戲] │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Plugin Registry │ ← ATG Adapter (首先實作)
              │  (Adapter 模式) │ ← PG Soft Adapter (未來)
              │                 │ ← Pragmatic Adapter (未來)
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Game Models    │ ← Pydantic v2 (frozen=True)
              │  (不可變資料)    │ ← 跨模組共用
              └─────────────────┘
```

---

## 2. 核心設計決策

### 2.1 Pipeline 架構（5 Phase）

整個 Clone 流程拆分為 5 個獨立 Phase，每個 Phase 是獨立模組，透過 `PipelineContext` 傳遞資料：

| Phase | 模組 | 輸入 | 輸出 |
|-------|------|------|------|
| 1. Recon | 偵察引擎 | URL | 遊戲技術指紋、框架辨識 |
| 2. Scrape | 資源擷取 | 偵察結果 | 圖片/音效/Sprite 檔案 |
| 3. Reverse | 逆向分析 | 資源 + 網路攔截 | 賠率表/規則/符號定義 |
| 4. Report | 報告產出 | 逆向結果 | Markdown 分析報告 |
| 5. Build | 遊戲重建 | 資源 + 規則 | 可運行的 HTML5 遊戲 |

**關鍵特性**：支援**斷點續傳** — 任何 Phase 失敗後可從 checkpoint 恢復，不需重頭來過。

### 2.2 Plugin/Adapter 模式

不同遊戲商（ATG、PG Soft、Pragmatic Play）使用不同技術架構：

```
slot_cloner/plugins/
├── base.py           # BaseAdapter 抽象類別
├── registry.py       # Plugin 自動發現 + 註冊
├── atg/              # ATG Adapter（首先實作）
│   ├── adapter.py
│   ├── recon.py      # ATG 特有偵察邏輯
│   ├── scraper.py    # ATG 資源擷取策略
│   └── reverse.py    # ATG 逆向分析策略
└── generic/          # 通用 Adapter（兜底）
    └── adapter.py
```

新增遊戲商支援只需新增 Adapter 資料夾，零核心修改。

### 2.3 多層逆向策略

逆向引擎不依賴單一策略，而是 **4 層遞降**：

```
Layer 1: 設定檔直接解析 → 遊戲配置 JSON（如有暴露）
    ↓ 失敗
Layer 2: WebSocket 攔截 → 瀏覽器 JS 上下文攔截（解密後明文）
    ↓ 失敗
Layer 3: JS 靜態分析 → AST 解析 + 關鍵函數搜索
    ↓ 失敗
Layer 4: 視覺 OCR 分析 → 截圖 + Tesseract OCR
```

報告中會標注每項資料的**分析可信度**（HIGH/MEDIUM/LOW）。

### 2.4 Config 驅動遊戲引擎

遊戲重建**不是「產生程式碼」**，而是：
- 預建 PixiJS 引擎（開發一次，所有 Clone 共用）
- `game-config.json` 驅動遊戲行為
- 未來換皮只需修改 config + 替換資源

```json
{
  "game": {
    "type": "cascade",
    "grid": { "cols": 6, "rows": 5 },
    "symbols": [...],
    "paytable": {...},
    "features": {
      "wild": { "substitutes": "all_except_scatter" },
      "scatter": { "trigger": 4, "reward": "free_spin" },
      "cascade": { "enabled": true },
      "multiplier": { "values": [2, 3, 5, 10, 25, 50, 100, 500] }
    }
  }
}
```

### 2.5 不可變資料模型

所有跨模組資料模型使用 Pydantic v2 `frozen=True`：

```python
class GameConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    game_type: GameType  # cascade | classic | ways
    grid: GridConfig
    symbols: tuple[SymbolConfig, ...]
    paytable: PaytableConfig
    features: FeaturesConfig
```

每個 Phase 回傳新的 context，不修改原有物件。

---

## 3. 模組詳細設計

### 3.1 模組總覽（13 個模組）

| # | 模組 | Python 路徑 | 核心技術 | 職責 |
|---|------|-------------|----------|------|
| 1 | CLI | `slot_cloner.cli` | Click | 命令列入口 |
| 2 | Orchestrator | `slot_cloner.pipeline` | State Machine | Pipeline 調度 + 狀態管理 |
| 3 | Recon Engine | `slot_cloner.recon` | Playwright | 遊戲偵察 + 技術指紋 |
| 4 | Asset Scraper | `slot_cloner.scraper` | Playwright Route | 資源攔截 + 下載 |
| 5 | Reverse Engine | `slot_cloner.reverse` | 多策略 | 遊戲邏輯逆向 |
| 6 | Report Builder | `slot_cloner.report` | Jinja2 | 分析報告產出 |
| 7 | Game Builder | `slot_cloner.builder` | Subprocess(Vite) | 遊戲專案建置 |
| 8 | Plugin Registry | `slot_cloner.plugins` | Adapter Pattern | 遊戲商適配器管理 |
| 9 | Game Models | `slot_cloner.models` | Pydantic v2 | 不可變資料模型 |
| 10 | Storage Manager | `slot_cloner.storage` | pathlib | 檔案管理 + 目錄結構 |
| 11 | Progress Reporter | `slot_cloner.progress` | Rich | 進度條 + 狀態回報 |
| 12 | Config Manager | `slot_cloner.config` | YAML | 工具設定管理 |
| 13 | Utils | `slot_cloner.utils` | Various | 圖片處理/JS 美化/Hash |

### 3.2 資料流

```
URL ──→ [Recon] ──→ GameFingerprint
              │         ├── framework: "pixi" | "phaser" | "cocos"
              │         ├── provider: "atg" | "pg_soft" | "unknown"
              │         ├── game_type: "cascade" | "classic" | "ways"
              │         └── endpoints: WebSocket URLs
              │
              ▼
         [Scraper] ──→ AssetBundle
              │         ├── images: Dict[str, ImageAsset]
              │         ├── sprites: Dict[str, SpriteSheet]
              │         ├── audio: Dict[str, AudioAsset]
              │         └── raw_configs: Dict[str, Any]
              │
              ▼
         [Reverse] ──→ GameModel
              │         ├── config: GameConfig (paytable, rules...)
              │         ├── symbols: List[Symbol]
              │         ├── features: Features (wild, scatter, bonus...)
              │         ├── confidence: Dict[str, ConfidenceLevel]
              │         └── raw_ws_messages: List[WSMessage]
              │
              ├──→ [Report] ──→ report.md + paytable.json + screenshots/
              │
              └──→ [Builder] ──→ game/
                                  ├── index.html
                                  ├── game-config.json
                                  └── dist/ (PixiJS 編譯產出)
```

---

## 4. 介面定義

### 4.1 BaseAdapter（Plugin 介面）

```python
class BaseAdapter(ABC):
    """遊戲商適配器基礎類別"""

    @staticmethod
    @abstractmethod
    def can_handle(url: str, fingerprint: GameFingerprint) -> bool:
        """判斷此 Adapter 是否能處理該遊戲"""

    @abstractmethod
    async def recon(self, page: Page) -> GameFingerprint:
        """偵察遊戲技術指紋"""

    @abstractmethod
    async def scrape(self, page: Page, fingerprint: GameFingerprint) -> AssetBundle:
        """擷取遊戲資源"""

    @abstractmethod
    async def reverse(self, page: Page, assets: AssetBundle) -> GameModel:
        """逆向分析遊戲邏輯"""
```

### 4.2 Pipeline Context

```python
class PipelineContext(BaseModel):
    """Pipeline 各 Phase 間傳遞的不可變上下文"""
    model_config = ConfigDict(frozen=True)

    url: str
    game_name: str
    output_dir: Path
    fingerprint: GameFingerprint | None = None
    assets: AssetBundle | None = None
    game_model: GameModel | None = None
    checkpoint: PipelinePhase = PipelinePhase.INIT
```

### 4.3 CLI 介面

```bash
# 基本用法
python -m slot_cloner clone <URL> --name <NAME>

# 進階選項
python -m slot_cloner clone <URL> --name <NAME> \
    --output ./output \
    --skip-build \           # 跳過遊戲重建（只要資源+報告）
    --resume \               # 從上次斷點續傳
    --adapter atg \          # 強制指定 Adapter
    --phases recon,scrape    # 只執行指定 Phase
```

---

## 5. 目錄結構

### 5.1 Python 套件（Clone 工具）

```
src/slot_cloner/
├── __init__.py
├── __main__.py              # python -m slot_cloner 入口
├── cli.py                   # Click CLI 定義
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py      # Pipeline 主控
│   ├── context.py           # PipelineContext
│   └── checkpoint.py        # 斷點管理
├── recon/
│   ├── __init__.py
│   ├── engine.py            # 偵察主引擎
│   └── fingerprint.py       # 技術指紋辨識
├── scraper/
│   ├── __init__.py
│   ├── engine.py            # 資源擷取主引擎
│   ├── interceptor.py       # Network 攔截器
│   ├── sprite_splitter.py   # Sprite Sheet 拆解
│   └── audio_extractor.py   # 音效擷取
├── reverse/
│   ├── __init__.py
│   ├── engine.py            # 逆向主引擎
│   ├── ws_analyzer.py       # WebSocket 分析
│   ├── js_analyzer.py       # JS 靜態分析
│   ├── visual_analyzer.py   # 視覺 OCR 分析
│   └── paytable_parser.py   # 賠率表解析
├── report/
│   ├── __init__.py
│   ├── builder.py           # 報告產生器
│   └── templates/           # Jinja2 模板
│       ├── report.md.j2
│       └── paytable.md.j2
├── builder/
│   ├── __init__.py
│   ├── engine.py            # 遊戲建置引擎
│   ├── config_generator.py  # game-config.json 產生
│   └── template/            # PixiJS 遊戲模板
│       └── (見 5.2)
├── plugins/
│   ├── __init__.py
│   ├── base.py              # BaseAdapter ABC
│   ├── registry.py          # Plugin 自動發現
│   ├── atg/                 # ATG 適配器
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── recon.py
│   │   ├── scraper.py
│   │   └── reverse.py
│   └── generic/             # 通用兜底
│       ├── __init__.py
│       └── adapter.py
├── models/
│   ├── __init__.py
│   ├── game.py              # GameConfig, GameModel
│   ├── symbol.py            # SymbolConfig, PaytableEntry
│   ├── feature.py           # WildConfig, ScatterConfig, CascadeConfig
│   └── asset.py             # AssetBundle, ImageAsset, AudioAsset
├── storage/
│   ├── __init__.py
│   └── manager.py           # 輸出目錄管理
├── progress/
│   ├── __init__.py
│   └── reporter.py          # Rich 進度條
├── config/
│   ├── __init__.py
│   └── settings.py          # 工具設定
└── utils/
    ├── __init__.py
    ├── image.py              # Pillow 圖片處理
    ├── js.py                 # JS 美化/分析
    └── hash.py               # 檔案 Hash
```

### 5.2 TypeScript 遊戲引擎（PixiJS v8）

```
src/slot_cloner/builder/template/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.ts              # 入口
│   ├── Game.ts              # 主遊戲類別（讀取 config 驅動）
│   ├── core/
│   │   ├── Engine.ts        # PixiJS Application 封裝
│   │   ├── AssetLoader.ts   # 資源載入器
│   │   └── SoundManager.ts  # 音效管理
│   ├── slot/
│   │   ├── Grid.ts          # 棋盤/滾輪
│   │   ├── Symbol.ts        # 符號元件
│   │   ├── Reel.ts          # 單軸滾輪（傳統模式用）
│   │   └── CascadeGrid.ts   # 消除模式棋盤
│   ├── features/
│   │   ├── WildFeature.ts   # Wild 替代
│   │   ├── ScatterFeature.ts # Scatter 觸發
│   │   ├── CascadeFeature.ts # 消除掉落
│   │   ├── MultiplierFeature.ts # 乘數系統
│   │   └── FreeSpinFeature.ts   # Free Spin
│   ├── math/
│   │   ├── RNG.ts           # 加密安全隨機數
│   │   ├── PaytableEngine.ts # 賠率計算
│   │   └── Simulator.ts     # Monte Carlo RTP 模擬
│   ├── ui/
│   │   ├── HUD.ts           # 餘額/投注/獎金 UI
│   │   ├── SpinButton.ts    # 旋轉按鈕
│   │   └── PaytableView.ts  # 賠率表檢視
│   └── animation/
│       ├── WinAnimation.ts  # 中獎動畫
│       └── BigWinAnimation.ts # 大獎動畫
└── game-config.json          # 由 Python 工具產生
```

---

## 6. 技術選型理由

| 技術 | 選擇 | 理由 |
|------|------|------|
| 瀏覽器自動化 | **Playwright** > Selenium | 原生 WebSocket 攔截 + Network Route，逆向分析的命脈 |
| 遊戲引擎 | **PixiJS v8** > Phaser/Cocos | 老虎機是純 2D，不需物理引擎；包體最小 (~150KB)；業界老虎機大量使用 |
| CLI 框架 | **Click** > argparse | 子命令、參數驗證、自動 help 更完善 |
| 資料模型 | **Pydantic v2** | frozen=True 不可變、自動驗證、JSON 序列化 |
| 進度回報 | **Rich** | 美觀進度條、表格、Panel 輸出 |
| 報告模板 | **Jinja2** | Markdown 模板渲染，支援迴圈/條件 |
| 前端建置 | **Vite** | TypeScript 編譯快、HMR 開發體驗好 |
| Sprite 拆解 | **Pillow** | Python 圖片處理標準庫 |

---

## 7. 風險評估

| 風險 | 等級 | 影響 | 緩解措施 |
|------|------|------|---------|
| **R1: JS 混淆** | 🔴 HIGH | ATG 幾乎一定混淆 | 多層策略，不依賴 JS 分析；優先用 WS 攔截 |
| **R2: WS 加密** | 🟡 MEDIUM | 無法讀取遊戲配置 | 在瀏覽器 JS 上下文攔截（解密後明文） |
| **R3: Canvas 渲染** | 🟡 MEDIUM | 圖片合成到 Canvas 無法擷取 | 攔截 Image/Texture 載入請求（Network 層） |
| **R4: Server-Side Logic** | 🔴 HIGH | 核心邏輯在伺服器 | Clone 模擬表現層 + 本地 RNG 模擬結果 |
| **R5: 反爬蟲** | 🟡 MEDIUM | Token 過期/IP 封鎖 | 使用真實瀏覽器（Playwright）+ 合理延遲 |
| **R6: 框架多樣性** | 🟡 MEDIUM | 不同遊戲商技術迥異 | Plugin 架構 + Generic Adapter 兜底 |

---

## 8. 擴展預留（Phase 2 換皮工具）

架構已預留以下擴展點：

1. **Config 驅動**：遊戲行為全由 `game-config.json` 控制，換皮只需改 config
2. **Asset Mapping**：`theme-config.json` 定義符號圖映射，批量替換
3. **Paytable Editor**：修改賠率表 → Monte Carlo 驗算新 RTP
4. **Theme CLI**：`python -m slot_cloner reskin <source> --theme <theme-dir>`

---

## 9. 依賴清單

### Python (Clone 工具)
```
playwright>=1.40
pydantic>=2.0
click>=8.0
rich>=13.0
jinja2>=3.0
pillow>=10.0
jsbeautifier>=1.14
pyyaml>=6.0
```

### Node.js (遊戲引擎)
```
pixi.js: ^8.0
vite: ^5.0
typescript: ^5.0
@pixi/sound: ^6.0
```
