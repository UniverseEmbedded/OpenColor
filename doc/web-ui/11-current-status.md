# 当前任务状态

本文档记录 OpenColor WebUI 项目的当前状态。

## 任务概述

**项目名称：** OpenColor WebUI  
**当前阶段：** 设计阶段已完成，准备进入开发阶段  
**目标：** 基于 Svelte 5 + Tauri 2 构建全新的 WebUI，适配 Python 原型管线

---

## 已完成的设计文档

### 核心设计文档（10个）

| 序号 | 文件 | 内容说明 |
|------|------|----------|
| 01 | `01-navigation.md` | 一级/二级导航结构设计 |
| 02 | `02-workspace.md` | 多工作区设计，目录结构 |
| 03 | `03-settings.md` | APP设置与项目设置区分 |
| 04 | `04-data-structures.md` | 所有数据结构定义（中英双语） |
| 05 | `05-layout.md` | 大窗口/小窗口响应式布局 |
| 06 | `06-data-sizes.md` | 文件大小估算与传输策略 |
| 07 | `07-api.md` | Web ↔ Rust API 完整定义 |
| 08 | `08-file-structure.md` | 项目文件结构规划 |
| 09 | `09-error-handling.md` | 错误处理策略与恢复机制 |
| 10 | `10-development-roadmap.md` | 5个Checkpoint开发路线图 |

### 交互演示文件（4个）

| 文件 | 内容 | 状态 |
|------|------|------|
| `mock-ui.html` | 照片校正页面布局演示 | 完成 |
| `log-panel-demo.html` | 日志面板演示（含虚拟滚动） | 完成 |
| `json-blueprint-demo.html` | JSON蓝图展示演示 | 完成 |
| `warp-canvas-demo.html` | 色盘变换Canvas演示 | 完成 |

---

## 项目代码结构

### 前端项目
```
web/                          # Svelte 5 + Tauri 2 项目
├── src/
│   ├── lib/                  # 库代码（待实现）
│   │   ├── api/              # API层
│   │   ├── components/       # 组件库
│   │   ├── stores/           # 状态管理
│   │   ├── i18n/             # 国际化
│   │   ├── utils/            # 工具函数
│   │   └── types/            # TypeScript类型
│   ├── routes/               # 页面路由（待实现）
│   ├── assets/               # 静态资源
│   └── app.html              # HTML模板
├── src-tauri/                # Rust后端（待实现）
└── ...                       # 配置文件
```

### Python原型管线
```
py_module/prototypes/         # 已存在的Python管线
├── src/oc_proto/
│   ├── calib_board_gen/      # 环节1：校准板生成
│   ├── calib_photo_warp/     # 环节2：照片校正
│   ├── calib_sample_build/   # 环节3：样本提取
│   ├── calib_color_rts/      # 环节4：模型训练
│   ├── gen_masks/            # 环节5：叠色像素生成
│   ├── gen_vector/           # 环节6：矢量化
│   └── gen_3mf/              # 环节7：模型导出
```

### 参考项目
```
project_ref/OpenColor-private-mainB-20/   # 旧版Vue UI（参考用）
├── web/                                    # Vue 3 + TypeScript
├── tutorials/                              # 教程文档
└── wiki/                                   # Wiki文档
```

---

## 技术栈

### 前端
- **框架：** Svelte 5
- **语言：** TypeScript
- **构建工具：** Vite
- **路由：** SvelteKit 文件系统路由
- **状态管理：** Svelte 5 Runes ($state, $derived)
- **样式：** CSS 变量 + 原生 CSS

### 后端
- **框架：** Tauri 2
- **语言：** Rust
- **进程通信：** Tauri Invoke / Event
- **Python绑定：** PyO3

### 设计参考
- **字体：** Maple Mono Normal NF CN
- **配色：** 深色主题（#0b0d10, #11151b, #1a1f28）
- **强调色：** #005984（蓝）, #fb6104（橙）

---

## 相关链接

- **设计文档目录：** `doc/web-ui/`
- **演示文件：** `doc/web-ui/*.html`
- **前端项目：** `web/`
- **Python原型：** `py_module/prototypes/`
- **旧版参考：** `project_ref/OpenColor-private-mainB-20/`
