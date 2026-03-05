#!/usr/bin/env node
/**
 * SessionEnd Hook — 對話結束自動保存
 *
 * 當 Claude 對話結束時：
 * 1. 讀取 transcript 提取修改了哪些檔案
 * 2. 在 active_context.md 追加「最後活動」時間戳
 * 3. 歸檔 session 摘要到 sessions/ 目錄
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const MEMORY_DIR = path.join(PROJECT_ROOT, 'data', 'memory');
const ACTIVE_CONTEXT = path.join(MEMORY_DIR, 'active_context.md');
const SESSIONS_DIR = path.join(MEMORY_DIR, 'sessions');

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getTimestamp() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function getDateId() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

/**
 * 從 transcript 提取摘要
 */
function extractSummary(transcriptPath) {
  try {
    const content = fs.readFileSync(transcriptPath, 'utf-8');
    const lines = content.split('\n').filter(Boolean);
    const filesModified = new Set();
    const toolsUsed = new Set();
    let userMessageCount = 0;

    for (const line of lines) {
      try {
        const entry = JSON.parse(line);

        // 計算使用者訊息數
        if (entry.type === 'user' || entry.role === 'user' || entry.message?.role === 'user') {
          userMessageCount++;
        }

        // 收集工具和修改的檔案
        if (entry.type === 'tool_use' || entry.tool_name) {
          const toolName = entry.tool_name || entry.name || '';
          if (toolName) toolsUsed.add(toolName);
          const filePath = entry.tool_input?.file_path || entry.input?.file_path || '';
          if (filePath && (toolName === 'Edit' || toolName === 'Write')) {
            filesModified.add(filePath);
          }
        }

        // Claude Code JSONL 格式
        if (entry.type === 'assistant' && Array.isArray(entry.message?.content)) {
          for (const block of entry.message.content) {
            if (block.type === 'tool_use') {
              const toolName = block.name || '';
              if (toolName) toolsUsed.add(toolName);
              const filePath = block.input?.file_path || '';
              if (filePath && (toolName === 'Edit' || toolName === 'Write')) {
                filesModified.add(filePath);
              }
            }
          }
        }
      } catch { /* skip unparseable lines */ }
    }

    return {
      userMessageCount,
      filesModified: Array.from(filesModified),
      toolsUsed: Array.from(toolsUsed),
    };
  } catch {
    return null;
  }
}

// 讀取 stdin
const MAX_STDIN = 1024 * 1024;
let stdinData = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  if (stdinData.length < MAX_STDIN) {
    stdinData += chunk.substring(0, MAX_STDIN - stdinData.length);
  }
});
process.stdin.on('end', () => {
  main().catch(err => {
    console.error('[SessionEnd] Error:', err.message);
    process.exit(0);
  });
});

async function main() {
  ensureDir(MEMORY_DIR);
  ensureDir(SESSIONS_DIR);

  const timestamp = getTimestamp();

  // 1. 嘗試從 stdin 取得 transcript 路徑
  let transcriptPath = null;
  try {
    const input = JSON.parse(stdinData);
    transcriptPath = input.transcript_path;
  } catch {
    transcriptPath = process.env.CLAUDE_TRANSCRIPT_PATH;
  }

  // 2. 提取摘要
  let summary = null;
  if (transcriptPath && fs.existsSync(transcriptPath)) {
    summary = extractSummary(transcriptPath);
  }

  // 3. 在 active_context.md 追加最後活動時間
  if (fs.existsSync(ACTIVE_CONTEXT)) {
    let content = fs.readFileSync(ACTIVE_CONTEXT, 'utf-8');

    // 更新時間戳
    content = content.replace(
      /更新：\d{4}-\d{2}-\d{2} \d{2}:\d{2}/,
      `更新：${timestamp}`
    );

    fs.writeFileSync(ACTIVE_CONTEXT, content, 'utf-8');
  }

  // 4. 歸檔 session
  if (summary && summary.userMessageCount > 0) {
    const dateId = getDateId();
    const sessionFile = path.join(SESSIONS_DIR, `${dateId}.md`);

    let sessionContent = `# 對話紀錄 — ${timestamp}\n\n`;
    sessionContent += `## 統計\n`;
    sessionContent += `- 使用者訊息數：${summary.userMessageCount}\n`;
    sessionContent += `- 使用工具：${summary.toolsUsed.join(', ') || '無'}\n\n`;

    if (summary.filesModified.length > 0) {
      sessionContent += `## 修改的檔案\n`;
      for (const f of summary.filesModified) {
        sessionContent += `- ${f}\n`;
      }
      sessionContent += '\n';
    }

    fs.writeFileSync(sessionFile, sessionContent, 'utf-8');
    console.error(`[SessionEnd] Session 已歸檔: ${sessionFile}`);
  }

  console.error(`[SessionEnd] 對話結束 (${timestamp})`);
  process.exit(0);
}
