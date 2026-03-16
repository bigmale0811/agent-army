# AgentForge MVP — 開發計畫

> **FSM Stage 2 產出** | 版本：v1.0 | 日期：2026-03-17
> 狀態：待 CEO 確認
> 依賴文件：`01_spec.md`、`02_architecture.md`

---

## 1. 開發原則

### 1.1 TDD 流程（必須遵循）

每個 Task 嚴格按照以下流程：

```
RED → GREEN → REFACTOR → VERIFY

1. RED：先寫測試（必須失敗）
2. GREEN：寫最小實作讓測試通過
3. REFACTOR：重構程式碼品質
4. VERIFY：覆蓋率 ≥ 80%
```

### 1.2 不可變資料

- 所有資料模型使用 `frozen=True`（Pydantic model 或 frozen dataclass）
- 禁止 in-place mutation，回傳新物件
- 參考 `02_architecture.md` 中所有 dataclass 定義

### 1.3 檔案規模限制

- 單一檔案 ≤ 400 行（目標），≤ 800 行（上限）
- 單一函式 ≤ 50 行
- 巢狀深度 ≤ 4 層

### 1.4 複用規範

- **直接複製**的模組：保持原始碼風格，僅改 import 路徑
- **借鑑重寫**的模組：保持介面設計精神，簡化實作
- **全新開發**的模組：遵循架構文件定義的介面

---

## 2. 開發時程總覽

```
Week 1: 基礎框架                Week 2: 核心引擎                Week 3: 修復+追蹤
┌─────────────────────┐        ┌─────────────────────┐        ┌─────────────────────┐
│ 1.1 專案初始化       │        │ 2.1 Step框架+Shell  │        │ 3.1 三級修復         │
│ 1.2 CLI 框架        │        │ 2.2 LLMStep+Provider│        │ 3.2 TaskTracker      │
│ 1.3 YAML Schema     │        │ 2.3 SaveStep+Pipeline│        │ 3.3 dry-run          │
└─────────────────────┘        └─────────────────────┘        └─────────────────────┘

Week 4: 預算+擴展                Week 5: 品質保證
┌─────────────────────┐        ┌─────────────────────┐
│ 4.1 BudgetTracker   │        │ 5.1 E2E 測試        │
│ 4.2 status 命令     │        │ 5.2 文件撰寫        │
│ 4.3 Gemini/Ollama   │        │ 5.3 打包發布        │
└─────────────────────┘        └─────────────────────┘
```

### 行數估算

| 類別 | 行數 | 說明 |
|------|------|------|
| 直接複製 | ~613 | Provider 全套（< 5% 改動） |
| 借鑑重寫 | ~1,516 → ~470 | FailureHandler + TaskTracker + BudgetTracker |
| 全新開發 | ~3,015 | CLI + Schema + Engine + Steps + Utils + Templates |
| 測試 | ~1,980 | 單元測試 + 整合測試 + E2E 測試 |
| **總計** | **~6,078** | |

---

## 3. 每週 Task 詳細描述

### Week 1：基礎框架

#### Task 1.1：專案初始化

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-1（安裝與初始化） |
| **複用/全新** | 全新 |
| **預估行數** | 程式碼 120 行 + 測試 60 行 |
| **前置依賴** | 無 |

**交付內容**：

1. 建立 `agentforge/` 套件目錄結構（完整 6 層）
2. `pyproject.toml`（PEP 621 格式）
   - 套件名稱：`agentforge`
   - Python 版本：`>=3.10`
   - 依賴：click, pyyaml, rich, openai, google-generativeai, pydantic
   - 入口點：`[project.scripts] agentforge = "agentforge.cli.main:cli"`
3. `agentforge/__init__.py`（版本號 `__version__ = "0.1.0"`）
4. `agentforge/__main__.py`（`python -m agentforge` 入口）
5. `agentforge/templates/agentforge.yaml`（全域設定模板）
6. `agentforge/templates/example.yaml`（範例 Agent）
7. `.gitignore` 更新（加入 `.agentforge/`、`*.db`）

**測試**：
- `test_package_importable`：`import agentforge` 成功
- `test_version_defined`：`agentforge.__version__` 為有效 semver
- `test_templates_exist`：模板檔案存在且為有效 YAML

