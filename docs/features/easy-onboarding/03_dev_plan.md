# 開發計畫 — 無腦上手體驗（Easy Onboarding）

> 本文件由 Stage 2 規劃師產出，需使用者確認後才進入開發階段。

## 開發順序總覽

```
Phase A（核心）：Claude Code Provider + 安裝精靈
  DEV-01 ~ DEV-06
    ↓
Phase B（擴展）：Telegram Bot
  DEV-07 ~ DEV-11
    ↓
Phase C（體驗）：白話文說明
  DEV-12
    ↓
Phase D（整合）：CLI 整合 + E2E 測試
  DEV-13 ~ DEV-14
```

---

## Phase A：核心（Claude Code Provider + 安裝精靈）

### DEV-01：ClaudeCodeProvider 基礎

**對應 AC**：AC-4, AC-5
**檔案**：`llm/providers/claude_code.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/llm/providers/test_claude_code.py` |
| 實作 | 繼承 `BaseProvider`，`generate()` 用 subprocess 呼叫 `claude -p` |
| 重點 | JSON 解析、timeout 處理、`FileNotFoundError` 處理 |
| 驗收 | mock subprocess → 正確解析回應、錯誤處理全部覆蓋 |

### DEV-02：ClaudeCodeProvider 進階

**對應 AC**：AC-4, AC-5
**檔案**：`llm/providers/claude_code.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `test_connection()`、`chat()` 的測試 |
| 實作 | `test_connection()` 偵測 CLI 可用、`chat()` 合併 messages |
| 重點 | Windows/Mac/Linux 跨平台 subprocess 行為 |
| 驗收 | mock subprocess → test_connection 回傳 True/False 正確 |

### DEV-03：Router + Budget 整合

**對應 AC**：AC-4, AC-5
**檔案**：`llm/router.py`、`llm/budget.py`、`llm/providers/__init__.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/llm/test_router_claude.py`、`tests/llm/test_budget_claude.py` |
| 實作 | router 新增 `claude-code` 分支、budget 記為 $0 |
| 重點 | 不破壞既有 openai/gemini/ollama 路由 |
| 驗收 | `model: claude-code/sonnet` 正確路由到 ClaudeCodeProvider |

### DEV-04：環境偵測器 + 通行證管理

**對應 AC**：AC-9, AC-10
**檔案**：`setup/detector.py`、`setup/credential.py`、`utils/credentials.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/setup/test_detector.py`、`tests/setup/test_credential.py` |
| 實作 | 偵測 claude CLI / ollama / 既有設定檔、API key 驗證、credentials.yaml 讀寫 |
| 重點 | 錯誤的 key 要有友善中文提示 |
| 驗收 | 各種錯誤情境全部有對應的白話文錯誤訊息 |

### DEV-05：安裝精靈核心流程

**對應 AC**：AC-1, AC-2, AC-3
**檔案**：`setup/wizard.py`、`setup/config_writer.py`、`cli/setup_cmd.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/setup/test_wizard.py`、`tests/cli/test_setup_cmd.py` |
| 實作 | 4 步驟狀態機、provider 選擇、設定檔產生 |
| 重點 | `--dry-run --auto` 必須 30 秒內完成、exit code 0 |
| 驗收 | E2E: `agentforge setup --dry-run --auto` 跑完不出錯 |

### DEV-06：Provider 專用範本 + Schema 擴充

**對應 AC**：AC-2, AC-3
**檔案**：`templates/agentforge_*.yaml`（4 個）、`schema/config.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/schema/test_config_telegram.py` |
| 實作 | 4 個 provider 專用 YAML 範本、TelegramConfig 加入 GlobalConfig |
| 重點 | 範本要有繁體中文註解、TelegramConfig 是可選的 |
| 驗收 | 既有的 config 測試不被破壞（向後相容） |

---

## Phase B：擴展（Telegram Bot）

### DEV-07：Telegram 白名單驗證

**對應 AC**：AC-7
**檔案**：`telegram/auth.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/telegram/test_auth.py` |
| 實作 | `AuthMiddleware` 白名單 decorator |
| 重點 | 白名單外的使用者收到「你沒有權限」 |
| 驗收 | 允許的 user ID 通過、其他拒絕 |

### DEV-08：Telegram 訊息格式化

**對應 AC**：AC-6
**檔案**：`telegram/formatter.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/telegram/test_formatter.py` |
| 實作 | Agent 清單、執行結果、統計資料的格式化 |
| 重點 | Telegram 訊息長度限制（4096 字元）、繁體中文 |
| 驗收 | 各種資料結構都能格式化為可讀訊息 |

### DEV-09：Telegram 指令處理器

**對應 AC**：AC-6
**檔案**：`telegram/handlers.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/telegram/test_handlers.py` |
| 實作 | /start, /list, /run, /status, /help 五個指令 |
| 重點 | /run 非同步執行：先回「執行中」，完成後推送結果 |
| 驗收 | mock PipelineEngine → 所有指令正確回應 |

### DEV-10：Telegram Bot 主類別

**對應 AC**：AC-6
**檔案**：`telegram/bot.py`、`telegram/__init__.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/telegram/test_bot.py` |
| 實作 | Bot 初始化、handlers 註冊、polling 啟動 |
| 重點 | 延遲 import python-telegram-bot（選配依賴） |
| 驗收 | Bot Token 無效時顯示友善錯誤 |

### DEV-11：Telegram CLI 指令

**對應 AC**：AC-6
**檔案**：`cli/telegram_cmd.py`

| 項目 | 內容 |
|------|------|
| 測試先行 | `tests/cli/test_telegram_cmd.py` |
| 實作 | `agentforge telegram` 指令，讀取 config 啟動 bot |
| 重點 | 未設定 bot_token 時顯示指引訊息 |
| 驗收 | 無 token 不崩潰、有 token 啟動正常 |

---

## Phase C：體驗（白話文說明）

### DEV-12：白話文安裝說明

**對應 AC**：AC-8
**檔案**：`docs/EASY_INSTALL.md`

| 項目 | 內容 |
|------|------|
| 實作 | 純文件撰寫，配合精靈實際畫面 |
| 重點 | 零專有名詞、教爸媽用手機的語氣 |
| 驗收 | 人工審查：找一個非技術人員讀過確認看得懂 |

---

## Phase D：整合（CLI 整合 + E2E）

### DEV-13：CLI 主入口整合

**對應 AC**：全部
**檔案**：`cli/main.py`

| 項目 | 內容 |
|------|------|
| 實作 | 註冊 `setup_command` + `telegram_command` |
| 重點 | 兩行 `add_command`，不影響既有指令 |
| 驗收 | `agentforge --help` 顯示 setup 和 telegram |

### DEV-14：E2E 整合測試

**對應 AC**：AC-1, AC-9, AC-10
**檔案**：`tests/e2e/test_setup_e2e.py`

| 項目 | 內容 |
|------|------|
| 實作 | `subprocess.run` 執行 `agentforge setup --dry-run --auto` |
| 重點 | exit code 0、輸出包含所有步驟標題、無 traceback |
| 驗收 | CI 可執行、30 秒內完成 |

---

## 依賴套件變更

```toml
# pyproject.toml
[project.optional-dependencies]
telegram = ["python-telegram-bot>=21.0,<22.0"]
```

基礎安裝不增加任何新依賴。

## 預估工時

| Phase | 項目數 | 預估 |
|-------|-------|------|
| Phase A（核心） | DEV-01 ~ 06 | 主要工作量 |
| Phase B（Telegram） | DEV-07 ~ 11 | 次要工作量 |
| Phase C（文件） | DEV-12 | 輕量 |
| Phase D（整合） | DEV-13 ~ 14 | 輕量 |

---

**使用者確認：** [ ] 已確認開發計畫，可進入開發階段
