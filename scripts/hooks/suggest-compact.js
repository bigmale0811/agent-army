#!/usr/bin/env node
/**
 * Strategic Compact Suggester — 在邏輯斷點提醒壓縮
 *
 * 追蹤工具呼叫次數，在達到門檻時提醒進行手動 /compact。
 * 這比 auto-compact 好，因為壓縮發生在邏輯斷點而非隨機時間。
 *
 * 環境變數：
 *   COMPACT_THRESHOLD — 幾次工具呼叫後提醒（預設 40，因為我們的流水線很吃 token）
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

async function main() {
  const sessionId = process.env.CLAUDE_SESSION_ID || 'default';
  const counterFile = path.join(os.tmpdir(), `agent-army-tool-count-${sessionId}`);
  const rawThreshold = parseInt(process.env.COMPACT_THRESHOLD || '40', 10);
  const threshold = (Number.isFinite(rawThreshold) && rawThreshold > 0 && rawThreshold <= 10000)
    ? rawThreshold
    : 40;

  let count = 1;

  try {
    const fd = fs.openSync(counterFile, 'a+');
    try {
      const buf = Buffer.alloc(64);
      const bytesRead = fs.readSync(fd, buf, 0, 64, 0);
      if (bytesRead > 0) {
        const parsed = parseInt(buf.toString('utf8', 0, bytesRead).trim(), 10);
        count = (Number.isFinite(parsed) && parsed > 0 && parsed <= 1000000)
          ? parsed + 1
          : 1;
      }
      fs.ftruncateSync(fd, 0);
      fs.writeSync(fd, String(count), 0);
    } finally {
      fs.closeSync(fd);
    }
  } catch {
    try { fs.writeFileSync(counterFile, String(count)); } catch { /* ignore */ }
  }

  // 達到門檻時提醒
  if (count === threshold) {
    console.error(`[StrategicCompact] ⚠️ ${threshold} 次工具呼叫 — 如果正在切換任務階段，建議 /compact`);
    console.error('[StrategicCompact] 壓縮前請確保 active_context.md 已更新');
  }

  // 之後每 20 次提醒一次
  if (count > threshold && (count - threshold) % 20 === 0) {
    console.error(`[StrategicCompact] ⚠️ ${count} 次工具呼叫 — context 可能很滿，考慮 /compact`);
  }

  process.exit(0);
}

main().catch(err => {
  console.error('[StrategicCompact] Error:', err.message);
  process.exit(0);
});
