# 🧠 Active Context
更新：2026-03-06

## 目前進行中
- ✅ 修復 gh CLI 安裝備援（winget 不可用時直接下載 MSI）— 已完成
- Singer Agent v0.3 端對端測試（仍待執行）

## 最近完成
- **✅ LLM 雲端模組** (`src/llm/`)：
  - 支援 OpenAI / DeepSeek / Groq / Together（OpenAI-compatible）+ Gemini
  - 32 個測試通過
  - CLI：`python -m src.llm.cli --list/--test/--prompt/--chat`
- **✅ Setup Wizard** (`setup/`)：
  - 7 步安裝精靈（既有專案自動偵測後減為 5 步）
  - 修復 5 個 bug：_generate_env_template、getpass 凍結、重複問路徑、Telegram 搜尋路徑、clone URL
  - 14 個測試通過
- **✅ 修復「完成後不通知」問題**（claude-code-telegram）：
  - `.env`：`CLAUDE_MAX_TURNS=50`、`CLAUDE_TIMEOUT_SECONDS=900`
  - `sdk_integration.py`：空回應合成摘要
- **✅ Git 初始提交 + Push** 到 `bigmale0811/agent-army`
- **✅ GitHub CLI 安裝 + 認證自動化**：
  - 安裝 gh CLI via winget、Classic Token 認證
  - `bigmale0811/claude-code-telegram` repo 建立並 push
- **✅ GitHub CLI 加入 Setup Wizard**（遵循 ECC 流程 TDD→Review→Verify）
- **✅ Setup Wizard v2.0 完全重寫**：
  - 架構分離：install.py（獨立安裝包 Step 1~3）+ setup.py（專案設定 Step 4~8）
  - install.py 是零依賴、純 stdlib 單一檔案，可獨立分發
  - 流程：環境檢查 → gh 安裝 → clone agent-army → pip install → 雲端模型 → Ollama → Telegram → 驗證
  - 移除 Claude CLI 登入步驟
  - 66 個 setup 測試全部通過
- **✅ gh CLI 安裝備援機制**：
  - 問題：winget 不可用時 gh 安裝直接失敗
  - 修復：加入 `_download_gh_msi()` / `install_gh_direct_download()`
  - 安裝順序：winget → 直接從 GitHub Releases 下載 MSI → 手動提示
  - 用 urllib.request（stdlib）下載，msiexec 靜默安裝
  - 76 個 setup 測試全部通過（遵循 TDD）

## ❌ ECC 流程違規（教訓）
- 開發 LLM 模組和 Setup Wizard 時跳過了：
  - Phase 1 (PLAN) — 沒有等使用者確認就動手
  - Phase 2 (TDD) — 先寫程式後補測試
  - Phase 3 (REVIEW) — 沒有跑 code-reviewer
  - Phase 4 (VERIFY) — 沒有跑完整驗證
- 結果：5 個 bug 到了使用者手上才被發現
- **決策**：已記錄到 decisions.md，未來必須嚴格遵守

## 重要決策
- ECC 標準流程必須嚴格遵守，不可因為「快」而跳過
- Ollama 是可選的，不是必要的
- 雲端 LLM 用 `openai` SDK 統一介面（base_url 切換）
- Gemini 用 `google-genai` SDK

## 下一步
1. 跑完整測試確認 46 個測試全部通過
2. 確認 `claude-code-telegram` 是否需要 push 到 GitHub
3. Singer Agent v0.3 端對端測試（仍待執行）
4. v0.3.1：服裝修改功能

## 專案現有素材
- MP3：`data/singer_agent/inbox/愛我的人和我愛的人_ζั͡ޓ擂戰އ沒人_2026_02_03_15_06_32.mp3`
- 角色圖片：`data/singer_agent/character/avatar.png`
- ComfyUI：`D:\Projects\ComfyUI`（SDXL base 1.0, PyTorch cu128）

## 使用者操作環境
- 透過 `D:\Projects\claude-code-telegram` 的 Telegram Bot 互動
- Bot 用 `claude-agent-sdk`，`cwd=D:\Projects\agent-army`
- Git repo：`https://github.com/bigmale0811/agent-army.git`

## ⚡ 最近壓縮事件
- [2026-03-06 08:35:58] Context 被自動壓縮，以上內容是壓縮前的狀態
- **請重新讀取此檔案確認進度**
