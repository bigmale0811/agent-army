# 需求規格書 — 無腦上手體驗

> 本文件由 Phase 0: RECEIVE 產出，需使用者確認後才進入架構設計階段。

## 基本資訊

| 欄位 | 內容 |
|------|------|
| 功能名稱 | 無腦上手體驗（Easy Onboarding） |
| 需求者 | CEO |
| 建立日期 | 2026-03-17 |
| 優先級 | P0 |

## 需求描述

目前 AgentForge 的安裝與設定過程對非技術人員（HR、會計）來說太困難。
文件充滿專有名詞（API Key、環境變數、pip、YAML），操作需要打指令，
造成非工程師根本無法自己完成安裝和使用。

**目標**：讓公司內部的 HR、會計等非技術同事，能在「不需要懂程式」的前提下，
自己完成 AgentForge 的安裝、設定、建立 Agent、執行 Agent。
他們就是最好的使用者體驗回饋來源。

## 目標使用者與環境

| 項目 | 說明 |
|------|------|
| 使用者 | 公司內部非技術人員（HR、會計），電腦操作能力等同「會用 Excel 跟瀏覽器」 |
| 作業系統 | Windows 10/11（主要），macOS（次要） |
| 權限 | 不一定有 admin 權限 |
| 前置條件 | 有網路、有 Google 帳號（用於免費 Gemini）或有 Claude Pro 訂閱 |
| 限制 | 不能假設使用者知道什麼是「終端機」「命令列」「環境變數」 |

## 功能項目

本次需求分為 **四大塊**：

| # | 功能 | 說明 | 必要/選配 |
|---|------|------|----------|
| F1 | 白話文安裝說明 | 重寫一份「完全沒有專有名詞」的安裝指南，每一步附截圖級描述 | 必要 |
| F2 | 安裝精靈（Setup Wizard） | 互動式引導程式，一步步帶使用者完成：選 AI 服務 → 取得通行證 → 設定完成 | 必要 |
| F3 | 新增 Claude API（Anthropic SDK）作為 Provider | 讓有 Claude Pro 方案的使用者，可以用 Claude 作為 AI 引擎 | 必要 |
| F4 | Telegram 機器人遠端操控 | 使用者可以在手機 Telegram 上觸發 Agent 執行、查看結果 | 必要 |

---

### F1：白話文安裝說明

**核心原則**：寫給「你教爸媽用手機」的那種程度

| 專有名詞 | 白話翻譯 |
|---------|---------|
| API Key | 通行證（就像進大樓的門禁卡） |
| 環境變數 | 電腦的隱藏設定 |
| pip install | 安裝軟體（就像在手機上裝 App） |
| 終端機 / CMD | 黑色的打字視窗 |
| YAML | 設定檔（就像 Excel 的表格，但用文字寫） |
| Provider | AI 服務商（提供聰明大腦的公司） |
| Model | AI 模型（不同等級的聰明大腦） |
| Token | 字數（AI 讀和寫的字數，用來計費） |

**產出**：`agentforge/docs/EASY_INSTALL.md`（繁體中文）

**內容結構**：
1. 你需要準備什麼（只需要：一台電腦 + 網路）
2. 第一步：安裝 Python（附圖文教學）
3. 第二步：安裝 AgentForge（一行指令，告訴他們怎麼打開黑色視窗）
4. 第三步：執行安裝精靈（精靈會問你問題，你只要回答就好）
5. 第四步：試跑你的第一個 Agent
6. 遇到問題怎麼辦（FAQ，用「你會看到…」的語氣寫）

---

### F2：安裝精靈（Setup Wizard）

使用者執行一行指令後，精靈用中文問答帶他完成所有設定：

```
你好！歡迎使用 AgentForge 🎉
我會一步一步帶你完成設定，你只要回答問題就好。

━━━ 第一步：選擇 AI 服務 ━━━

  你想用哪個 AI 服務？（直接輸入數字）

  1. Google Gemini ⭐ 推薦（免費，只要有 Google 帳號）
  2. Claude（需要 Anthropic 帳號，付費但很強）
  3. OpenAI / ChatGPT（需要 OpenAI 帳號，付費）
  4. Ollama（免費但需要額外安裝，適合有經驗的人）

你的選擇 [1]:
```

