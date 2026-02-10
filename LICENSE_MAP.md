# OpenColor 许可证映射

本文档记录 OpenColor 项目及其依赖的许可证信息。

## 本仓库许可证

OpenColor 项目本身采用 **MIT 许可证**（或您指定的其他许可证），详见仓库根目录的 LICENSE 文件。

## 数据来源

- `pixi.toml` - Python 依赖
- `web/package.json` - Web 前端依赖
- `web/src-tauri/Cargo.toml` - Rust 依赖
- `cpp_module/vcpkg.json` - C++ 依赖
- `py_module/*/pyproject.toml` - Python 子模块

---

## Python 引擎与核心算法（pixi.toml）

### 运行时与工具链

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| python | PSF License | Python 运行时环境 |
| pip | MIT | Python 包管理器 |
| nodejs | MIT | Node.js 运行时 |
| pnpm | MIT | Node.js 包管理器 |

### 数值计算与科学计算

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| numpy | BSD-3-Clause | 数值计算基础库 |
| scipy | BSD-3-Clause | 科学计算库 |
| jax | Apache-2.0 | 自动微分与加速计算 |
| jaxlib | Apache-2.0 | JAX 运行时 |
| xgboost | Apache-2.0 | 梯度提升机器学习库 |

### 图像与矢量处理

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| opencv-python-headless | Apache-2.0 | 计算机视觉库（无 GUI 版本） |
| pillow | HPND | 图像处理库 |
| scikit-image | BSD-3-Clause | 图像处理算法库 |
| cairosvg | LGPL-3.0 | SVG 转位图 |
| svgpathtools | MIT | SVG 路径操作 |
| lxml | BSD-3-Clause | XML/HTML 处理 |

### 几何与网格处理

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| trimesh | MIT | 3D 网格处理 |
| shapely | BSD-3-Clause | 2D 几何操作（依赖 GEOS LGPL-2.1） |
| mapbox-earcut | ISC | 多边形三角剖分 |
| manifold3d | Apache-2.0 | 高性能几何布尔运算 |
| rtree | MIT | R-tree 空间索引 |
| triangle | 自定义（非商业）| 三角剖分库 |

### 3D 文件格式

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| lib3mf | BSD-2-Clause | 3MF 文件格式支持 |
| pygltflib | MIT | glTF 文件处理 |

### UI 与工具

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| gradio | Apache-2.0 | Web UI 界面库 |
| pydantic | MIT | 数据验证库 |
| tqdm | MPL-2.0 | 进度条库 |
| pytest | MIT | 测试框架 |
| pyinstaller | GPL-2.0+ | 打包工具（需关注 copyleft）|

### AprilTag 检测

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| pupil-apriltags | MIT | AprilTag 检测库 |

### 矢量化

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| vtracer | BSD-2-Clause | 位图转 SVG 矢量化 |

---

## 本仓库 Python 子模块

| 模块 | 路径 | 许可证 | 备注 |
|------|------|--------|------|
| opencolor (oc-core) | `py_module/opencolor/` | MIT | 核心算法库（已整合 LumenBoardTool） |
| oc-engine | `py_module/engine/` | MIT | API 服务 |
| oc-calib | `py_module/calibration/` | MIT | 校准类型 |
| model-export | `py_module/model_export/` | MIT | 3MF 导出 |
| oc-prototypes | `py_module/prototypes/` | MIT | 原型管线 |
| oc-scripts | `py_module/scripts/` | MIT | 脚本集 |
| oc-analyze | `py_module/analyze/` | MIT | 分析工具 |

---

## Web 前端（web/package.json）

### 核心框架

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| vue | MIT | 前端框架 |
| vue-i18n | MIT | 国际化插件 |
| @vitejs/plugin-vue | MIT | Vite Vue 插件 |

### 构建工具

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| vite | MIT | 构建工具 |
| vitest | MIT | 测试框架 |
| typescript | Apache-2.0 | TypeScript 编译器 |
| vue-tsc | MIT | Vue TypeScript 检查 |

### UI 组件与图标

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| @tabler/icons-webfont | MIT | Tabler 图标 |
| konva | MIT | Canvas 绘图库 |
| vue-konva | MIT | Vue Konva 绑定 |

