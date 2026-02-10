import { defineConfig, devices } from '@playwright/test';

/**
 * ⚠️ 已弃用 (DEPRECATED)
 * 
 * 此配置用于浏览器模式的 Playwright 测试。
 * 由于 OpenColor 项目依赖 Tauri 原生 API（文件系统、对话框、后端命令等），
 * 浏览器模式无法提供有效的测试环境。
 * 
 * 请使用 Tauri 原生模式进行 E2E 测试：
 * - 配置: playwright.config.tauri.ts
 * - 命令: pnpm test:e2e:tauri
 * 
 * @deprecated 请使用 playwright.config.tauri.ts 替代
 */
export default defineConfig({
  testDir: './e2e',
  
  // 完全并行运行测试
  fullyParallel: true,
  
  // 禁止在测试文件中使用 test.only
  forbidOnly: !!process.env.CI,
  
  // 重试次数
  retries: process.env.CI ? 2 : 0,
  
  // 并行工作进程数
  workers: process.env.CI ? 1 : undefined,
  
  // 测试报告器
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list']
  ],
  
  // 全局超时设置
  globalTimeout: 10 * 60 * 1000, // 10分钟全局超时
  
  // 每个测试的超时
  timeout: 30 * 1000, // 30秒
  
  use: {
    // 基础 URL
    baseURL: 'http://localhost:5173',
    
    // 收集跟踪信息
    trace: 'on-first-retry',
    
    // 截图设置
    screenshot: 'only-on-failure',
    
    // 视频录制
    video: 'on-first-retry',
    
    // 视口大小
    viewport: { width: 1280, height: 720 },
    
    // 动作超时
    actionTimeout: 10 * 1000, // 10秒
    
    // 导航超时
    navigationTimeout: 10 * 1000, // 10秒
  },

  projects: [
    // 桌面 Chromium
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // 桌面 Firefox
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    // 桌面 WebKit
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],

  // 开发服务器配置
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000, // 2分钟启动超时
  },
});