**選擇後的流程**：

- 選 1 (Gemini)：
  - 「請打開這個網址：https://aistudio.google.com/app/apikey」
  - 「用你的 Google 帳號登入」
  - 「點畫面上的『建立 API 金鑰』按鈕」
  - 「把產生的那串文字複製，貼在下面：」
  - 使用者貼上 → 精靈自動寫入設定檔

- 選 2 (Claude)：
  - 偵測電腦上是否已安裝 `claude` CLI（Claude Code）
  - 已安裝 → 偵測是否已登入（`claude --version`）→ 已登入 → 設定完成
  - 未安裝 → 「請先訂閱 Claude Pro，然後安裝 Claude Code：https://claude.ai/download」
  - 「安裝好之後，打開黑色視窗輸入 claude 登入你的帳號，然後再回來跑一次精靈」
  - 不需要通行證，使用 Claude Pro/Max 訂閱額度

- 選 3 (OpenAI)：類似流程

- 選 4 (Ollama)：
  - 「Ollama 是裝在你自己電腦上的 AI，不需要通行證」
  - 偵測 Ollama 是否已安裝 → 有就直接設定 → 沒有就教他裝

**精靈完成後**：
- 自動建立 `agentforge.yaml` + 範例 Agent
- 自動測試連線是否成功（呼叫一次 AI 確認通行證有效）
- 顯示「✅ 設定完成！你可以輸入 agentforge run example 試試看」

**技術要求**：
- 使用 `agentforge setup` 指令啟動
- 支援 `--dry-run`（模擬執行不實際操作）
- 支援 `--auto`（全自動用預設值，不問問題，用於測試）
- 通行證存在本地設定檔，不用環境變數（降低門檻）
- 通行證檔案要有提醒「這是機密，不要分享給別人」

---

### F3：新增 Claude Code CLI 作為 Provider

**不是用 Anthropic API（按 token 付費），而是用 Claude Code CLI（訂閱制吃到飽）。**

使用者只要有 Claude Pro ($20/月) 或 Claude Max 訂閱，
AgentForge 就透過 `claude -p "prompt"` subprocess 呼叫 Claude，
用訂閱額度跑，不需要另外申請 API Key。

**使用方式**：
```yaml
model: claude-code/sonnet
model: claude-code/opus
```

**技術需求**：
- 透過 `subprocess` 呼叫 `claude -p "prompt" --output-format json`
- 不需要 API Key，不需要 `anthropic` SDK
- 偵測 `claude` CLI 是否已安裝並已登入
- 與現有 Router 架構整合（跟 openai/gemini/ollama 並列，新增 `claude-code` provider）
- 設定範例：
  ```yaml
  providers:
    claude-code:
      # 不需要 API key，使用 Claude Pro/Max 訂閱
      # 確保 claude CLI 已安裝且已登入
  ```

**優勢（對非技術使用者）**：
- ✅ 不需要申請 API Key
- ✅ 月費制，不怕超額帳單
- ✅ 安裝精靈只需確認 `claude` CLI 可用
- ✅ Claude Pro/Max 使用者零設定成本

**費用追蹤**：
- Claude Pro/Max 為訂閱制，不按 token 計費
- Budget tracker 記錄為 `$0.00`（已含在訂閱中）
- 仍記錄 token 數量供參考

---

### F4：Telegram 機器人遠端操控

讓使用者在手機 Telegram 上操控 AgentForge：

**基本功能**：

| 指令 | 功能 |
|------|------|
| `/start` | 歡迎訊息 + 使用說明 |
| `/list` | 列出所有可用的 Agent |
| `/run <agent名稱>` | 執行指定 Agent |
| `/status` | 查看上次執行結果與成本統計 |
| `/help` | 顯示指令列表 |

**使用情境**：
- HR 在手機上傳 `/run daily-report`，就能收到今天的工作報告
- 會計傳 `/run expense-checker`，就能收到費用檢查結果
- 主管傳 `/status`，看所有 Agent 的執行統計

