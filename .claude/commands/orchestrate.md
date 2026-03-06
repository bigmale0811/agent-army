# Orchestrate Command — ECC v2 流程引擎

文件驅動的完整開發流程。每個 Phase 產出文件，下一個 Phase 讀取文件。
**有 🚦 標記的步驟必須等使用者確認才能繼續。**

## Usage

`/orchestrate feature <description>`

## Feature Workflow（完整功能開發）

```
Phase 0 RECEIVE → Phase 1 ARCHITECT → Phase 2 PLAN → Phase 3 DEV
    → Phase 4 REVIEW → Phase 5 QA → [ITERATE] → Phase 6 RELEASE → Phase 7 DOCUMENT
```

$ARGUMENTS — 用 `$ARGUMENTS` 取得功能描述。

---

### Phase 0: RECEIVE（接收需求）🚦

**角色**：Orchestrator（你自己）
**輸入**：使用者的需求描述
**輸出**：`docs/features/<name>/01_spec.md`

步驟：
1. 建立功能目錄：`mkdir -p docs/features/<name>/`
2. 複製模板：`docs/templates/01_spec.md`
3. 根據使用者描述填寫所有欄位，特別注意：
   - **驗收標準**：每一條必須可測試，QA 會根據這些寫測試
   - **邊界條件**：列出所有可能出錯的情境
   - **不做的事**：明確排除範圍
4. 🚦 **停下來，請使用者確認規格**
5. 使用者確認後才進入 Phase 1

```
📋 產出物：docs/features/<name>/01_spec.md ✅ 使用者已確認
```

---

### Phase 1: ARCHITECT（架構設計）🚦

**角色**：architect agent
**輸入**：`01_spec.md`
**輸出**：`docs/features/<name>/02_architecture.md`

步驟：
1. 啟動 architect agent（Task tool, subagent_type: architect）
2. Agent 讀取 `01_spec.md`
3. 根據 `docs/templates/02_architecture.md` 模板產出架構設計
4. 包含：模組拆分、技術選型、介面定義、風險評估
5. 🚦 **停下來，請使用者確認架構**

```
📋 產出物：docs/features/<name>/02_architecture.md ✅ 使用者已確認
```

---

### Phase 2: PLAN（開發計畫）🚦

**角色**：planner agent
**輸入**：`01_spec.md` + `02_architecture.md`
**輸出**：`docs/features/<name>/03_dev_plan.md`

步驟：
1. 啟動 planner agent（Task tool, subagent_type: planner）
2. Agent 讀取 spec + architecture
3. 根據 `docs/templates/03_dev_plan.md` 模板拆解開發項目
4. 每個 DEV 項目必須對應至少一個 AC（驗收標準）
5. 🚦 **停下來，請使用者確認開發計畫**

```
📋 產出物：docs/features/<name>/03_dev_plan.md ✅ 使用者已確認
```

---

### Phase 3: DEV（開發）

**角色**：tdd-guide agent
**輸入**：`03_dev_plan.md`
**輸出**：程式碼 + 單元測試

步驟：
1. 啟動 tdd-guide agent（Task tool, subagent_type: tdd-guide）
2. 按 dev_plan 的開發項目逐一實作
3. 每個項目：寫測試 (RED) → 實作 (GREEN) → 重構 (REFACTOR)
4. 確認單元測試覆蓋率 80%+
5. **不需要使用者確認，直接進入 Review**

```
📋 產出物：程式碼 + tests/
```

---

### Phase 4: REVIEW（代碼審查）

**角色**：python-reviewer + security-reviewer（平行執行）
**輸入**：Phase 3 產出的程式碼
**輸出**：審查報告

步驟：
1. **平行啟動兩個 agent**：
   - python-reviewer（Task tool, subagent_type: python-reviewer）
   - security-reviewer（Task tool, subagent_type: security-reviewer）
2. 收集兩份審查結果
3. CRITICAL / HIGH 問題必須修復後才進入 QA
4. MEDIUM 問題記錄，建議修復

