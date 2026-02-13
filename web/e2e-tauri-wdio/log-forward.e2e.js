import fs from 'fs';
import path from 'path';
import os from 'os';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findLatestLogFile(logDir) {
  if (!fs.existsSync(logDir)) {
    return null;
  }
  const entries = fs.readdirSync(logDir, { withFileTypes: true });
  const logFiles = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.log'))
    .map((entry) => ({
      name: entry.name,
      fullPath: path.join(logDir, entry.name),
      mtime: fs.statSync(path.join(logDir, entry.name)).mtimeMs
    }))
    .sort((a, b) => b.mtime - a.mtime);

  return logFiles[0]?.fullPath || null;
}

async function waitForLogEntry(logFile, token, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  const pattern = new RegExp(`\\[\\d{4}-\\d{2}-\\d{2}\\]\\[\\d{2}:\\d{2}:\\d{2}\\].*前端.*${token}`);

  while (Date.now() < deadline) {
    if (fs.existsSync(logFile)) {
      const content = fs.readFileSync(logFile, 'utf-8');
      if (pattern.test(content)) {
        return true;
      }
    }
    await delay(500);
  }

  return false;
}

describe('日志转发测试 - tauri-driver', () => {
  it('前端日志会写入应用日志并带时间戳', async () => {
    await browser.url('/');
    await delay(3000);

    const logDir = process.env.LOCALAPPDATA
      ? path.join(process.env.LOCALAPPDATA, 'OpenColor', 'logs')
      : process.env.APPDATA
        ? path.join(process.env.APPDATA, 'OpenColor', 'logs')
      : process.platform === 'darwin'
        ? path.join(os.homedir(), 'Library', 'Logs', 'OpenColor')
        : path.join(os.homedir(), '.local', 'share', 'OpenColor', 'logs');

    const token = `日志转发测试-${Date.now()}`;

    await browser.execute((message) => {
      console.log(message);
    }, token);

    await delay(1000);

    let logFile = null;
    const logFileDeadline = Date.now() + 10000;
    while (Date.now() < logFileDeadline) {
      logFile = findLatestLogFile(logDir);
      if (logFile) {
        break;
      }
      await delay(500);
    }

    if (!logFile) {
      throw new Error(`未找到日志文件: ${logDir}`);
    }

    const matched = await waitForLogEntry(logFile, token, 10000);
    if (!matched) {
      throw new Error(`日志未写入或缺少时间戳: ${logFile}`);
    }
  });
});
