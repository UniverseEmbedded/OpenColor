const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// 获取Tauri应用路径（优先使用 debug 版本）
function getTauriBinaryPath() {
  const debugPath = path.join(__dirname, '..', 'src-tauri', 'target', 'debug', 'app.exe');
  const releasePath = path.join(__dirname, '..', 'src-tauri', 'target', 'release', 'app.exe');
  
  if (fs.existsSync(debugPath)) {
    console.log('使用 debug 版本:', debugPath);
    return debugPath;
  }
  
  if (fs.existsSync(releasePath)) {
    console.log('使用 release 版本:', releasePath);
    return releasePath;
  }
  
  throw new Error('找不到 Tauri 应用');
}

// 等待函数
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function runTest() {
  console.log('=== Tauri E2E 测试 ===');
  
  // 启动前端开发服务器
  console.log('\n[1/5] 启动前端开发服务器...');
  const devServer = spawn('pnpm', ['dev'], {
    cwd: path.join(__dirname, '..'),
    detached: false
  });
  
  // 等待服务器启动
  await delay(10000);
  
  // 启动 Tauri 应用
  console.log('[2/5] 启动 Tauri 应用...');
  const tauriPath = getTauriBinaryPath();
  const tauriApp = spawn(tauriPath, [], {
    detached: false
  });
  
  // 等待 Tauri 应用启动
  await delay(8000);
  
  let browser;
  try {
    // 连接到 Tauri 的 WebView
    console.log('[3/5] 连接到 Tauri WebView...');
    
    // 尝试通过 CDP 连接
    browser = await chromium.connectOverCDP('http://localhost:9222').catch(async () => {
      console.log('CDP 连接失败，尝试直接启动浏览器...');
      return await chromium.launch({
        headless: false,
        args: ['--window-size=1280,720']
      });
    });
    
    const context = await browser.newContext({
      viewport: { width: 1280, height: 720 }
    });
    
    const page = await context.newPage();
    
    // 监听控制台日志
    page.on('console', msg => {
      console.log(`[${msg.type()}] ${msg.text()}`);
    });
    
    // 导航到页面
    console.log('[4/5] 导航到校准色盘生成页面...');
    await page.goto('http://localhost:5173/calibrate/board-gen');
    await page.waitForLoadState('networkidle');
    await delay(3000);
    
    // 截图
    await page.screenshot({ path: 'test-results/tauri-js-01-page.png' });
    console.log('已截图: test-results/tauri-js-01-page.png');
    
    // 等待配置文件加载
    console.log('等待配置文件加载...');
    const profileSelect = page.locator('select#profile');
    await profileSelect.waitFor({ state: 'visible', timeout: 15000 });
    
    // 获取可用的配置文件
    const options = await profileSelect.locator('option').all();
    console.log(`找到 ${options.length} 个配置文件`);
    
    for (let i = 0; i < options.length; i++) {
      const text = await options[i].textContent();
      console.log(`  配置文件 ${i}: ${text}`);
    }
    
    if (options.length <= 1) {
      throw new Error('没有可用的配置文件');
    }
    
    // 选择第一个可用配置
    await profileSelect.selectOption({ index: 1 });
    console.log('选择了第一个可用配置文件');
    await delay(1500);
    
    // 设置生成数量为1
    console.log('设置生成数量为1...');
    const numBoardsInput = page.locator('input#numBoards');
    await numBoardsInput.fill('1');
    await delay(500);
    
    // 点击生成按钮
    console.log('点击生成按钮...');
    const generateBtn = page.locator('button.generate-btn');
    await generateBtn.click();
    
    // 等待生成完成
    console.log('等待生成完成（最多5分钟）...');
    const startTime = Date.now();
    const maxWaitTime = 5 * 60 * 1000;
    
    while (Date.now() - startTime < maxWaitTime) {
      const isGenerating = await generateBtn.locator('text=生成中').isVisible().catch(() => false);
      const hasProgress = await page.locator('.progress-detail').isVisible().catch(() => false);
      
      if (!isGenerating && !hasProgress) {
        console.log('生成完成');
        break;
      }
      
      const progressText = await page.locator('.progress-info .stage').textContent().catch(() => '');
      console.log(`进度: ${progressText}`);
      
      await delay(3000);
    }
    
    // 截图结果
    await page.screenshot({ path: 'test-results/tauri-js-02-result.png', fullPage: true });
    console.log('已截图: test-results/tauri-js-02-result.png');
    
    // 检查生成的卡片
    const cards = await page.locator('.cards-container .board-card, [class*="board-card"]').all();
    console.log(`\n生成了 ${cards.length} 张色盘`);
    
    if (cards.length === 0) {
      throw new Error('没有生成任何色盘');
    }
    
    console.log('\n[5/5] 测试完成！');
    
  } catch (error) {
    console.error('\n测试失败:', error.message);
    process.exitCode = 1;
  } finally {
    // 清理
    console.log('\n清理进程...');
    if (browser) {
      await browser.close();
    }
    tauriApp.kill();
    devServer.kill();
    console.log('清理完成');
  }
}

runTest();
