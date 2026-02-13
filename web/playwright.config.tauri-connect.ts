import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright 配置 - 连接到已运行的 Tauri 应用
 * 
 * 使用方式：
 * 1. 先运行: pnpm tauri dev (或 pixi run web-tauri-dev)
 * 2. 然后运行: pnpm exec playwright test --config=playwright.config.tauri-connect.ts
 */

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
    
    // 连接到已运行的前端服务器
    baseURL: 'http://localhost:5173',
  },

  projects: [
    {
      name: 'tauri-connect',
      use: {
        ...devices['Desktop Chrome'],
        headless: false,
      },
    },
  ],

  // 不需要 webServer，因为假设服务已运行
});
