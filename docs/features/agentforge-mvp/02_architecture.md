# AgentForge MVP — 架構設計文件

> **FSM Stage 2 產出** | 版本：v1.0 | 日期：2026-03-17
> 狀態：待 CEO 確認

---

## 1. 系統總覽

### 1.1 一句話定位

AgentForge 是一個 6 層架構的 CLI 工具 + Python SDK，讓企業用 YAML 定義 AI Agent，用一行指令執行，自帶三級自動修復。

### 1.2 架構總覽圖

```
┌──────────────────────────────────────────────────────────────────┐
│                      AgentForge 6 層架構                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 1: CLI（Click）                                     │   │
│  │  agentforge init / run / status / list / version           │   │
│  │  入口點：__main__.py → cli/main.py                         │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │  Layer 2: Schema（Pydantic v2）                            │   │
│  │  AgentDef / StepDef / GlobalConfig / ModelRef              │   │
│  │  YAML 解析 + 驗證 + 不可變資料模型                          │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │  Layer 3: Core（Engine + Failure + TaskTracker）           │   │
│  │  ┌─────────────┐ ┌───────────────┐ ┌──────────────┐      │   │
│  │  │ PipelineEngine│ │ FailureHandler│ │ TaskTracker   │      │   │
│  │  │（步驟編排）   │ │（三級修復）    │ │（SQLite 追蹤）│      │   │
│  │  └──────┬──────┘ └───────┬───────┘ └──────┬───────┘      │   │
│  └─────────┼───────────────┼────────────────┼───────────────┘   │
│            │               │                │                    │
│  ┌─────────▼───────────────▼────────────────▼───────────────┐   │
│  │  Layer 4: LLM（Router + Budget + Providers）              │   │
│  │  ┌──────────┐ ┌──────────────┐ ┌───────────────────────┐ │   │
│  │  │ LLMRouter │ │ BudgetTracker│ │ Providers             │ │   │
│  │  │（模型路由）│ │（成本追蹤）  │ │ OpenAI│Ollama│Gemini  │ │   │
│  │  └──────────┘ └──────────────┘ └───────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 5: Steps（Shell / LLM / Save）                      │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐               │   │
│  │  │ ShellStep  │ │ LLMStep   │ │ SaveStep   │               │   │
│  │  │ subprocess │ │ LLM 呼叫  │ │ 檔案寫入   │               │   │
│  │  └───────────┘ └───────────┘ └───────────┘               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 6: Utils（Template + Display）                      │   │
│  │  ┌───────────────┐ ┌───────────────┐                      │   │
│  │  │ TemplateEngine │ │ DisplayManager│                      │   │
│  │  │ {{ }} 變數替換  │ │ Rich 終端輸出 │                      │   │
│  │  └───────────────┘ └───────────────┘                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Storage: .agentforge/                                     │   │
│  │  ┌──────────────────────────────────────────────────────┐ │   │
│  │  │ SQLite（WAL 模式）                                    │ │   │
│  │  │ runs / step_runs / cost_log 三張表                     │ │   │
│  │  └──────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 資料流

```
使用者
  │
  ├── agentforge run code-reviewer
  │
  ▼
CLI (Click)
  │ 解析命令列參數
  ▼
Schema (Pydantic v2)
  │ 載入 + 驗證 YAML → 不可變 AgentDef
  ▼
PipelineEngine
  │ 依序執行 steps[]
  │ ┌──────────────────────────┐
  │ │ Step 1: ShellStep        │
  │ │   └→ subprocess.run()    │──→ output 存入 context
  │ │ Step 2: LLMStep          │
  │ │   └→ LLMRouter.call()    │──→ output 存入 context
  │ │ Step 3: SaveStep         │
  │ │   └→ 寫入檔案            │──→ output 存入 context
  │ └──────────────────────────┘
  │ 每步結果 → TaskTracker（SQLite）
  │ 每步 LLM → BudgetTracker（成本記錄）
  │
  ▼
FailureHandler（失敗時觸發）
  │ 第 1 次：注入修復 prompt → 重跑該步驟
  │ 第 2 次：LLM 重新規劃整個 pipeline → 全部重跑
  │ 第 3 次：停機 → exit(1) + 錯誤報告
  ▼
DisplayManager（Rich 終端輸出）
  │ 進度條 + 成本 + 結果摘要
  ▼
使用者看到結果
```

---

## 2. 模組設計

### 2.1 Layer 1: CLI（Click 框架）

**設計決策**：選擇 Click 而非 Typer。

| 比較項 | Click | Typer |
|--------|-------|-------|
| 依賴 | 零額外依賴（pip 已內建） | 依賴 Click + typing_extensions |
| 控制力 | 顯式裝飾器，完全控制 | 自動推斷，隱藏魔法 |
| 成熟度 | 2014 年，Flask 同作者 | 2020 年，FastAPI 同作者 |
| 子命令 | `@click.group()` 原生支援 | 底層也是 Click group |

**結論**：Click 顯式控制，零額外依賴，更適合 CLI 工具的精確需求。

```python
# agentforge/cli/main.py
import click