---

#### Task 1.2：CLI 框架

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-7（CLI 完整性） |
| **複用/全新** | 全新 |
| **預估行數** | 程式碼 350 行 + 測試 200 行 |
| **前置依賴** | Task 1.1 |

**交付內容**：

1. `cli/main.py`：Click group + version 命令
2. `cli/init_cmd.py`：`agentforge init <name>`
   - 建立目錄結構：`<name>/agentforge.yaml` + `agents/example.yaml` + `.agentforge/`
   - 從 `templates/` 複製模板
   - 已存在目錄時給明確錯誤
3. `cli/list_cmd.py`：`agentforge list`
   - 掃描 `agents/` 目錄，列出所有 `.yaml` 檔案
   - 顯示名稱、描述、模型
4. `cli/run_cmd.py`：骨架（實際執行邏輯 Task 2.3 實作）
   - 接受 `agent` 參數 + `--dry-run` + `--verbose` 選項
   - 載入 YAML（呼叫 Schema 層）
   - 暫時印出 "Not implemented yet"
5. `cli/status_cmd.py`：骨架（實際查詢邏輯 Task 4.2 實作）
6. 所有命令支援 `--help`

**測試**：
- `test_cli_help`：`agentforge --help` 輸出包含所有子命令
- `test_init_creates_structure`：init 建立正確目錄
- `test_init_existing_dir_error`：目錄已存在時報錯
- `test_list_finds_agents`：list 找到 agents/ 中的 YAML
- `test_list_empty_dir`：無 Agent 時顯示提示
- `test_version`：`agentforge version` 輸出版本號
- `test_run_missing_agent`：run 不存在的 Agent 時報錯

---

#### Task 1.3：YAML Schema

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-2（Agent 定義解析） |
| **複用/全新** | 全新 |
| **預估行數** | 程式碼 300 行 + 測試 250 行 |
| **前置依賴** | Task 1.1 |

**交付內容**：

1. `schema/agent_def.py`：
   - `ActionType` 枚舉（shell / llm / save）
   - `StepDef` Pydantic model（含交叉驗證）
   - `ModelRef` Pydantic model（provider/model-name 解析）
   - `AgentDef` Pydantic model（含步驟名稱唯一性驗證）
2. `schema/config.py`：
   - `ProviderSettings` Pydantic model
   - `BudgetSettings` Pydantic model
   - `GlobalConfig` Pydantic model
3. `schema/loader.py`：
   - `load_agent(path: Path) -> AgentDef`：載入 + 驗證 Agent YAML
   - `load_config(path: Path) -> GlobalConfig`：載入 + 驗證全域設定
   - 驗證失敗時輸出人類可讀的錯誤訊息（行號 + 欄位名）

**測試**：
- `test_valid_agent_yaml`：合法 YAML 解析成功
- `test_missing_required_field`：缺少 name/model/steps 時報錯
- `test_invalid_action_type`：action 不是 shell/llm/save 時報錯
- `test_duplicate_step_names`：步驟名稱重複時報錯
- `test_shell_requires_command`：action=shell 但沒有 command 時報錯
- `test_model_ref_parsing`：`openai/gpt-4o` 正確解析
- `test_model_ref_invalid`：沒有 `/` 時報錯
- `test_global_config_defaults`：預設值正確
- `test_template_variable_format`：`{{ steps.x.output }}` 格式接受
- `test_steps_limit`：超過 100 步驟時警告

---

### Week 2：核心引擎

#### Task 2.1：Step 框架 + ShellStep

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-3（FSM 執行引擎）、AC-7（CLI） |
| **複用/全新** | 全新 |
| **預估行數** | 程式碼 280 行 + 測試 200 行 |
| **前置依賴** | Task 1.3 |

**交付內容**：

1. `steps/base.py`：
   - `StepOutput` frozen dataclass（success, output, error, cost_usd, tokens）
   - `BaseStep` 抽象類別（execute, dry_run）
2. `steps/shell_step.py`：
   - `ShellStep` 實作（subprocess.run）
   - 超時處理（`timeout` 參數）
   - stdout/stderr 捕獲
   - 模板變數替換（呼叫 TemplateEngine）
