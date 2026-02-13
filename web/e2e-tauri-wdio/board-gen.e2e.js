import fs from 'fs';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

describe('校准色盘生成测试 - tauri-driver', () => {
  it('生成1张8色校准色盘', async () => {
    fs.mkdirSync('test-results', { recursive: true });

    console.log('[E2E] 正在访问页面...');
    await browser.url('/#calibrate/board-gen');
    
    const currentUrl = await browser.getUrl();
    console.log(`[E2E] 当前页面 URL: ${currentUrl}`);

    await delay(5000);

    const profileSelect = await $('select#profile');

    const exists = await profileSelect.isExisting();
    console.log(`[E2E] select#profile 是否存在: ${exists}`);

    if (!exists) {
      console.log('[E2E] 元素不存在，尝试截屏...');
      try {
        const screenshot = await browser.takeScreenshot();
        if (screenshot) {
          fs.writeFileSync('test-results/wdio-01-no-profiles.png', screenshot, 'base64');
          console.log('[E2E] 截屏已保存到 test-results/wdio-01-no-profiles.png');
        }
      } catch (err) {
        console.error('[E2E] 截屏失败:', err.message);
      }
      throw new Error('页面未加载成功或 select#profile 元素未找到');
    }

    await profileSelect.waitForExist({ timeout: 15000 });
    await delay(2000);

    const options = await profileSelect.$$('option');
    console.log(`[E2E] 找到 ${options.length} 个配置文件选项`);

    if (options.length <= 1) {
      try {
        const screenshot = await browser.takeScreenshot();
        if (screenshot) {
          fs.writeFileSync('test-results/wdio-01-no-profiles.png', screenshot, 'base64');
        }
      } catch (err) {}
      throw new Error('没有可用的配置文件');
    }

    let selected = false;
    for (let i = 0; i < options.length; i++) {
      const text = await options[i].getText();
      if (text?.includes('8')) {
        await profileSelect.selectByIndex(i);
        selected = true;
        break;
      }
    }

    if (!selected) {
      await profileSelect.selectByIndex(1);
    }

    await delay(1500);
    await browser.saveScreenshot('test-results/wdio-02-profile-selected.png');

    const numBoards = await $('input#numBoards');
    await numBoards.waitForExist({ timeout: 15000 });
    await numBoards.setValue('1');
    await delay(800);

    const generateBtn = await $('button.generate-btn');
    await generateBtn.waitForExist({ timeout: 15000 });
    await generateBtn.click();

    const startTime = Date.now();
    const maxWaitTime = 5 * 60 * 1000;

    while (Date.now() - startTime < maxWaitTime) {
      const buttonText = await generateBtn.getText().catch(() => '');
      const hasProgress = await $('.progress-detail').isExisting().catch(() => false);
      const isGenerating = (buttonText || '').includes('生成中') || hasProgress;
      if (!isGenerating) break;
      await delay(3000);
    }

    await browser.saveScreenshot('test-results/wdio-03-generation-complete.png');

    const errorMessage = await $('.error-message');
    if (await errorMessage.isExisting()) {
      const errorText = await errorMessage.getText();
      await browser.saveScreenshot('test-results/wdio-04-error.png');
      throw new Error(`生成失败: ${errorText}`);
    }

    const cards = await $$('.cards-container .board-card, [class*="board-card"]');
    if (cards.length === 0) {
      await browser.saveScreenshot('test-results/wdio-04-no-cards.png');
      throw new Error('没有生成任何色盘');
    }

    await cards[0].click();
    await delay(1500);
    await browser.saveScreenshot('test-results/wdio-05-card-selected.png');

    const preview = await $('.grid-wrapper');
    const emptyPreview = await $('.empty-preview');
    const hasPreview = (await preview.isExisting().catch(() => false)) || (await emptyPreview.isExisting().catch(() => false));
    if (!hasPreview) {
      await browser.saveScreenshot('test-results/wdio-06-no-preview.png');
      throw new Error('预览区域未显示');
    }
  });
});
