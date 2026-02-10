# OpenColor Web 界面

这是 OpenColor 的 Web 前端项目，基于 Vue 3 + Vite 开发，并支持通过 Tauri 打包为桌面应用。

## 开发环境准备

项目推荐使用 [pixi](https://pixi.sh/) 来管理依赖和运行命令。pixi 会自动处理 Node.js、pnpm 以及相关的 Python 环境。

### 1. 安装依赖

在项目根目录下运行：

```bash
pixi run web-install
```

## 常用开发命令

所有的开发命令都建议在**项目根目录**下通过 `pixi` 执行：

- **启动开发服务器**:
  ```bash
  pixi run web-dev
  ```
- **构建静态网页**:
  ```bash
  pixi run web-build
  ```
## Tauri 桌面应用打包

项目集成了 Tauri v2，可以将 Web 界面打包为独立的桌面可执行文件（.exe）。

### 1. 启动 Tauri 开发模式
这将启动一个窗口化应用，支持热更新：
```bash
pixi run web-tauri-dev
```

### 2. 打包生成可执行文件
运行以下命令进行正式打包：
```bash
pixi run web-tauri-build
```

打包完成后，生成的安装包位于：
`web/src-tauri/target/release/bundle/nsis/` 目录下。

> **注意**: 配置文件已设置为支持 NSIS 安装程序，包含中文和英文语言支持，可自定义安装路径。

## 技术栈

- **前端框架**: Vue 3 (Composition API)
- **构建工具**: Vite
- **国际化**: vue-i18n
- **图标库**: Tabler Icons (Webfont 模式)
- **桌面壳子**: Tauri v2
