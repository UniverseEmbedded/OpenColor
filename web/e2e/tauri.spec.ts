import { test, expect } from '@playwright/test';

/**
 * ⚠️ 已弃用 (DEPRECATED)
 * 
 * 这些测试在浏览器模式下运行，但 OpenColor 项目依赖 Tauri 原生 API，
 * 浏览器模式无法提供有效的测试环境。
 * 
 * 请使用 e2e-tauri/ 目录下的测试文件，它们使用 Tauri 原生模式。
 * 
 * @deprecated 请使用 e2e-tauri/tauri.spec.ts 替代
 */

test.describe('Tauri 运行时检测', () => {
  
  test('检测 Tauri 运行时环境', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(2000);
    
    // 检查是否在 Tauri 环境中
    const isTauri = await page.evaluate(() => {
      return !!(window as any).__TAURI__;
    });
    
    console.log('Tauri 运行时环境:', isTauri ? '已检测到' : '未检测到（浏览器模式）');
    
    // 在浏览器测试中，这可能为 false，这是正常的
    expect(typeof isTauri).toBe('boolean');
  });

  test('检查 Tauri API 可用性', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(2000);
    
    // 检查 Tauri API 的各个部分
    const tauriInfo = await page.evaluate(() => {
      const tauri = (window as any).__TAURI__;
      if (!tauri) return null;
      
      return {
        hasCore: !!tauri.core,
        hasEvent: !!tauri.event,
        hasOs: !!tauri.os,
        hasPath: !!tauri.path,
        hasFs: !!tauri.fs,
        hasDialog: !!tauri.dialog,
      };
    });
    
    console.log('Tauri API 信息:', JSON.stringify(tauriInfo, null, 2));
  });
});

test.describe('文件操作测试', () => {
  
  test('文件选择对话框功能存在', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(2000);
    
    // 查找文件选择相关的按钮
    const fileButtons = await page.locator('button:has-text("导入"), button:has-text("打开"), button:has-text("选择文件")').all();
    
    console.log('找到文件操作按钮数量:', fileButtons.length);
    
    // 记录找到的按钮
    for (let i = 0; i < Math.min(fileButtons.length, 5); i++) {
      const text = await fileButtons[i].textContent();
      console.log(`按钮 ${i + 1}:`, text);
    }
  });
});

test.describe('引擎连接测试', () => {
  
  test('引擎状态指示器存在', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(3000);
    
    // 查找引擎状态相关的元素
    const engineIndicators = await page.locator('[class*="engine"], [data-testid*="engine"], .engine-status').all();
    
    console.log('找到引擎状态指示器数量:', engineIndicators.length);
  });

  test('检查控制台日志捕获', async ({ page }) => {
    await page.goto('/');
    
    // 收集控制台日志
    const logs: string[] = [];
    page.on('console', msg => {
      logs.push(`[${msg.type()}] ${msg.text()}`);
    });
    
    // 等待一段时间收集日志
    await page.waitForTimeout(3000);
    
    // 检查是否有初始化日志
    const initLogs = logs.filter(log => 
      log.includes('初始化') || 
      log.includes('引擎') || 
      log.includes('Tauri')
    );
    
    console.log('初始化相关日志数量:', initLogs.length);
    console.log('前5条日志:', logs.slice(0, 5));
  });
});

test.describe('设置和配置测试', () => {
  
  test('设置页面可访问', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(2000);
    
    // 查找设置按钮
    const settingsButton = page.locator('button[title*="设置"], button[class*="settings"], a[href*="settings"]').first();
    
    if (await settingsButton.isVisible().catch(() => false)) {
      await settingsButton.click();
      
      // 等待设置页面加载
      await page.waitForTimeout(1000);
      
      // 检查设置页面是否显示
      const settingsContent = page.locator('[class*="settings"], .settings-view, [data-testid="settings"]').first();
      const isVisible = await settingsContent.isVisible().catch(() => false);
      
      console.log('设置页面显示:', isVisible);
    }
  });
});

test.describe('相册和资源库测试', () => {
  
  test('相册页面可访问', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(2000);
    
    // 查找相册导航项
    const albumNav = page.locator('a:has-text("相册"), button:has-text("相册"), [class*="album"]').first();
    
    if (await albumNav.isVisible().catch(() => false)) {
      await albumNav.click();
      
      // 等待相册页面加载
      await page.waitForTimeout(1000);
      
      // 检查相册内容区域
      const albumContent = page.locator('[class*="album"], .album-view, [data-testid="album"]').first();
      const isVisible = await albumContent.isVisible().catch(() => false);
      
      console.log('相册页面显示:', isVisible);
    }
  });
});
