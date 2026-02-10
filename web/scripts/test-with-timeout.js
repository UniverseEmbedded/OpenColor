#!/usr/bin/env node
/**
 * 自动化测试脚本 - 带超时控制 (Node.js 版本)
 * 支持 Windows/Linux/Mac
 */

const { spawn } = require('child_process');
const path = require('path');

// 解析命令行参数
const args = process.argv.slice(2);
const options = {
  timeoutMinutes: 10,
  skipRust: args.includes('--skip-rust'),
  skipUnit: args.includes('--skip-unit'),
  verbose: args.includes('--verbose') || args.includes('-v'),
};

// 解析超时参数
const timeoutIndex = args.findIndex(arg => arg === '--timeout' || arg === '-t');
if (timeoutIndex !== -1 && args[timeoutIndex + 1]) {
  options.timeoutMinutes = parseInt(args[timeoutIndex + 1], 10) || 15;
}

const startTime = Date.now();
const timeoutMs = options.timeoutMinutes * 60 * 1000;

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
};

function logHeader(message) {
  console.log(`\n${colors.cyan}========================================${colors.reset}`);
  console.log(`${colors.cyan}  ${message}${colors.reset}`);
  console.log(`${colors.cyan}========================================\n${colors.reset}`);
}

function logSuccess(message) {
  console.log(`${colors.green}✓ ${message}${colors.reset}`);
}

function logError(message) {
  console.log(`${colors.red}✗ ${message}${colors.reset}`);
}

function logWarning(message) {
  console.log(`${colors.yellow}⚠ ${message}${colors.reset}`);
}

function checkTimeout() {
  const elapsed = Date.now() - startTime;
  if (elapsed > timeoutMs) {
    logError(`测试超时！已运行 ${(elapsed / 60000).toFixed(1)} 分钟`);
    process.exit(1);
  }
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const cmdTimeout = (options.timeoutMinutes || 10) * 60 * 1000;
    const cmdStart = Date.now();
    
    const isWindows = process.platform === 'win32';
    const shell = isWindows ? true : false;
    
    const child = spawn(command, args, {
      cwd: options.cwd || process.cwd(),
      shell,
      stdio: options.verbose ? 'inherit' : 'pipe',
    });

    let stdout = '';
    let stderr = '';

    if (!options.verbose) {
      child.stdout?.on('data', (data) => {
        stdout += data.toString();
      });
      
      child.stderr?.on('data', (data) => {
        stderr += data.toString();
      });
    }

    const timeoutCheck = setInterval(() => {
      checkTimeout();
      
      const cmdElapsed = Date.now() - cmdStart;
      if (cmdElapsed > cmdTimeout) {
        clearInterval(timeoutCheck);
        child.kill('SIGTERM');
        
        // 等待进程退出
        setTimeout(() => {
          if (!child.killed) {
            child.kill('SIGKILL');
          }
        }, 5000);
        
        resolve({
          success: false,
          exitCode: -1,
          output: stdout,
          error: stderr + '\n命令执行超时！',
        });
      }
    }, 1000);

    child.on('close', (code) => {
      clearInterval(timeoutCheck);
      resolve({
        success: code === 0,
        exitCode: code,
        output: stdout,
        error: stderr,
      });
    });

    child.on('error', (err) => {
      clearInterval(timeoutCheck);
      resolve({
        success: false,
        exitCode: -1,
        output: stdout,
        error: stderr + '\n' + err.message,
      });
    });
  });
}

async function main() {
  logHeader('OpenColor Web 自动化测试');
  console.log(`超时设置: ${options.timeoutMinutes} 分钟`);
  console.log(`开始时间: ${new Date().toLocaleString()}`);
  console.log(`平台: ${process.platform}`);
  console.log('');

  const results = {
    unit: null,
    rust: null,
  };

  // 单元测试
  if (!options.skipUnit) {
    logHeader('运行单元测试 (Vitest)');
    checkTimeout();
    
    results.unit = await runCommand('pnpm', ['run', 'test:unit'], {
      timeoutMinutes: 5,
      verbose: options.verbose,
    });
    
    if (results.unit.success) {
      logSuccess('单元测试通过');
    } else {
      logError('单元测试失败');
      if (results.unit.error && !options.verbose) {
        console.log(results.unit.error);
      }
    }
  } else {
    logWarning('跳过单元测试');
  }

  // Rust 测试
  if (!options.skipRust) {
    logHeader('运行 Rust 后端测试');
    checkTimeout();
    
    results.rust = await runCommand('cargo', ['test'], {
      cwd: path.join(process.cwd(), 'src-tauri'),
      timeoutMinutes: 5,
      verbose: options.verbose,
    });
    
    if (results.rust.success) {
      logSuccess('Rust 测试通过');
    } else {
      logError('Rust 测试失败');
      if (results.rust.error && !options.verbose) {
        console.log(results.rust.error);
      }
    }
  } else {
    logWarning('跳过 Rust 测试');
  }



  // 汇总结果
  logHeader('测试结果汇总');
  
  const endTime = Date.now();
  const totalDuration = endTime - startTime;
  const durationStr = new Date(totalDuration).toISOString().substr(11, 8);

  let allPassed = true;

  if (!options.skipUnit) {
    const status = results.unit?.success ? '通过 ✓' : '失败 ✗';
    const color = results.unit?.success ? colors.green : colors.red;
    console.log(`${color}单元测试: ${status}${colors.reset}`);
    allPassed = allPassed && results.unit?.success;
  }

  if (!options.skipRust) {
    const status = results.rust?.success ? '通过 ✓' : '失败 ✗';
    const color = results.rust?.success ? colors.green : colors.red;
    console.log(`${color}Rust 测试: ${status}${colors.reset}`);
    allPassed = allPassed && results.rust?.success;
  }

  console.log('');
  console.log(`总耗时: ${durationStr}`);

  if (allPassed) {
    logSuccess('所有测试通过！');
    process.exit(0);
  } else {
    logError('部分测试失败');
    process.exit(1);
  }
}

main().catch(err => {
  logError(`测试脚本出错: ${err.message}`);
  process.exit(1);
});