@click.group()
@click.version_option()
def cli() -> None:
    """AgentForge — YAML 定義 AI Agent，一行指令執行。"""
    pass

@cli.command()
@click.argument("name")
@click.option("--template", default="default", help="專案模板")
def init(name: str, template: str) -> None:
    """初始化 AgentForge 專案。"""
    ...

@cli.command()
@click.argument("agent")
@click.option("--dry-run", is_flag=True, help="乾跑模式")
@click.option("--verbose", "-v", is_flag=True, help="詳細輸出")
def run(agent: str, dry_run: bool, verbose: bool) -> None:
    """執行指定的 Agent。"""
    ...

@cli.command()
def status() -> None:
    """顯示任務狀態與成本統計。"""
    ...

@cli.command(name="list")
def list_agents() -> None:
    """列出所有已定義的 Agent。"""
    ...
```

### 2.2 Layer 2: Schema（Pydantic v2）

**設計決策**：
- 外部資料（YAML）使用 Pydantic v2 BaseModel（驗證 + 清晰錯誤訊息）
- 內部資料（runtime）使用 frozen dataclass（輕量 + 不可變）

```python
# agentforge/schema/agent_def.py
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from enum import Enum

class ActionType(str, Enum):
    """步驟動作類型"""
    SHELL = "shell"
    LLM = "llm"
    SAVE = "save"

class StepDef(BaseModel):
    """單一步驟定義（從 YAML 解析）"""
    name: str = Field(..., min_length=1, max_length=64,
                      description="步驟名稱，用於 {{ steps.<name>.output }} 引用")
    action: ActionType = Field(..., description="動作類型：shell / llm / save")

    # shell 專用
    command: Optional[str] = Field(None, description="Shell 命令（action=shell 時必填）")
    timeout: int = Field(30, ge=1, le=3600, description="命令超時秒數")

    # llm 專用
    prompt: Optional[str] = Field(None, description="LLM 提示詞（action=llm 時必填）")
    input: Optional[str] = Field(None, description="輸入模板（支援 {{ }} 變數）")
    model: Optional[str] = Field(None, description="覆蓋 Agent 級別的模型設定")

    # save 專用
    path: Optional[str] = Field(None, description="儲存路徑（action=save 時必填）")
    content: Optional[str] = Field(None, description="儲存內容模板")

    @field_validator("command")
    @classmethod
    def command_required_for_shell(cls, v, info):
        if info.data.get("action") == "shell" and not v:
            raise ValueError("action=shell 時 command 為必填")
        return v

class ModelRef(BaseModel):
    """模型引用（provider/model-name 格式）"""
    provider: str = Field(..., description="Provider 名稱")
    model_name: str = Field(..., description="模型名稱")

    @classmethod
    def from_string(cls, s: str) -> "ModelRef":
        """解析 'provider/model-name' 格式"""
        if "/" not in s:
            raise ValueError(f"模型格式錯誤：'{s}'，應為 'provider/model-name'")
        provider, model_name = s.split("/", 1)
        return cls(provider=provider, model_name=model_name)

class AgentDef(BaseModel):
    """Agent 定義（從 YAML 解析）"""
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field("", max_length=500)
    model: str = Field(..., description="預設模型（provider/model-name）")
    max_retries: int = Field(3, ge=0, le=10, description="三級修復上限")
    steps: list[StepDef] = Field(..., min_length=1, max_length=100)

    @field_validator("steps")
    @classmethod
    def validate_unique_step_names(cls, v):
        names = [step.name for step in v]
        if len(names) != len(set(names)):
            raise ValueError("步驟名稱不可重複")
        return v

# agentforge/schema/config.py
class GlobalConfig(BaseModel):
    """全域設定（agentforge.yaml）"""
    default_model: str = Field("openai/gpt-4o", description="預設模型")
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    budget: BudgetSettings = Field(default_factory=BudgetSettings)
    storage_dir: str = Field(".agentforge", description="本地儲存目錄")

class ProviderSettings(BaseModel):
    """Provider 設定"""
    api_key_env: str = Field(..., description="API key 環境變數名稱")
    base_url: Optional[str] = Field(None, description="自訂 API 端點")
    default_model: str = Field(..., description="預設模型名稱")

class BudgetSettings(BaseModel):
    """預算設定"""
    daily_limit_usd: float = Field(10.0, ge=0, description="每日預算上限")
    warn_at_percent: int = Field(80, ge=0, le=100, description="預算警告閾值")
```

### 2.3 Layer 3: Core（Engine + Failure + TaskTracker）

#### 2.3.1 PipelineEngine（全新開發）

Pipeline 執行引擎，負責按順序執行 Agent 定義中的 steps。

```python
# agentforge/core/engine.py
from dataclasses import dataclass, field
from typing import Protocol, Optional

