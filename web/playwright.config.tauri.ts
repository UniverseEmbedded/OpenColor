import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Tauri 原生模式配置
 * 用于在真实的 Tauri 应用中运行测试
 * 
 * 注意：运行此测试需要先构建 Tauri 应用
 * 命令：pnpm tauri build
 */

// Tauri 应用路径（根据平台自动选择）
const getTauriBinary = () => {
  const platform = process.platform;
  const targetDir = './src-tauri/target/release';
  
  switch (platform) {
    case 'win32':
      return `${targetDir}/app.exe`;
    case 'darwin':
      return `${targetDir}/app`;
    case 'linux':
      return `${targetDir}/app`;
    default:
      throw new Error(`不支持的平台: ${platform}`);
  }
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
    // Tauri 使用 WebDriver 协议
    connectOptions: {
      wsEndpoint: 'ws://127.0.0.1:9000',
    },
    
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    
    // Tauri 窗口大小
    viewport: { width: 1280, height: 720 },
    
    actionTimeout: 15 * 1000,
    navigationTimeout: 15 * 1000,
  },

  projects: [
    {
      name: 'tauri',
      use: {
        // Tauri 特定的配置
      },
    },
  ],

  // 不需要 webServer，因为直接启动 Tauri 应用
});
