import { test, expect, chromium } from '@playwright/test';
import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const pnpmCommand = process.platform === 'win32' ? 'pnpm.cmd' : 'pnpm';

function getTauriBinaryPath(): string {
  const debugPath = path.join(__dirname, '..', 'src-tauri', 'target', 'debug', 'app.exe');
  const releasePath = path.join(__dirname, '..', 'src-tauri', 'target', 'release', 'app.exe');

  if (fs.existsSync(debugPath)) {
    console.log('使用 debug 版本:', debugPath);
    return debugPath;
  }

  if (fs.existsSync(releasePath)) {
    console.log('使用 release 版本:', releasePath);
    return releasePath;
  }

  throw new Error('找不到 Tauri 应用，请先运行 pnpm tauri dev 或 pnpm tauri build');
}

function checkTauriBuild(): boolean {
  try {
    const binaryPath = getTauriBinaryPath();
    return fs.existsSync(binaryPath);
  } catch {
    return false;
  }
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

test.describe('日志转发测试 - Tauri手动模式', () => {
  let tauriProcess: any;
  let devServer: any;
  let browser: any;
  let context: any;
  let tauriOutput = '';

  test.beforeAll(async () => {
    if (!checkTauriBuild()) {
      throw new Error('Tauri应用未构建，请先运行: pnpm tauri build');
    }
    console.log('Tauri应用已就绪:', getTauriBinaryPath());
  });

  test.beforeEach(async () => {
    devServer = spawn(pnpmCommand, ['dev'], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, FORCE_COLOR: '0' },
      detached: false,
      shell: true
    });

    await delay(10000);

    tauriProcess = spawn(getTauriBinaryPath(), [], {
      env: { ...process.env },
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    tauriOutput = '';
    if (tauriProcess.stdout) {
      tauriProcess.stdout.on('data', (data: Buffer) => {
        tauriOutput += data.toString();
      });
    }
    if (tauriProcess.stderr) {
      tauriProcess.stderr.on('data', (data: Buffer) => {
        tauriOutput += data.toString();
      });
    }

    await delay(8000);

    browser = await chromium.connectOverCDP('http://localhost:9222');

    context = await browser.newContext({
      viewport: { width: 1280, height: 720 }
    });
  });

  test.afterEach(async () => {
    if (context) {
      await context.close();
    }
    if (browser) {
      await browser.close();
    }
    if (tauriProcess) {
      tauriProcess.kill('SIGTERM');
      await delay(3000);
    }
    if (devServer) {
      devServer.kill('SIGTERM');
      await delay(2000);
    }
  });

  test('前端日志会转发到终端并带时间戳', async () => {
    const page = await context.newPage();
    await page.goto('http://localhost:5173/');
    await page.waitForLoadState('networkidle');

    const token = `日志转发测试-${Date.now()}`;
    await page.evaluate((message) => {
      console.log(message);
    }, token);

    const pattern = new RegExp(`\\[\\d{4}-\\d{2}-\\d{2}\\]\\[\\d{2}:\\d{2}:\\d{2}\\].*前端.*${escapeRegex(token)}`);
    const deadline = Date.now() + 20000;

    let matched = false;
    while (Date.now() < deadline) {
      if (pattern.test(tauriOutput)) {
        matched = true;
        break;
      }
      await delay(500);
    }

    expect(matched).toBe(true);
  });
});