3. `utils/template.py`：
   - `TemplateEngine.render(template, context)` 靜態方法
   - 正則匹配 `{{ steps.<name>.output }}`
   - 未知變數 → KeyError + 明確訊息

**測試**：
- `test_shell_echo`：`echo hello` 回傳 "hello"
- `test_shell_timeout`：超時拋出錯誤
- `test_shell_failure`：命令失敗（exit code != 0）回傳 error
- `test_shell_template_substitution`：命令中的 `{{ }}` 正確替換
- `test_template_render_basic`：基本變數替換
- `test_template_render_missing_var`：缺少變數時拋出 KeyError
- `test_template_render_no_vars`：無變數模板原文回傳
- `test_dry_run_shell`：dry-run 回傳描述，不執行

---

#### Task 2.2：LLMStep + Provider

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-5（多模型路由） |
| **複用/全新** | 直接複製 Provider + 全新 LLMStep |
| **預估行數** | 複製 613 行 + 全新 350 行 + 測試 250 行 |
| **前置依賴** | Task 2.1 |

**交付內容**：

1. **直接複製**（< 5% 改動）：
   - `llm/providers/base.py` ← `src/llm/providers/base.py`
   - `llm/providers/openai_compat.py` ← `src/llm/providers/openai_compat.py`
   - `llm/providers/gemini.py` ← `src/llm/providers/gemini.py`
   - 改動：import 路徑調整
2. **全新開發**：
   - `llm/router.py`：`LLMRouter` 類別
     - 懶載入 Provider
     - `call(model_ref, prompt, context)` → `LLMCallResult`
     - Provider 快取（避免重複初始化）
   - `steps/llm_step.py`：`LLMStep` 類別
     - 組合 prompt + input context
     - 呼叫 LLMRouter
     - 回傳 StepOutput（含 cost）
3. **Ollama 支援**（不建獨立 Provider）：
   - 在 `LLMRouter` 中，當 provider=ollama 時：
     - `base_url = "http://localhost:11434/v1"`
     - `api_key = "ollama"`（OpenAI SDK 要求非空）
     - 使用 `OpenAICompatProvider`

**測試**：
- `test_router_openai_call`：mock OpenAI 呼叫成功
- `test_router_ollama_uses_openai_compat`：Ollama 走 OpenAI 相容路徑
- `test_router_unknown_provider`：未知 Provider 報明確錯誤
- `test_router_lazy_init`：Provider 只在首次呼叫時初始化
- `test_llm_step_basic`：LLMStep 正確呼叫 Router
- `test_llm_step_template_input`：input 中的 `{{ }}` 正確替換
- `test_llm_step_model_override`：step 級別 model 覆蓋 agent 級別
- `test_provider_base_interface`：BaseProvider 介面完整性

---

#### Task 2.3：SaveStep + Pipeline + run 命令

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-3（FSM 執行引擎）、AC-7（CLI） |
| **複用/全新** | 全新 |
| **預估行數** | 程式碼 400 行 + 測試 280 行 |
| **前置依賴** | Task 2.2 |

**交付內容**：

1. `steps/save_step.py`：`SaveStep` 類別
   - 寫入檔案（自動建立目錄）
   - content 模板替換
   - path 模板替換
2. `core/engine.py`：`PipelineEngine` 類別
   - `ProgressCallback` Protocol 定義
   - `StepResult` / `PipelineResult` frozen dataclass
   - `execute(agent_def, dry_run)` 方法
   - 步驟間 context 傳遞（`_build_context`）
   - 每步計時
3. `utils/display.py`：`DisplayManager` 類別
   - 實作 `ProgressCallback`
   - Rich 進度輸出：`[1/3] step_name... ✅ (0.3s, $0.003)`
   - Pipeline 完成摘要
4. `cli/run_cmd.py`：完整實作
   - 載入 GlobalConfig + AgentDef
   - 建構 PipelineEngine（注入 LLMRouter + DisplayManager）
   - 執行 pipeline
   - 顯示結果

**測試**：
- `test_save_step_creates_file`：SaveStep 建立檔案
- `test_save_step_creates_dirs`：自動建立目錄
- `test_save_step_template`：content 模板替換
- `test_pipeline_three_steps`：3 步 pipeline 完整執行
- `test_pipeline_context_passing`：步驟間 output 正確傳遞
- `test_pipeline_step_failure`：步驟失敗時 pipeline 結果為 failed
- `test_pipeline_dry_run`：dry-run 不實際執行
- `test_run_cmd_integration`：CLI run 命令整合測試（mock LLM）
- `test_display_progress`：DisplayManager 輸出正確格式