class ProgressCallback(Protocol):
    """進度回呼協議 — 觀察者模式擴展點

    未來 Web UI 可實作此 Protocol 接收進度事件，
    MVP 階段由 DisplayManager 實作。
    """
    def on_step_start(self, step_index: int, step_name: str, total: int) -> None: ...
    def on_step_success(self, step_index: int, step_name: str,
                        elapsed_sec: float, cost_usd: float) -> None: ...
    def on_step_failure(self, step_index: int, step_name: str,
                        error: str, retry_round: int) -> None: ...
    def on_pipeline_complete(self, total_time: float, total_cost: float) -> None: ...

@dataclass(frozen=True)
class StepResult:
    """單步執行結果（不可變）"""
    step_name: str
    success: bool
    output: str = ""
    error: str = ""
    elapsed_sec: float = 0.0
    cost_usd: float = 0.0
    retry_count: int = 0

@dataclass(frozen=True)
class PipelineResult:
    """Pipeline 整體執行結果（不可變）"""
    agent_name: str
    success: bool
    step_results: tuple[StepResult, ...] = ()
    total_time: float = 0.0
    total_cost: float = 0.0
    failure_report: str = ""

class PipelineEngine:
    """Pipeline 執行引擎

    按順序執行 AgentDef 中的 steps，
    管理步驟間的輸出傳遞和失敗修復。
    """

    def __init__(
        self,
        llm_router: "LLMRouter",
        failure_handler: "FailureHandler",
        task_tracker: "TaskTracker",
        progress: Optional[ProgressCallback] = None,
    ) -> None: ...

    def execute(self, agent_def: "AgentDef", dry_run: bool = False) -> PipelineResult:
        """執行 Agent Pipeline

        Args:
            agent_def: 驗證後的 Agent 定義
            dry_run: True 時只顯示步驟，不實際執行

        Returns:
            PipelineResult 不可變結果
        """
        ...

    def _build_context(self, results: list[StepResult]) -> dict[str, str]:
        """建構步驟間的上下文 — { "step_name": "output" }"""
        ...
```

#### 2.3.2 FailureHandler（借鑑 FailureInjector 重寫）

借鑑 `src/fsm/failure_injector.py` 的三級修復策略，但簡化為 AgentForge 的場景。

**與原模組的差異**：

| 項目 | FailureInjector（Agent Army） | FailureHandler（AgentForge） |
|------|------------------------------|------------------------------|
| 修復目標 | FSM Stage 6 測試失敗 | Agent Step 執行失敗 |
| 第 1 級 | 注入 prompt → Stage 3&4 | 注入修復 prompt → 重跑該步驟 |
| 第 2 級 | 退回 Stage 2 重新規劃 | LLM 重新規劃整個 pipeline |
| 第 3 級 | 停機通知使用者 | exit(1) + 錯誤報告 |
| 持久化 | JSON 檔案 | SQLite step_runs 表 |
| 跨對話 | 支援（JSON 檔案） | 不需要（單次執行） |

```python
# agentforge/core/failure.py
from dataclasses import dataclass
from enum import Enum

class RepairLevel(str, Enum):
    """修復等級"""
    RETRY_WITH_FIX = "retry_with_fix"      # 第 1 次：注入修復 prompt
    REPLAN_PIPELINE = "replan_pipeline"    # 第 2 次：LLM 重新規劃
    HALT = "halt"                          # 第 3 次：停機

_LEVEL_MAP = {1: RepairLevel.RETRY_WITH_FIX, 2: RepairLevel.REPLAN_PIPELINE}

@dataclass(frozen=True)
class FailureRecord:
    """失敗記錄（不可變）"""
    step_name: str
    round_number: int
    error_message: str
    repair_level: RepairLevel
    repair_prompt: str = ""

class FailureHandler:
    """三級自動修復處理器

    借鑑 Agent Army 的 FailureInjector 設計，
    簡化為 Agent 執行場景的修復機制。
    """

    def __init__(self, max_retries: int = 3, llm_router: "LLMRouter" = None) -> None:
        self._max_retries = max_retries
        self._llm_router = llm_router
        self._failures: list[FailureRecord] = []

    def get_repair_level(self, retry_count: int) -> RepairLevel:
        """根據已重試次數決定修復等級"""
        if retry_count >= self._max_retries:
            return RepairLevel.HALT
        return _LEVEL_MAP.get(retry_count, RepairLevel.HALT)

    def build_fix_prompt(self, step_name: str, error: str,
                         original_prompt: str) -> str:
        """建構第 1 級修復 prompt（注入錯誤上下文）"""
        ...

    def replan_pipeline(self, agent_def: "AgentDef",
                        failure_history: list[FailureRecord]) -> "AgentDef":
        """第 2 級修復：用 LLM 重新規劃 pipeline steps"""
        ...

    def generate_report(self) -> str:
        """第 3 級：產出完整錯誤報告"""
        ...
