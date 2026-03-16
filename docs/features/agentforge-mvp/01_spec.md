# AgentForge MVP — 需求規格書

> **FSM Stage 1 產出** | 版本：v1.0 | 日期：2026-03-17
> 狀態：🟢 待 CEO 確認

---

## 1. 產品定位

**一句話**：讓企業用 YAML 定義 AI Agent，用一行指令執行，自帶三級自動修復。

**AgentForge MVP** 是一個 **CLI 工具 + Python SDK**，將 Agent Army 的核心引擎
（FSM 狀態機、三級自動修復、多模型路由）封裝為可安裝的開源產品。

**目標用戶**：有 Python 經驗的技術人員（工程師、技術主管、AI 愛好者）

---

## 2. MVP 範圍（做什麼 / 不做什麼）

### ✅ MVP 包含（Must Have）

| # | 功能 | 說明 |
|---|------|------|
| F1 | **YAML Agent 定義** | 用 YAML 檔定義 Agent 的角色、工具、LLM、工作流 |
| F2 | **CLI 工具** | `agentforge init / run / status / list` 四個核心指令 |
| F3 | **FSM 執行引擎** | 狀態機驅動 Agent 執行，支援多步驟工作流 |
| F4 | **三級自動修復** | 失敗自動重試 → 升級重新規劃 → 停機通知（核心差異化） |
| F5 | **多模型路由** | 支援 OpenAI / Ollama 本地 / Gemini，YAML 設定切換 |
| F6 | **任務看板** | SQLite 本地儲存，追蹤每個 Agent 的任務狀態與歷史 |
| F7 | **成本追蹤** | 每次 LLM 呼叫自動計費，日報表，預算上限告警 |
| F8 | **Terminal Dashboard** | `agentforge status` 顯示即時狀態（Rich TUI 或簡潔表格） |

### ❌ MVP 不做（明確排除）

| 排除項 | 原因 |
|--------|------|
| Web UI / 視覺化 Builder | Step 2 再做，MVP 先用 YAML + CLI |
| 多租戶 / 帳號系統 | 企業版功能，MVP 是單用戶工具 |
| 計費 / 付費牆 | MVP 開源免費，先衝用戶量 |
| 產業模板市集 | Step 2 以後 |
| Docker / K8s 部署 | MVP 先做 `pip install agentforge` |
| Anthropic Claude API | 目前 Claude 不提供直接 API 呼叫，透過 Claude Code 使用 |

---

## 3. 用戶故事

### US-1：初始化專案
```
身為技術主管，
我想用一行指令初始化 AgentForge 專案，
這樣我的團隊可以快速開始定義 Agent。

agentforge init my-project
→ 產生：
  my-project/
  ├── agentforge.yaml    ← 全域設定（LLM、預算）
  ├── agents/
  │   └── example.yaml   ← 範例 Agent 定義
  └── .agentforge/       ← 本地狀態（SQLite、日誌）
```

### US-2：定義 Agent
```
身為工程師，
我想用 YAML 定義一個代碼審查 Agent，
指定它的角色、使用的 LLM、工作步驟。

# agents/code-reviewer.yaml
name: code-reviewer
description: "自動審查 Pull Request 的程式碼品質"
model: openai/gpt-4o          # 或 ollama/qwen3:14b
max_retries: 3                 # 三級修復上限

steps:
  - name: fetch_diff
    action: shell
    command: "git diff main...HEAD"

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

### US-3：執行 Agent
```
身為工程師，
我想用一行指令執行 Agent 並看到結果。

agentforge run code-reviewer
→ [1/3] fetch_diff... ✅ (0.3s)
→ [2/3] review... ✅ (4.2s, $0.003)
→ [3/3] report... ✅ (0.1s)
→ 完成！報告已存到 review-report.md
→ 總成本：$0.003 | 總時間：4.6s
```

### US-4：失敗自動修復
```
身為工程師，
當 Agent 執行步驟失敗時，
我希望它能自動修復而不是直接崩潰。

agentforge run data-processor
→ [1/3] fetch_data... ✅
→ [2/3] transform... ❌ KeyError: 'price'
→ [修復] 第 1 次失敗 → ⚡ 自動注入修復 prompt
→ [2/3] transform... ✅ (自動修復成功)
→ [3/3] save... ✅
→ 完成！修復歷史已記錄。
```

### US-5：查看狀態與成本
```
身為技術主管，
我想查看所有 Agent 的執行歷史和成本統計。

