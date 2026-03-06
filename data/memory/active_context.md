# 🧠 Active Context
更新：2026-03-06

## 目前進行中
- Singer Agent v0.3 端對端測試（仍待執行）

## 最近完成
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
- **ECC v2 升級**：從 4 步線性流程升級為 8 Phase 文件驅動流程
  - 新增 Phase 0 RECEIVE（需求規格）、Phase 1 ARCHITECT（架構設計）
  - 新增 Phase 5 QA（獨立品質測試）、Phase 5b ITERATE（迴圈修復）
  - 新增 qa-reviewer agent（只讀 spec，不讀實作）
  - 每個 Phase 有文件交接物，有 🚦 人工閘門
- ECC 標準流程必須嚴格遵守
- CLI 互動工具必須支援 --dry-run + --auto

## 下一步
1. 用 `/orchestrate feature` 實測 ECC v2 流程（以安裝精靈為第一個案例）
2. Singer Agent v0.3 端對端測試
3. v0.3.1：服裝修改功能

## 專案現有素材
- MP3：`data/singer_agent/inbox/愛我的人和我愛的人_ζั͡ޓ擂戰އ沒人_2026_02_03_15_06_32.mp3`
- 角色圖片：`data/singer_agent/character/avatar.png`
- ComfyUI：`D:\Projects\ComfyUI`（SDXL base 1.0, PyTorch cu128）

## 使用者操作環境
- 透過 `D:\Projects\claude-code-telegram` 的 Telegram Bot 互動
- Bot 用 `claude-agent-sdk`，`cwd=D:\Projects\agent-army`
- Git repo：`https://github.com/bigmale0811/agent-army.git`
