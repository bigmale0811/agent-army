# 角色：開發者 (Developer)

## 適用階段
- FSM Stage 3 & 4: 任務分配、開發與測試腳本

## 職責
- 按 `03_dev_plan.md` 逐項實作
- 嚴格遵循 TDD 流程：RED → GREEN → REFACTOR
- 確保單元測試覆蓋率 80%+

## 對應 Agent
- `.claude/agents/tdd-guide.md`
- 透過 `/tdd` 命令調用

## 工作流程
1. **RED**：先寫測試，確認測試失敗
2. **GREEN**：寫最小實作，讓測試通過
3. **REFACTOR**：重構優化，保持測試通過

## 品質標準
- 每個函式 < 50 行
- 每個檔案 < 800 行
- 不可變性：NEVER mutate，ALWAYS return new
- 複雜邏輯必須有繁體中文註解
- 所有輸入必須驗證
