import { defineConfig, devices } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Playwright Tauri 原生模式配置
 * 用于在真实的 Tauri 应用中运行测试
 * 
 * 运行方式：
 * 1. 先启动前端开发服务器：pnpm dev
 * 2. 然后运行测试，测试会启动 Tauri 应用并连接到前端服务器
 */

// Tauri 应用路径（优先使用 debug 版本）
const getTauriBinary = () => {
  const debugPath = path.join(__dirname, 'src-tauri', 'target', 'debug', 'app.exe');
  const releasePath = path.join(__dirname, 'src-tauri', 'target', 'release', 'app.exe');
  
  // 优先使用 debug 版本
  if (fs.existsSync(debugPath)) {
    console.log('使用 debug 版本:', debugPath);
    return debugPath;
  }
  
  // 否则使用 release 版本
  if (fs.existsSync(releasePath)) {
    console.log('使用 release 版本:', releasePath);
    return releasePath;
  }
  
  throw new Error('找不到 Tauri 应用，请先运行 pnpm tauri dev 或 pnpm tauri build');
};

export default defineConfig({
  testDir: './e2e-tauri',
  
  // 串行运行（Tauri 应用同时只能运行一个实例）
  fullyParallel: false,
  workers: 1,
  
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  
  reporter: [
    ['html', { outputFolder: 'playwright-report-tauri' }],
    ['list']
  ],
  
  globalTimeout: 10 * 60 * 1000,
  timeout: 60 * 1000, // Tauri 启动较慢，给 60 秒
  
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    
    // Tauri 窗口大小
    viewport: { width: 1280, height: 720 },
    
    actionTimeout: 15 * 1000,
    navigationTimeout: 15 * 1000,
    
    // 基础 URL
    baseURL: 'http://localhost:5173',
  },

  projects: [
    {
      name: 'tauri',
      use: {
        // 启动 Tauri 应用
        launchOptions: {
          executablePath: getTauriBinary(),
          args: [],
          env: {
            ...process.env,
          }
        }
      },
    },
  ],

  // 启动前端开发服务器
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000, // 2分钟启动超时
  },
});
