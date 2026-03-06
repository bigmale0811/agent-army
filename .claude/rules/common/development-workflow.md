# Development Workflow — ECC v2

> 文件驅動、角色分離、有迴圈的完整開發流程。
> 完整指令參考：`/orchestrate feature <description>`

## Feature Implementation Workflow

每個 Phase 必須產出文件，下一個 Phase 必須讀取文件。
有 🚦 標記的步驟必須等使用者確認才能繼續。

### Phase 0: RECEIVE（接收需求）🚦

- 接收使用者需求
- 產出 `docs/features/<name>/01_spec.md`（需求規格書）
- 包含：驗收標準（AC）、邊界條件、不做的事
- 🚦 **等使用者確認規格才進入下一步**

### Phase 1: ARCHITECT（架構設計）🚦

- 使用 **architect** agent
- 讀取 `01_spec.md` → 產出 `02_architecture.md`
- 包含：模組拆分、技術選型、介面定義、風險評估
- 🚦 **等使用者確認架構才進入下一步**

### Phase 2: PLAN（開發計畫）🚦

- 使用 **planner** agent
- 讀取 spec + architecture → 產出 `03_dev_plan.md`
- 每個 DEV 項目對應至少一個驗收標準
- 🚦 **等使用者確認計畫才進入下一步**

### Phase 3: DEV（開發）

- 使用 **tdd-guide** agent
- 按 dev_plan 逐項：寫測試 (RED) → 實作 (GREEN) → 重構 (REFACTOR)
- 覆蓋率目標 80%+

### Phase 4: REVIEW（代碼審查）

- **平行執行**：python-reviewer + security-reviewer
- CRITICAL / HIGH 問題必須修復
- MEDIUM 問題記錄、建議修復

### Phase 5: QA（獨立品質測試）

- 使用 **qa-reviewer** agent（新角色）
- **只讀 `01_spec.md` 的驗收標準，不讀實作程式碼**
- 產出 `04_test_plan.md` + `05_test_report.md`
- 黑箱測試：從使用者角度驗證功能

### Phase 5b: ITERATE（迴圈修復）

- QA 不過 → 回到 Phase 3 修復 → Phase 4 審查 → Phase 5 重測
- **最多 3 輪**，超過需升級處理
- 每輪更新測試報告歷史

### Phase 6: RELEASE（發布）

- QA 全部 PASS 才能進入
- type check + lint + 全部測試
- git commit（Conventional Commits）+ push
- 更新 CHANGELOG

### Phase 7: DOCUMENT（文件更新）

- 使用 **doc-updater** agent
- 更新 CODEMAPS + active_context.md
- 歸檔 session

## 文件結構

```
docs/features/<feature-name>/
  ├── 01_spec.md           ← Phase 0
  ├── 02_architecture.md   ← Phase 1
  ├── 03_dev_plan.md       ← Phase 2
  ├── 04_test_plan.md      ← Phase 5
  └── 05_test_report.md    ← Phase 5
```

## 文件模板

所有模板在 `docs/templates/` 目錄下。

## 簡化流程

- **Bugfix**：Phase 0 → 2 → 3 → 4 → 5 → 6（跳過架構設計）
- **Refactor**：Phase 1 → 2 → 3 → 4 → 5 → 6（跳過需求接收）

## Research（研究）

所有流程開始前，先搜尋有沒有現成方案：
- GitHub code search：`gh search repos` / `gh search code`
- Package registries：PyPI / npm / crates.io
- 找到 80%+ 符合的方案就用現成的
