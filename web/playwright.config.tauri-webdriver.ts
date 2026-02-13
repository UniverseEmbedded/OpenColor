import { defineConfig, devices } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Playwright Tauri WebDriver 配置
 * 
 * 使用 tauri-driver 进行真正的 Tauri E2E 测试
 * 
 * 前置条件：
 * 1. 安装 tauri-driver: cargo install tauri-driver --locked
 * 2. 安装 Edge Driver: choco install selenium-edge-driver (或手动下载)
 * 3. 确保 msedgedriver 在 PATH 中
 * 
 * 运行方式：
 * 1. 先启动 tauri-driver: tauri-driver --port 4444
 * 2. 然后运行测试: pnpm exec playwright test --config=playwright.config.tauri-webdriver.ts
 */

// 获取Tauri应用路径（优先使用 debug 版本）
function getTauriBinary(): string {
  const debugPath = path.join(__dirname, 'src-tauri', 'target', 'debug', 'app.exe');
  const releasePath = path.join(__dirname, 'src-tauri', 'target', 'release', 'app.exe');
  
  if (fs.existsSync(debugPath)) {
    console.log('使用 debug 版本:', debugPath);
    return debugPath;
  }
  
  if (fs.existsSync(releasePath)) {
    console.log('使用 release 版本:', releasePath);
    return releasePath;
  }
  
  throw new Error('找不到 Tauri 应用，请先运行: pnpm tauri build');
}

export default defineConfig({
  testDir: './e2e-tauri',
  
  fullyParallel: false,
  workers: 1,
  
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  
  reporter: [
    ['html', { outputFolder: 'playwright-report-tauri' }],
    ['list']
  ],
  
  globalTimeout: 10 * 60 * 1000,
  timeout: 60 * 1000,
  
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    
    viewport: { width: 1280, height: 720 },
    
    actionTimeout: 15 * 1000,
    navigationTimeout: 15 * 1000,
    
    // 连接到 tauri-driver
    connectOptions: {
      wsEndpoint: 'ws://localhost:4444/session',
    },
  },

  projects: [
    {
      name: 'tauri-webdriver',
      use: {
        // WebDriver 特定的配置
        launchOptions: {
          executablePath: getTauriBinary(),
        }
      },
    },
  ],
});
