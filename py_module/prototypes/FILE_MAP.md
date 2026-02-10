# OpenColor Prototypes 文件映射

本文档描述 `py_module/prototypes` 模块的文件结构，包括内部组件和外部依赖关系。

## 目录结构

```
py_module/prototypes/
├── src/oc_proto/                   # 原型实现（核心，不可修改）
│   ├── calib_board_gen/            # 校准板生成
│   ├── calib_photo_warp/           # 照片透视校正
│   ├── calib_sample_build/         # 样本数据集构建
│   ├── calib_color_rts/            # 色彩模型拟合（物理+GPR）
│   ├── gen_masks/                  # 掩码生成
│   ├── gen_vector/                 # 矢量化
│   ├── gen_3mf/                    # 模型导出（STL/3MF）
│   ├── common/                     # 通用工具
│   └── __init__.py
├── README.md                       # 模块说明
├── pyproject.toml                  # 构建配置
├── FILE_MAP.md                     # 本文件映射文档
├── clean_oc_proto.py               # 清理脚本
├── pack_code.py                    # 代码打包
└── pack_resources.py               # 资源打包
```

## 内部组件

### 1. 校准流程环节

| 目录 | 功能 | 入口文件 |
|------|------|----------|
| `calib_board_gen/` | 生成8色校准板的规格文件和3MF打印文件 | `main.py` |
| `calib_photo_warp/` | 通过AprilTag或手动4点进行色盘照片透视校正 | `app.py` |
| `calib_sample_build/` | 从校正后的照片提取颜色样本，生成训练数据集 | `main.py` |
| `calib_color_rts/` | 使用物理模型+GPR残差修正训练颜色预测模型 | `main.py`, `cli.py` |

### 2. 生成流程环节

| 目录 | 功能 | 入口文件 |
|------|------|----------|
| `gen_masks/` | 基于训练好的模型进行实时配色求解，生成各层掩码 | `main.py` |
| `gen_vector/` | 将掩码转换为SVG矢量多边形 | `main.py` |
| `gen_3mf/` | 从SVG多边形重建3D网格，导出STL和3MF | `main.py` |

### 3. 通用工具 (common/)

| 文件 | 功能 |
|------|------|
| `paths.py` | 路径管理（ensure_data, get_out_dir, RESOURCES） |
| `manifest.py` | 清单文件读写（write_manifest, read_manifest） |
| `io_utils.py` | IO工具（copy_file, sync_file） |
| `spec_adapter.py` | 规格适配器（SpecAdapter, extract_layer_sequence） |
| `color_utils.py` | 颜色工具函数 |
| `vtracer_bridge.py` | vtracer矢量化桥接 |
| `clean.py` | 清理工具 |

## 外部依赖

### Python 模块依赖

#### 1. oc_core_02

**被依赖的文件**：
- `oc_core_02.core.bitmap_pipeline` - BitmapParams, _mask_transparency_and_bg
- `oc_core_02.core.bitmap_pipeline_sdf` - _prepare_data, _generate_layer_volumes, _finalize_slot_mesh, _extrude_layer_mesh
- `oc_core_02.core.color_systems` - ALL_SYSTEMS, ColorSystem
- `oc_core_02.core.sdf_types` - SDFParams
- `oc_core_02.core.sdf_io` - save_svg, rasterize_geometry, rasterize_geometry_soft, load_svg_polygons
- `oc_core_02.core.sdf_mesh` - clean_mesh
- `oc_core_02.core.mesh_export` - export_stl
- `oc_core_02.core.calibration` - WarpParams, estimate_coarse_homography, get_board_corners_from_h

**使用环节**：
- `gen_masks/main.py`
- `gen_vector/main.py`
- `gen_3mf/main.py`
- `gen_3mf/evidence_rebuild.py`
- `gen_3mf/stl_poly_compare.py`
- `calib_photo_warp/app.py`

#### 2. Calibration (calib)

**被依赖的文件**：
- `calib.board_spec` - BoardSpec

**使用环节**：
- `calib_photo_warp/app.py`

#### 3. oc_proto 内部依赖

**环节间依赖**：
- `gen_masks` → `calib_color_rts/model_io` (load_model)
- `gen_masks` → `calib_color_rts/color_space` (lab_to_rgb01, rgb01_to_lab, delta_e_cie76)
- `gen_3mf` → `gen_3mf/stl_poly_compare` (run_stl_poly_comparison)

