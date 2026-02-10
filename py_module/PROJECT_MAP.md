# OpenColor Python 模块项目地图

本文档描述 `py_module` 目录下各 Python 模块的结构、功能和依赖关系。

## 更新记录

- **2026-02-10**: 全面更新文档，反映最新代码结构
  - 更新原型模块路径（oc_prototypes_02 → oc_proto）
  - 更新环节名称（移除 _01 后缀，calib_color_model_fit → calib_color_rts）
  - 添加 sdf 和 xgb 模块说明
  - 移除 LumenBoardTool 独立模块说明（已整合到 opencolor）
  - 更新模块依赖关系图

---

## 模块概览

| 模块 | 路径 | 功能 | 状态 |
|------|------|------|------|
| opencolor | `opencolor/` | 核心算法库（颜色系统、叠层模型、网格处理） | 稳定 |
| engine | `engine/` | HTTP API 服务（JSON-RPC），供 Web 前端调用 | 活跃开发 |
| calibration | `calibration/` | 自动校准基础类型定义 | 稳定 |
| model_export | `model_export/` | 3MF 导出引擎（标准） | 稳定 |
| prototypes | `prototypes/` | 实验性管线（7 个环节） | 测试完成 |
| scripts | `scripts/` | 命令行脚本集 | 维护中 |
| analyze | `analyze/` | 分析与诊断工具 | 维护中 |
| sdf | `sdf/` | 基于 SDF 的位图到 3D 网格转换 | 活跃开发 |
| xgb | `xgb/` | XGBoost 颜色预测与物理 GPR 模型 | 活跃开发 |

---

## 详细模块说明

### 1. opencolor (oc_core_02)

**路径**: `opencolor/src/oc_core_02/`

**功能**: 核心算法库，提供位图处理、SDF 网格生成、颜色系统、MCRT 引擎等功能。

**核心组件**:

#### core/ - 核心功能
| 文件 | 功能 |
|------|------|
| `bitmap_pipeline.py` | 位图处理流程参数和预处理 |
| `bitmap_pipeline_sdf.py` | SDF 体积生成和网格挤出（核心） |
| `color_systems.py` | 颜色系统定义（RYBW, CMYK 等） |
| `mesh_export.py` | STL/GLB 导出 |
| `recipes.py` | 配方管理 |
| `svg_processing.py` | SVG 处理 |
| `three_mf.py` | 3MF 处理 |
| `app_paths.py` | 应用路径管理 |
| `model_analysis.py` | 模型分析 |

#### ui/ - Gradio 界面
| 文件 | 功能 |
|------|------|
| `bitmap.py` | 位图处理界面 |
| `board.py` | 色盘界面 |
| `calibration.py` | 校准界面 |
| `dataset.py` | 数据集界面 |
| `utils.py` | UI 工具 |

#### utils/ - 工具
| 文件 | 功能 |
|------|------|
| `logger.py` | 日志工具（基于 loguru） |
| `bin_loader.py` | 二进制文件加载工具 |
| `paths.py` | 路径管理 |
| `manifest.py` | 清单管理 |
| `io_utils.py` | IO 工具 |
| `color_utils.py` | 颜色工具 |
| `vtracer_bridge.py` | vtracer 桥接 |
| `clean.py` | 清理工具 |

**入口**: `app.py` - Gradio 应用入口

**依赖**:
- `calibration` - BoardSpec

**被依赖**:
- `prototypes` - `oc_proto` 重度依赖 oc_core_02.core 的功能
- `engine` - 部分 handler 可能使用 lumina 功能
- `sdf` - SDF 功能集成

---

### 2. engine (oc-engine)

**路径**: `engine/src/oc_engine/`

**功能**: HTTP 服务端（JSON-RPC），将算法封装为 API 供 Web 前端调用。

**核心组件**:
| 文件 | 功能 |
|------|------|
| `main.py` | 引擎主入口，请求分发 |
| `api_bridge.py` | Python API 桥接（供 Tauri 调用） |
| `protocol.py` | JSON-RPC 协议处理 |
| `schema.py` | Pydantic 数据模型 |
| `jobs.py` | 异步任务管理 |
| `errors.py` | 错误定义 |

#### handlers/ - 请求处理器
| 文件 | 功能 |
|------|------|
| `health.py` | 健康检查 |
| `board.py` | 色盘生成 |
| `lut.py` | LUT 提取和检测 |
| `bitmap.py` | 位图导出 |
| `svg.py` | SVG 导出 |
| `dataset.py` | 数据集管理 |

**依赖**:
- `opencolor` - 核心算法
- `calibration` - 校准类型

**被依赖**:
- `web` (Tauri) - Web 前端通过 Tauri 调用 engine

---

### 3. calibration (oc-calib)

