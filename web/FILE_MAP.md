# OpenColor Web 前端文件映射

本文档描述 OpenColor Web 前端项目的文件结构和各文件用途。

## 项目概述

OpenColor Web 是基于 Tauri + Vue 3 + TypeScript 的桌面应用前端，提供用户界面与 Python 引擎进行交互。

## 目录结构

```
web/
├── README.md              # 项目说明文档
├── FILE_MAP.md            # 本文件 - 文件映射说明
├── package.json           # Node.js 依赖配置
├── vite.config.ts         # Vite 构建配置
├── tsconfig.json          # TypeScript 配置
├── index.html             # 入口 HTML 文件
├── src/
│   ├── main.ts            # 应用入口
│   ├── App.vue            # 根组件
│   ├── env.d.ts           # 环境类型声明
│   ├── i18n.ts            # 国际化配置
│   ├── styles.css         # 全局样式
│   ├── engine_contract.ts # 引擎接口类型定义
│   ├── engine_contract.js # 引擎接口运行时定义
│   ├── assets/            # 静态资源
│   ├── components/        # Vue 组件
│   ├── composables/       # 组合式函数
│   ├── locales/           # 国际化语言包
│   └── styles/            # 样式文件
├── src-tauri/             # Tauri 后端（Rust）
│   ├── Cargo.toml         # Rust 依赖配置
│   ├── build.rs           # 构建脚本
│   ├── capabilities/      # 权限配置
│   ├── icons/             # 应用图标
│   └── src/
│       ├── main.rs        # 入口（调用 lib）
│       └── lib.rs         # 主逻辑（命令、引擎管理）
└── dist/                  # 构建输出（自动生成）
```

## 源文件详细说明

### 入口与配置

| 文件 | 说明 |
|------|------|
| [src/main.ts](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/main.ts) | 应用入口，初始化 Vue 应用、i18n、挂载根组件 |
| [src/App.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/App.vue) | 根组件，管理全局状态、侧边栏、主内容区、模态框 |
| [src/i18n.ts](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/i18n.ts) | 国际化配置，支持中英文切换 |
| [src/engine_contract.ts](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/engine_contract.ts) | 引擎接口类型定义，应与 py_module/engine 保持同步 |
| [src/styles.css](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/styles.css) | 全局样式入口，导入各样式模块 |

### 组件 (src/components/)

| 文件 | 说明 |
|------|------|
| [Sidebar.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/Sidebar.vue) | 侧边导航栏，视图切换、快捷操作 |
| [AppMain.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/AppMain.vue) | 主内容区容器，根据当前视图渲染不同内容 |
| [TopBar.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/TopBar.vue) | 顶部工具栏 |
| **视图组件** ||
| [GenerateView.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/GenerateView.vue) | 生成视图 - 位图/SVG 转 3D 模型 |
| [CalibrateView.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/CalibrateView.vue) | 校准视图 - 色盘校准、数据集管理 |
| [MaterialsView.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/MaterialsView.vue) | 材料视图 - 耗材配置管理 |
| [AlbumView.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/AlbumView.vue) | 相册视图 - 资源库浏览 |
| [SettingsView.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/SettingsView.vue) | 设置视图 - 应用配置 |
| **功能卡片** ||
| [GenerateInputCard.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/GenerateInputCard.vue) | 生成输入卡片 - 位图/SVG 输入配置 |
| [GenerateOutputCard.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/GenerateOutputCard.vue) | 生成输出卡片 - 输出格式、尺寸配置 |
| **模态框** ||
| [HelpModal.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/HelpModal.vue) | 帮助模态框 |
| [AboutModal.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/AboutModal.vue) | 关于模态框 |
| [Toast.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/Toast.vue) | 提示消息组件 |
| [ScreenCalibrator.vue](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/components/ScreenCalibrator.vue) | 屏幕校准组件 |

### 组合式函数 (src/composables/)

| 文件 | 说明 |
|------|------|
| [useAppState.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useAppState.js) | 应用状态管理（视图、输入、输出、位图、LUT 等） |
| [useAppChips.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useAppChips.js) | 顶部芯片状态（输入、配置、输出） |
| [usePreviewState.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/usePreviewState.js) | 预览状态管理（缩放、模式切换） |
| [useTauriBridge.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useTauriBridge.js) | Tauri API 桥接（invoke, listen, dialog 等） |
| [useEngineOps.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useEngineOps.js) | 引擎操作封装（ping, 生成, 校准等） |
| [useFileHandlers.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useFileHandlers.js) | 文件处理（选择、导入、保存） |
| [useLibrary.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useLibrary.js) | 资源库管理 |
| [useSettingsStore.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useSettingsStore.js) | 设置存储（本地持久化） |
| [useLocaleSetting.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useLocaleSetting.js) | 语言设置管理 |
| [useThemeSetting.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useThemeSetting.js) | 主题设置管理（亮色/暗色） |
| [useToast.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useToast.js) | Toast 提示管理 |
| [useCalibrate.js](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/composables/useCalibrate.js) | 校准相关逻辑 |

