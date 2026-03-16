# AgentForge v0.1.0 — 完整使用說明手冊

> **YAML 定義 AI Agent，一行執行，三級自動修復**

---

## 目錄

1. [系統需求](#1-系統需求)
2. [安裝方式](#2-安裝方式)
3. [快速開始（5 分鐘教程）](#3-快速開始)
4. [CLI 指令完整參考](#4-cli-指令完整參考)
5. [Agent YAML 語法參考](#5-agent-yaml-語法參考)
6. [全域設定 (agentforge.yaml)](#6-全域設定)
7. [Provider 設定指南](#7-provider-設定指南)
8. [模板語法](#8-模板語法)
9. [三級自動修復機制](#9-三級自動修復機制)
10. [成本追蹤與預算管理](#10-成本追蹤與預算管理)
11. [範例 Agent](#11-範例-agent)
12. [疑難排解](#12-疑難排解)

---

## 1. 系統需求

| 項目 | 最低需求 |
|------|---------|
| Python | 3.10 以上 |
| 作業系統 | Windows 10/11, macOS, Linux |
| 磁碟空間 | 約 50MB（含依賴套件）|
| 網路 | 需要（呼叫 LLM API 時）|

### 可選：本地模型

如果使用 Ollama 本地模型（免費、無需網路）：
- 安裝 [Ollama](https://ollama.com)
- 至少 8GB RAM（建議 16GB+）
- 下載模型：`ollama pull qwen3:14b`

---

## 2. 安裝方式

### 方式 A：pip 安裝（推薦）

```bash
pip install agentforge
```

### 方式 B：從原始碼安裝

```bash
git clone https://github.com/your-org/agentforge.git
cd agentforge
pip install -e ".[dev]"
```

### 驗證安裝

```bash
agentforge --version
# 輸出：agentforge, version 0.1.0
```

---

## 3. 快速開始

### Step 1：建立專案

```bash
agentforge init my-project
cd my-project
```

這會建立以下結構：
```
my-project/
├── agentforge.yaml          # 全域設定（Provider、預算）
├── agents/
│   └── example.yaml          # 範例 Agent
└── .agentforge/              # 執行記錄（SQLite）
```

### Step 2：設定 API Key

```bash
# OpenAI（如果使用 OpenAI 模型）
export OPENAI_API_KEY="sk-your-key-here"

# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-key-here"

# 或使用 Ollama（免費本地模型，無需 API key）
# 確保 Ollama 已啟動：ollama serve
```

### Step 3：修改全域設定（可選）

打開 `agentforge.yaml`，調整預設模型：

```yaml
# 使用 Ollama 本地模型（免費）
default_model: ollama/qwen3:14b

# 或使用 OpenAI
default_model: openai/gpt-4o-mini
```

### Step 4：執行 Agent

```bash
# 先模擬執行（不實際操作）
agentforge run example --dry-run

# 正式執行
agentforge run example

# 詳細輸出模式
agentforge run example -v
```

### Step 5：查看結果

```bash
# 查看執行統計
agentforge status
```

---

## 4. CLI 指令完整參考

### `agentforge init <name>`

初始化新的 AgentForge 專案。

```bash
agentforge init my-project
```

**行為**：
- 建立 `<name>/` 目錄
- 複製 `agentforge.yaml` 全域設定模板
- 複製 `agents/example.yaml` 範例 Agent
- 建立 `.agentforge/` 執行記錄目錄

**注意**：如果目錄已存在，會報錯不覆蓋。

---

### `agentforge run <agent> [OPTIONS]`

執行指定的 Agent。

```bash
agentforge run example              # 正式執行
agentforge run example --dry-run    # 模擬執行
agentforge run example -v           # 詳細輸出
agentforge run code-reviewer -v     # 執行 code-reviewer agent
```

**參數**：
| 參數 | 說明 |
|------|------|
| `<agent>` | Agent 名稱（對應 `agents/<agent>.yaml`）|
| `--dry-run` | 模擬執行，不實際呼叫 LLM 或執行命令 |
| `-v, --verbose` | 顯示詳細輸出（每步驟的完整結果）|

**退出碼**：
- `0`：所有步驟成功
- `1`：有步驟失敗

---

### `agentforge list`

列出專案中所有可用的 Agent。

```bash
agentforge list
```

**輸出範例**：
```
╭──────────────────────────────────────────╮
│          AgentForge Agents               │
├─────────────┬───────────────┬────────────┤
│ Name        │ Description   │ Steps      │
├─────────────┼───────────────┼────────────┤
│ example     │ 檔案分析器     │ 3          │
│ code-review │ 程式碼審查員   │ 3          │
╰─────────────┴───────────────┴────────────╯
Total: 2 agents
```

---

### `agentforge status [OPTIONS]`

顯示執行記錄統計與成本。

```bash
agentforge status
agentforge status --db path/to/.agentforge/tracker.db
```

**參數**：
| 參數 | 說明 |
|------|------|
| `--db` | 指定資料庫路徑（預設自動搜尋）|

---

### `agentforge --version`

顯示版本號。

### `agentforge --help`

顯示所有可用命令。

---

## 5. Agent YAML 語法參考

每個 Agent 是一個 YAML 檔案，放在 `agents/` 目錄下。

### 完整語法

```yaml
# 必要欄位
name: my-agent                    # Agent 名稱（唯一識別）
steps:                            # 步驟列表（至少 1 個）
  - name: step1                   # 步驟名稱（同 Agent 內唯一）
    action: shell                 # 動作類型：shell | llm | save

# 可選欄位
description: "Agent 描述"         # Agent 描述
model: openai/gpt-4o-mini        # 預設 LLM 模型（覆蓋全域設定）
max_retries: 3                    # 最大重試次數（1-10，預設 3）
```

### 三種動作類型

#### `action: shell` — 執行系統命令

```yaml
- name: get_diff
  action: shell
  command: "git diff main...HEAD"
```

支援所有 Shell 語法（管道、重導向等）。

#### `action: llm` — 呼叫 LLM

```yaml
- name: review_code
  action: llm
  prompt: |
    請審查以下程式碼差異，找出潛在問題：
    {{ steps.get_diff.output }}
  model: openai/gpt-4o            # 可選：覆蓋 Agent 預設模型
  input: "{{ steps.get_diff.output }}"  # 可選：額外輸入
```

#### `action: save` — 寫入檔案

```yaml
- name: save_report
  action: save
  path: "output/review-report.md"
  content: "{{ steps.review_code.output }}"
```

自動建立父目錄。

---

## 6. 全域設定

`agentforge.yaml` 控制全域行為：

```yaml
# 預設 LLM 模型
default_model: openai/gpt-4o-mini

# Provider 設定
providers:
  openai:
    api_key_env: OPENAI_API_KEY       # 環境變數名稱
    base_url: https://api.openai.com/v1

  ollama:
    base_url: http://localhost:11434/v1
    # Ollama 不需要 API key

  gemini:
    api_key_env: GOOGLE_API_KEY

# 預算設定
budget:
  daily_limit_usd: 10.0              # 每日預算上限（USD）
  warn_at_percent: 80.0              # 使用量警告閾值
```

---

## 7. Provider 設定指南

### OpenAI

1. 取得 API Key：https://platform.openai.com/api-keys
2. 設定環境變數：
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```
3. 在 YAML 中使用：
   ```yaml
   model: openai/gpt-4o-mini     # 經濟型
   model: openai/gpt-4o          # 高品質
   model: openai/gpt-4.1         # 最新版
   model: openai/gpt-4.1-nano    # 超低成本
   ```

### Ollama（本地免費）

1. 安裝：https://ollama.com
2. 啟動服務：`ollama serve`
3. 下載模型：`ollama pull qwen3:14b`
4. 在 YAML 中使用：
   ```yaml
   model: ollama/qwen3:14b       # 推薦
   model: ollama/llama3.1:8b     # 輕量
   model: ollama/deepseek-r1:14b # 推理
   ```

**成本：$0**（本地運算，不產生 API 費用）

### Google Gemini

1. 取得 API Key：https://aistudio.google.com/app/apikey
2. 設定環境變數：
   ```bash
   export GOOGLE_API_KEY="..."
   ```
3. 在 YAML 中使用：
   ```yaml
   model: gemini/gemini-2.0-flash   # 快速
   model: gemini/gemini-2.5-pro     # 高品質
   ```

---

## 8. 模板語法

AgentForge 使用 `{{ }}` 語法在步驟間傳遞資料。

### 引用前步驟輸出

```yaml
{{ steps.<step_name>.output }}    # 前一步驟的標準輸出
{{ steps.<step_name>.error }}     # 前一步驟的錯誤輸出
```

### 範例

```yaml
steps:
  - name: get_info
    action: shell
    command: "python --version"

  - name: analyze
    action: llm
    prompt: "系統版本是：{{ steps.get_info.output }}"

  - name: save
    action: save
    path: "report.md"
    content: |
      # 分析報告
      {{ steps.analyze.output }}
```

### 注意事項

- 模板引用的步驟必須在當前步驟之前執行
- 引用不存在的步驟會導致步驟失敗（不會崩潰）
- 模板語法可用在 `command`、`prompt`、`input`、`path`、`content` 欄位

---

## 9. 三級自動修復機制

AgentForge 內建三級自動修復，當步驟失敗時自動嘗試修復：

| 等級 | 觸發條件 | 動作 |
|------|---------|------|
| Level 1 | 第 1 次失敗 | **注入修復提示** → 重跑該步驟 |
| Level 2 | 第 2 次失敗 | **重新規劃** → 重跑整個 Pipeline |
| Level 3 | 第 3 次失敗 | **停機通知** → 輸出完整錯誤報告 |

### 設定重試次數

```yaml
max_retries: 3    # 預設，最多重試 3 次
max_retries: 5    # 容錯更高，最多 5 次
max_retries: 1    # 立即失敗，不重試
```

---

## 10. 成本追蹤與預算管理

### 即時成本追蹤

每次 LLM 呼叫都會記錄 token 數量和費用。
Ollama 本地模型費用為 $0。

### 查看統計

```bash
agentforge status
```

顯示每個 Agent 的執行次數、成功率、累計成本。

### 預算警告

在 `agentforge.yaml` 設定每日預算上限：

```yaml
budget:
  daily_limit_usd: 10.0       # 每日 $10 上限
  warn_at_percent: 80.0       # 達 80% 時警告
```

⚠️ 超預算時會顯示警告，但**不會阻擋執行**（MVP 設計決策）。

### 定價參考

| 模型 | 輸入 ($/1M tokens) | 輸出 ($/1M tokens) |
|------|-------------------|-------------------|
| openai/gpt-4o-mini | $0.15 | $0.60 |
| openai/gpt-4o | $2.50 | $10.00 |
| openai/gpt-4.1-nano | $0.10 | $0.40 |
| gemini/gemini-2.0-flash | $0.10 | $0.40 |
| ollama/* | **$0** | **$0** |

---

## 11. 範例 Agent

### 範例 1：檔案分析器（example.yaml）

```yaml
name: file-analyzer
description: "分析當前目錄的檔案結構並產出摘要報告"
model: openai/gpt-4o-mini
max_retries: 3

steps:
  - name: list_files
    action: shell
    command: "ls -la"

  - name: analyze
    action: llm
    prompt: |
      請分析以下目錄檔案列表，產出一份簡短的摘要報告，
      包括：檔案總數、總大小、最大的 3 個檔案、建議清理的項目。

      檔案列表：
      {{ steps.list_files.output }}

  - name: save_report
    action: save
    path: "file-analysis-report.md"
    content: "{{ steps.analyze.output }}"
```

### 範例 2：程式碼審查員

```yaml
name: code-reviewer
description: "自動審查 Git 差異並產出審查報告"
model: openai/gpt-4o
max_retries: 2

steps:
  - name: get_diff
    action: shell
    command: "git diff main...HEAD"

  - name: review
    action: llm
    prompt: |
      你是資深程式碼審查員。請審查以下 Git diff，
      找出：安全問題、效能問題、程式碼風格問題、邏輯錯誤。

      {{ steps.get_diff.output }}

  - name: save_review
    action: save
    path: "code-review-report.md"
    content: "{{ steps.review.output }}"
```

### 範例 3：資料處理器

```yaml
name: data-processor
description: "讀取 CSV/JSON 資料並產出分析報告"
model: openai/gpt-4o-mini

steps:
  - name: read_data
    action: shell
    command: "cat data.csv"

  - name: analyze
    action: llm
    prompt: |
      請分析以下資料，產出：
      1. 資料摘要（行數、欄位）
      2. 關鍵發現
      3. 建議的下一步分析

      {{ steps.read_data.output }}

  - name: save_result
    action: save
    path: "analysis-result.md"
    content: "{{ steps.analyze.output }}"
```

### 範例 4：自訂 Agent（使用 Ollama 免費模型）

```yaml
name: daily-report
description: "產生每日工作報告"
model: ollama/qwen3:14b
max_retries: 2

steps:
  - name: git_log
    action: shell
    command: "git log --oneline --since='1 day ago'"

  - name: summarize
    action: llm
    prompt: |
      根據以下 Git 提交記錄，用繁體中文撰寫一份簡潔的每日工作報告：
      {{ steps.git_log.output }}

  - name: save
    action: save
    path: "daily-report.md"
    content: |
      # 每日工作報告

      {{ steps.summarize.output }}
```

---

## 12. 疑難排解

### 問題：`agentforge: command not found`

**原因**：pip 安裝的 scripts 目錄不在 PATH 中。

**解決**：
```bash
# 方式 1：使用 python -m
python -m agentforge --version

# 方式 2：加入 PATH
# Windows: 將 %APPDATA%\Python\Python312\Scripts 加入 PATH
# Linux/Mac: 將 ~/.local/bin 加入 PATH
```

### 問題：`OPENAI_API_KEY not set`

**解決**：設定環境變數
```bash
export OPENAI_API_KEY="sk-..."          # Linux/Mac
set OPENAI_API_KEY=sk-...              # Windows CMD
$env:OPENAI_API_KEY="sk-..."           # Windows PowerShell
```

### 問題：Ollama 連線失敗

**解決**：
1. 確認 Ollama 正在運行：`ollama list`
2. 確認模型已下載：`ollama pull qwen3:14b`
3. 確認服務地址正確（預設 `http://localhost:11434`）

### 問題：`agents/ directory not found`

**解決**：確認你在正確的專案目錄中執行命令（有 `agentforge.yaml` 的目錄）。

### 問題：步驟失敗 — 模板變數不存在

**原因**：`{{ steps.xxx.output }}` 引用了不存在的步驟。

**解決**：確認 `xxx` 步驟名稱拼寫正確，且在引用之前執行。

### 問題：Windows 終端亂碼

**原因**：Windows CMD 預設使用 cp950 編碼，無法顯示繁體中文。

**解決**：
```bash
# 方式 1：切換為 UTF-8
chcp 65001

# 方式 2：使用 Windows Terminal（推薦）

# 方式 3：使用 PowerShell 7
```

---

## 附錄：專案架構

```
agentforge/
├── cli/                    # CLI 命令層（Click）
│   ├── main.py             # CLI 入口點
│   ├── init_cmd.py         # agentforge init
│   ├── list_cmd.py         # agentforge list
│   ├── run_cmd.py          # agentforge run
│   └── status_cmd.py       # agentforge status
├── schema/                 # 資料模型層（Pydantic v2）
│   ├── agent_def.py        # Agent 定義模型
│   ├── config.py           # 全域設定模型
│   └── validator.py        # YAML 驗證器
├── core/                   # 核心引擎
│   ├── engine.py           # Pipeline 執行引擎
│   ├── failure.py          # 三級自動修復
│   └── task_tracker.py     # SQLite 記錄追蹤
├── steps/                  # 步驟執行器
│   ├── base.py             # 抽象基底類別
│   ├── shell_step.py       # Shell 命令步驟
│   ├── llm_step.py         # LLM 呼叫步驟
│   └── save_step.py        # 檔案寫入步驟
├── llm/                    # LLM 抽象層
│   ├── router.py           # 模型路由器
│   ├── budget.py           # 成本追蹤
│   └── providers/          # Provider 實作
│       ├── base.py         # 抽象介面
│       ├── openai_compat.py # OpenAI / Ollama
│       └── gemini.py       # Google Gemini
├── utils/                  # 工具模組
│   ├── template.py         # 模板引擎
│   └── display.py          # Rich 終端輸出
└── templates/              # 專案模板
    ├── agentforge.yaml     # 全域設定模板
    ├── example.yaml        # 範例 Agent
    ├── code-reviewer.yaml  # 程式碼審查 Agent
    └── data-processor.yaml # 資料處理 Agent
```

---

**版本**：v0.1.0 | **授權**：MIT | **Python**：3.10+
