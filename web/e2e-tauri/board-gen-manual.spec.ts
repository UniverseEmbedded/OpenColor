import { test, expect, chromium } from '@playwright/test';
import { spawn, exec } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { promisify } from 'util';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);

// 获取当前文件的目录路径（ES模块兼容）
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 等待指定时间
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// 获取Tauri应用路径（优先使用 debug 版本）
function getTauriBinaryPath(): string {
  const debugPath = path.join(__dirname, '..', 'src-tauri', 'target', 'debug', 'app.exe');
  const releasePath = path.join(__dirname, '..', 'src-tauri', 'target', 'release', 'app.exe');
  
  // 优先使用 debug 版本（dev 模式）
  if (fs.existsSync(debugPath)) {
    console.log('使用 debug 版本:', debugPath);
    return debugPath;
  }
  
  // 否则使用 release 版本
  if (fs.existsSync(releasePath)) {
    console.log('使用 release 版本:', releasePath);
    return releasePath;
  }
  
  throw new Error('找不到 Tauri 应用，请先运行 pnpm tauri dev 或 pnpm tauri build');
}

// 检查Tauri应用是否已构建
function checkTauriBuild(): boolean {
  try {
    const binaryPath = getTauriBinaryPath();
    return fs.existsSync(binaryPath);
  } catch {
    return false;
  }
}

test.describe('校准色盘生成测试 - Tauri手动启动模式', () => {
  let tauriProcess: any;
  let browser: any;
  let context: any;

  test.beforeAll(async () => {
    // 检查Tauri应用是否已构建
    if (!checkTauriBuild()) {
      throw new Error('Tauri应用未构建，请先运行: pnpm tauri build');
    }
    console.log('Tauri应用已就绪:', getTauriBinaryPath());
  });

  test.beforeEach(async () => {
    // 启动前端开发服务器
    console.log('启动前端开发服务器...');
    const devServer = spawn('pnpm', ['dev'], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, FORCE_COLOR: '0' },
      detached: false
    });

    // 等待服务器启动
    console.log('等待前端服务器启动...');
    await delay(10000);

    // 启动Tauri应用
    const binaryPath = getTauriBinaryPath();
    console.log(`启动Tauri应用: ${binaryPath}`);
    
    tauriProcess = spawn(binaryPath, [], {
      env: { ...process.env },
      detached: false
    });

    // 等待Tauri应用启动
    console.log('等待Tauri应用启动...');
    await delay(8000);

    // 使用 Playwright 连接到 Tauri 的 WebView
    console.log('连接到Tauri应用...');
    browser = await chromium.connectOverCDP('http://localhost:9222').catch(async () => {
      // 如果 CDP 连接失败，尝试直接启动浏览器
      console.log('CDP连接失败，尝试直接启动...');
      return await chromium.launch({
        headless: false,
        args: ['--window-size=1280,720']
      });
    });

    context = await browser.newContext({
      viewport: { width: 1280, height: 720 }
    });
  });

  test.afterEach(async () => {
    // 关闭浏览器
    if (context) {
      await context.close();
    }
    if (browser) {
      await browser.close();
    }

    // 关闭Tauri应用
    if (tauriProcess) {
      console.log('关闭Tauri应用...');
      tauriProcess.kill('SIGTERM');
      await delay(3000);
    }
  });

  test('生成1张8色校准色盘', async () => {
    console.log('开始测试：生成1张8色校准色盘 (Tauri手动启动模式)');

    fs.mkdirSync('test-results', { recursive: true });

    const page = await context.newPage();

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
    await page.goto('http://localhost:5173/calibrate/board-gen');
    await page.waitForLoadState('networkidle');
    await delay(3000);
    
    // 截图：页面加载后
    await page.screenshot({ path: 'test-results/tauri-manual-01-board-gen-page.png' });

    // 2. 等待配置文件加载
    console.log('2. 等待配置文件加载');
    const profileSelect = page.locator('select#profile');
    await profileSelect.waitFor({ state: 'visible', timeout: 15000 });
    
    // 等待选项加载
    await delay(2000);
    
    // 获取可用的配置文件
    const options = await profileSelect.locator('option').all();
    console.log(`找到 ${options.length} 个配置文件`);
    
    for (let i = 0; i < options.length; i++) {
      const text = await options[i].textContent();
      console.log(`  配置文件 ${i}: ${text}`);
    }
    
    if (options.length <= 1) {
      console.log('警告：没有可用的配置文件');
      await page.screenshot({ path: 'test-results/tauri-manual-02-no-profiles.png' });
      throw new Error('没有可用的配置文件');
    }

    // 选择一个8色的配置文件
    let selected8ColorProfile = false;
    for (let i = 0; i < options.length; i++) {
      const text = await options[i].textContent();
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
    
    await delay(1500);
    await page.screenshot({ path: 'test-results/tauri-manual-02-profile-selected.png' });

    // 3. 设置生成数量为1
    console.log('3. 设置生成数量为1');
    const numBoardsInput = page.locator('input#numBoards');
    await numBoardsInput.fill('1');
    await delay(800);

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
      
      await delay(3000);
    }

    // 截图：生成完成后
    await page.screenshot({ path: 'test-results/tauri-manual-03-generation-complete.png', fullPage: true });

    // 6. 检查生成的结果
    console.log('6. 检查生成的结果');
    
    // 检查是否有错误信息
    const errorMessage = await page.locator('.error-message').isVisible().catch(() => false);
    if (errorMessage) {
      const errorText = await page.locator('.error-message span').textContent();
      console.error(`发现错误: ${errorText}`);
      await page.screenshot({ path: 'test-results/tauri-manual-04-error.png', fullPage: true });
      throw new Error(`生成失败: ${errorText}`);
    }

    // 检查是否生成了卡片
    const cards = await page.locator('.cards-container .board-card, [class*="board-card"]').all();
    console.log(`生成了 ${cards.length} 张色盘`);
    
    if (cards.length === 0) {
      console.error('没有生成任何色盘卡片');
      await page.screenshot({ path: 'test-results/tauri-manual-04-no-cards.png', fullPage: true });
      
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
    await delay(1500);
    await page.screenshot({ path: 'test-results/tauri-manual-05-card-selected.png', fullPage: true });

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
      log.text.includes('预览生成失败') ||
      log.text.includes('mu_a')
    );
    
    if (pythonErrors.length > 0) {
      console.error('发现Python错误:');
      pythonErrors.forEach(err => console.error(`[${err.type}] ${err.text}`));
      throw new Error('测试过程中发现Python错误');
    }

    console.log('测试完成！');
    
    // 最终截图
    await page.screenshot({ path: 'test-results/tauri-manual-06-final.png', fullPage: true });
    
    // 输出所有日志供分析
    console.log('\n=== 完整控制台日志 ===');
    logs.forEach(log => {
      console.log(`[${log.type}] ${log.text}`);
    });
  });
});
