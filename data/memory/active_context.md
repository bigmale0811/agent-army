# 🧠 Active Context
更新：2026-03-06

## 目前進行中
- Singer Agent v0.3 端對端測試（仍待執行）

## 最近完成
- **✅ 安裝精靈 E2E 自動化測試**（完整 ECC 流程）：
  - Phase 0 Research：搜尋 CLI E2E 測試最佳實踐（subprocess.communicate）
  - Phase 1 Plan：規劃 --dry-run --auto 旗標 + E2E 測試 → 使用者核准
  - Phase 2 TDD：先寫 8 個 E2E 測試 (RED) → 實作 (GREEN) → 92 個測試全部通過
  - install.py：加入 --dry-run / --auto / --path、ask/ask_yn auto 模式、subprocess dry-run 跳過
  - setup.py：加入 --dry-run / --auto argparse 參數
  - wizard.py：_DRY_RUN / _AUTO_MODE 全域旗標、所有互動函式 auto 模式
  - 新增：`tests/test_setup/test_e2e_installer.py`（8 個 E2E 場景）
  - ECC rules 更新：`.claude/rules/common/testing.md` 加入 CLI E2E 規範
- **✅ 修復 4 個安裝精靈 bug**（使用者手動測試發現）：
  - Bug 1: winget 不可用 → 加入 `_download_gh_msi()` 直接下載
  - Bug 2: msiexec 需 admin → 加入 `_download_gh_zip()` zip 解壓（免 admin）
  - Bug 3: clone 非空目錄閃退 → 加入 `_check_existing_repo()` + `_pull_agent_army()`
  - Bug 4: Telegram poetry 依賴安裝失敗 → 支援 requirements.txt / poetry / pip install .
- **✅ LLM 雲端模組** (`src/llm/`)
- **✅ Setup Wizard v2.0 完全重寫**
- **✅ gh CLI 安裝備援機制**（winget → MSI → zip → 手動）
- **✅ Git 初始提交 + Push** 到 `bigmale0811/agent-army`

## ❌ ECC 流程違規（教訓）
- 開發 LLM 模組和 Setup Wizard 時跳過了 Phase 1~4
- 結果：5 個 bug 到了使用者手上才被發現
- **修正**：E2E 自動化測試已使用完整 ECC 流程實作
- **新規範**：CLI 互動工具必須支援 --dry-run --auto，Phase 4 必須包含 E2E

## 重要決策
- ECC 標準流程必須嚴格遵守，不可因為「快」而跳過
- CLI 互動工具必須支援 --dry-run + --auto（寫入 ECC rules）
- Ollama 是可選的，不是必要的
- 雲端 LLM 用 `openai` SDK 統一介面（base_url 切換）
- Gemini 用 `google-genai` SDK

## 下一步
1. commit + push E2E 自動化測試的所有變更
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