---

### Week 3：修復 + 追蹤

#### Task 3.1：三級修復

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-4（三級自動修復） |
| **複用/全新** | 借鑑 FailureInjector 重寫 |
| **預估行數** | 程式碼 250 行 + 測試 200 行 |
| **前置依賴** | Task 2.3 |

**交付內容**：

1. `core/failure.py`：`FailureHandler` 類別
   - `RepairLevel` 枚舉（RETRY_WITH_FIX / REPLAN_PIPELINE / HALT）
   - `FailureRecord` frozen dataclass
   - `get_repair_level(retry_count)` → RepairLevel
   - `build_fix_prompt(step_name, error, original_prompt)` → 修復 prompt
   - `replan_pipeline(agent_def, failures)` → 新的 AgentDef（用 LLM 重新規劃）
   - `generate_report()` → 完整錯誤報告
2. 整合到 `PipelineEngine`：
   - 步驟失敗時呼叫 FailureHandler
   - 第 1 級：注入修復 prompt → 重跑該步驟
   - 第 2 級：LLM 重新規劃 → 全部重跑
   - 第 3 級：停機 → exit(1)
   - 修復歷史記錄到 DisplayManager

**測試**：
- `test_level_1_retry_with_fix`：第 1 次失敗觸發修復 prompt
- `test_level_2_replan`：第 2 次失敗觸發 LLM 重新規劃
- `test_level_3_halt`：第 3 次失敗停機
- `test_fix_prompt_contains_error`：修復 prompt 包含錯誤日誌
- `test_replan_returns_valid_agent`：重新規劃回傳合法 AgentDef
- `test_report_contains_all_failures`：報告包含所有失敗記錄
- `test_pipeline_with_failure_recovery`：Pipeline 整合失敗修復
- `test_max_retries_respected`：遵循 max_retries 設定

---

#### Task 3.2：TaskTracker + SQLite

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-3（執行結果持久化）、AC-4（修復歷史記錄）、AC-6（成本追蹤） |
| **複用/全新** | 借鑑 TaskBoard 重寫 |
| **預估行數** | 程式碼 300 行 + 測試 200 行 |
| **前置依賴** | Task 2.3 |

**交付內容**：

1. `core/task_tracker.py`：`TaskTracker` 類別
   - SQLite 初始化（3 表：runs + step_runs + cost_log）
   - WAL 模式 + foreign_keys
   - `start_run()` / `record_step()` / `finish_run()`
   - `get_agent_stats()` / `get_all_stats()`
   - `get_recent_runs()`
   - SQLite 損壞時自動重建
2. 整合到 `PipelineEngine`：
   - 每步執行前後呼叫 TaskTracker
   - Pipeline 結束時更新 run 狀態

**測試**：
- `test_start_and_finish_run`：run 生命週期
- `test_record_step`：步驟記錄寫入
- `test_agent_stats`：統計查詢正確
- `test_all_stats`：全域統計正確
- `test_recent_runs`：最近記錄查詢
- `test_wal_mode`：WAL 模式生效
- `test_db_auto_rebuild`：SQLite 損壞時自動重建
- `test_concurrent_read`：併發讀取不阻塞

---

#### Task 3.3：dry-run 模式

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-3（dry-run）、AC-7（CLI） |
| **複用/全新** | 全新 |
| **預估行數** | 程式碼 80 行 + 測試 100 行 |
| **前置依賴** | Task 2.3 |

**交付內容**：

1. 每個 Step 類別實作 `dry_run()` 方法：
   - `ShellStep.dry_run()` → `"[SHELL] 將執行: git diff main...HEAD"`
   - `LLMStep.dry_run()` → `"[LLM] 將呼叫 openai/gpt-4o: 請審查...（前 100 字）"`
   - `SaveStep.dry_run()` → `"[SAVE] 將寫入: review-report.md"`
2. `PipelineEngine.execute(dry_run=True)` 跳過實際執行
3. DisplayManager 用不同顏色顯示 dry-run 輸出

