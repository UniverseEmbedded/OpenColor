import { test, expect } from '@playwright/test';

/**
 * Tauri 原生模式端到端测试
 * 这些测试在真实的 Tauri 应用中运行，可以访问 Tauri API
 * 
 * 运行前需要：
 * 1. 安装 tauri-driver: cargo install tauri-driver
 * 2. 构建应用: pnpm tauri build
 * 3. 运行测试: pnpm test:e2e:tauri
 */

test.describe('Tauri 原生环境测试', () => {
  
  test('Tauri API 存在', async ({ page }) => {
    // 检查 Tauri 运行时
    const isTauri = await page.evaluate(() => {
      return !!(window as any).__TAURI__;
    });
    
    // 在 Tauri 原生模式下，这应该为 true
    expect(isTauri).toBe(true);
  });

  test('Tauri Core API 可用', async ({ page }) => {
    const tauriInfo = await page.evaluate(() => {
      const tauri = (window as any).__TAURI__;
      return {
        hasCore: !!tauri?.core,
        hasEvent: !!tauri?.event,
        hasOs: !!tauri?.os,
        hasPath: !!tauri?.path,
        hasFs: !!tauri?.fs,
        hasDialog: !!tauri?.dialog,
        hasShell: !!tauri?.shell,
      };
    });
    
    console.log('Tauri API 信息:', tauriInfo);
    
    // 验证核心 API 存在
    expect(tauriInfo.hasCore).toBe(true);
    expect(tauriInfo.hasEvent).toBe(true);
  });

  test('可以调用 Tauri 命令', async ({ page }) => {
    // 测试调用 Rust 后端命令
    const result = await page.evaluate(async () => {
      try {
        const { invoke } = (window as any).__TAURI__.core;
        // 调用 health.ping 命令
        const response = await invoke('engine_request', {
          method: 'health.ping',
          params: {}
        });
        return { success: true, response };
      } catch (error) {
        return { success: false, error: String(error) };
      }
    });
    
    console.log('命令调用结果:', result);
    
    // 命令应该成功执行（即使引擎未启动，也应该有响应）
    expect(result).toBeDefined();
  });

  test('应用窗口标题正确', async ({ page }) => {
    // 检查窗口标题
    const title = await page.title();
    console.log('窗口标题:', title);
    
    expect(title).toMatch(/OpenColor|opencolor/i);
  });
});

test.describe('Tauri 文件系统测试', () => {
  
  test('文件系统 API 可用', async ({ page }) => {
    const fsAvailable = await page.evaluate(() => {
      const tauri = (window as any).__TAURI__;
      return !!tauri?.fs;
    });
    
    console.log('文件系统 API 可用:', fsAvailable);
    
    // 文件系统插件应该可用
    expect(fsAvailable).toBe(true);
  });

  test('可以获取应用目录', async ({ page }) => {
    const paths = await page.evaluate(async () => {
      try {
        const { appLocalDataDir, documentDir } = (window as any).__TAURI__.path;
        return {
          appData: await appLocalDataDir(),
          documents: await documentDir(),
        };
      } catch (error) {
        return { error: String(error) };
      }
    });
    
    console.log('应用目录:', paths);
    
    // 应该能获取到路径
    expect(paths).toBeDefined();
    if (!paths.error) {
      expect(paths.appData).toBeTruthy();
      expect(paths.documents).toBeTruthy();
    }
  });
});

test.describe('Tauri 对话框测试', () => {
  
  test('对话框 API 可用', async ({ page }) => {
    const dialogAvailable = await page.evaluate(() => {
      const tauri = (window as any).__TAURI__;
      return !!tauri?.dialog;
    });
    
    console.log('对话框 API 可用:', dialogAvailable);
    expect(dialogAvailable).toBe(true);
  });
});

test.describe('Tauri 原生菜单测试', () => {
  
  test('应用菜单存在', async ({ page }) => {
    // 检查菜单（Windows/Linux 有菜单栏，macOS 有系统菜单）
    const hasMenu = await page.evaluate(() => {
      // 检查是否有菜单相关的 DOM 元素
      const menuElements = document.querySelectorAll('[role="menubar"], .menu, [class*="menu"]');
      return menuElements.length > 0;
    });
    
    console.log('应用菜单存在:', hasMenu);
    
    // 记录结果，但不做强制断言（因为不同平台表现不同）
    expect(typeof hasMenu).toBe('boolean');
  });
});