```

#### 2.3.3 TaskTracker（借鑑 TaskBoard 重寫）

借鑑 `src/fsm/task_board.py` 的 SQLite 設計，但表結構針對 AgentForge 重新設計。

**與原模組的差異**：

| 項目 | TaskBoard（Agent Army） | TaskTracker（AgentForge） |
|------|------------------------|--------------------------|
| 表結構 | tasks + checklist + audit_log | runs + step_runs + cost_log |
| 用途 | FSM 工單管理 | Agent 執行追蹤 |
| 查詢 | 任務 CRUD + 狀態切換 | 執行歷史 + 成本統計 |
| Checklist | 支援 | 不需要 |
| 匯出 | Markdown 工單 | Status Dashboard |

```python
# agentforge/core/task_tracker.py
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

@dataclass(frozen=True)
class RunRecord:
    """執行記錄（不可變）"""
    id: int
    agent_name: str
    status: str          # running / success / failed
    started_at: str
    finished_at: Optional[str]
    total_steps: int
    completed_steps: int
    total_cost_usd: float
    error_message: str = ""

@dataclass(frozen=True)
class StepRunRecord:
    """步驟執行記錄（不可變）"""
    id: int
    run_id: int
    step_name: str
    action: str          # shell / llm / save
    status: str          # running / success / failed / skipped
    started_at: str
    finished_at: Optional[str]
    output_preview: str = ""    # 前 500 字元
    error_message: str = ""
    cost_usd: float = 0.0
    retry_count: int = 0

class TaskTracker:
    """SQLite 任務追蹤器

    借鑑 Agent Army TaskBoard 的 SQLite + WAL 設計，
    表結構針對 Agent 執行追蹤重新設計。
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(".agentforge/agentforge.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        """WAL 模式資料庫連線"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def start_run(self, agent_name: str, total_steps: int) -> int:
        """開始一次執行，回傳 run_id"""
        ...

    def record_step(self, run_id: int, step_name: str, action: str,
                    status: str, output: str = "", error: str = "",
                    cost_usd: float = 0.0, retry_count: int = 0) -> None:
        """記錄步驟結果"""
        ...

    def finish_run(self, run_id: int, success: bool, error: str = "") -> None:
        """結束一次執行"""
        ...

    def get_agent_stats(self, agent_name: str) -> dict:
        """取得 Agent 統計：執行數、成功率、總成本"""
        ...

    def get_all_stats(self) -> list[dict]:
        """取得所有 Agent 的統計（status 命令用）"""
        ...

    def get_recent_runs(self, limit: int = 20) -> list[RunRecord]:
        """取得最近執行記錄"""
        ...
```

### 2.4 Layer 4: LLM（Router + Budget + Providers）

#### 2.4.1 LLMRouter（借鑑 LLMClient 重寫）

**設計決策**：Ollama 不建獨立 Provider，改用 OpenAI 相容 API（改 base_url 即可）。

這個決策直接複用 `src/llm/providers/openai_compat.py`，不需要為 Ollama 寫新的 Provider。

```python
# agentforge/llm/router.py
from dataclasses import dataclass
from typing import Optional, Protocol

class LLMResponse(Protocol):
    """LLM 回應協議"""
    content: str
    model: str
    provider: str
    usage: Optional[dict[str, int]]

@dataclass(frozen=True)
class LLMCallResult:
    """LLM 呼叫結果（不可變）"""
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

class LLMRouter:
    """模型路由器

    根據 Agent YAML 中的 model 欄位（provider/model-name）
    自動路由到對應的 Provider。

    Provider 初始化策略：懶載入，首次使用時才建立。
    Ollama 透過 OpenAI 相容 API 支援（base_url=http://localhost:11434/v1）。
    """

    def __init__(self, global_config: "GlobalConfig") -> None:
        self._config = global_config
        self._providers: dict[str, "BaseProvider"] = {}  # 懶載入快取

    def call(self, model_ref: str, prompt: str,
             context: str = "", **kwargs) -> LLMCallResult:
        """呼叫 LLM

        Args:
            model_ref: "provider/model-name" 格式
            prompt: 提示詞
            context: 上下文（來自前一步的 output）
            **kwargs: temperature, max_tokens 等

        Returns:
            LLMCallResult 不可變結果
        """
        ...

    def _get_or_create_provider(self, provider_name: str) -> "BaseProvider":
        """懶載入 Provider"""
        ...

    def test_connection(self, provider_name: str) -> bool:
        """測試指定 Provider 連線"""
        ...
```

**Provider 支援矩陣**：

| Provider | 實作方式 | base_url | API Key 環境變數 |
|----------|---------|----------|-----------------|
| OpenAI | OpenAICompatProvider（直接複製） | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| Ollama | OpenAICompatProvider（改 base_url） | `http://localhost:11434/v1` | 不需要（`ollama`） |
| Gemini | GeminiProvider（直接複製） | — | `GOOGLE_API_KEY` |