**路径**: `calibration/src/oc_calib/`

**功能**: 自动校准基础类型定义。

**核心组件**:
| 文件 | 功能 |
|------|------|
| `board_spec.py` | 色盘规格定义（BoardSpec） |
| `board.py` | 色盘逻辑 |
| `dataset.py` | 数据集管理 |
| `observation.py` | 观测数据管理 |
| `calibration.py` | 校准算法 |
| `calib_types.py` | 校准类型定义 |
| `aggregate.py` | 数据聚合 |
| `spec_adapter.py` | 规格适配器 |

**依赖**: 无

**被依赖**:
- `opencolor` - 使用 BoardSpec
- `prototypes` - 使用 BoardSpec
- `engine` - 使用校准类型

---

### 4. model_export

**路径**: `model_export/src/model_export/`

**功能**: 3MF 导出引擎，支持标准 3MF。

**核心组件**:
| 文件 | 功能 |
|------|------|
| `standard_3mf.py` | 标准 3MF 导出（基于 lib3mf） |
| `types.py` | 网格数据类型定义（MeshData） |
| `atomic_io.py` | 原子 IO 操作 |
| `mesh_utils.py` | 网格工具 |

**依赖**: 无内部模块依赖

**被依赖**:
- `prototypes` - `gen_3mf` 使用
- `scripts` - 部分脚本使用
- `sdf` - SDF 导出使用

---

### 5. prototypes (oc-proto)

**路径**: `prototypes/src/oc_proto/`

**功能**: 实验性管线，包含完整的校准和生成流程（7 个环节）。

**核心组件**:

#### 校准流程
| 环节 | 功能 |
|------|------|
| `calib_board_gen/` | 校准板生成 |
| `calib_photo_warp/` | 照片透视校正 |
| `calib_sample_build/` | 样本数据集构建 |
| `calib_color_rts/` | 色彩模型拟合（物理+GPR） |

#### calib_color_rts/ 组件
| 文件/目录 | 功能 |
|-----------|------|
| `models/` | 模型实现（phys_gpr_model, new_model_template） |
| `dataset_io.py` | 数据集 IO |
| `model_io.py` | 模型 IO |
| `optical_model.py` | 光学模型 |
| `color_space.py` | 颜色空间转换 |
| `diagnostics.py` | 诊断工具 |
| `eval_*.py` | 评估脚本 |
| `runner.py`, `rt_stack_fit_eval.py` | 运行器 |

#### 生成流程
| 环节 | 功能 |
|------|------|
| `gen_masks/` | 掩码生成 |
| `gen_vector/` | 矢量化 |
| `gen_3mf/` | 模型导出 |

#### gen_masks/ 组件
| 文件 | 功能 |
|------|------|
| `solver.py`, `solver_wrapper.py`, `solver_cpp_wrapper.py` | 求解器 |
| `optimizer.py` | 优化器 |
| `filters.py` | 过滤器 |
| `island_suppress.py` | 孤岛抑制 |
| `joint_refinement*.py` | 联合优化 |
| `visualization.py` | 可视化 |
| `stats.py` | 统计 |

#### gen_vector/ 组件
| 文件 | 功能 |
|------|------|
| `deviation.py` | 偏差计算 |
| `exclusive_clipper.py` | 排他裁剪 |
| `resampler.py` | 重采样 |
| `svg_utils.py` | SVG 工具 |
| `workers.py` | 工作器 |

#### gen_3mf/ 组件
| 文件 | 功能 |
|------|------|
| `evidence_rebuild.py` | 证据重建 |
| `geometry_bridge.py` | 几何桥接 |
| `voxel_repair.py` | 体素修复 |
| `stl_poly_compare.py` | STL 多边形比较 |

#### 通用工具
| 文件 | 功能 |
|------|------|
| `common/` | 通用工具（paths, manifest, io_utils, spec_adapter, color_utils, vtracer_bridge, clean） |

**依赖**:
- `opencolor` - **重度依赖**，生成流程使用 oc_core_02.core 的 SDF 功能
- `calibration` - 使用 BoardSpec
- `model_export` - 使用 3MF 导出
- `xgb` - 使用 XGBoost 模型
- C++ 扩展 - `opencolor_solver`（强制）、`opencolor_geometry`（可选）

**被依赖**:
- `analyze` - `debug_cell_b.py` 使用原型中的数据集和模型功能

**注意**: `oc_proto` 是实验性管线，接口可能不稳定。

---

### 6. scripts (oc-scripts)

**路径**: `scripts/src/oc_scripts/`

**功能**: 命令行脚本集，用于快速生成、验证与实验。

**子模块**:

#### calibration/ - 校准相关
| 文件/目录 | 功能 |
|-----------|------|
| `color_board/` | 色板校准（calib_color, calib_geom, calibrate, make, projection, recipes） |
| `multicolor/` | 多色校准（geom, make, seq, utils） |
| `utils/` | 校准工具（mat_from_photos, optics_from_crops, screen_trans_pairs） |

#### planning/ - 叠层规划
| 文件 | 功能 |
|------|------|
| `layerplan.py` | 层规划 |
| `planner.py` | 规划器 |
| `planner_io.py` | 规划器 IO |
| `planner_models.py` | 规划器模型 |
| `planner_search.py` | 规划器搜索 |
| `forward_mc.py` | 蒙特卡洛前向模拟 |
| `validate_stack.py` | 验证堆叠 |

#### stl/ - 3D 几何
| 文件 | 功能 |
|------|------|
| `bmp_map4stl_nooverlap.py` | 无重叠位图映射 |
| `bmp_map4stl_plus.py` | 增强位图映射 |
| `color_square_stack.py` | 彩色方块堆叠 |
| `layercap_dome.py` | 层盖圆顶 |
| `mixplane.py` | 混合平面 |
| `screen_grad_16x9.py` | 16x9 屏幕渐变 |
| `thick_grad_card.py` | 厚渐变卡片 |

#### svg/ - 矢量图
| 文件 | 功能 |
|------|------|
| `svg4stl_vector.py` | SVG 转 STL |
| `svg4stl_vector_plus.py` | 增强 SVG 转 STL |
| `svg_mesh_verify.py` | 网格验证 |

#### utils/ - 工具
| 文件 | 功能 |
|------|------|
| `build_tauri_resources.py` | 构建 Tauri 资源 |
| `rectify_rectangles.py` | 矩形校正 |

**依赖**:
- `opencolor` - 核心算法
- `model_export` - 3MF 导出
- `prototypes` - 部分脚本使用

---

### 7. analyze (oc-analyze)

**路径**: `analyze/src/oc_analyze/`

**功能**: 分析与诊断工具集。

**核心组件**:
| 文件 | 功能 |
|------|------|
| `scan_large_files.py` | 大文件扫描 |
| `scan_long_filenames.py` | 长文件名扫描 |
| `scan_dense_dirs.py` | 密集目录扫描 |
| `scan_comment.py` | 代码注释扫描 |
| `scan_ruff.py` | Ruff 检查扫描 |
| `scan_duplicate.py` | 重复文件扫描 |
| `package_project.py` | 项目打包工具 |
| `replace_print.py` | 替换 print 语句 |

**依赖**: 无内部模块依赖

---

### 8. sdf (oc_sdf)

**路径**: `sdf/src/oc_sdf/`

**功能**: 基于 SDF（有向距离场）的位图到 3D 网格转换算法模块。

**核心组件**:
| 文件 | 功能 |
|------|------|
| `sdf_data_prep.py` | 数据准备（图像加载、LUT 匹配、层体积数据生成） |
| `sdf_polygon_gen.py` | 多边形生成（SDF 平滑、轮廓提取、多边形化） |
| `sdf_extrude.py` | 网格挤出（2D 多边形拉伸为 3D 网格） |
| `sdf_export.py` | 文件导出（STL、3MF 导出） |
| `sdf_io.py` | SVG/几何 IO |
| `sdf_mesh.py` | 网格处理 |
| `sdf_quality.py` | 质量分析 |
| `sdf_types.py` | SDF 类型定义 |
| `sdf_utils.py` | SDF 工具函数 |
| `geometry_utils.py` | 几何工具 |

**主要功能**:
- 基于 SDF 的轮廓重建
- 多层挤出和互斥裁剪
- 支持多种轮廓后端（bitmap2svg、vtracer、OpenCV）
- STL 和 3MF 导出

**依赖**: 无内部模块依赖

**被依赖**:
- `opencolor` - SDF 功能集成
- `prototypes` - `gen_3mf` 使用 SDF 功能

---

### 9. xgb (oc_xgb)

**路径**: `xgb/src/oc_xgb/`

**功能**: XGBoost 机器学习模块，用于颜色预测与物理 GPR 模型拟合。

**核心组件**:
| 文件 | 功能 |
|------|------|
| `xgb_model.py` | XGBoost 模型核心（训练、预测、保存） |
| `xgb_fit.py` | 物理 GPR 拟合 |
| `xgb_features.py` | 特征工程 |
| `xgb_dataset.py` | 数据集处理 |
| `xgb_colorspace.py` | 颜色空间转换 |
| `xgb_viz.py` | 可视化 |
| `model_base.py` | 模型基类 |
| `model_io.py` | 模型 IO |
| `optical_model.py` | 光学模型 |
| `color_space.py` | 颜色空间 |