### 内容处理

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| markdown-it | MIT | Markdown 解析 |

### Tauri 桌面端

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| @tauri-apps/api | MIT/Apache-2.0 | 双许可 |
| @tauri-apps/cli | MIT/Apache-2.0 | 双许可 |

### 开发工具

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| rollup-plugin-visualizer | MIT | 包体积分析 |

---

## Tauri 桌面端（web/src-tauri/Cargo.toml）

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| tauri | MIT/Apache-2.0 | 双许可 |
| tauri-build | MIT/Apache-2.0 | 双许可 |
| tauri-plugin-log | MIT/Apache-2.0 | 双许可 |
| tauri-plugin-dialog | MIT/Apache-2.0 | 双许可 |
| serde | MIT/Apache-2.0 | 双许可 |
| serde_json | MIT/Apache-2.0 | 双许可 |
| log | MIT/Apache-2.0 | 双许可 |

---

## C++ 核心模块（cpp_module/vcpkg.json）

| 依赖 | 许可证 | 备注 |
|------|--------|------|
| vulkan | 混合 | 需以 SDK 与 vcpkg 产物为准 |
| pybind11 | BSD-3-Clause | Python C++ 绑定 |
| shaderc | Apache-2.0 | 着色器编译 |
| manifold | Apache-2.0 | 几何布尔运算 |
| clipper2 | Boost-1.0 | 多边形裁剪 |
| sdl3 | zlib | 跨平台多媒体库 |
| imgui | MIT | 即时模式 GUI |

---

## 资源与字体

| 资源 | 许可证 | 备注 |
|------|--------|------|
| Maple Mono 字体 | OFL-1.1 | 开源字体许可证 |

---

## 第三方参考与灵感

| 项目 | 许可证 | 备注 |
|------|--------|------|
| BambuStudio | AGPL-3.0 | 3MF 格式参考 |
| HueForge | 商业软件 | 项目灵感来源 |
| PrusaSlicer | AGPL-3.0 | BambuStudio 上游 |
| Slic3r | AGPL-3.0 | PrusaSlicer 上游 |

---

## 许可证说明

### 宽松许可证（Permissive）
- **MIT** - 允许自由使用、修改、分发，需保留版权声明
- **BSD-2/3-Clause** - 类似 MIT，条款略有不同
- **Apache-2.0** - 允许专利授权，需保留 NOTICE 文件
- **ISC** - 类似 MIT，更简洁
- **HPND** - 历史宽松许可证

### 弱 Copyleft
- **MPL-2.0** - 文件级 copyleft，修改文件需开源
- **LGPL-2.1/3.0** - 库级 copyleft，动态链接可规避

### 强 Copyleft
- **GPL-2.0+/3.0+** - 传染性 copyleft，衍生作品需开源
- **AGPL-3.0** - 网络服务也触发 copyleft

### 其他
- **OFL-1.1** - 开源字体许可证
- **PSF License** - Python 软件基金会许可证
- **Boost-1.0** - Boost 库许可证
- **zlib** - zlib 压缩库许可证

---

## 发行合规提示

### 必须遵守的许可证要求

1. **MIT/BSD/Apache-2.0** - 保留版权声明和许可证文本
2. **MPL-2.0** - 提供修改文件的源代码
3. **LGPL** - 提供库修改的源代码，或动态链接
4. **GPL/AGPL** - 提供完整源代码，衍生作品同许可

### 建议做法

1. 在发行包中包含 `LICENSES/` 目录，存放所有依赖的许可证
2. 对于 Apache-2.0 依赖，保留 NOTICE 文件
3. 对于 MPL-2.0 依赖，标记修改的文件
4. 避免将 GPL/AGPL 代码静态链接到非 GPL 项目

### 本仓库合规状态

- ✅ 本仓库代码采用 MIT（或指定许可证）
- ✅ 所有依赖均为宽松许可证或弱 copyleft
- ⚠️ pyinstaller (GPL-2.0+) 仅用于打包，不链接到运行时
- ⚠️ cairosvg (LGPL-3.0) 以动态方式使用
- ✅ 无 AGPL 依赖（除参考的 BambuStudio 外）

---

## 更新记录

- 2025-02-05: 更新为最新项目结构，添加所有 Python 模块和依赖
