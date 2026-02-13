import fs from 'fs';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let lastSessionId = null;
const ensureSession = async () => {
  try {
    await browser.getUrl();
  } catch (e) {
    console.log('[E2E] 会话已断开，正在重新启动应用');
    await browser.reloadSession();
    await delay(3000);
  }
};
const ensureAppLoaded = async () => {
  if (browser.sessionId !== lastSessionId) {
    console.log('[E2E] 初始化应用页面');
    await browser.url('/');
    lastSessionId = browser.sessionId;
    await delay(1000);
  }
  const loadingScreen = await $('#loading-screen');
  await loadingScreen.waitForExist({ timeout: 10000 });
  return loadingScreen;
};
const waitAppReady = async () => {
  const loadingScreen = await $('#loading-screen');
  await loadingScreen.waitForDisplayed({ reverse: true, timeout: 30000 });
  await delay(500);
  return loadingScreen;
};
const navigateTo = async (hash) => {
  await browser.execute((target) => {
    window.location.hash = target;
  }, hash);
  await browser.waitUntil(async () => {
    const currentHash = await browser.execute(() => window.location.hash);
    return currentHash === `#${hash}`;
  }, { timeout: 5000 });
  await delay(500);
};

describe('全局加载层测试', () => {
  before(() => {
    fs.mkdirSync('test-results', { recursive: true });
  });

  beforeEach(async () => {
    await ensureSession();
  });

  it('应用启动时应显示全屏加载层', async () => {
    console.log('[E2E] 测试1：应用启动时全屏加载层应正确显示');

    console.log('[E2E] 导航到应用首页');
    const loadingScreen = await ensureAppLoaded();

    console.log('[E2E] 检查 #loading-screen 元素是否存在');

    console.log('[E2E] ✓ 加载层元素已存在于DOM中');

    const isDisplayed = await loadingScreen.isDisplayed().catch(() => false);
    const appReady = await browser.execute(() => !!window.__appReady);
    console.log(`[E2E] 加载层可见性: ${isDisplayed}, 应用就绪: ${appReady}`);
    if (!isDisplayed && !appReady) {
      throw new Error('应用启动时全屏加载层应该可见或应用已完成初始化');
    }

    const opacity = await loadingScreen.getCSSProperty('opacity');
    const display = await loadingScreen.getCSSProperty('display');
    console.log(`[E2E] 加载层样式 - opacity: ${opacity.value}, display: ${display.value}`);

    if (isDisplayed) {
      const opacityValue = Number(opacity.value);
      if (!Number.isFinite(opacityValue) || opacityValue < 0.99) {
        throw new Error(`加载层opacity应该接近1，实际为${opacity.value}`);
      }
      if (display.value !== 'flex') {
        throw new Error(`加载层display应该为flex，实际为${display.value}`);
      }
    } else if (display.value !== 'none') {
      throw new Error(`加载层隐藏时display应该为none，实际为${display.value}`);
    }

    // 检查加载层内容
    const loadingText = await loadingScreen.$('.loading-text');
    const textExists = await loadingText.isExisting();
    if (textExists) {
      const text = await loadingText.getText();
      console.log(`[E2E] 加载层文字: ${text}`);
      if (text && !text.includes('OpenColor')) {
        throw new Error('加载层应该显示OpenColor文字');
      }
    } else {
      console.log('[E2E] 未找到加载层文字元素');
    }

    // 检查加载层z-index确保在最上层
    const zIndex = await loadingScreen.getCSSProperty('z-index');
    console.log(`[E2E] 加载层z-index: ${zIndex.value}`);
    if (parseInt(zIndex.value) <= 9999) {
      throw new Error('加载层z-index应该很高');
    }

    // 截图记录启动状态
    await browser.saveScreenshot('test-results/wdio-loading-overlay-01-startup.png');
    console.log('[E2E] ✓ 应用启动加载层测试通过');
  });

  it('应用初始化完成后加载层应自动隐藏', async () => {
    console.log('[E2E] 测试2：应用初始化完成后加载层应自动隐藏');

    await ensureAppLoaded();
    const loadingScreen = await $('#loading-screen');

    // 等待加载层消失（最多等待30秒）
    console.log('[E2E] 等待应用初始化完成，加载层自动隐藏...');
    try {
      await loadingScreen.waitForDisplayed({ reverse: true, timeout: 30000 });
      console.log('[E2E] ✓ 加载层已自动隐藏');
    } catch (e) {
      // 如果超时，检查是否还在加载中
      const isDisplayed = await loadingScreen.isDisplayed().catch(() => false);
      if (isDisplayed) {
        const opacity = await loadingScreen.getCSSProperty('opacity');
        const display = await loadingScreen.getCSSProperty('display');
        console.error(`[E2E] 加载层仍然可见 - opacity: ${opacity.value}, display: ${display.value}`);
        throw new Error('应用初始化完成后加载层没有自动隐藏');
      }
    }

    // 确认加载层已隐藏
    const isDisplayed = await loadingScreen.isDisplayed().catch(() => false);
    console.log(`[E2E] 加载层显示状态: ${isDisplayed}`);
    if (isDisplayed) {
      throw new Error('应用初始化完成后加载层应该隐藏');
    }

    // 检查加载层是否还在DOM中（应该保留以便重复使用）
    const isExisting = await loadingScreen.isExisting();
    console.log(`[E2E] 加载层仍在DOM中: ${isExisting}`);
    if (!isExisting) {
      throw new Error('加载层应该保留在DOM中以便重复使用');
    }

    // 截图记录状态
    await browser.saveScreenshot('test-results/wdio-loading-overlay-02-hidden.png');
    console.log('[E2E] ✓ 加载层自动隐藏测试通过');
  });

  it('debug页面加载覆盖层测试按钮应能触发全屏加载层', async () => {
    console.log('[E2E] 测试3：debug页面加载覆盖层测试按钮应能触发全屏加载层');

    await ensureAppLoaded();
    const loadingScreen = await waitAppReady();

    // 导航到debug页面
    console.log('[E2E] 导航到debug页面');
    await navigateTo('settings/debug');

    // 截图记录debug页面
    await browser.saveScreenshot('test-results/wdio-loading-overlay-03-debug-page.png');

    // 找到并点击"触发加载覆盖层"按钮
    console.log('[E2E] 查找加载覆盖层测试按钮');
    const triggerButton = await $('button*=触发加载覆盖层');
    await triggerButton.waitForExist({ timeout: 5000 });
    console.log('[E2E] ✓ 找到按钮，准备点击');

    // 点击按钮前确认加载层是隐藏的
    const wasDisplayed = await loadingScreen.isDisplayed().catch(() => false);
    console.log(`[E2E] 点击前加载层状态: ${wasDisplayed ? '显示' : '隐藏'}`);
    if (wasDisplayed) {
      throw new Error('点击按钮前加载层应该是隐藏的');
    }

    // 点击按钮
    console.log('[E2E] 点击加载覆盖层测试按钮');
    await triggerButton.click();

    // 立即检查加载层是否显示
    await delay(100); // 给一点反应时间
    const isDisplayedAfterClick = await loadingScreen.isDisplayed().catch(() => false);
    console.log(`[E2E] 点击后加载层可见性: ${isDisplayedAfterClick}`);
    if (!isDisplayedAfterClick) {
      throw new Error('点击按钮后加载层应该立即显示');
    }

    // 检查加载层样式
    const opacity = await loadingScreen.getCSSProperty('opacity');
    const display = await loadingScreen.getCSSProperty('display');
    console.log(`[E2E] 加载层样式 - opacity: ${opacity.value}, display: ${display.value}`);
    const opacityValue = Number(opacity.value);
    if (!Number.isFinite(opacityValue) || opacityValue < 0.99) {
      throw new Error(`加载层opacity应该接近1，实际为${opacity.value}`);
    }
    if (display.value !== 'flex') {
      throw new Error(`加载层display应该为flex，实际为${display.value}`);
    }

    // 截图记录加载层显示状态
    await browser.saveScreenshot('test-results/wdio-loading-overlay-04-triggered.png');
    console.log('[E2E] ✓ 按钮成功触发加载层显示');

    // 等待3秒后检查加载层是否自动隐藏
    console.log('[E2E] 等待3秒，检查加载层是否自动隐藏...');
    await loadingScreen.waitForDisplayed({ reverse: true, timeout: 5000 });

    const isDisplayedAfterTimeout = await loadingScreen.isDisplayed().catch(() => false);
    console.log(`[E2E] 3秒后加载层显示状态: ${isDisplayedAfterTimeout}`);
    if (isDisplayedAfterTimeout) {
      throw new Error('3秒后加载层应该自动隐藏');
    }

    // 截图记录最终状态
    await browser.saveScreenshot('test-results/wdio-loading-overlay-05-auto-hidden.png');
    console.log('[E2E] ✓ 加载层自动隐藏测试通过');
  });

  it('加载覆盖层测试按钮应可重复触发', async () => {
    console.log('[E2E] 测试4：加载覆盖层测试按钮应可重复触发');

    await ensureAppLoaded();
    const loadingScreen = await waitAppReady();

    await navigateTo('settings/debug');

    const triggerButton = await $('button*=触发加载覆盖层');

    // 第一次触发
    console.log('[E2E] 第一次触发加载层');
    await triggerButton.click();
    await delay(100);
    const firstTriggerDisplayed = await loadingScreen.isDisplayed().catch(() => false);
    if (!firstTriggerDisplayed) {
      throw new Error('第一次点击后加载层应该显示');
    }
    console.log('[E2E] ✓ 第一次触发成功');

    // 等待第一次自动隐藏
    await loadingScreen.waitForDisplayed({ reverse: true, timeout: 5000 });
    await delay(500);

    // 第二次触发
    console.log('[E2E] 第二次触发加载层');
    await triggerButton.click();
    await delay(100);
    const secondTriggerDisplayed = await loadingScreen.isDisplayed().catch(() => false);
    if (!secondTriggerDisplayed) {
      throw new Error('第二次点击后加载层应该再次显示');
    }
    console.log('[E2E] ✓ 第二次触发成功');

    // 等待第二次自动隐藏
    await loadingScreen.waitForDisplayed({ reverse: true, timeout: 5000 });

    // 第三次触发
    console.log('[E2E] 第三次触发加载层');
    await triggerButton.click();
    await delay(100);
    const thirdTriggerDisplayed = await loadingScreen.isDisplayed().catch(() => false);
    if (!thirdTriggerDisplayed) {
      throw new Error('第三次点击后加载层应该仍然可以显示');
    }
    console.log('[E2E] ✓ 第三次触发成功');

    await browser.saveScreenshot('test-results/wdio-loading-overlay-06-repeatable.png');
    console.log('[E2E] ✓ 按钮可重复触发测试通过');
  });
});
