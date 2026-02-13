# 文件结构规划

本文档定义 OpenColor WebUI 的完整文件结构规划。

## 目录结构概览

```
web/src/
├── lib/                        # 库代码
│   ├── api/                    # API 层
│   ├── components/             # 共享组件
│   ├── stores/                 # 状态管理
│   ├── i18n/                   # 国际化
│   ├── utils/                  # 工具函数
│   └── types/                  # TypeScript 类型
├── routes/                     # 页面路由
├── assets/                     # 静态资源
└── app.html                    # HTML 模板
```

---

## lib/api/ - API 层

```
lib/api/
├── index.ts                    # API 统一导出
├── workspace.ts                # 工作区管理 API
├── file.ts                     # 文件操作 API
├── board-gen.ts                # 校准板生成 API
├── photo-warp.ts               # 照片校正 API
├── sample-extract.ts           # 样本提取 API
├── model-train.ts              # 模型训练 API
├── mask-gen.ts                 # 叠色像素生成 API
├── vectorize.ts                # 矢量化 API
├── export.ts                   # 模型导出 API
└── library.ts                  # 素材库 API
```

**设计原则：**
- 每个功能模块独立文件
- 统一错误处理
- 异步任务返回 jobId
- 大文件只传路径

---

## lib/components/ - 共享组件

### lib/components/layout/ - 布局组件

```
lib/components/layout/
├── Sidebar.svelte              # 侧边栏（一级/二级导航）
├── Header.svelte               # 页面标题栏
├── LogPanel.svelte             # 日志面板
└── WorkspaceSelector.svelte    # 工作区选择器
```

### lib/components/ui/ - 基础 UI 组件

```
lib/components/ui/
├── Button.svelte               # 按钮
├── Input.svelte                # 文本输入
├── NumberInput.svelte          # 数字输入
├── Select.svelte               # 下拉选择
├── Toggle.svelte               # 开关
├── ColorPicker.svelte          # 颜色选择
├── FilePicker.svelte           # 文件选择
└── ProgressBar.svelte          # 进度条
```

### lib/components/json/ - JSON 蓝图组件

```
lib/components/json/
├── BlueprintRenderer.svelte    # 蓝图渲染器
├── StringField.svelte          # 字符串字段
├── NumberField.svelte          # 数字字段
├── BooleanField.svelte         # 布尔字段
├── ColorField.svelte           # 颜色字段
├── ObjectField.svelte          # 对象字段
├── ArrayField.svelte           # 数组字段
└── GridField.svelte            # 网格字段
```

### lib/components/canvas/ - Canvas 组件

```
lib/components/canvas/
├── WarpCanvas.svelte           # 透视校正画布
├── SampleGrid.svelte           # 样本网格画布
├── ImagePreview.svelte         # 图像预览画布
└── MaskOverlay.svelte          # 掩码叠加画布
```

---

## lib/stores/ - 状态管理

```
lib/stores/
├── app.svelte.ts               # APP 设置状态
├── workspace.svelte.ts         # 工作区状态
├── project.svelte.ts           # 项目设置状态
├── logs.svelte.ts              # 日志状态
└── jobs.svelte.ts              # 异步任务状态
```

**状态设计：**
- 使用 Svelte 5 Runes（$state, $derived）
- 跨组件共享通过 props 或 context
- 持久化状态自动同步

---

## lib/i18n/ - 国际化

```
lib/i18n/
├── index.ts                    # i18n 入口
├── zh-CN.json                  # 中文翻译
└── en-US.json                  # 英文翻译
```

---

## lib/utils/ - 工具函数

```
lib/utils/
├── format.ts                   # 格式化（时间、数字）
├── color.ts                    # 颜色处理（RGB转换）
├── file.ts                     # 文件处理
└── validate.ts                 # 数据验证
```

---

## lib/types/ - TypeScript 类型

```
lib/types/
├── index.ts                    # 类型统一导出
├── api.ts                      # API 相关类型
└── data.ts                     # 数据结构类型
```

---

## routes/ - 页面路由

### 根路由

```
routes/
├── +layout.svelte              # 根布局
└── +page.svelte                # 首页（流程图）
```

### 校准标签页

