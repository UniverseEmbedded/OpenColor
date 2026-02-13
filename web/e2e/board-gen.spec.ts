import { test, expect } from '@playwright/test';

// 等待指定时间
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

test.describe('校准色盘生成测试', () => {
  test('生成1张8色校准色盘', async ({ page }) => {
    console.log('开始测试：生成1张8色校准色盘');

    // 监听控制台日志
    const logs: { type: string; text: string }[] = [];
    page.on('console', msg => {
      const logEntry = {
        type: msg.type(),
        text: msg.text()
      };
      logs.push(logEntry);
      console.log(`[${logEntry.type}] ${logEntry.text}`);
    });

    // 监听页面错误
    page.on('pageerror', error => {
      console.error('页面错误:', error.message);
    });

    // 1. 导航到校准色盘生成页面
    console.log('1. 导航到校准色盘生成页面');
    await page.goto('/calibrate/board-gen');
    await page.waitForLoadState('networkidle');
    await delay(2000);
    
    // 截图：页面加载后
    await page.screenshot({ path: 'test-results/01-board-gen-page.png' });

    // 2. 等待配置文件加载
    console.log('2. 等待配置文件加载');
    const profileSelect = page.locator('select#profile');
    await profileSelect.waitFor({ state: 'visible', timeout: 10000 });
    
    // 等待选项加载
    await delay(1000);
    
    // 获取可用的配置文件
    const options = await profileSelect.locator('option').all();
    console.log(`找到 ${options.length} 个配置文件`);
    
    for (let i = 0; i < options.length; i++) {
      const text = await options[i].textContent();
      console.log(`  配置文件 ${i}: ${text}`);
    }
    
    if (options.length <= 1) {
      console.log('警告：没有可用的配置文件');
      await page.screenshot({ path: 'test-results/02-no-profiles.png' });
      throw new Error('没有可用的配置文件');
    }

    // 选择一个8色的配置文件（通常是第一个非空选项）
    let selected8ColorProfile = false;
    for (let i = 0; i < options.length; i++) {
      const text = await options[i].textContent();
      
      // 查找包含"8"的配置文件
      if (text && text.includes('8')) {
        await profileSelect.selectOption({ index: i });
        selected8ColorProfile = true;
        console.log(`选择了8色配置文件: ${text}`);
        break;
      }
    }
    
    // 如果没有找到8色配置，选择第一个可用配置
    if (!selected8ColorProfile && options.length > 1) {
      await profileSelect.selectOption({ index: 1 });
      console.log('选择了第一个可用配置文件');
    }
    
    await delay(1000);
    await page.screenshot({ path: 'test-results/02-profile-selected.png' });

    // 3. 设置生成数量为1
    console.log('3. 设置生成数量为1');
    const numBoardsInput = page.locator('input#numBoards');
    await numBoardsInput.fill('1');
    await delay(500);

    // 4. 点击生成按钮
    console.log('4. 点击生成按钮');
    const generateBtn = page.locator('button.generate-btn');
    await generateBtn.click();

    // 5. 等待生成完成（最多等待5分钟）
    console.log('5. 等待生成完成...');
    const startTime = Date.now();
    const maxWaitTime = 5 * 60 * 1000; // 5分钟
    
    while (Date.now() - startTime < maxWaitTime) {
      // 检查是否还在生成中
      const isGenerating = await generateBtn.locator('text=生成中').isVisible().catch(() => false);
      const hasProgress = await page.locator('.progress-detail').isVisible().catch(() => false);
      
      if (!isGenerating && !hasProgress) {
        console.log('生成完成');
        break;
      }
      
      // 获取进度信息
      const progressText = await page.locator('.progress-info .stage').textContent().catch(() => '');
      const percentage = await page.locator('.progress-fill').getAttribute('style').catch(() => '');
      console.log(`进度: ${progressText} ${percentage}`);
      
      await delay(2000);
    }

    // 截图：生成完成后
    await page.screenshot({ path: 'test-results/03-generation-complete.png', fullPage: true });

    // 6. 检查生成的结果
    console.log('6. 检查生成的结果');
    
    // 检查是否有错误信息
    const errorMessage = await page.locator('.error-message').isVisible().catch(() => false);
    if (errorMessage) {
      const errorText = await page.locator('.error-message span').textContent();
      console.error(`发现错误: ${errorText}`);
      await page.screenshot({ path: 'test-results/04-error.png', fullPage: true });
      throw new Error(`生成失败: ${errorText}`);
    }

    // 检查是否生成了卡片
    const cards = await page.locator('.cards-container .board-card, [class*="board-card"]').all();
    console.log(`生成了 ${cards.length} 张色盘`);
    
    if (cards.length === 0) {
      console.error('没有生成任何色盘卡片');
      await page.screenshot({ path: 'test-results/04-no-cards.png', fullPage: true });
      
      // 输出所有收集到的日志
      console.log('\n=== 所有控制台日志 ===');
      logs.forEach(log => {
        console.log(`[${log.type}] ${log.text}`);
      });
      
      throw new Error('没有生成任何色盘');
    }

    // 7. 点击第一张卡片查看详情
    console.log('7. 点击第一张卡片查看详情');
    await cards[0].click();
    await delay(1000);
    await page.screenshot({ path: 'test-results/05-card-selected.png', fullPage: true });

    // 8. 检查预览区域
    console.log('8. 检查预览区域');
    const preview = await page.locator('.grid-wrapper').isVisible().catch(() => false);
    const emptyPreview = await page.locator('.empty-preview').isVisible().catch(() => false);
    
    if (preview) {
      console.log('预览区域已显示');
    } else if (emptyPreview) {
      console.log('预览区域为空');
    }

    // 9. 检查是否有Python错误
    console.log('9. 检查Python错误');
    const pythonErrors = logs.filter(log => 
      log.text.includes('Python错误') || 
      log.text.includes('KeyError') ||
      log.text.includes('Traceback') ||
      log.text.includes('预览生成失败')
    );
    
    if (pythonErrors.length > 0) {
      console.error('发现Python错误:');
      pythonErrors.forEach(err => console.error(`[${err.type}] ${err.text}`));
      throw new Error('测试过程中发现Python错误');
    }

    console.log('测试完成！');
    
    // 最终截图
    await page.screenshot({ path: 'test-results/06-final.png', fullPage: true });
    
    // 输出所有日志供分析
    console.log('\n=== 完整控制台日志 ===');
    logs.forEach(log => {
      console.log(`[${log.type}] ${log.text}`);
    });
  });
});
