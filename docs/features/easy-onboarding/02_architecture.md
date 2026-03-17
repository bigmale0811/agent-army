# 架構設計 — 無腦上手體驗（Easy Onboarding）

> 本文件由 Stage 2 架構師產出，需使用者確認後才進入開發計畫。

## 1. 整合概覽圖

```
                          agentforge CLI (Click)
                    ┌──────────┬──────────┬──────────┐
                    │          │          │          │
                  init       list       run       status
                    │                    │          │
                    │          ┌─────────┴──────────┘
                    │          │
              setup ◀──新增──┤────────▶ telegram  ◀── 新增
                │              │              │
                ▼              ▼              ▼
        SetupWizard    PipelineEngine    TelegramBot
           │                 │              │
           ▼                 ▼              │
     ConfigWriter       LLMRouter ◀────────┘
                             │
         ┌───────────────────┼───────────────┐
         ▼                   ▼               ▼
    OpenAICompat          Gemini       ClaudeCode ◀── 新增
    (含 Ollama)                        (subprocess)
```

## 2. 新檔案清單（16 個新增 + 5 個修改）

### F2: 安裝精靈

| 檔案 | 職責 | 行數 |
|------|------|------|
| `cli/setup_cmd.py` | Click 指令入口 | ~80 |
| `setup/__init__.py` | 模組匯出 | ~10 |
| `setup/wizard.py` | 精靈主流程狀態機 | ~250 |
| `setup/detector.py` | 環境偵測器（Python/Claude/Ollama） | ~150 |
| `setup/credential.py` | 通行證驗證與安全儲存 | ~200 |
| `setup/config_writer.py` | 產生設定檔 + 範例 Agent | ~150 |
| `utils/credentials.py` | API Key 解析工具 | ~80 |
| `templates/agentforge_*.yaml` | 4 個 provider 專用範本 | ~20 each |

### F3: Claude Code CLI Provider

| 檔案 | 職責 | 行數 |
|------|------|------|
| `llm/providers/claude_code.py` | subprocess 呼叫 claude CLI | ~300 |

### F4: Telegram Bot

| 檔案 | 職責 | 行數 |
|------|------|------|
| `cli/telegram_cmd.py` | Click 指令入口 | ~60 |
| `telegram/__init__.py` | 模組匯出 | ~10 |
| `telegram/bot.py` | Bot 主類別 + polling | ~200 |
| `telegram/handlers.py` | 指令處理器 | ~250 |
| `telegram/auth.py` | 白名單驗證 | ~80 |
| `telegram/formatter.py` | 結果格式化為 TG 訊息 | ~100 |

### 需修改的既有檔案

| 檔案 | 修改內容 |
|------|---------|
| `cli/main.py` | 註冊 `setup` + `telegram` 兩個子指令 |
| `llm/router.py` | `_create_provider()` 新增 `claude-code` 分支 |
| `llm/budget.py` | PRICING 新增 `claude-code/*` 為 $0 |
| `llm/providers/__init__.py` | 匯出 ClaudeCodeProvider |
| `schema/config.py` | 新增 TelegramConfig |

## 3. Claude Code CLI Provider 關鍵設計

### 3.1 呼叫方式

```python
cmd = ["claude", "-p", prompt, "--output-format", "json",
       "--model", "sonnet", "--no-session-persistence"]

result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
```

### 3.2 模型對應

```yaml
model: claude-code/sonnet   →  claude -p ... --model sonnet
model: claude-code/opus     →  claude -p ... --model opus
model: claude-code/haiku    →  claude -p ... --model haiku
```

### 3.3 JSON 輸出解析

```json
{"type": "result", "result": "回應文字", "cost_usd": 0.0, "is_error": false}
```

### 3.4 不需要 API Key

- 傳入 `api_key="subscription"` 作為佔位符滿足 BaseProvider
- 偵測已安裝：`claude --version` → returncode 0
- 偵測已登入：同上（未登入會 returncode != 0）

### 3.5 費用追蹤

- 訂閱制 → budget tracker 記為 $0.00
- 仍記錄 token 數量供參考

## 4. 安裝精靈設計

### 狀態機

```
START → CHOOSE_PROVIDER → CONFIGURE_CREDENTIAL → VERIFY_CONNECTION → WRITE_CONFIG → DONE
              ↑                    ↓ (失敗)                ↓ (失敗)
              └────────────────── 允許重新輸入（最多 3 次）──┘
```

### 通行證儲存

- 存在 `.agentforge/credentials.yaml`（與 agentforge.yaml 分離）
- 自動加入 `.gitignore`
- 檔案頂部安全警語

### dry-run + auto 模式

- `--auto`：自動選 Gemini + 測試用 key + 跳過驗證
- `--dry-run`：不實際寫檔案
- 合併用：E2E 測試，30 秒內完成

## 5. Telegram Bot 設計

### 架構

- `python-telegram-bot>=21.0`（選配依賴，`pip install agentforge[telegram]`）
- Polling 模式
- 白名單驗證 decorator

### 非同步執行

```
使用者 /run agent → Bot 先回「⏳ 執行中…」
                  → asyncio.to_thread 背景執行 PipelineEngine
                  → 完成後 edit_text 推送結果
```

### 設定格式

```yaml
telegram:
  bot_token: "123456:ABC..."
  allowed_users: [987654321]
```

## 6. 風險與緩解

| 風險 | 緩解策略 |
|------|---------|
| Claude CLI JSON 格式變更 | 版本偵測 + fallback 純文字 |
| Windows PATH 找不到 claude | `shutil.which("claude")` 先偵測 |
| credentials.yaml 被誤 commit | 自動 .gitignore + 安全警語 |
| Agent 執行太久 TG 超時 | 先回執行中，完成後推送 |
| 非技術使用者看不懂錯誤 | 所有錯誤用白話中文 + 下一步指引 |

---

**使用者確認：** [ ] 已確認架構設計，可進入開發計畫