```
routes/calibrate/
├── +layout.svelte              # 校准标签页布局
├── board-gen/
│   └── +page.svelte            # 校准板生成页面
├── photo-warp/
│   ├── +page.svelte            # 照片校正与样本提取页面（容器）
│   ├── WarpCanvas.svelte       # 校正画布
│   ├── SampleGrid.svelte       # 样本网格
│   ├── WarpControls.svelte     # 校正控制面板
│   └── SampleControls.svelte   # 样本控制面板
└── model-train/
│   ├── +page.svelte            # 模型训练页面（容器）
│   ├── ConfigForm.svelte       # 配置表单
│   ├── ProgressPanel.svelte    # 进度面板
│   ├── LossChart.svelte        # 损失曲线
│   └── EvalResults.svelte      # 评估结果
```

**拆分原因：**
- `photo-warp/+page.svelte` 预估 35-50KB，拆分为容器 + 4 个子组件
- `model-train/+page.svelte` 预估 30-40KB，拆分为容器 + 4 个子组件

### 生成标签页

```
routes/generate/
├── +layout.svelte              # 生成标签页布局
├── mask-gen/
│   ├── +page.svelte            # 叠色像素生成页面（容器）
│   ├── ImagePreview.svelte     # 图像预览
│   ├── MaskOverlay.svelte      # 掩码叠加
│   ├── ErrorHeatmap.svelte     # 误差热图
│   └── ConfigPanel.svelte      # 配置面板
├── vectorize/
│   └── +page.svelte            # 矢量化页面
└── export/
│   └── +page.svelte            # 模型导出页面
```

**拆分原因：**
- `mask-gen/+page.svelte` 预估 30-45KB，拆分为容器 + 4 个子组件

### 素材库标签页

```
routes/library/
├── +layout.svelte              # 素材库布局
├── boards/
│   ├── +page.svelte            # 校准板列表
│   └── [id]/
│       └── +page.svelte        # 校准板详情（蓝图渲染）
├── photos/
│   ├── +page.svelte            # 照片列表
│   └── [id]/
│       └── +page.svelte        # 照片详情
├── models/
│   ├── +page.svelte            # 模型列表
│   └── [id]/
│       └── +page.svelte        # 模型详情
├── materials/
│   ├── +page.svelte            # 材料管理
│   └── [id]/
│       └── +page.svelte        # 耗材组详情
└── exports/
    ├── +page.svelte            # 生成文件列表
    └── [id]/
        └── +page.svelte        # 文件详情
```

### 设置标签页

```
routes/settings/
├── +layout.svelte              # 设置布局
├── general/
│   └── +page.svelte            # 通用设置
├── workspace/
│   └── +page.svelte            # 工作区管理
├── engine/
│   └── +page.svelte            # 引擎设置
└── project/
    └── +page.svelte            # 项目设置
```

---

## assets/ - 静态资源

```
assets/
├── docs/                       # 文档
│   ├── zh/                     # 中文文档
│   └── en/                     # 英文文档
├── fonts/                      # 字体
│   └── MapleMonoNormal-NF-CN-Regular.woff2
├── icons/                      # 图标
│   └── icon.svg
└── loading.svg                 # 加载动画
```

---

## 文件大小控制策略

### 28KB 分界线

| 文件 | 预估大小 | 策略 |
|------|----------|------|
| `photo-warp/+page.svelte` | 35-50KB | 拆分为容器 + 4 个子组件 |
| `model-train/+page.svelte` | 30-40KB | 拆分为容器 + 4 个子组件 |
| `mask-gen/+page.svelte` | 30-45KB | 拆分为容器 + 4 个子组件 |
| `BlueprintRenderer.svelte` | 25-35KB | 保持现状（已按类型拆分）|
| `workspace.svelte.ts` | 25-35KB | 保持现状（状态管理）|

### 拆分原则

1. **页面容器**（~15KB）：路由入口，负责数据获取和布局
2. **功能组件**（~10-20KB）：具体功能实现
3. **基础组件**（~5-10KB）：可复用的 UI 组件

---

## 命名规范

### 文件命名

- 组件：PascalCase.svelte（如 `Sidebar.svelte`）
- 工具：camelCase.ts（如 `format.ts`）
- 路由目录：kebab-case（如 `photo-warp/`）
- 动态路由：[id]/（如 `[id]/+page.svelte`）

### 变量命名

- 组件名：PascalCase
- 函数名：camelCase
- 常量名：UPPER_SNAKE_CASE
- 类型名：PascalCase

---

## 导入规范

### 绝对导入

```typescript
// 使用 $lib 别名
import { Button } from '$lib/components/ui';
import { workspaceStore } from '$lib/stores';
import type { BoardSpec } from '$lib/types';
```

### 相对导入

```typescript
// 同一目录内
import WarpCanvas from './WarpCanvas.svelte';

// 上级目录
import { api } from '../api';
```