#### 2.4.2 BudgetTracker（簡化提取 BudgetGuard）

從 `src/fsm/budget_guard.py` 簡化提取，移除「模型降級」邏輯（AgentForge 由使用者在 YAML 指定模型，不自動降級），保留成本追蹤和預算警告。

**與原模組的差異**：

| 項目 | BudgetGuard（Agent Army） | BudgetTracker（AgentForge） |
|------|--------------------------|---------------------------|
| 模型降級 | 自動降級（Opus→Sonnet→Haiku→Ollama） | 不降級（使用者 YAML 指定） |
| GM 閘門 | CEO 面對面限制 | 不需要 |
| 定價表 | Claude 定價 | OpenAI + Gemini + Ollama 定價 |
| 儲存 | JSON 日檔案 | SQLite cost_log 表 |
| 警告 | 日誌 | 終端警告 + exit code |

```python
# agentforge/llm/budget.py
from dataclasses import dataclass

# 定價表（USD per 1M tokens）
PRICING = {
    "openai/gpt-4o":      {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini":  {"input": 0.15, "output": 0.60},
    "gemini/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "ollama/*":            {"input": 0.00, "output": 0.00},
}

@dataclass(frozen=True)
class CostEntry:
    """成本記錄（不可變）"""
    timestamp: str
    agent_name: str
    step_name: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

class BudgetTracker:
    """成本追蹤器

    從 BudgetGuard 簡化提取，專注於：
    1. 記錄每次 LLM 呼叫的 token 和成本
    2. 查詢統計（每 Agent、每日、每月）
    3. 預算超限警告
    """

    def __init__(self, task_tracker: "TaskTracker",
                 daily_limit_usd: float = 10.0) -> None:
        self._tracker = task_tracker  # 共用 SQLite
        self._daily_limit = daily_limit_usd

    def record(self, agent_name: str, step_name: str, model: str,
               input_tokens: int, output_tokens: int) -> CostEntry:
        """記錄一次 LLM 使用"""
        ...

    def get_daily_total(self) -> float:
        """取得今日總成本"""
        ...

    def get_agent_total(self, agent_name: str) -> float:
        """取得指定 Agent 總成本"""
        ...

    def check_budget(self) -> tuple[bool, str]:
        """檢查預算，回傳 (is_over, message)"""
        ...

    @staticmethod
    def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """計算成本"""
        ...
```

### 2.5 Layer 5: Steps（Shell / LLM / Save）

```python
# agentforge/steps/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class StepOutput:
    """步驟輸出（不可變）"""
    success: bool
    output: str = ""
    error: str = ""
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

class BaseStep(ABC):
    """步驟基底類別"""

    @abstractmethod
    def execute(self, step_def: "StepDef", context: dict[str, str]) -> StepOutput:
        """執行步驟

        Args:
            step_def: 步驟定義
            context: 上下文 {"step_name": "output", ...}

        Returns:
            StepOutput 不可變結果
        """
        ...

    @abstractmethod
    def dry_run(self, step_def: "StepDef", context: dict[str, str]) -> str:
        """乾跑：回傳描述字串，不實際執行"""
        ...


# agentforge/steps/shell_step.py
class ShellStep(BaseStep):
    """Shell 命令步驟

    使用 subprocess.run() 執行命令，
    捕獲 stdout/stderr，處理超時。
    """

    def execute(self, step_def: "StepDef", context: dict[str, str]) -> StepOutput:
        """執行 shell 命令"""
        # 1. 用 TemplateEngine 替換 command 中的 {{ }} 變數
        # 2. subprocess.run(command, capture_output=True, timeout=step_def.timeout)
        # 3. 回傳 StepOutput
        ...


# agentforge/steps/llm_step.py
class LLMStep(BaseStep):
    """LLM 呼叫步驟

    組合 prompt + input context，
    透過 LLMRouter 呼叫對應 Provider。
    """

    def __init__(self, llm_router: "LLMRouter") -> None:
        self._router = llm_router

    def execute(self, step_def: "StepDef", context: dict[str, str]) -> StepOutput:
        """執行 LLM 呼叫"""
        # 1. 用 TemplateEngine 替換 prompt 和 input 中的 {{ }} 變數
        # 2. 組合完整 prompt
        # 3. LLMRouter.call(model, prompt)
        # 4. 回傳 StepOutput（含 cost）
        ...


# agentforge/steps/save_step.py
class SaveStep(BaseStep):
    """檔案儲存步驟

    將內容寫入指定路徑。
    """

    def execute(self, step_def: "StepDef", context: dict[str, str]) -> StepOutput:
        """儲存檔案"""
        # 1. 用 TemplateEngine 替換 path 和 content 中的 {{ }} 變數
        # 2. 寫入檔案（自動建立目錄）
        # 3. 回傳 StepOutput
        ...
```