agentforge status
→ ┌─────────────────────────────────────────┐
→ │ AgentForge Dashboard                    │
→ ├──────────────┬────────┬────────┬────────┤
→ │ Agent        │ 執行數 │ 成功率 │ 本月成本 │
→ ├──────────────┼────────┼────────┼────────┤
→ │ code-reviewer│  47    │ 95.7%  │ $0.14  │
→ │ data-proc    │  23    │ 87.0%  │ $0.31  │
→ │ report-gen   │  12    │ 100%   │ $0.05  │
→ └──────────────┴────────┴────────┴────────┘
→ 本月總成本：$0.50 / 預算 $10.00
```

---

## 4. 驗收標準（Acceptance Criteria）

每條 AC 必須可測試。

### AC-1：安裝與初始化
- [ ] `pip install agentforge` 成功（Python 3.10+）
- [ ] `agentforge init <name>` 產生正確的目錄結構
- [ ] 產生的 `agentforge.yaml` 包含 LLM 設定模板
- [ ] 產生的 `example.yaml` 是可直接執行的範例 Agent

### AC-2：Agent 定義解析
- [ ] YAML 格式驗證：缺少必填欄位時給出明確錯誤訊息
- [ ] 支援 `shell`、`llm`、`save` 三種 action type
- [ ] 支援 `{{ steps.<name>.output }}` 模板變數
- [ ] 支援 `model` 欄位指定 LLM（格式：`provider/model-name`）

### AC-3：FSM 執行引擎
- [ ] 按 `steps` 順序執行，每步顯示進度
- [ ] 每步輸出可傳遞給下一步（pipeline）
- [ ] 執行結果持久化到 `.agentforge/` SQLite
- [ ] 支援 `--dry-run` 模式（顯示步驟但不實際執行）

### AC-4：三級自動修復
- [ ] 第 1 次失敗 → 自動注入修復 prompt，重新執行該步驟
- [ ] 第 2 次失敗 → 升級：用 LLM 重新規劃整個工作流再執行
- [ ] 第 3 次失敗 → 停機：記錄錯誤，輸出報告，exit code = 1
- [ ] 修復歷史記錄到 SQLite，可用 `agentforge status` 查看

### AC-5：多模型路由
- [ ] 支援 OpenAI API（GPT-4o / GPT-4o-mini）
- [ ] 支援 Ollama 本地推理（任意模型）
- [ ] 支援 Google Gemini API
- [ ] 在 `agentforge.yaml` 設定 API key 和預設模型
- [ ] Agent YAML 可覆蓋全域模型設定

### AC-6：成本追蹤
- [ ] 每次 LLM 呼叫記錄 token 用量和成本
- [ ] `agentforge status` 顯示每個 Agent 和全域成本統計
- [ ] 支援設定預算上限，超過時警告（不阻擋）

### AC-7：CLI 完整性
- [ ] `agentforge init <name>` — 初始化專案
- [ ] `agentforge run <agent>` — 執行指定 Agent
- [ ] `agentforge run <agent> --dry-run` — 乾跑模式
- [ ] `agentforge status` — 顯示狀態面板
- [ ] `agentforge list` — 列出所有已定義的 Agent
- [ ] `agentforge version` — 顯示版本
- [ ] 所有指令支援 `--help`
- [ ] 所有錯誤訊息清晰、有 actionable 建議

---

## 5. 技術規格

### 5.1 複用模組（來自 Agent Army）

| 模組 | 來源 | 改動程度 | 行數 |
|------|------|---------|------|
| FailureInjector | `src/fsm/failure_injector.py` | < 5% | 499 |
| TaskBoard | `src/fsm/task_board.py` | < 5% | 588 |
| WorkerManager | `src/fsm/worker_manager.py` | < 10% | 433 |
| MemoryPriority | `src/memory/priority.py` | < 5% | 318 |
| LLMConfig | `src/llm/config.py` | < 5% | 133 |
| BudgetGuard | `src/fsm/budget_guard.py` | ~25% | 435 |
| LLMClient | `src/llm/client.py` + providers | ~30% | 607 |

**可複用總計：3,013 行，預估節省 35-40% 開發時間**

### 5.2 需要全新開發

| 模組 | 說明 | 預估行數 |
|------|------|---------|
| CLI 入口 | Click/Typer CLI 框架 | 300-400 |
| YAML 解析器 | Agent 定義的 schema 驗證 | 200-300 |
| Step 執行器 | shell/llm/save 三種 action | 300-400 |
| 模板引擎 | `{{ steps.x.output }}` 變數替換 | 100-150 |
| 專案初始化 | scaffolding 模板 | 100-150 |
| 整合層 | 將複用模組接上 CLI | 200-300 |

**全新開發總計：1,200-1,700 行**

### 5.3 套件結構

```
agentforge/
├── __init__.py
├── __main__.py          ← python -m agentforge
├── cli/
│   ├── __init__.py
│   ├── main.py          ← CLI 入口（Click/Typer）
│   ├── init_cmd.py      ← agentforge init
│   ├── run_cmd.py       ← agentforge run
│   ├── status_cmd.py    ← agentforge status
│   └── list_cmd.py      ← agentforge list
├── core/
│   ├── __init__.py
│   ├── engine.py        ← FSM 執行引擎（複用 + 整合）
│   ├── failure.py       ← 三級修復（複用 FailureInjector）
│   ├── worker.py        ← 並行調度（複用 WorkerManager）
│   └── task_board.py    ← 任務看板（複用 TaskBoard）
├── llm/
│   ├── __init__.py
│   ├── router.py        ← 模型路由（複用 LLMClient）
│   ├── budget.py        ← 成本追蹤（複用 BudgetGuard）
│   └── providers/       ← 各 LLM provider
├── schema/
│   ├── __init__.py
│   ├── agent_def.py     ← Agent YAML schema
│   ├── config.py        ← 全域設定 schema
│   └── validator.py     ← 驗證器
├── steps/
│   ├── __init__.py
│   ├── base.py          ← Step 基底類別
│   ├── shell_step.py    ← shell action
│   ├── llm_step.py      ← llm action
│   └── save_step.py     ← save action
├── templates/
│   ├── agentforge.yaml  ← 初始化模板
│   └── example.yaml     ← 範例 Agent
└── utils/
    ├── __init__.py
    ├── template.py      ← {{ }} 變數替換
    └── display.py       ← Rich 終端輸出
