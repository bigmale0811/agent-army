# 🧠 Active Context
更新：2026-03-06

## 目前進行中
- **Stock Analyzer 整體進度**：DEV-A 完成、WO-001 Bug 修復完成，DEV-B 待執行
  - 基底：TradingAgents v0.2.0（Apache 2.0）
  - LLM：Ollama QWen3 14B 本地端
  - 標的：台股+基金+BTC（主力）、美股+黃金（參考）
  - 首次 AAPL 分析已跑完（446 秒），驗證了端到端流程
  - 獨立執行腳本：`scripts/run_analysis.py`（PID lock + 狀態追蹤）
  - AAPL 修復後驗證分析已於背景啟動（2026-03-06）
- Singer Agent ECC v2 重建：批次 A 已完成

## 最近完成
- **✅ WO-001 Stock Analyzer Bug 修復**（完整 Kanban 流程）：
  - BUG-1 ✅：`market_research_report` → `market_report` key 修正
  - BUG-2 ✅：新增 `clean_thinking_tags()` 清除 QWen3 think 標籤（含 Optional[str] 型別、\r\n 支援、propagate 錯誤處理）
  - BUG-3 ⏳：報告中文化，留待 DEV-C1
  - 15 項測試全部 PASS（12 clean_thinking_tags + 3 regression）
  - 2 輪 Code Review：0 CRITICAL、0 HIGH、3 MEDIUM 已修復
  - 派工單 WO-001 已關閉 [DONE]
- **✅ Git 整理**：7 個 commits（FSM、Stock Analyzer、Bug Fix、Singer Agent、Memory、Gitignore）
- **✅ FSM 狀態機工作流整合**
- **✅ Kanban 派工系統建立**
- **✅ Singer Agent 批次 A TDD 完成**（96 項測試，98% 覆蓋率）
- **✅ ECC v2 流程引擎建立**

## 重要決策
- **FSM 狀態機工作流**：6 Stage FSM 遞迴流程，失敗退回 Stage 2
- **Kanban 派工系統**：`.claude/work_orders/` 驅動異步開發
- ECC 標準流程必須嚴格遵守
- CLI 互動工具必須支援 --dry-run + --auto

## 下一步
1. **Stock Analyzer DEV-B**：台股（2330.TW）、BTC、黃金分析測試
2. **Stock Analyzer DEV-C**：中文化（prompt 層 + 報告輸出）
3. **Stock Analyzer DEV-D**：Pydantic schema 驗證、安全強化
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
- 已完成工單：`WO-001-stock-analyzer-bugfix.md` [DONE]

## Git 狀態
- master 領先 origin/master 7 個 commits（未 push）