### 2.6 Layer 6: Utils（Template + Display）

```python
# agentforge/utils/template.py
import re

class TemplateEngine:
    """Mustache 風格模板引擎

    支援 {{ steps.<name>.output }} 變數替換。
    不使用 Jinja2（避免依賴膨脹），自行實作簡易替換。
    """

    PATTERN = re.compile(r"\{\{\s*steps\.(\w+)\.output\s*\}\}")

    @staticmethod
    def render(template: str, context: dict[str, str]) -> str:
        """替換模板中的變數

        Args:
            template: 包含 {{ steps.<name>.output }} 的字串
            context: {"step_name": "output_value", ...}

        Returns:
            替換後的字串

        Raises:
            KeyError: 引用了不存在的步驟名稱
        """
        ...


# agentforge/utils/display.py
from typing import Optional

class DisplayManager:
    """Rich 終端輸出管理器

    實作 ProgressCallback Protocol，
    提供進度條、表格、彩色輸出等功能。
    """

    def __init__(self, verbose: bool = False, quiet: bool = False) -> None:
        self._verbose = verbose
        self._quiet = quiet

    # ── ProgressCallback 實作 ──
    def on_step_start(self, step_index: int, step_name: str, total: int) -> None:
        """顯示 [1/3] step_name..."""
        ...

    def on_step_success(self, step_index: int, step_name: str,
                        elapsed_sec: float, cost_usd: float) -> None:
        """顯示 ✅ (0.3s, $0.003)"""
        ...

    def on_step_failure(self, step_index: int, step_name: str,
                        error: str, retry_round: int) -> None:
        """顯示 ❌ + 修復提示"""
        ...

    def on_pipeline_complete(self, total_time: float, total_cost: float) -> None:
        """顯示完成摘要"""
        ...

    # ── Status Dashboard ──
    def render_status_table(self, stats: list[dict]) -> None:
        """渲染 status 表格（Rich Table）"""
        ...

    def render_agent_list(self, agents: list[dict]) -> None:
        """渲染 agent 列表"""
        ...
```

---

## 3. 資料模型

### 3.1 YAML Schema

#### 3.1.1 全域設定（agentforge.yaml）

```yaml
# agentforge.yaml — 全域設定
default_model: openai/gpt-4o

providers:
  openai:
    api_key_env: OPENAI_API_KEY
    default_model: gpt-4o
  ollama:
    api_key_env: ""              # Ollama 不需要 API key
    base_url: http://localhost:11434/v1
    default_model: qwen3:14b
  gemini:
    api_key_env: GOOGLE_API_KEY
    default_model: gemini-2.0-flash

budget:
  daily_limit_usd: 10.0
  warn_at_percent: 80

storage_dir: .agentforge
```

#### 3.1.2 Agent 定義（agents/*.yaml）

```yaml
# agents/code-reviewer.yaml
name: code-reviewer
description: "自動審查 Pull Request 的程式碼品質"
model: openai/gpt-4o          # 可覆蓋全域設定
max_retries: 3                 # 三級修復上限

steps:
  - name: fetch_diff
    action: shell
    command: "git diff main...HEAD"
    timeout: 30

  - name: review
    action: llm
    prompt: |
      請審查以下程式碼差異，找出：
      1. 潛在 bug
      2. 安全漏洞
      3. 效能問題
      回傳 JSON 格式報告。
    input: "{{ steps.fetch_diff.output }}"

  - name: report
    action: save
    path: "review-report.md"
    content: "{{ steps.review.output }}"
```

### 3.2 SQLite DDL

```sql
-- .agentforge/agentforge.db
-- WAL 模式，支援併發讀取

-- 執行記錄表
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',   -- running / success / failed
    started_at TEXT NOT NULL,
    finished_at TEXT,
    total_steps INTEGER NOT NULL DEFAULT 0,
    completed_steps INTEGER NOT NULL DEFAULT 0,
    total_cost_usd REAL NOT NULL DEFAULT 0.0,
    error_message TEXT DEFAULT ''
);

-- 步驟執行記錄表
CREATE TABLE IF NOT EXISTS step_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    action TEXT NOT NULL,                     -- shell / llm / save
    status TEXT NOT NULL DEFAULT 'running',   -- running / success / failed / skipped
    started_at TEXT NOT NULL,
    finished_at TEXT,
    output_preview TEXT DEFAULT '',            -- 前 500 字元
    error_message TEXT DEFAULT '',
    cost_usd REAL NOT NULL DEFAULT 0.0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

-- 成本日誌表
CREATE TABLE IF NOT EXISTS cost_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    agent_name TEXT NOT NULL,
    step_name TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_runs_agent ON runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_step_runs_run ON step_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_cost_log_run ON cost_log(run_id);
CREATE INDEX IF NOT EXISTS idx_cost_log_agent ON cost_log(agent_name);
CREATE INDEX IF NOT EXISTS idx_cost_log_timestamp ON cost_log(timestamp);
```

