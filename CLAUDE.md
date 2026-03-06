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

## FSM 狀態機工作流（最高優先級）

> **嚴格的專案秘書模式**：由有限狀態機 (FSM) 驅動，具備遞迴驗證機制。
> 詳細規則：`.claude/rules/common/state-machine.md`
> 角色設定：`.claude/roles/`

### 狀態轉換圖
```
🟢 Stage 1 需求釐清 ──(使用者確認)──→ 🟡 Stage 2 規劃與架構
                                           │
                                     (使用者同意)
                                           ▼
                                     🔵 Stage 3&4 開發與測試
                                           │
                                     (程式碼+測試完成)
                                           ▼
                                     🟣 Stage 5 審查與 QA
                                           │
                                     (審查+測試執行)
                                           ▼
                                     🔴 Stage 6 遞迴驗證
                                          / \
                                    ❌ FAIL  ✅ PASS → 🏁 完成
                                       │
                                       ▼
                                 🟡 Stage 2（退回重新規劃）
```

### 核心規則
1. **遞迴驗證**：失敗時退回 Stage 2（重新規劃），不只是修 bug
2. **最多 3 輪**遞迴，超過停下來通知使用者
3. **🚦 人工閘門**：Stage 1→2 和 Stage 2→3 必須等使用者確認
4. **角色自動切換**：每個 Stage 自動調用對應的 `.claude/roles/` 專家

### 角色對應
| Stage | 角色 | 對應命令 |
|-------|------|---------|
| Stage 1 | Orchestrator | — |
| Stage 2 | architect + planner | `/plan` + architect agent |
| Stage 3&4 | developer (TDD) | `/tdd` |
| Stage 5 | reviewer + security | `/code-review` + `/python-review` |
| Stage 6 ❌ | error-analyst | `/build-fix` |
| Stage 6 ✅ | doc-updater | `/update-docs` |

### 快捷指令
- `/orchestrate feature <描述>` — 完整流程：Stage 1 → 2 → 3&4 → 5 → 6
- `/orchestrate bugfix <描述>` — 簡化流程：Stage 1 → 2(跳過架構) → 3&4 → 5 → 6

### 文件結構
```
docs/features/<name>/
  ├── 01_spec.md          ← Stage 1
  ├── 02_architecture.md  ← Stage 2
  ├── 03_dev_plan.md      ← Stage 2
  ├── 04_test_plan.md     ← Stage 5
  └── 05_test_report.md   ← Stage 5
```

## Common Commands
- python -m pytest tests/
- python -m pytest tests/ --cov=src/
- pip install -r requirements.txt

## Project Paths
- Main: D:\\Projects\\agent-army
- ECC: D:\\Projects\\everything-claude-code
- Ollama MCP: D:\\Projects\\OllamaClaude