**測試**：
- `test_dry_run_no_side_effects`：dry-run 不建立檔案、不呼叫 LLM、不執行命令
- `test_dry_run_shows_all_steps`：顯示所有步驟描述
- `test_dry_run_cli`：`agentforge run example --dry-run` E2E
- `test_dry_run_no_db_write`：dry-run 不寫入 SQLite

---

### Week 4：預算 + 擴展

#### Task 4.1：BudgetTracker

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-6（成本追蹤） |
| **複用/全新** | 簡化提取 BudgetGuard |
| **預估行數** | 程式碼 200 行 + 測試 150 行 |
| **前置依賴** | Task 3.2 |

**交付內容**：

1. `llm/budget.py`：`BudgetTracker` 類別
   - 定價表（OpenAI / Gemini / Ollama）
   - `CostEntry` frozen dataclass
   - `record(agent, step, model, tokens)` → CostEntry
   - `get_daily_total()` / `get_agent_total()`
   - `check_budget()` → `(is_over, message)`
   - `calculate_cost()` 靜態方法
2. 整合到 `LLMRouter`：
   - 每次 LLM 呼叫後自動記錄成本
   - 超預算時在終端顯示警告（不阻擋）

**測試**：
- `test_cost_calculation_openai`：OpenAI 成本計算正確
- `test_cost_calculation_ollama`：Ollama 成本為 0
- `test_record_updates_total`：記錄後總成本更新
- `test_daily_total`：每日統計正確
- `test_agent_total`：Agent 統計正確
- `test_budget_warning`：超預算時回傳警告訊息
- `test_budget_no_block`：超預算不阻擋執行

---

#### Task 4.2：status 命令

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-6（成本統計）、AC-7（CLI） |
| **複用/全新** | 全新 |
| **預估行數** | 程式碼 180 行 + 測試 120 行 |
| **前置依賴** | Task 4.1 |

**交付內容**：

1. `cli/status_cmd.py`：完整實作
   - 從 TaskTracker 查詢全域統計
   - 從 BudgetTracker 查詢成本統計
   - 合併為 Dashboard 表格
2. `utils/display.py`：擴充
   - `render_status_table(stats)` → Rich Table
   - 顯示：Agent 名稱、執行數、成功率、本月成本
   - 底部總計行：總成本 / 預算

**測試**：
- `test_status_empty_db`：空資料庫時顯示 "無執行記錄"
- `test_status_with_data`：有資料時顯示正確表格
- `test_status_cost_summary`：成本統計正確
- `test_status_cli`：`agentforge status` E2E

---

#### Task 4.3：Gemini + Ollama Provider

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-5（多模型路由） |
| **複用/全新** | 直接複製 + 整合測試 |
| **預估行數** | 程式碼 50 行（整合）+ 測試 120 行 |
| **前置依賴** | Task 2.2 |

**交付內容**：

1. 驗證 `GeminiProvider` 複製後可正常工作
2. 驗證 Ollama via OpenAI 相容 API 可正常工作
3. `LLMRouter` 整合測試：
   - 從 YAML 讀取 provider → 自動路由到正確 Provider
   - Agent YAML `model` 覆蓋全域設定
4. `agentforge.yaml` 模板中新增 Gemini + Ollama 設定區塊

**測試**：
- `test_gemini_provider_basic`：Gemini 基本呼叫（mock）
- `test_ollama_connection`：Ollama 連線測試（mock base_url）
- `test_ollama_no_api_key_needed`：Ollama 不需要 API key
- `test_model_override_in_step`：step 級別 model 覆蓋
- `test_config_loading_all_providers`：全域設定正確載入 3 個 Provider
- `test_unavailable_provider_error`：Provider 不可用時明確報錯

---

### Week 5：品質保證

#### Task 5.1：E2E 測試

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-1 ~ AC-7（全部） |
| **複用/全新** | 全新 |
| **預估行數** | 測試 350 行 |
| **前置依賴** | Task 4.2 |

**交付內容**：

1. `tests/e2e/test_full_workflow.py`：
   - `test_init_run_status_flow`：init → 建立 Agent → run → status 完整流程
   - `test_failure_recovery_e2e`：3 級修復 E2E（mock LLM 控制失敗）
   - `test_dry_run_e2e`：dry-run 不產生副作用
   - `test_multi_step_pipeline`：多步 pipeline 資料傳遞
   - `test_cost_tracking_e2e`：成本記錄 E2E
