# Agent Army Project Rules

## Overview
Universal agent framework built on ECC (everything-claude-code).
Claude Code Opus 4.6 as orchestrator, with subagents and local Ollama.

## Tech Stack
- OS: Windows 10
- Languages: Python 3.12.8 (primary), Node.js (secondary)
- Local Model: Ollama + QWen3 14B (localhost:11434)
- Version Control: Git
- Language: Traditional Chinese for comments/docs, English for code

## Development Rules
- All files use UTF-8 encoding
- Python follows PEP 8
- Every module needs corresponding tests
- Commit messages use Conventional Commits format
- Complex logic needs Traditional Chinese comments
- All paths under D:\

## Agent Dispatch Strategy
- Opus 4.6: Architecture design, complex algorithms, key decisions
- Sonnet 4.5: General development, code review, refactoring
- Haiku 4.5: Formatting, simple changes, documentation
- Ollama QWen3: Local inference, draft generation, bulk tasks (save tokens)

## Communication Rules（溝通規則，最高優先級）
- **禁止沉默作業**：絕對不要在沒有回應的情況下持續工作，使用者不應該需要主動詢問「好了嗎」
- **每步回報**：每完成一個工具呼叫或步驟，立即用文字告知使用者目前進度與下一步
- **長時間操作預告**：如果即將執行耗時操作（測試、build、大量檔案處理），先告知使用者預計等待時間
- **背景任務狀態**：使用 `run_in_background` 時，告知使用者任務已在背景執行，會在完成時通知
- **明確完成宣告**：所有工作完成時，主動用摘要格式告知：做了什麼、結果如何、是否有後續事項
- **錯誤即時通報**：遇到錯誤時立即告知，不要試圖靜默重試超過一次

## Memory System（跨對話記憶，最高優先級）
- **每次新對話開始時**：必須先讀取 `data/memory/active_context.md`，了解上次做到哪裡
- **每次對話結束前**：必須更新 `active_context.md`，記錄進行中/已完成/下一步
- **每完成一個重要步驟時**：立即更新 `active_context.md`（不要等到對話結束！）
- **重大決策時**：同步寫入 `data/memory/decisions.md`
- **記憶模組位置**：`src/memory/manager.py`（MemoryManager 類別）
- **讀取記憶**：`Read data/memory/active_context.md`
- **翻閱歷史**：`ls data/memory/sessions/` 找過去的對話紀錄

## Anti-Amnesia（防失憶機制，最高優先級）

### Compaction 恢復規則
- **壓縮後第一件事**：立即讀取 `data/memory/active_context.md` 恢復記憶
- **看到「⚡ 最近壓縮事件」標記**：代表 auto-compact 剛觸發，檢查壓縮前的狀態
- **壓縮日誌**：`data/memory/compaction-log.txt` 記錄所有壓縮事件

### Token 節省策略
- **禁止在主對話讀大量原始碼**：用 Task agent 隔離讀取，只回傳摘要
- **長流水線（如 Singer Agent 8 步）**：每 2-3 步更新一次 active_context.md
- **背景任務結果**：只取關鍵輸出，不要把整個 log 倒進 context
- **大檔案**：用 `limit` 參數只讀需要的行數

### Hooks 已安裝（`.claude/settings.json`）
- `SessionStart` → `scripts/hooks/session-start.js`（自動載入記憶）✅ 已驗證
- `PreCompact` → `scripts/hooks/pre-compact.js`（壓縮前自動保存狀態）
- `PreToolUse(Edit|Write)` → `scripts/hooks/suggest-compact.js`（40 次工具呼叫後提醒）✅ 已驗證
- `PreToolUse(Bash)` → git push 前提醒更新記憶
- `SessionEnd` → `scripts/hooks/session-end.js`（自動歸檔 session）
- `PostToolUse(Bash)` → PR 建立後顯示 URL

### Rules 已安裝（`.claude/rules/`）
- `common/`: development-workflow, testing, security, coding-style, git-workflow, agents, hooks, patterns, performance
- `python/`: coding-style, testing, security, patterns, hooks

## ECC Standard Workflow（標準開發流程，每個項目必須遵守）

每個開發項目啟動前，必須先告知使用者將使用哪些 ECC 模組。

### Phase 0: RESEARCH（研究）
- **模組**：`search-first` skill + WebSearch
- **動作**：搜尋 PyPI/GitHub 有沒有現成方案
- **規則**：先搜尋再寫（`common/patterns.md`）

### Phase 1: PLAN（規劃）
- **模組**：`/plan` → `planner` agent (Opus)
- **動作**：拆解需求、識別風險、建立步驟
- **⚠️ 等使用者確認才動手寫程式碼**

### Phase 2: TDD（測試驅動開發）
- **模組**：`/tdd` → `tdd-guide` agent (Sonnet)
- **Skills**：`python-testing`, `tdd-workflow`
- **動作**：先寫測試(RED) → 寫程式(GREEN) → 重構(REFACTOR)
- **目標**：80%+ 覆蓋率

### Phase 3: REVIEW（程式碼審查）
- **模組**：`/python-review` → `python-reviewer` agent (Sonnet)
- **模組**：`security-reviewer` agent（如涉及安全/API/使用者輸入）
- **Skills**：`python-patterns`, `security-review`

### Phase 4: VERIFY（驗證）
- **模組**：`/verify`
- **動作**：type check → lint → test suite → git status
- **全部通過才能進入下一步**

### Phase 5: COMMIT（提交）
- **規則**：`common/git-workflow.md`（Conventional Commits）
- **動作**：`/checkpoint` 建立安全回滾點 → commit

### Phase 6: DOCUMENT（文件更新）
- **模組**：`/changelog` + `/update-codemaps`
- **Agent**：`doc-updater` (Haiku)

### Phase 7: MEMORY（記憶保存）
- **動作**：更新 `active_context.md`、歸檔 session

### 快捷指令
- `/orchestrate feature <描述>` — 自動串接：planner → tdd-guide → code-reviewer → security-reviewer

## Common Commands
- python -m pytest tests/
- python -m pytest tests/ --cov=src/
- pip install -r requirements.txt

## Project Paths
- Main: D:\\Projects\\agent-army
- ECC: D:\\Projects\\everything-claude-code
- Ollama MCP: D:\\Projects\\OllamaClaude