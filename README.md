<p align="center">
  <img alt="OpenColor logo" src="data/icon.svg" width="128" height="128">
  <br>
  <em>我已精通此间奥秘，亦已吸取潜藏教诲。 ————《司辰之书》</em>
  <br>
  <p align="center">
    | <a href="README_en.md">English</a> | <a href="README.md">简体中文</a> |
  </p>
</p>

> [!WARNING]
> 注意项目依旧在草稿阶段，Web-UI无法使用，推荐按顺序使用[oc_proto](./py_module/prototypes/src/oc_proto/)中的模块环节来完成位图转全彩叠色3D模型的任务。

# OpenColor

OpenColor 是一个用于 FDM 3D 打印的多色叠层规划与生成工具集。它通过将不同颜色的材料（如 R, G, B, W）以微小层厚进行物理堆叠，在打印件表面或内部实现精细的色彩表现。

## 核心特性

- **物理驱动的颜色预测**: 基于 Adding-Doubling 物理模型
- **机器学习增强**: 使用 XGBoost/GPR 修正物理模型的残差，提高预测精度
- **完整的校准流程**: 从色盘生成、照片校正到模型训练的端到端校准
- **高性能 C++ 核心**: Vulkan 加速的几何处理和颜色求解
- **现代化 UI**: Vue 3 + Tauri 构建的跨平台桌面应用
- **标准 3MF 导出**: 基于 lib3mf 的标准 3MF 格式支持

## 项目结构

```
OpenColor/
├── py_module/          # Python 模块
│   ├── opencolor/      # 核心算法库 (oc_core_02)
│   ├── engine/         # HTTP API 服务 (oc_engine)
│   ├── calibration/    # 自动校准 (oc_calib)
│   ├── model_export/   # 3MF 导出引擎
│   ├── prototypes/     # 原型开发 (oc_proto)
│   ├── scripts/        # 脚本集 (oc_scripts)
│   ├── analyze/        # 分析诊断 (oc_analyze)
│   ├── sdf/            # SDF 转换 (oc_sdf)
│   └── xgb/            # XGBoost 模型 (oc_xgb)
├── cpp_module/         # C++ 高性能模块
│   ├── src/solver/     # 求解器 (opencolor_solver)
│   ├── src/geometry/   # 几何处理 (opencolor_geometry)
│   └── src/models/     # 预测模型 (opencolor_models)
├── web/                # Web 前端 + Tauri 桌面壳
│   ├── src/            # Vue 3 前端源码
│   └── src-tauri/      # Rust 后端
├── data/               # 数据文件（校准数据、示例图像）
└── doc/                # 文档
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- Pixi (包管理器)
- Vulkan SDK (C++ 模块可选)

### 安装

```bash
# 克隆仓库
git clone https://github.com/UniverseEmbedded/OpenColor.git --depth 1
cd OpenColor

# 安装所有依赖（Python + Node.js + C++）
pixi install

# 设置 C++ 环境（可选）
pixi run setup-cpp
```

### 运行 Web 应用

```bash
# 开发模式
pixi run web-tauri-dev

# 构建生产版本
pixi run web-tauri-build
```

### 运行原型环节

```bash
# 校准流程
pixi run p2-calib-board-gen      # 生成校准板
pixi run p2-calib-photo-warp-ui  # 照片透视校正（UI）
pixi run p2-calib-sample-build   # 构建样本数据集
pixi run p2-calib-color-rts      # 训练色彩模型

# 生成流程
pixi run p2-gen-masks            # 生成掩码
pixi run p2-gen-vtracer          # 矢量化
pixi run p2-gen-3mf              # 导出 STL/3MF
```

## 工作流程

### 1. 校准流程 (Calibration)

用于训练颜色预测模型：

1. **生成校准板** (`calib_board_gen`): 生成 8 色校准板的规格文件和 3MF 打印文件
2. **照片透视校正** (`calib_photo_warp`): 通过 AprilTag 或手动 4 点校正色盘照片
3. **构建样本数据集** (`calib_sample_build`): 从校正后的照片提取颜色样本
4. **训练色彩模型** (`calib_color_rts`): 使用物理模型 + GPR 训练颜色预测模型

### 2. 生成流程 (Generation)

用于从图像生成 3D 打印文件：

1. **生成掩码** (`gen_masks`): 基于训练好的模型进行实时配色求解，生成各层掩码
2. **矢量化** (`gen_vector`): 将掩码转换为 SVG 矢量多边形
3. **模型导出** (`gen_3mf`): 从 SVG 多边形重建 3D 网格，导出 STL 和 3MF

## 技术栈

### Python
- **数值计算**: NumPy, SciPy, JAX, XGBoost
- **图像处理**: OpenCV, Pillow, scikit-image
- **几何处理**: Trimesh, Shapely, Manifold3D
- **3D 格式**: lib3mf, pygltflib
- **UI**: Gradio
- **数据验证**: Pydantic

### C++
- **图形**: Vulkan
- **几何**: Manifold, Clipper2, earcut-hpp
- **Python 绑定**: Pybind11
- **着色器**: Shaderc
- **SVG**: nanosvg

### Web
- **前端**: Vue 3, TypeScript, Vite
- **桌面**: Tauri v2 (Rust)
- **国际化**: vue-i18n

## 文档

- [FILE_MAP.md](FILE_MAP.md) - 详细的文件映射
- [PROJECT_MAP.md](PROJECT_MAP.md) - 项目级结构说明
- [py_module/PROJECT_MAP.md](py_module/PROJECT_MAP.md) - Python 模块详细说明
- [REFACTOR_MAP.md](REFACTOR_MAP.md) - 重构建议地图
- [DEPC_MAP.md](DEPC_MAP.md) - 依赖清理地图
- [IP_SAFETY.md](IP_SAFETY.md) - 知识产权安全文档（竞争对手专利规避）
- [cpp_module/README.md](cpp_module/README.md) - C++ 模块说明
- [web/FILE_MAP.md](web/FILE_MAP.md) - Web 前端文件映射

## 许可证

见 [LICENSE_MAP.md](LICENSE_MAP.md)

## 致谢

- 灵感来源于 [HueForge](https://shop.thehueforge.com/)
- 参考开源项目 [Lumina-Layers](https://github.com/MOVIBALE/Lumina-Layers)
- Bambu Studio 3MF 格式参考 [BambuStudio](https://github.com/bambulab/BambuStudio) (AGPL v3)