```
📋 產出物：審查報告（CRITICAL / HIGH 已修復）
```

---

### Phase 5: QA（獨立品質測試）

**角色**：qa-reviewer agent ← 新角色
**輸入**：`01_spec.md`（驗收標準）— **不讀實作程式碼**
**輸出**：`docs/features/<name>/04_test_plan.md` + `05_test_report.md`

步驟：
1. 啟動 qa-reviewer agent（Task tool, subagent_type: general-purpose）
   - Prompt 中包含 `.claude/agents/qa-reviewer.md` 的完整指示
2. Agent 只讀 `01_spec.md`，根據驗收標準撰寫測試計畫
3. 產出 `04_test_plan.md`
4. 實作測試腳本：`tests/test_<feature>/test_qa_<name>.py`
5. 執行測試
6. 產出 `05_test_report.md`

```
📋 產出物：
  - docs/features/<name>/04_test_plan.md
  - docs/features/<name>/05_test_report.md
  - tests/test_<feature>/test_qa_<name>.py
```

---

### Phase 5b: ITERATE（迴圈修復）

**觸發條件**：`05_test_report.md` 判定為 ❌ FAIL

```
FAIL → 回到 Phase 3 (DEV) 修復 → Phase 4 (REVIEW) → Phase 5 (QA) 重新測試
最多 3 輪。超過 3 輪 → 停下來通知使用者。
```

迴圈紀錄：
- 每輪更新 `05_test_report.md` 的歷史輪次表
- 記錄每輪修了什麼、還剩什麼

---

### Phase 6: RELEASE（發布）

**觸發條件**：`05_test_report.md` 判定為 ✅ PASS

步驟：
1. 驗證：type check + lint + 全部測試
2. git add + commit（Conventional Commits）
3. 更新 CHANGELOG.md
4. git push
5. 通知使用者：commit hash、變更摘要

```
📋 產出物：git commit + CHANGELOG
```

---

### Phase 7: DOCUMENT（文件更新）

**角色**：doc-updater agent
**輸入**：所有功能文件 + 程式碼
**輸出**：更新後的文件

步驟：
1. 啟動 doc-updater agent（Task tool, subagent_type: general-purpose, model: haiku）
2. 更新 `docs/CODEMAPS/`
3. 更新 `data/memory/active_context.md`
4. 歸檔 session

```
📋 產出物：CODEMAPS + active_context.md
```

---

## Bugfix Workflow

`/orchestrate bugfix <description>`

簡化流程（跳過架構設計）：
```
Phase 0 RECEIVE → Phase 2 PLAN → Phase 3 DEV
    → Phase 4 REVIEW → Phase 5 QA → Phase 6 RELEASE
```

## Refactor Workflow

`/orchestrate refactor <description>`

```
Phase 1 ARCHITECT → Phase 2 PLAN → Phase 3 DEV
    → Phase 4 REVIEW → Phase 5 QA → Phase 6 RELEASE
```

---

## 文件結構

每個功能在 `docs/features/` 下有獨立目錄：

```
docs/features/<feature-name>/
  ├── 01_spec.md           ← Phase 0 產出
  ├── 02_architecture.md   ← Phase 1 產出
  ├── 03_dev_plan.md       ← Phase 2 產出
  ├── 04_test_plan.md      ← Phase 5 QA 產出
  └── 05_test_report.md    ← Phase 5 QA 產出
```

## 關鍵規則

1. **文件驅動**：每個 Phase 必須產出文件，下一個 Phase 必須讀取文件
2. **🚦 人工閘門**：Phase 0/1/2 必須等使用者確認
3. **獨立 QA**：qa-reviewer 只讀 spec，不讀程式碼
4. **迴圈機制**：QA 不過 → 回到 DEV → 最多 3 輪
5. **平行審查**：python-reviewer + security-reviewer 同時跑
6. **記憶保存**：Phase 7 必須更新 active_context.md
