# Update Changelog

每次完成開發任務後，自動分析變更並更新 CHANGELOG.md。

## 觸發時機
- 完成功能開發後，commit 之前
- 使用者輸入 `/changelog` 時

## Step 1: 分析本次變更

1. 執行 `git diff --stat` 和 `git diff --name-only` 查看已修改的檔案
2. 如果有未追蹤的新檔案，也列入分析
3. 讀取 CHANGELOG.md 的 `[Unreleased]` 區塊，了解已記錄的內容

## Step 2: 分類變更

依 Keep a Changelog 格式分類：

| 類別 | 適用場景 |
|------|---------|
| **Added** | 新功能、新檔案、新指令、新模組 |
| **Changed** | 既有功能的修改、重構、效能改善 |
| **Fixed** | Bug 修復 |
| **Removed** | 刪除的功能或檔案 |
| **Security** | 安全性相關修復 |
| **Deprecated** | 即將移除的功能 |

## Step 3: 更新 CHANGELOG.md

1. 在 `[Unreleased]` 區塊下的對應分類中追加條目
2. 每個條目格式：`- **簡短標題**: 詳細說明`
3. 如果涉及檔案變更，標註檔案路徑
4. 使用繁體中文撰寫

## Step 4: 驗證

1. 確認 CHANGELOG.md 格式正確（Markdown lint）
2. 確認沒有重複的條目
3. 告知使用者本次新增了哪些 changelog 條目

## 注意事項

- 不要刪除或修改已有的條目
- 版本發布時（使用者指定版號），將 `[Unreleased]` 的內容移到新版號區塊下，並加上日期
- 條目要簡潔但有足夠資訊，讓未來的開發者能理解每次變更的目的