```

### 5.4 依賴

```toml
[project]
name = "agentforge"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",         # CLI 框架
    "pyyaml>=6.0",        # YAML 解析
    "rich>=13.0",         # 終端美化
    "openai>=1.0",        # OpenAI API
    "google-generativeai", # Gemini API
    "pydantic>=2.0",      # Schema 驗證
]
```

---

## 6. 邊界條件與風險

### 6.1 邊界條件
- Agent YAML 超過 100 個 steps → 警告但不阻擋
- LLM 回應超過 token 上限 → 自動截斷 + 警告
- SQLite 資料庫損壞 → 自動重建 + 警告
- Ollama 未啟動 → 明確錯誤訊息：「請先啟動 Ollama」
- API key 未設定 → 明確錯誤訊息：「請設定 OPENAI_API_KEY」

### 6.2 風險
| 風險 | 影響 | 緩解 |
|------|------|------|
| YAML DSL 設計不好用 | 用戶流失 | 先做 3 個真實使用案例驗證 |
| 三級修復對某些場景無效 | 核心賣點受損 | 允許用戶自訂修復策略 |
| Ollama 相容性問題 | 本地部署體驗差 | 優先支援 QWen3/Llama3 |

---

## 7. 開發時程預估

| 週 | 階段 | 產出 |
|----|------|------|
| Week 1 | 基礎框架 + CLI 骨架 | `agentforge init / version / list` 可用 |
| Week 2 | YAML 解析 + Step 執行器 | `agentforge run` 可執行簡單 Agent |
| Week 3 | FSM 引擎整合 + 三級修復 | 自動修復功能可用 |
| Week 4 | 多模型路由 + 成本追蹤 | 完整功能 + `agentforge status` |
| Week 5 | 測試 + 文件 + 打包 | `pip install agentforge` 可用 |

**總計：5 週，由小良帶 Agent 團隊執行，零額外人力成本。**

---

## 8. 成功指標

| 指標 | 目標 |
|------|------|
| 安裝到第一個 Agent 執行 | < 5 分鐘 |
| YAML 定義學習曲線 | 看範例 10 分鐘即可自行定義 |
| 三級修復成功率 | > 70% 的可修復錯誤被自動解決 |
| CLI 回應速度 | 所有非 LLM 指令 < 1 秒 |
| 測試覆蓋率 | > 80% |
| PyPI 發布 | `pip install agentforge` 可用 |

---

*本文件為 FSM Stage 1 產出，待 CEO 確認後進入 Stage 2（架構設計 + 開發計畫）。*
