#!/usr/bin/env node
/**
 * SessionStart Hook — 新對話自動載入記憶
 *
 * 每次新對話開始時：
 * 1. 讀取 active_context.md 並注入 Claude 的 context
 * 2. 檢查是否有壓縮標記，提醒恢復
 * 3. 報告最近的 session 數量
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const MEMORY_DIR = path.join(PROJECT_ROOT, 'data', 'memory');
const ACTIVE_CONTEXT = path.join(MEMORY_DIR, 'active_context.md');
const SESSIONS_DIR = path.join(MEMORY_DIR, 'sessions');

async function main() {
  // 1. 讀取 active_context.md
  if (fs.existsSync(ACTIVE_CONTEXT)) {
    const content = fs.readFileSync(ACTIVE_CONTEXT, 'utf-8');

    if (content.trim()) {
      // 注入到 Claude 的 context（stdout 會被 Claude 讀取）
      process.stdout.write(`[Memory Loaded] active_context.md:\n${content}\n`);

      // 檢查壓縮標記
      if (content.includes('⚡ 最近壓縮事件')) {
        console.error('[SessionStart] ⚠️ 偵測到壓縮標記！上次對話可能被 auto-compact 中斷');
        console.error('[SessionStart] 請仔細確認 active_context.md 的狀態是否完整');
      }
    }
  } else {
    console.error('[SessionStart] 沒有找到 active_context.md，這可能是第一次對話');
  }

  // 2. 報告 session 歷史
  if (fs.existsSync(SESSIONS_DIR)) {
    try {
      const sessions = fs.readdirSync(SESSIONS_DIR).filter(f => f.endsWith('.md'));
      if (sessions.length > 0) {
        console.error(`[SessionStart] 有 ${sessions.length} 筆歷史對話紀錄`);
      }
    } catch { /* ignore */ }
  }

  process.exit(0);
}

main().catch(err => {
  console.error('[SessionStart] Error:', err.message);
  process.exit(0);
});
