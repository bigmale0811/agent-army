# Testing Requirements

## Minimum Test Coverage: 80%

Test Types (ALL required):
1. **Unit Tests** - Individual functions, utilities, components
2. **Integration Tests** - API endpoints, database operations
3. **E2E Tests** - Critical user flows (framework chosen per language)

## Test-Driven Development

MANDATORY workflow:
1. Write test first (RED)
2. Run test - it should FAIL
3. Write minimal implementation (GREEN)
4. Run test - it should PASS
5. Refactor (IMPROVE)
6. Verify coverage (80%+)

## Troubleshooting Test Failures

1. Use **tdd-guide** agent
2. Check test isolation
3. Verify mocks are correct
4. Fix implementation, not tests (unless tests are wrong)

## CLI 互動工具 E2E 規範

任何 CLI 互動工具（如安裝精靈、設定精靈）必須：
1. **支援 `--dry-run`**：走完整流程但跳過真實操作（subprocess、檔案寫入等）
2. **支援 `--auto`**：所有互動提示自動用預設值回答，不等人輸入
3. **E2E 測試**：用 `subprocess.run()` 執行 `--dry-run --auto`，驗證：
   - exit code == 0
   - 輸出包含所有步驟標題
   - 無 Python traceback
   - dry-run 模式不產生副作用（不建立檔案、不安裝套件）
4. **Phase 4 Verify 須包含 E2E 場景測試**，不能只跑 mock unit test

> 教訓：mock unit test 無法偵測整合問題（winget 不可用、msiexec 需 admin、
> clone 非空目錄、poetry vs requirements.txt），這些全部是使用者手動測試才抓到的 bug。

## Agent Support

- **tdd-guide** - Use PROACTIVELY for new features, enforces write-tests-first
