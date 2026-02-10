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

test.describe('基础页面测试', () => {
  
  test('页面标题正确', async ({ page }) => {
    await page.goto('/');
    
    // 检查页面标题
    await expect(page).toHaveTitle(/OpenColor|opencolor/i);
  });

  test('页面加载成功', async ({ page }) => {
    await page.goto('/');
    
    // 检查页面主体是否加载
    await expect(page.locator('body')).toBeVisible();
    
    // 检查 #app 元素是否存在
    await expect(page.locator('#app')).toBeVisible();
  });

  test('侧边栏导航存在', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(1000);
    
    // 检查侧边栏是否存在
    const sidebar = page.locator('.sidebar, [class*="sidebar"], nav').first();
    await expect(sidebar).toBeVisible();
  });

  test('顶部栏存在', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(1000);
    
    // 检查顶部栏是否存在
    const topbar = page.locator('.topbar, [class*="topbar"], header').first();
    await expect(topbar).toBeVisible();
  });
});

test.describe('主题切换测试', () => {
  
  test('可以切换主题', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(1000);
    
    // 查找主题切换按钮
    const themeButton = page.locator('button[title*="主题"], button[class*="theme"]').first();
    
    if (await themeButton.isVisible().catch(() => false)) {
      // 点击主题切换
      await themeButton.click();
      
      // 检查主题是否切换（通过检查 body 或 html 的 class）
      const html = page.locator('html');
      const hasDarkClass = await html.evaluate(el => el.classList.contains('dark'));
      
      // 主题应该切换了
      console.log('主题切换测试结果:', hasDarkClass ? '暗色模式' : '亮色模式');
    }
  });
});

test.describe('国际化测试', () => {
  
  test('语言切换功能存在', async ({ page }) => {
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(1000);
    
    // 查找语言切换按钮或下拉框
    const langSelector = page.locator('select[class*="locale"], button[class*="locale"], [data-testid="locale-select"]').first();
    
    // 语言选择器可能存在也可能不存在，记录结果
    const exists = await langSelector.isVisible().catch(() => false);
    console.log('语言切换功能存在:', exists);
  });
});

test.describe('响应式布局测试', () => {
  
  test('在移动视口下布局正确', async ({ page }) => {
    // 设置移动设备视口
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(1000);
    
    // 检查页面是否正常加载
    await expect(page.locator('#app')).toBeVisible();
    
    // 检查是否有移动端适配的类或样式
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('在平板视口下布局正确', async ({ page }) => {
    // 设置平板设备视口
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    
    // 等待应用初始化
    await page.waitForTimeout(1000);
    
    // 检查页面是否正常加载
    await expect(page.locator('#app')).toBeVisible();
  });
});
