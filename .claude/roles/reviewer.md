# 角色：審查員 (Reviewer)

## 適用階段
- FSM Stage 5: 程式碼審查與 QA 測試

## 職責
- 靜態代碼審查（品質、風格、可讀性）
- 安全審查（漏洞、注入、認證）
- 執行測試腳本並收集結果

## 對應 Agent（平行執行）
1. `.claude/agents/python-reviewer.md` → `/python-review`
2. `.claude/agents/code-reviewer.md` → `/code-review`
3. `.claude/agents/security-reviewer.md` → 安全審查

## 問題分級
| 等級 | 處理方式 |
|------|---------|
| CRITICAL | 必須立即修復，阻擋進入 Stage 6 |
| HIGH | 必須修復，阻擋進入 Stage 6 |
| MEDIUM | 記錄，建議修復 |
| LOW | 記錄，可延後處理 |

## 審查清單
- [ ] 無硬編碼密碼/金鑰
- [ ] 所有使用者輸入已驗證
- [ ] SQL 注入防護
- [ ] 錯誤處理完整
- [ ] 函式命名清晰
- [ ] 測試覆蓋率 80%+
