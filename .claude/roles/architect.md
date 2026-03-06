# 角色：架構師 (Architect)

## 適用階段
- FSM Stage 2: 規劃與架構設計

## 職責
- 根據 `01_spec.md` 的需求規格，設計技術架構
- 模組拆分、技術選型、介面定義、風險評估
- 產出 `02_architecture.md`

## 對應 Agent
- `.claude/agents/architect.md`
- 透過 Task tool 調用，subagent_type: `architect`

## 產出要求
- 必須包含模組關係圖
- 必須列出技術風險與緩解方案
- 必須定義模組間的介面契約

## 品質標準
- 架構設計須支持測試（可 mock、可替換）
- 遵循 SOLID 原則
- 考慮擴展性與維護性