2. `tests/e2e/test_cli_e2e.py`：
   - `test_all_commands_help`：所有命令 --help 正常
   - `test_init_from_scratch`：全新 init 到可執行
   - `test_error_messages_actionable`：錯誤訊息包含建議
   - `test_exit_codes`：成功 = 0，失敗 = 1

**測試規範**：
- 所有 E2E 測試使用 `subprocess.run()` 執行 CLI
- 使用 `tmp_path` fixture 隔離檔案系統
- Mock LLM（避免真實 API 呼叫）
- 每個測試 < 10 秒

---

#### Task 5.2：文件撰寫

| 項目 | 內容 |
|------|------|
| **AC 對應** | — |
| **複用/全新** | 全新 |
| **預估行數** | 文件 ~500 行 |
| **前置依賴** | Task 5.1 |

**交付內容**：

1. `README.md`：
   - 安裝指南（pip install）
   - 快速開始（5 分鐘教程）
   - YAML 語法參考
   - Provider 設定指南
   - 範例 Agent 列表
2. `CHANGELOG.md`：v0.1.0 變更日誌
3. `agentforge/templates/` 更新：
   - 3 個範例 Agent：code-reviewer、data-processor、report-generator

---

#### Task 5.3：打包發布

| 項目 | 內容 |
|------|------|
| **AC 對應** | AC-1（pip install） |
| **複用/全新** | 全新 |
| **預估行數** | 設定 ~80 行 |
| **前置依賴** | Task 5.2 |

**交付內容**：

1. `pyproject.toml` 最終確認：
   - 所有 metadata 完整
   - 依賴版本鎖定
   - `[project.scripts]` 入口點
2. `python -m build` 成功產出 `.whl` + `.tar.gz`
3. `pip install dist/agentforge-0.1.0-*.whl` 本地測試
4. `agentforge version` / `init` / `list` 安裝後可用
5. TestPyPI 上傳測試（選做）

---

## 4. 交付檢查清單

每個 Task 完成前必須通過：

- [ ] 所有新增/修改的程式碼有對應測試
- [ ] `python -m pytest tests/` 全部通過
- [ ] 覆蓋率 ≥ 80%（`python -m pytest --cov=agentforge tests/`）
- [ ] 無 type check 錯誤（若啟用 mypy/pyright）
- [ ] 檔案行數 ≤ 800 行
- [ ] 函式行數 ≤ 50 行
- [ ] 所有 frozen dataclass / Pydantic model 為不可變
- [ ] 錯誤訊息清晰、有 actionable 建議
- [ ] Conventional Commits 格式 commit

---

## 5. 依賴關係圖

```
Task 1.1 專案初始化
  │
  ├──→ Task 1.2 CLI 框架
  │       │
  │       └──→ Task 2.3 SaveStep+Pipeline+run ──→ Task 3.1 三級修復
  │                │                                     │
  │                ├──→ Task 3.2 TaskTracker ──→ Task 4.1 BudgetTracker
  │                │                                     │
  │                └──→ Task 3.3 dry-run                 └──→ Task 4.2 status
  │
  ├──→ Task 1.3 YAML Schema
  │       │
  │       └──→ Task 2.1 Step框架+Shell
  │               │
  │               └──→ Task 2.2 LLMStep+Provider ──→ Task 4.3 Gemini/Ollama
  │                       │
  │                       └──→ Task 2.3（同上）
  │
  └──────────────────────────────────────────────────→ Task 5.1 E2E
                                                         │
                                                         └──→ Task 5.2 文件
                                                                │
                                                                └──→ Task 5.3 打包
```

### 關鍵路徑（Critical Path）

```
1.1 → 1.2 → 2.1 → 2.2 → 2.3 → 3.1 → 3.3 → 4.1 → 5.1
                                        │
                                        └→ 4.2（可與 4.1 平行）
```

