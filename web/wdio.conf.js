import path from 'path';
import os from 'os';
import fs from 'fs';
import { spawn, spawnSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function getTauriBinaryPath() {
  const debugPath = path.join(__dirname, 'src-tauri', 'target', 'debug', 'app.exe');
  const releasePath = path.join(__dirname, 'src-tauri', 'target', 'release', 'app.exe');

  if (fs.existsSync(debugPath)) {
    console.log(`[WDIO] 使用调试构建: ${debugPath}`);
    return debugPath;
  }
  if (fs.existsSync(releasePath)) {
    console.log(`[WDIO] 使用发布构建: ${releasePath}`);
    return releasePath;
  }
  throw new Error('找不到 Tauri 应用二进制文件。请先运行: pnpm tauri build --debug --no-bundle');
}

function tauriBinaryExists() {
  try {
    getTauriBinaryPath();
    return true;
  } catch {
    return false;
  }
}

let tauriDriver;
let exit = false;

function closeTauriDriver() {
  exit = true;
  tauriDriver?.kill();
}

function onShutdown(fn) {
  const cleanup = () => {
    try {
      fn();
    } finally {
      process.exit();
    }
  };

  process.on('exit', cleanup);
  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
  process.on('SIGHUP', cleanup);
  process.on('SIGBREAK', cleanup);
}

export const config = {
  host: '127.0.0.1',
  port: 4444,
  baseUrl: 'tauri://localhost',
  specs: ['./e2e-tauri-wdio/**/*.e2e.js'],
  maxInstances: 1,
  logLevel: 'error',
  capabilities: [
    {
      maxInstances: 1,
      'tauri:options': {
        application: getTauriBinaryPath(),
      },
    },
  ],
  reporters: ['spec'],
  framework: 'mocha',
  mochaOpts: {
    ui: 'bdd',
    timeout: 5 * 60 * 1000,
  },
  onPrepare: () => {
    if (tauriBinaryExists()) return;
    console.log('[WDIO] 未找到二进制文件，正在启动调试构建...');
    const result = spawnSync('pnpm', ['tauri', 'build', '--debug', '--no-bundle'], {
      cwd: __dirname,
      stdio: 'inherit',
      shell: true,
      env: { ...process.env, FORCE_COLOR: '0' },
    });
    if (result.status !== 0) {
      process.exit(result.status ?? 1);
    }
  },
  beforeSession: async () => {
    const { download } = await import('edgedriver');
    const msEdgeDriverPath = await download();

    const tauriDriverBinary = process.platform === 'win32'
      ? path.join(os.homedir(), '.cargo', 'bin', 'tauri-driver.exe')
      : path.join(os.homedir(), '.cargo', 'bin', 'tauri-driver');

    const resolvedTauriDriverBinary = fs.existsSync(tauriDriverBinary) ? tauriDriverBinary : 'tauri-driver';

    const logFile = path.join(__dirname, 'tauri-driver.log');
    const out = fs.openSync(logFile, 'w');
    tauriDriver = spawn(
      resolvedTauriDriverBinary,
      ['--port', '4444', '--native-driver', msEdgeDriverPath],
      {
        stdio: [null, out, 'inherit'],
        env: { ...process.env, FORCE_COLOR: '0' },
      },
    );

    await new Promise(resolve => setTimeout(resolve, 2000));

    tauriDriver.on('exit', (code) => {
      if (!exit) {
        console.error('tauri-driver 异常退出，退出码:', code);
        process.exit(code ?? 1);
      }
    });
  },
  afterSession: () => {
    closeTauriDriver();
  },
};

onShutdown(() => {
  closeTauriDriver();
});