### 样式 (src/styles/)

| 文件 | 说明 |
|------|------|
| [variables.css](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/styles/variables.css) | CSS 变量定义（颜色、尺寸、动画） |
| [base.css](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/styles/base.css) | 基础样式重置、全局样式 |
| [components.css](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/styles/components.css) | 组件通用样式 |
| [layouts.css](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/styles/layouts.css) | 布局样式（网格、弹性布局） |

### 国际化 (src/locales/)

| 文件 | 说明 |
|------|------|
| [zh-CN.json](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/locales/zh-CN.json) | 简体中文语言包 |
| [en-US.json](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/locales/en-US.json) | 英文语言包 |

### 静态资源 (src/assets/)

| 路径 | 说明 |
|------|------|
| [icon.svg](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/assets/icon.svg) | 应用图标 |
| [loading.svg](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/assets/loading.svg) | 加载动画 |
| [MapleMonoNormal-NF-CN-Regular.woff2](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/assets/MapleMonoNormal-NF-CN-Regular.woff2) | Maple Mono 字体 |
| [docs/zh/](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/assets/docs/zh/) | 中文帮助文档 |
| [docs/en/](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src/assets/docs/en/) | 英文帮助文档 |

## Tauri 后端 (src-tauri/)

### Rust 源文件

| 文件 | 说明 |
|------|------|
| [src/main.rs](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src-tauri/src/main.rs) | 入口文件，调用 lib::run() |
| [src/lib.rs](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src-tauri/src/lib.rs) | 主逻辑，包含：命令处理、引擎管理、资源库管理 |

### 核心功能

**引擎管理 (EngineManager)**
- `start_engine()` - 启动 Python 引擎（PyO3）
- `restart_engine()` - 重启引擎
- `send_request()` - 向引擎发送 JSON-RPC 请求

**Tauri 命令**
- `engine_request` - 向 Python 引擎发送请求
- `engine_restart` - 重启引擎
- `cpp_probe` - 调用 C++ 探测程序
- `read_file_base64` - 读取文件并返回 Base64
- `save_settings` / `load_settings` - 设置持久化
- `init_library` / `get_library_index` / `list_album_files` / `import_to_library` - 资源库管理
- `open_path` - 在文件管理器中打开路径

### 配置文件

| 文件 | 说明 |
|------|------|
| [Cargo.toml](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src-tauri/Cargo.toml) | Rust 依赖配置 |
| [build.rs](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src-tauri/build.rs) | 构建脚本 |
| [capabilities/](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src-tauri/capabilities/) | Tauri 权限配置 |
| [icons/](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/src-tauri/icons/) | 应用图标（多尺寸） |

## 构建配置

### Vite 配置 ([vite.config.ts](file:///d:/pama1234/pfp/p-2026-01/OpenColor-05/web/vite.config.ts))
- 使用 `@vitejs/plugin-vue` 处理 Vue 单文件组件
- 集成 `rollup-plugin-visualizer` 进行包体积分析
- 开发服务器端口：5173

### TypeScript 配置 ([tsconfig.json](file:///d:/pama1234/pfp/p-2026-01/OpenColor-02/web/tsconfig.json))
- 目标：ES2020
- 模块：ESNext
- 严格模式启用
- 包含：src 目录下的 .ts, .d.ts, .tsx, .vue 文件

## 数据流

```
用户界面 (Vue Components)
    ↓
组合式函数 (Composables) - 状态管理
    ↓
Tauri Bridge - 调用 Rust 命令
    ↓
Rust 后端 (lib.rs) - 引擎管理
    ↓
Python 引擎 (PyO3) - 业务逻辑
    ↓
事件回调 - 进度/结果返回前端
```

## 开发命令

```bash
# 安装依赖
npm install

# 开发模式（Web）
npm run dev

# 开发模式（Tauri）
npm run tauri dev

# 构建
npm run tauri build
```

## 注意事项

1. **引擎接口同步**: `engine_contract.ts` 应与 `py_module/engine/src/oc_engine/schema.py` 保持同步
2. **资源库路径**: 默认在用户文档目录下创建 `OpenColor` 文件夹
3. **Python 路径**: 引擎自动查找项目根目录（包含 `py_module` 或 `pixi.toml` 的目录）
4. **C++ 探测**: 调试模式下从 `cpp_module/build/Release` 加载，发布模式从资源目录加载
