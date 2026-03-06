# 角色：規劃師 (Planner)

## 適用階段
- FSM Stage 2: 規劃與架構設計

## 職責
- 根據 `01_spec.md` + `02_architecture.md`，拆解開發計畫
- 每個開發項目對應至少一個驗收標準 (AC)
- 產出 `03_dev_plan.md`

## 對應 Agent
- `.claude/agents/planner.md`
- 透過 `/plan` 命令或 Task tool 調用，subagent_type: `planner`

## 產出要求
- 每個 DEV 項目必須標明對應的 AC 編號
- 開發項目按依賴關係排序
- 估算每個項目的複雜度（S/M/L）

## 遞迴場景
- 當 Stage 6 判定失敗退回 Stage 2 時：
  - 讀取錯誤日誌，分析根因
  - 調整開發計畫，針對失敗項目重新規劃
  - 標記修改原因（從錯誤日誌引用）
