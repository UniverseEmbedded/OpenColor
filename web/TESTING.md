# OpenColor Web 测试架构

本文档说明 web 模块的测试架构，包括单元测试、Rust 后端测试和端到端测试。

## 测试类型概览

```
web/
├── test/                          # 单元测试目录
│   └── engine_contract.test.js    # 引擎契约测试
├── e2e/                           # ⚠️ 已弃用 - 浏览器模式 Playwright 测试
│   ├── example.spec.ts            # (已弃用)
│   └── tauri.spec.ts              # (已弃用)
├── e2e-tauri/                     # Tauri 原生模式 E2E 测试（推荐）
│   └── tauri.spec.ts              # Tauri API 测试
├── src-tauri/src/
│   └── lib.rs                     # Rust 后端代码（包含单元测试）
├── scripts/
│   ├── test-with-timeout.js       # 自动化测试脚本（Node.js）
│   └── test-with-timeout.ps1      # 自动化测试脚本（PowerShell）
├── playwright.config.ts           # ⚠️ 已弃用 - 浏览器模式配置
├── playwright.config.tauri.ts     # Tauri 原生模式配置（推荐）
└── vite.config.ts                 # Vitest 配置
```

## 重要说明：浏览器模式已弃用

由于 OpenColor 项目重度依赖 Tauri 原生 API（文件系统、对话框、后端命令等），**浏览器模式无法提供有效的测试环境**。因此：

- ❌ `playwright.config.ts` (浏览器模式) - **已弃用**
- ❌ `e2e/` 目录下的测试 - **已弃用**
- ✅ `playwright.config.tauri.ts` (Tauri 原生模式) - **推荐使用**
- ✅ `e2e-tauri/` 目录下的测试 - **推荐使用**

## 1. 单元测试 (Vitest)

**位置**: `test/` 目录和 `src/**/*.test.{js,ts}`

**运行命令**:
```bash
# 运行所有单元测试
pnpm test:unit

# 监视模式
pnpm test:unit:watch
```

**特点**:
- 使用 Vitest 测试框架
- jsdom 环境模拟浏览器
- 测试纯 JavaScript/TypeScript 逻辑
- 不依赖 Tauri 运行时

## 2. Rust 后端测试

**位置**: `src-tauri/src/lib.rs` (模块内的 `#[cfg(test)]` 部分)

**运行命令**:
```bash
# 运行 Rust 测试
pnpm test:rust

# 详细输出
pnpm test:rust:verbose
```

**特点**:
- 使用 Rust 标准测试框架
- 测试后端逻辑：文件解析、MIME 类型猜测、数据序列化等
- 纯 Rust 代码测试，不依赖前端

## 3. 端到端测试 (E2E)

### 3.1 Tauri 原生模式 (推荐)

**配置**: `playwright.config.tauri.ts`

**运行命令**:
```bash
# 需要先生成构建
pnpm tauri build

# 运行 Tauri 原生 E2E 测试
pnpm test:e2e:tauri

# 一键构建并测试
pnpm test:e2e:tauri:build
```

**前置要求**:
```bash
# 安装 tauri-driver
cargo install tauri-driver
```

**特点**:
- 在真实的 Tauri 应用中运行测试
- 可以访问 `window.__TAURI__` 对象
- 可以测试文件系统、对话框等原生 API
- 可以调用 Rust 后端命令

### 3.2 浏览器模式 (已弃用)

⚠️ **此模式已弃用，无法有效测试 Tauri 应用**

浏览器模式的问题：
- `window.__TAURI__` 对象不存在
- 无法测试文件系统操作
- 无法测试原生对话框
- 无法调用 Rust 后端命令

如果你运行以下命令，会收到弃用提示：
```bash
pnpm test:e2e          # ⚠️ 已弃用提示
pnpm test:e2e:ui       # ⚠️ 已弃用提示
pnpm test:e2e:debug    # ⚠️ 已弃用提示
```

## 4. 自动化测试脚本

### Node.js 版本（跨平台）

```bash
# 运行所有测试（带超时控制）
pnpm test:all

# 选项
node scripts/test-with-timeout.js --timeout 20          # 设置超时 20 分钟
node scripts/test-with-timeout.js --skip-rust           # 跳过 Rust 测试
node scripts/test-with-timeout.js --skip-unit           # 跳过单元测试
node scripts/test-with-timeout.js --verbose             # 详细输出

# CI 模式
pnpm test:ci
```

### PowerShell 版本（Windows）

```powershell
# 运行所有测试
pnpm test:all:ps

# 或使用参数
powershell -File scripts/test-with-timeout.ps1 -TimeoutMinutes 20 -SkipRust
```

## 5. Pixi 任务

```bash
# 单元测试
pixi run web-test-unit

# Rust 测试
pixi run web-test-rust

# 所有测试（带超时）
pixi run web-test-all

# Tauri 原生 E2E 测试（需先构建）
pixi run web-test-tauri

# 安装 Playwright 浏览器
pixi run web-playwright-install
```

## 6. 测试超时配置

### 全局超时
- 自动化脚本: 10 分钟（可配置）

### 单项超时
- 单元测试: 5 秒
- Rust 测试: 5 分钟
- E2E Tauri 原生: 60 秒（应用启动较慢）

## 7. 推荐的工作流程

### 开发阶段
```bash
# 1. 运行单元测试（快速反馈）
pnpm test:unit

# 2. 运行 Rust 测试
pnpm test:rust

# 3. 启动开发服务器进行手动测试
pnpm tauri dev
```

### 提交前
```bash
# 运行所有单元测试和 Rust 测试
pnpm test:all

# 或 CI 模式
pnpm test:ci
```

### 发布前
```bash
# 1. 构建应用
pnpm tauri build

# 2. 运行 Tauri 原生 E2E 测试
pnpm test:e2e:tauri

# 3. 运行所有测试
pnpm test:all
```

## 8. 注意事项

1. **Tauri 原生模式要求**:
   - 必须先构建应用 (`pnpm tauri build`)
   - 需要安装 `tauri-driver` (`cargo install tauri-driver`)
   - 测试运行时间较长（需要启动应用）

2. **CI/CD 环境**:
   - 使用 `pnpm test:ci` 运行单元测试和 Rust 测试
   - Tauri 原生 E2E 测试需要在有图形界面的环境运行
   - 或使用 headless 模式: `pnpm test:e2e:tauri -- --headless`

3. **测试数据**:
   - E2E 测试使用真实应用数据
   - 注意测试可能修改文件系统（在临时目录中进行）

4. **并行执行**:
   - 单元测试和 Rust 测试可以并行
   - Tauri 原生 E2E 测试必须串行（应用只能运行一个实例）