---

## 4. 錯誤處理策略

### 4.1 錯誤分層

```
Layer 1 CLI 錯誤
├── 命令不存在 → Click 自動處理，顯示 --help
├── 參數錯誤 → Click 自動驗證，顯示用法
└── Agent YAML 不存在 → 明確錯誤 + 建議 agentforge list

Layer 2 Schema 錯誤
├── YAML 語法錯誤 → PyYAML 解析錯誤 + 行號
├── 欄位缺失 → Pydantic ValidationError + 欄位名稱
├── 欄位值非法 → Pydantic ValidationError + 允許值
└── 步驟名稱重複 → 自訂驗證器 + 明確訊息

Layer 3 Core 錯誤
├── Pipeline 執行失敗 → FailureHandler 三級修復
├── SQLite 損壞 → 自動重建 + 警告
└── 步驟超時 → subprocess TimeoutExpired + 重試

Layer 4 LLM 錯誤
├── API key 未設定 → 明確訊息 + 環境變數名稱
├── Provider 連線失敗 → retry 3 次 + 明確錯誤
├── 回應超時 → 設定超時 + 重試
├── Rate limit → 指數退避重試（1s, 2s, 4s）
└── 預算超限 → 警告（不阻擋）+ exit code

Layer 5 Step 錯誤
├── Shell 命令失敗 → 捕獲 stderr + 傳給 FailureHandler
├── Shell 超時 → TimeoutExpired + 重試
├── 檔案寫入失敗 → 路徑不存在自動建立 / 權限錯誤
└── 模板變數缺失 → KeyError + 明確提示哪個變數

Layer 6 Utils 錯誤
├── 模板語法錯誤 → 正則匹配失敗 + 原文保留
└── Rich 輸出錯誤 → fallback 到 print()
```

### 4.2 錯誤訊息格式

所有使用者面對的錯誤訊息必須包含三個部分：

```
❌ 錯誤：<簡短描述>
   原因：<技術細節>
   建議：<使用者可以做什麼>
```

範例：
```
❌ 錯誤：無法連線到 Ollama
   原因：Connection refused at http://localhost:11434
   建議：請確認 Ollama 已啟動（ollama serve）
```

---

## 5. 複用策略

### 5.1 複用評估總表

| 模組 | 來源 | 複用方式 | 預估改動 | 行數 |
|------|------|---------|---------|------|
| `OpenAICompatProvider` | `src/llm/providers/openai_compat.py` | 直接複製 | < 5% | ~200 |
| `GeminiProvider` | `src/llm/providers/gemini.py` | 直接複製 | < 5% | ~180 |
| `BaseProvider` + `LLMResponse` | `src/llm/providers/base.py` | 直接複製 | < 5% | ~99 |
| `ProviderConfig` | `src/llm/config.py` | 直接複製 | < 5% | ~134 |
| FailureInjector 設計 | `src/fsm/failure_injector.py` | 借鑑重寫 | ~60% | ~250→150 |
| TaskBoard 設計 | `src/fsm/task_board.py` | 借鑑重寫 | ~70% | ~300→200 |
| BudgetGuard 設計 | `src/fsm/budget_guard.py` | 簡化提取 | ~50% | ~250→120 |

**直接複製（< 5% 改動）**：Provider 層共 ~613 行
**借鑑重寫（50-70% 改動）**：Core 層共 ~470 行（從 ~1,050 行簡化）
**不複用**：WorkerManager（MVP 不需並行）、MemoryPriority（MVP 不需跨對話記憶）

### 5.2 複用行數估算

```
直接複製   ≈   613 行（Provider 全套）
借鑑重寫   ≈ 1,516 行原始碼 → 470 行新碼（節省設計時間）
全新開發   ≈ 3,015 行
測試        ≈ 1,980 行
─────────────────
總計        ≈ 6,078 行（含測試）
```

---

## 6. 技術決策記錄

### TD-1: Click > Typer

- **決策**：CLI 框架使用 Click，不使用 Typer
- **理由**：顯式控制、零額外依賴、更好的子命令支援
- **影響**：CLI 層需要多寫裝飾器，但獲得完全控制力

### TD-2: Pydantic v2 for YAML, frozen dataclass for runtime

- **決策**：外部資料用 Pydantic v2 驗證，內部資料用 frozen dataclass
- **理由**：Pydantic v2 驗證錯誤訊息對使用者友好；frozen dataclass 輕量高效
- **影響**：需要在 Schema 層做一次轉換（Pydantic model → frozen dataclass）

### TD-3: Ollama via OpenAI 相容 API

- **決策**：Ollama 不建獨立 Provider，用 OpenAICompatProvider 改 base_url
- **理由**：Ollama 自 0.1.24 起支援 OpenAI 相容 API，減少維護成本
- **影響**：直接複用 OpenAICompatProvider，Ollama 設定只需 `base_url: http://localhost:11434/v1`