**技術需求**：
- 使用 `python-telegram-bot` 套件
- 長輪詢（polling）模式即可（不需要 webhook）
- 透過 `agentforge telegram` 指令啟動機器人
- Bot Token 由安裝精靈引導設定

**安全需求**：
- 必須設定「允許使用者清單」（白名單），不是任何人都能操控
- Bot Token 存在本地設定檔，不硬編碼

---

## 驗收標準

> 每一條驗收標準都必須可測試。QA Agent 會根據這些標準獨立撰寫測試。

| # | 驗收標準 | 測試方式 |
|---|---------|---------|
| AC-1 | `agentforge setup --dry-run --auto` 可在 30 秒內跑完，exit code = 0 | E2E |
| AC-2 | 安裝精靈選擇 Gemini 後，自動產生正確的 `agentforge.yaml` 設定 | Unit + E2E |
| AC-3 | 安裝精靈選擇 Claude 後，偵測 `claude` CLI 是否已安裝並已登入，產生正確的 `agentforge.yaml` | Unit + E2E |
| AC-4 | `model: claude-code/sonnet` 可透過 `claude -p` subprocess 呼叫 Claude Code CLI 並回傳結果 | Integration |
| AC-5 | Claude Code Provider 記錄 token 數量，費用記為 $0（訂閱制） | Unit |
| AC-6 | Telegram Bot 啟動後可回應 `/list`、`/run`、`/status` 指令 | Integration |
| AC-7 | Telegram Bot 只回應白名單內的使用者，拒絕其他人 | Unit |
| AC-8 | 白話文安裝說明不包含任何未翻譯的專有名詞 | 人工審查 |
| AC-9 | 安裝精靈通行證輸入錯誤時，顯示友善中文錯誤訊息，不閃退 | E2E |
| AC-10 | 安裝精靈完成後自動驗證 AI 連線是否成功 | E2E |

## 邊界條件與錯誤處理

| 情境 | 預期行為 |
|------|---------|
| 使用者貼了錯誤的通行證 | 精靈顯示「❌ 這個通行證無法使用，請確認有沒有複製完整」 |
| 網路斷線 | 精靈顯示「⚠️ 網路似乎斷了，請檢查 Wi-Fi 連線後再試」 |
| 已經設定過，再跑一次精靈 | 詢問「偵測到你之前設定過了，要重新設定嗎？」 |
| Ollama 未安裝但使用者選了 Ollama | 顯示「Ollama 還沒安裝在你的電腦上，要我幫你打開下載頁面嗎？」 |
| Telegram Bot Token 無效 | 顯示「這個 Bot Token 不正確，請回到 @BotFather 重新取得」 |
| 使用者沒在白名單上試圖操控 Bot | Bot 回應「抱歉，你沒有權限使用這個機器人」 |
| Agent 執行時間超過 Telegram 回應限制 | 先回「⏳ 正在執行中，完成後會通知你」，完成後主動推送結果 |

## 不做的事（Out of Scope）

- ❌ 不做 Web 圖形介面（這次只做 CLI 精靈 + Telegram）
- ❌ 不做多語言支援（這次只做繁體中文）
- ❌ 不做 Agent 拖拉式編輯器（使用者還是要手寫 YAML，但精靈會教）
- ❌ 不做 Azure OpenAI / AWS Bedrock 等企業 Provider
- ❌ 不做 Telegram Bot 的 webhook 模式（MVP 用 polling 即可）
- ❌ 不做付費 / 帳號管理系統

## 開發優先順序建議

```
Phase A（核心）：F2 安裝精靈 + F3 Claude Provider
    ↓ （因為精靈需要支援選 Claude）
Phase B（體驗）：F1 白話文說明
    ↓ （因為說明要配合精靈的實際畫面寫）
Phase C（擴展）：F4 Telegram Bot
    ↓ （獨立模組，可平行開發）
```

---

**使用者確認：** [ ] 已確認上述規格正確，可進入架構設計階段