### C++ 扩展依赖

| 模块名 | 功能 | 使用环节 |
|--------|------|----------|
| `opencolor_solver` | Hill Climbing求解器 | `gen_masks/solver_cpp_wrapper.py` |
| `opencolor_geometry` | 3D布尔运算、体积计算 | `gen_3mf/main.py` |
| `opencolor_mcrt` | 蒙特卡洛光线追踪 | `calib_color_rts/models/tmm_model.py`, `optical_model.py` |

**注意**：C++扩展是可选依赖，如果不可用会回退到Python实现或报错。

### 反向依赖（谁依赖oc_proto）

| 模块 | 依赖内容 | 说明 |
|------|----------|------|
| `oc_analyze/debug_cell_b.py` | `calib_color_rts/dataset_io`, `model_io`, `xgb_features`, `xgb_fit`, `color_space` | 分析诊断工具依赖原型中的数据集和模型功能 |

## 数据流

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           校准流程 (Calibration)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  calib_board_gen                                                        │
│       ↓                                                                 │
│  calib_photo_warp  ←── 依赖: oc_core_02.core.calibration (WarpParams)   │
│       ↓                  依赖: calib.board_spec (BoardSpec)             │
│  calib_sample_build                                                     │
│       ↓                                                                 │
│  calib_color_rts  ←── 可选依赖: opencolor_mcrt                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                           生成流程 (Generation)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  gen_masks  ←── 依赖: oc_core_02.core.bitmap_pipeline                   │
│       ↓            依赖: oc_core_02.core.bitmap_pipeline_sdf            │
│       ↓            依赖: oc_core_02.core.color_systems                  │
│       ↓            依赖: opencolor_solver (C++)                         │
│       ↓            依赖: calib_color_rts/model_io (load_model)          │
│  gen_vector  ←── 依赖: oc_core_02.core.bitmap_pipeline                  │
│       ↓            依赖: oc_core_02.core.sdf_types, sdf_io              │
│  gen_3mf  ←── 依赖: oc_core_02.core.bitmap_pipeline_sdf                 │
│       ↓                   依赖: oc_core_02.core.sdf_io, sdf_mesh        │
│       ↓                   依赖: oc_core_02.core.mesh_export             │
│       ↓                   依赖: opencolor_geometry (C++)                │
└─────────────────────────────────────────────────────────────────────────┘
```

## 关键依赖说明

### 为什么依赖 oc_core_02？

`oc_proto` 的生成流程环节（gen_masks, gen_vector, gen_3mf）重度依赖 `oc_core_02.core` 的以下功能：

1. **bitmap_pipeline** - 位图处理流程参数和预处理
2. **bitmap_pipeline_sdf** - SDF（有向距离场）体积生成和网格挤出
3. **sdf_io** - SVG多边形的加载和栅格化
4. **sdf_mesh** - 网格清理
5. **mesh_export** - STL导出
6. **color_systems** - 颜色系统定义（RYBW等）

### 为什么依赖 C++ 扩展？

1. **opencolor_solver** - `gen_masks` 强制使用C++求解器进行颜色配方优化，Python实现性能不足
2. **opencolor_geometry** - `gen_3mf` 可选使用C++进行3D布尔运算，加速体积分析
3. **opencolor_mcrt** - `calib_color_rts` 可选使用C++进行蒙特卡洛光线追踪，加速模型训练

## 运行方式

```bash
# 校准流程
pixi run python -m oc_proto.calib_board_gen.main
pixi run python -m oc_proto.calib_photo_warp.app
pixi run python -m oc_proto.calib_sample_build.main
pixi run python -m oc_proto.calib_color_rts.main

# 生成流程
pixi run python -m oc_proto.gen_masks.main
pixi run python -m oc_proto.gen_vector.main
pixi run python -m oc_proto.gen_3mf.main
```

## 注意事项

1. **oc_proto 是实验性管线**，虽然经过测试，但接口可能不稳定
2. **C++ 扩展是可选的**，但强烈建议使用以获得最佳性能
3. **外部依赖变更可能影响原型功能**，修改 `oc_core_02.core` 或 `calib` 时需要测试原型环节
