# 🧠 Active Context
更新：2026-03-06

## 目前進行中
- **Stock Analyzer WO-001 Bug 修復**：BUG-1 + BUG-2 已修復，待 Code Review 及重跑驗證
  - BUG-1 ✅：`market_research_report` → `market_report` key 修正
  - BUG-2 ✅：新增 `clean_thinking_tags()` 清除 QWen3 think 標籤
  - BUG-3 ⏳：報告中文化，留待 DEV-C1
  - 12 項新增單元測試全部 PASS
  - 派工單：`.claude/work_orders/WO-001-stock-analyzer-bugfix.md`
- **Stock Analyzer 整體進度**：DEV-A 批次完成，DEV-B 進行中
  - 基底：TradingAgents v0.2.0（Apache 2.0）
  - LLM：Ollama QWen3 14B 本地端
  - 首次 AAPL 分析已跑完（446 秒），驗證了端到端流程
  - 獨立執行腳本：`scripts/run_analysis.py`（PID lock + 狀態追蹤）
- Singer Agent ECC v2 重建：批次 A 已完成，進行中批次 B

## 最近完成
- **✅ FSM 狀態機工作流整合**：
  - `.claude/rules/common/state-machine.md`（6 Stage 遞迴驗證 FSM 核心規則）
  - `.claude/roles/`（5 個角色設定檔：architect、planner、developer、reviewer、error-analyst）
  - `CLAUDE.md` 更新：ECC v2 Phase 替換為 FSM Stage 表述
  - `.claude/rules/common/agents.md` 更新：FSM Stage 角色對應表
  - 關鍵改進：失敗時退回 Stage 2（重新規劃），不只是修 bug
- **✅ Singer Agent 批次 A（DEV-1 + DEV-2）TDD 完成**：
  - `src/singer_agent/__init__.py`（空模組）
  - `src/singer_agent/models.py`（6 個 dataclass：SongResearch, SongSpec, CopySpec, PrecheckResult, ProjectState, PipelineRequest）
  - `src/singer_agent/config.py`（路徑常數 + 環境變數 + dotenv）
  - `tests/singer_agent/conftest.py`（共用 fixtures）
  - `tests/singer_agent/test_models.py`（60 項測試）
  - `tests/singer_agent/test_config.py`（36 項測試）
  - 96 項全部 PASS，覆蓋率 98%（models 100%, config 93%）
- **✅ ECC v2 流程引擎建立**：
  - 文件模板系統：`docs/templates/` 5 個模板（spec、architecture、dev_plan、test_plan、test_report）
  - QA Agent：`.claude/agents/qa-reviewer.md`（獨立品質測試，只讀 spec 不讀程式碼）
  - 流程引擎：升級 `/orchestrate` 指令，8 個 Phase + 迴圈機制 + 人工閘門
  - ECC rules 更新：`development-workflow.md`、`agents.md`、`CLAUDE.md`
  - 核心改進：文件驅動、角色分離、獨立 QA、迴圈修復（最多 3 輪）
- **✅ 安裝精靈 E2E 自動化測試**（完整 ECC 流程）
- **✅ 修復 4 個安裝精靈 bug**
- **✅ LLM 雲端模組** (`src/llm/`)
- **✅ Setup Wizard v2.0 完全重寫**
- **✅ gh CLI 安裝備援機制**（winget → MSI → zip → 手動）

## 重要決策
- **FSM 狀態機工作流**：從 ECC v2 的 8 Phase 線性流程升級為 6 Stage FSM 遞迴流程
  - 🟢 Stage 1 需求釐清 → 🟡 Stage 2 規劃與架構 → 🔵 Stage 3&4 開發與測試
  - → 🟣 Stage 5 審查與 QA → 🔴 Stage 6 遞迴驗證
  - **關鍵差異**：失敗退回 Stage 2（重新規劃+重新架構），非僅修 bug
  - 角色設定檔在 `.claude/roles/`，自動調用
  - 最多 3 輪遞迴，超過通知使用者
- ECC 標準流程必須嚴格遵守
- CLI 互動工具必須支援 --dry-run + --auto

## 下一步
1. **WO-001 待完成**：Code Review + 重跑 AAPL 分析驗證修復效果
2. **Stock Analyzer DEV-B**：台股（2330.TW）、BTC、黃金分析測試
3. **Stock Analyzer DEV-C**：中文化（prompt 層 + 報告輸出）
4. Singer Agent v0.3 端對端測試
5. v0.3.1：服裝修改功能

## 專案現有素材
- MP3：`data/singer_agent/inbox/愛我的人和我愛的人_ζั͡ޓ擂戰އ沒人_2026_02_03_15_06_32.mp3`
- 角色圖片：`data/singer_agent/character/avatar.png`
- ComfyUI：`D:\Projects\ComfyUI`（SDXL base 1.0, PyTorch cu128）

## 使用者操作環境
- 透過 `D:\Projects\claude-code-telegram` 的 Telegram Bot 互動
- Bot 用 `claude-agent-sdk`，`cwd=D:\Projects\agent-army`
- Git repo：`https://github.com/bigmale0811/agent-army.git`

## Kanban 派工系統
- 模板：`.claude/work_orders/_template.md`
- 規則：`.claude/rules/common/kanban-orchestrator.md`
- 目前工單：`WO-001-stock-analyzer-bugfix.md` [IN_PROGRESS]

## ⚡ 最近壓縮事件
- [2026-03-06 16:37:00] Context 被自動壓縮
- [2026-03-06 ~17:00] 接續修復 WO-001，BUG-1+2 程式碼修正完成
- **請重新讀取此檔案確認進度**