**瓶頸分析**：
- Task 2.2（LLMStep + Provider）是整個 pipeline 的核心節點，所有後續功能都依賴它
- Task 3.1（三級修復）是核心差異化功能，需要高品質實作
- Week 1 的 Task 1.2 和 1.3 可以平行開發（互不依賴）
- Week 3 的 Task 3.2 和 3.3 可以平行開發（都依賴 2.3 但互不依賴）
- Week 4 的 Task 4.3 可以提前（只依賴 2.2）

### 平行化機會

| 時段 | 可平行的 Task | 說明 |
|------|--------------|------|
| Week 1 | 1.2 + 1.3 | CLI 骨架和 Schema 互不依賴 |
| Week 3 | 3.2 + 3.3 | TaskTracker 和 dry-run 互不依賴 |
| Week 4 | 4.1 + 4.3 | BudgetTracker 和 Provider 整合互不依賴 |

---

## 6. 風險與緩解

### R-1：Ollama OpenAI 相容 API 不完整

- **風險**：某些 OpenAI SDK 功能 Ollama 不支援（如 function calling、streaming）
- **影響**：LLM Step 可能無法正常呼叫 Ollama
- **緩解**：
  - MVP 只使用基本 `chat.completions.create()`，不使用進階功能
  - Task 4.3 專門做 Ollama 整合測試
  - 備案：若相容 API 問題太多，用 `requests` 直接呼叫 Ollama 原生 API

### R-2：三級修復中 LLM 重新規劃品質不穩定

- **風險**：第 2 級修復（LLM 重新規劃 pipeline）可能產出無效 YAML
- **影響**：自動修復變成無限迴圈
- **緩解**：
  - LLM 產出的 YAML 必須通過 Pydantic 驗證
  - 驗證失敗直接升級到第 3 級（停機）
  - max_retries 硬限制（預設 3，不可超過 10）

### R-3：PyPI 名稱衝突

- **風險**：`agentforge` 名稱可能已被佔用
- **影響**：無法 `pip install agentforge`
- **緩解**：
  - 提前到 PyPI 檢查名稱可用性
  - 備選名稱：`agentforge-cli`、`agentforgeai`
  - 先上 TestPyPI 測試

### R-4：Rich 終端相容性

- **風險**：某些 Windows 終端不支援 Rich 的 ANSI 顏色
- **影響**：status 和 run 輸出亂碼
- **緩解**：
  - Rich 自帶 Windows 偵測（`colorama` fallback）
  - 加入 `--no-color` 全域選項
  - CI/CD 中使用 `TERM=dumb`

### R-5：Pydantic v2 驗證錯誤訊息不夠友好

- **風險**：Pydantic v2 的 ValidationError 對 YAML 使用者不友好
- **影響**：使用者看到 Python 技術錯誤
- **緩解**：
  - 在 `schema/loader.py` 捕獲 `ValidationError`，轉換為人類可讀格式
  - 包含 YAML 行號（PyYAML 的 `Mark` 物件）
  - 提供修復建議

---

## 7. Task 與 AC 對照矩陣

| Task | AC-1 | AC-2 | AC-3 | AC-4 | AC-5 | AC-6 | AC-7 |
|------|------|------|------|------|------|------|------|
| 1.1 專案初始化 | **主要** | | | | | | |
| 1.2 CLI 框架 | 部分 | | | | | | **主要** |
| 1.3 YAML Schema | 部分 | **主要** | | | | | |
| 2.1 Step+Shell | | | **主要** | | | | |
| 2.2 LLM+Provider | | | | | **主要** | | |
| 2.3 Save+Pipeline | | | **主要** | | | | 部分 |
| 3.1 三級修復 | | | | **主要** | | | |
| 3.2 TaskTracker | | | 部分 | 部分 | | **主要** | |
| 3.3 dry-run | | | 部分 | | | | 部分 |
| 4.1 BudgetTracker | | | | | | **主要** | |
| 4.2 status 命令 | | | | | | 部分 | **主要** |
| 4.3 Gemini/Ollama | | | | | **主要** | | |
| 5.1 E2E 測試 | 驗證 | 驗證 | 驗證 | 驗證 | 驗證 | 驗證 | 驗證 |
| 5.2 文件 | | | | | | | |
| 5.3 打包發布 | **主要** | | | | | | |

---

*本文件為 FSM Stage 2 開發計畫產出，待 CEO 確認後進入 Stage 3&4（TDD 開發）。*