### TD-4: ProgressCallback Protocol 觀察者模式

- **決策**：PipelineEngine 透過 ProgressCallback Protocol 通知進度
- **理由**：解耦 Engine 和 UI，未來 Web UI 可以實作此 Protocol
- **影響**：MVP 由 DisplayManager 實作；Step 2 Web UI 只需新增一個實作

### TD-5: SQLite 3 表（runs / step_runs / cost_log）

- **決策**：用 SQLite WAL 模式儲存執行記錄和成本
- **理由**：單檔案、零設定、支援併發讀取、SQL 查詢彈性大
- **影響**：status 命令可以用 SQL 做複雜統計

### TD-6: MVP 不複用 WorkerManager 和 MemoryPriority

- **決策**：MVP 不實作並行 Agent 和跨對話記憶
- **理由**：MVP 聚焦單 Agent 執行，並行和記憶是 Step 2 功能
- **影響**：架構預留擴展點（PipelineEngine 可包裝為 Worker），但 MVP 不實作

### TD-7: 自行實作模板引擎，不用 Jinja2

- **決策**：用正則表達式實作 `{{ steps.<name>.output }}` 替換
- **理由**：MVP 只需一種模板語法，Jinja2 太重（依賴 MarkupSafe）
- **影響**：模板引擎只支援 `{{ steps.<name>.output }}`，不支援 if/for 等邏輯

---

## 7. 套件結構（最終版）

```
agentforge/                         # PyPI 套件根目錄
├── __init__.py                     # 版本號 + 公開 API
├── __main__.py                     # python -m agentforge 入口
│
├── cli/                            # Layer 1: CLI
│   ├── __init__.py
│   ├── main.py                     # Click group + version
│   ├── init_cmd.py                 # agentforge init
│   ├── run_cmd.py                  # agentforge run
│   ├── status_cmd.py              # agentforge status
│   └── list_cmd.py                 # agentforge list
│
├── schema/                         # Layer 2: Schema
│   ├── __init__.py
│   ├── agent_def.py                # AgentDef / StepDef / ModelRef
│   ├── config.py                   # GlobalConfig / ProviderSettings
│   └── loader.py                   # YAML 載入 + 驗證 + 轉換
│
├── core/                           # Layer 3: Core
│   ├── __init__.py
│   ├── engine.py                   # PipelineEngine + ProgressCallback
│   ├── failure.py                  # FailureHandler（三級修復）
│   └── task_tracker.py             # TaskTracker（SQLite）
│
├── llm/                            # Layer 4: LLM
│   ├── __init__.py
│   ├── router.py                   # LLMRouter
│   ├── budget.py                   # BudgetTracker
│   └── providers/                  # Provider 實作
│       ├── __init__.py
│       ├── base.py                 # BaseProvider + LLMResponse
│       ├── openai_compat.py        # OpenAI + Ollama（改 base_url）
│       └── gemini.py               # Google Gemini
│
├── steps/                          # Layer 5: Steps
│   ├── __init__.py
│   ├── base.py                     # BaseStep + StepOutput
│   ├── shell_step.py              # ShellStep
│   ├── llm_step.py                 # LLMStep
│   └── save_step.py                # SaveStep
│
├── utils/                          # Layer 6: Utils
│   ├── __init__.py
│   ├── template.py                 # TemplateEngine
│   └── display.py                  # DisplayManager（Rich）
│
└── templates/                      # init 命令用的模板
    ├── agentforge.yaml             # 全域設定模板
    └── example.yaml                # 範例 Agent 模板
```

---

## 8. 非功能需求

### 8.1 效能

| 指標 | 目標 |
|------|------|
| CLI 啟動時間（非 LLM 命令） | < 500ms |
| YAML 解析 + 驗證 | < 100ms |
| SQLite 查詢（status） | < 200ms |
| 記憶體使用（idle） | < 50MB |

### 8.2 相容性

- Python 3.10+ （使用 `X | Y` 聯合型別語法）
- Windows 10/11、macOS、Linux
- Ollama 0.1.24+（OpenAI 相容 API）

### 8.3 擴展點（Step 2 預留）

| 擴展點 | 預留方式 | Step 2 用途 |
|--------|---------|------------|
| `ProgressCallback` Protocol | Engine 透過 Protocol 通知進度 | Web UI 即時顯示 |
| `BaseStep` 抽象類別 | 新增 Step 類型只需繼承 | HTTP Step、DB Step 等 |
| `BaseProvider` 抽象類別 | 新增 Provider 只需繼承 | Anthropic、Cohere 等 |
| SQLite schema | 遷移腳本預留 | 新增表/欄位 |

---

*本文件為 FSM Stage 2 架構設計產出，待 CEO 確認後進入開發計畫。*
