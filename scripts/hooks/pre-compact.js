#!/usr/bin/env node
/**
 * PreCompact Hook — 壓縮前自動保存狀態
 *
 * 當 Claude Code auto-compact 觸發前，此 hook 會：
 * 1. 讀取 stdin 取得當前 context（如果有的話）
 * 2. 在 active_context.md 加入壓縮標記
 * 3. 記錄壓縮事件到 compaction-log.txt
 *
 * 這是防止失憶的第一道防線。
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const MEMORY_DIR = path.join(PROJECT_ROOT, 'data', 'memory');
const ACTIVE_CONTEXT = path.join(MEMORY_DIR, 'active_context.md');
const COMPACTION_LOG = path.join(MEMORY_DIR, 'compaction-log.txt');

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getTimestamp() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

async function main() {
  ensureDir(MEMORY_DIR);

  const timestamp = getTimestamp();

  // 1. 記錄壓縮事件
  const logEntry = `[${timestamp}] ⚡ Auto-compaction triggered\n`;
  fs.appendFileSync(COMPACTION_LOG, logEntry, 'utf-8');

  // 2. 在 active_context.md 加入壓縮警告
  if (fs.existsSync(ACTIVE_CONTEXT)) {
    const content = fs.readFileSync(ACTIVE_CONTEXT, 'utf-8');

    // 檢查是否已有壓縮標記（避免重複追加）
    if (!content.includes('## ⚡ 最近壓縮事件')) {
      const compactionNote = `\n## ⚡ 最近壓縮事件\n- [${timestamp}] Context 被自動壓縮，以上內容是壓縮前的狀態\n- **請重新讀取此檔案確認進度**\n`;
      fs.writeFileSync(ACTIVE_CONTEXT, content + compactionNote, 'utf-8');
    } else {
      // 追加新的壓縮記錄
      const updatedContent = content.replace(
        /## ⚡ 最近壓縮事件\n/,
        `## ⚡ 最近壓縮事件\n- [${timestamp}] Context 被自動壓縮\n`
      );
      fs.writeFileSync(ACTIVE_CONTEXT, updatedContent, 'utf-8');
    }
  }

  // 3. 輸出提醒（會顯示在 Claude 的 context 中）
  console.error(`[PreCompact] ⚡ 狀態已保存到 active_context.md (${timestamp})`);
  console.error('[PreCompact] 壓縮後請先讀取 data/memory/active_context.md 恢復記憶');

  process.exit(0);
}

main().catch(err => {
  console.error('[PreCompact] Error:', err.message);
  process.exit(0); // 不要阻擋壓縮
});