**主要功能**:
- XGBoost 三通道回归器训练（Lab 颜色空间）
- 物理 GPR 模型拟合
- GPU 加速支持
- 模型结果可视化

**依赖**: 无内部模块依赖

**被依赖**:
- `prototypes` - `calib_color_rts` 使用 XGBoost 模型

---

## 模块依赖关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           外部依赖 (External)                            │
│  C++ Extensions: opencolor_solver, opencolor_geometry, opencolor_mcrt   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↑
                                    │ 可选/强制依赖
┌─────────────────────────────────────────────────────────────────────────┐
│                           Python 模块 (Internal)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │ calibration │◄───│ opencolor   │    │    xgb      │                 │
│  │ (oc-calib)  │    │(oc_core_02) │    │  (oc_xgb)   │                 │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │
│         │                  │                   │                        │
│         │         ┌────────┴────────┐         │                        │
│         │         │                 │         │                        │
│         │    ┌────┴────┐      ┌────┴────┐    │                        │
│         │    │ engine  │      │prototypes│◄───┘                        │
│         │    │(oc-engine)     │(oc-proto)│                             │
│         │    └────┬────┘      └────┬────┘                             │
│         │         │                │                                   │
│         │         │           ┌────┴────┐                              │
│         │         │           │ scripts │                              │
│         │         │           │(oc-scripts)                            │
│         │         │           └────┬────┘                              │
│         │         │                │                                   │
│         │         │           ┌────┴────┐                              │
│         │         │           │ analyze │                              │
│         │         │           │(oc-analyze)                           │
│         │         │           └─────────┘                              │
│         │         │                                                    │
│         │    ┌────┴────┐    ┌───────────┐                              │
│         └───►│ model_  │    │    sdf    │                              │
│              │ export  │    │ (oc_sdf)  │                              │
│              └─────────┘    └─────┬─────┘                              │
│                                   │                                    │
│                              ┌────┴────┐                               │
│                              │opencolor│                               │
│                              │(oc_core_02)                             │
│                              └─────────┘                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↑
                                    │ 调用
┌─────────────────────────────────────────────────────────────────────────┐
│                           Web 前端 (Web Frontend)                        │
│                              web/ (Tauri + Vue)                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 关键数据流

### 校准流程

```
calib_board_gen
        ↓
calib_photo_warp  ←── oc_core_02.core
        ↓
calib_sample_build
        ↓
calib_color_rts  ←── oc_xgb
```

### 生成流程

```
gen_masks  ←── oc_core_02.core.bitmap_pipeline/sdf
        ↓       ←── opencolor_solver (C++, 强制)
        ↓       ←── calib_color_rts/model_io
gen_vector  ←── oc_core_02.core.svg_processing
        ↓
gen_3mf  ←── oc_core_02.core.bitmap_pipeline_sdf
        ↓       ←── oc_sdf
        ↓       ←── model_export.standard_3mf
        ↓       ←── 可选: opencolor_geometry (C++)
```

---

## 运行命令

```bash
# opencolor (Gradio 界面)
pixi run python -m oc_core_02.app

# Engine (API 服务)
pixi run python -m oc_engine.main

# Prototypes 环节
pixi run python -m oc_proto.calib_board_gen.main
pixi run python -m oc_proto.calib_photo_warp.app
pixi run python -m oc_proto.calib_sample_build.main
pixi run python -m oc_proto.calib_color_rts.main
pixi run python -m oc_proto.gen_masks.main
pixi run python -m oc_proto.gen_vector.main
pixi run python -m oc_proto.gen_3mf.main
```

---

## 注意事项

1. **opencolor 是核心依赖**: `prototypes` 和 `scripts` 重度依赖 `oc_core_02.core` 的功能
2. **C++ 扩展是性能关键**: `opencolor_solver` 是 `gen_masks` 的强制依赖
3. **prototypes 是实验性**: 虽然经过测试，但接口可能不稳定
4. **engine 是 Web 前端入口**: Web 应用通过 `engine` 调用底层功能
5. **sdf 和 xgb 是新增模块**: 分别提供 SDF 转换和 XGBoost 模型功能

---

## 路径变更记录

| 旧路径 | 新路径 | 变更时间 |
|--------|--------|----------|
| `py_module/prototypes/src/oc_prototypes_02/` | `py_module/prototypes/src/oc_proto/` | 2026-02 |
| `oc_prototypes_02/calib_color_model_fit_01/` | `oc_proto/calib_color_rts/` | 2026-02 |
| `oc_prototypes_02/gen_model_exporter_01/` | `oc_proto/gen_3mf/` | 2026-02 |
| `py_module/LumenBoardTool/` | 整合到 `opencolor/src/oc_core_02/` | 2026-02 |
