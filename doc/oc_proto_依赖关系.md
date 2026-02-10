# oc_proto 模块依赖分析报告

**生成日期**: 2026-02-09  
**模块路径**: `py_module/prototypes/src/oc_proto/`  
**分析目的**: 记录 oc_proto 与 oc_core_02 的依赖关系

---

## 1. 模块结构概览

```
oc_proto/
├── __init__.py                    # 空文件
├── common/                        # 共享工具库
│   ├── __init__.py
│   ├── clean.py                   # 清理中间产物
│   ├── color_utils.py             # 颜色空间转换
│   ├── io_utils.py                # IO工具
│   ├── manifest.py                # Manifest生成
│   ├── paths.py                   # 路径管理
│   ├── spec_adapter.py            # BoardSpec适配器
│   └── vtracer_bridge.py          # VTracer桥接
├── calib_board_gen/               # 校准板生成
│   ├── main.py
│   ├── __init__.py
│   └── README.md
├── calib_sample_build/            # 样本构建
│   ├── main.py
│   ├── __init__.py
│   └── README.md
├── calib_color_rts/               # 颜色模型拟合 (RTS - Real Time System)
│   ├── main.py
│   ├── cli.py
│   ├── runner.py
│   ├── dataset_io.py
│   ├── color_space.py
│   ├── xgb_fit.py
│   ├── xgb_model.py
│   ├── xgb_dataset.py
│   ├── xgb_features.py
│   ├── xgb_colorspace.py
│   ├── xgb_viz.py
│   ├── model_io.py
│   ├── diagnostics.py
│   ├── od_eval_runner.py
│   ├── od_eval_logit_pairs.py
│   ├── od_eval_fullpairs.py
│   ├── rt_stack_fit_eval.py
│   ├── optical_model.py
│   ├── model_base.py
│   ├── model_physics_visualizer.py
│   ├── eval_comparison_all.py
│   ├── main_depc.py
│   ├── __init__.py
│   ├── README.md
│   └── models/                    # 模型实现
│       ├── __init__.py
│       ├── tmm_model.py
│       └── phys_gpr_model.py
├── calib_photo_warp/              # 照片透视校正
│   ├── app.py
│   ├── __init__.py
│   └── README.md
├── gen_masks/                     # 掩码生成
│   ├── main.py
│   ├── solver.py
│   ├── solver_wrapper.py
│   ├── solver_cpp_wrapper.py
│   ├── optimizer.py
│   ├── filters.py
│   ├── stats.py
│   ├── joint_refinement.py
│   ├── visualization.py
│   ├── dot_pattern_test.py
│   ├── gray_test.py
│   ├── diagnose_all_pure_colors.py
│   ├── __init__.py
│   ├── README.md
│   └── mask_postprocess_v2/       # 掩码后处理
│       ├── __init__.py
│       └── island_suppress.py
├── gen_vector/                    # 矢量化
│   ├── main.py
│   ├── workers.py
│   ├── resampler.py
│   ├── reconcile.py
│   ├── deviation.py
│   ├── mask_overlap_check.py
│   ├── svg_utils.py
│   ├── geometry_utils.py
│   ├── exclusive_clipper.py
│   ├── visualization.py
│   ├── __init__.py
│   └── README.md
└── gen_model_exporter/            # 模型导出
    ├── main.py
    ├── geometry_bridge.py
    ├── mesh_utils.py
    ├── evidence_rebuild.py
    ├── voxel_repair.py
    ├── stl_poly_compare.py
    ├── interrupt_handler.py
    ├── __init__.py
    └── README.md
```

---

## 2. 内部模块依赖关系

### 2.1 common 模块被引用情况

| 引用模块 | 引用文件 | 引用的 common 内容 |
|---------|---------|-------------------|
| calib_board_gen | main.py | paths, manifest |
| calib_sample_build | main.py | paths, manifest, spec_adapter, io_utils |
| calib_color_rts | cli.py | spec_adapter |
| calib_color_rts | runner.py | manifest |
| calib_photo_warp | app.py | paths, manifest, io_utils, spec_adapter |
| gen_masks | main.py | paths, manifest |
| gen_vector | main.py | paths, manifest, vtracer_bridge |
| gen_model_exporter | main.py | paths |

### 2.2 子模块间交叉引用

```
calib_board_gen ──► calib_sample_build (通过 subprocess 调用生成 spec)
                ──► gen_masks (引用 generate_8color_board)

calib_sample_build ──► calib_board_gen (同步 spec 文件)
                   ──► calib_photo_warp (读取 warped 图像)
                   ──► calib_color_rts (间接引用)

calib_color_rts ──► calib_sample_build (加载 dataset_cells.json)
                ──► calib_board_gen (生成 mock 数据)

calib_photo_warp ──► calib_board_gen (同步 spec 文件)
                 ──► calib_sample_build (间接)

gen_masks ──► calib_color_rts (加载训练好的模型)
          ──► gen_vector (输出作为输入)

gen_vector ──► gen_masks (读取 mask_manifest.json)
           ──► gen_model_exporter (输出作为输入)

gen_model_exporter ──► gen_vector (读取 manifest.json 和 SVG)
```

---

## 3. 外部项目依赖 - oc_core_02 (opencolor)

### 3.1 核心模块引用详情

| 模块 | 引用位置 | 用途 |
|-----|---------|-----|
| `oc_core_02.core.sdf_io` | gen_vector/main.py, gen_vector/reconcile.py, gen_vector/visualization.py, gen_vector/workers.py, gen_vector/deviation.py, gen_model_exporter/evidence_rebuild.py, gen_model_exporter/stl_poly_compare.py | SVG保存、栅格化、加载SVG多边形 |
| `oc_core_02.core.sdf_utils` | common/vtracer_bridge.py | SVG路径解析 |
| `oc_core_02.core.mesh_export` | gen_model_exporter/voxel_repair.py | 体素网格导出 |
| `oc_core_02.core.sdf_export` | gen_model_exporter/main.py | SDF导出、最终网格处理 |
| `oc_core_02.core.sdf_extrude` | gen_model_exporter/main.py | 网格挤出 |
| `oc_core_02.core.sdf_data_prep` | gen_masks/main.py, gen_masks/dot_pattern_test.py | 层体积生成 |
| `oc_core_02.core.bitmap_pipeline` | gen_masks/main.py, gen_masks/dot_pattern_test.py, gen_masks/gray_test.py | 位图处理管道、BitmapParams |
| `oc_core_02.core.bitmap_pipeline_sdf` | gen_masks/gray_test.py | SDF位图管线、层体积生成 |
| `oc_core_02.core.color_systems` | gen_masks/main.py, gen_masks/dot_pattern_test.py, gen_masks/gray_test.py, gen_model_exporter/main.py | 颜色系统 |
| `oc_core_02.core.calibration` | calib_photo_warp/app.py | 透视校正、单应性估计 |
| `oc_core_02.core.apriltag_utils` | calib_photo_warp/app.py | AprilTag检测 |
| `oc_core_02.core.chroma_utils` | calib_photo_warp/app.py | 色度角点检测 |
| `oc_core_02.core.model_analysis` | calib_board_gen/main.py | 3MF模型分析 |
| `oc_core_02.utils.bin_loader` | calib_color_rts/models/tmm_model.py, calib_color_rts/optical_model.py | C++扩展加载 |

### 3.2 按文件细分的 oc_core_02 引用

#### gen_vector 模块
- **main.py**: `sdf_io.save_svg`, `sdf_io.rasterize_geometry_soft`
- **reconcile.py**: `sdf_io.rasterize_geometry_soft`
- **visualization.py**: `sdf_io.save_svg`, `sdf_io.rasterize_geometry_soft`
- **workers.py**: `sdf_io.save_svg`, `sdf_io.rasterize_geometry`, `sdf_io.rasterize_geometry_soft`
- **deviation.py**: `sdf_io.rasterize_geometry_soft`

#### gen_model_exporter 模块
- **main.py**: `color_systems.ColorSystem`, `sdf_export.finalize_slot_mesh`, `sdf_extrude.extrude_layer_mesh`, `sdf_io.load_svg_polygons`
- **voxel_repair.py**: `mesh_export.VoxelGrid`, `mesh_export.voxel_grid_to_mesh`
- **evidence_rebuild.py**: `sdf_io.rasterize_geometry_soft`, `sdf_io.load_svg_polygons`
- **stl_poly_compare.py**: `sdf_io.rasterize_geometry_soft`, `sdf_io.load_svg_polygons`

#### gen_masks 模块
- **main.py**: `bitmap_pipeline.BitmapParams`, `bitmap_pipeline._mask_transparency_and_bg`, `color_systems.ColorSystem`, `sdf_data_prep.generate_layer_volumes`
- **dot_pattern_test.py**: `bitmap_pipeline.BitmapParams`, `color_systems.ColorSystem`, `sdf_data_prep.generate_layer_volumes`
- **gray_test.py**: `bitmap_pipeline.BitmapParams`, `bitmap_pipeline_sdf._generate_layer_volumes`, `color_systems.ColorSystem`

#### calib_color_rts 模块
- **models/tmm_model.py**: `utils.bin_loader.import_cpp_extension`
- **optical_model.py**: `utils.bin_loader.import_cpp_extension`

#### calib_photo_warp 模块
- **app.py**: `calibration.WarpParams`, `calibration.estimate_coarse_homography`, `calibration.get_board_corners_from_h`, `apriltag_utils.detect_apriltags_corners`, `chroma_utils.detect_chroma_corners`

#### calib_board_gen 模块
- **main.py**: `model_analysis.analyze_3mf_lib3mf`

#### common 模块
- **vtracer_bridge.py**: `sdf_utils._parse_path_d_simple`, `sdf_utils._parse_svg_points`

---

## 4. 第三方库依赖

### 4.1 必需依赖 (pyproject.toml)

| 库 | 用途 |
|---|-----|
| `numpy` | 数值计算 |
| `opencv-python` | 图像处理 |
| `gradio` | Web UI |
| `pillow` | 图像IO |
| `scipy` | 科学计算 |

### 4.2 实际代码中的其他依赖

| 库 | 用途 | 引用位置 |
|---|-----|---------|
| `shapely` | 几何操作 | vtracer_bridge.py, gen_vector/resampler.py, gen_vector/main.py, gen_model_exporter/main.py |
| `trimesh` | 3D网格处理 | gen_model_exporter/main.py |
| `xgboost` | XGBoost模型 | calib_color_rts/xgb_model.py |
| `vtracer` | 矢量化 | vtracer_bridge.py |
| `matplotlib` | 绘图 | calib_color_rts/xgb_viz.py, calib_color_rts/model_physics_visualizer.py |
| `sklearn` | 机器学习工具 | calib_color_rts/xgb_fit.py |
| `skimage` | 图像处理 | gen_masks/solver.py |
| `torch` | 深度学习 | calib_color_rts/models/phys_gpr_model.py |

---

## 5. 包配置说明

### 5.1 oc_proto (prototypes)

**pyproject.toml**:
```toml
[project]
name = "oc-prototypes"
version = "0.1.0"
dependencies = [
    "numpy",
    "opencv-python",
    "gradio",
    "pillow",
    "scipy"
]
```

注意：**没有显式声明对 oc_core 的依赖**，依赖通过 pixi 工作区管理。

### 5.2 oc_core_02 (opencolor)

**pyproject.toml**:
```toml
[project]
name = "oc_core"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["src/oc_core"]
```

注意：包名是 `oc_core`，但实际代码中导入使用的是 `oc_core_02`（源代码文件夹名）。

---

## 6. 模块功能说明

| 模块 | 功能描述 | 输入 | 输出 |
|-----|---------|-----|-----|
| calib_board_gen | 生成8色校准板规格和3MF文件 | - | board_spec.json, .3mf |
| calib_sample_build | 从校正照片提取颜色样本 | warped.png, spec.json | dataset_cells.json |
| calib_color_rts | 训练颜色预测模型 | dataset_cells.json | color_model.json, phys_gpr_model.npz |
| calib_photo_warp | 交互式照片透视校正 | 原始照片, spec | board_warped.png |
| gen_masks | 图像色彩分解为层掩码 | 输入图像, 训练模型 | mask.png, mask_manifest.json |
| gen_vector | 掩码矢量化 | mask.png | SVG多边形 |
| gen_model_exporter | 导出3D打印模型 | SVG多边形 | STL/3MF文件 |

---

## 7. 数据流

```
校准线路:
calib_board_gen → calib_photo_warp → calib_sample_build → calib_color_rts

生成线路:
gen_masks → gen_vector → gen_model_exporter
```

---

## 8. 总结

`oc_proto` 是一个高度集成的多阶段图像到3D打印管线，依赖 `oc_core_02` 提供的核心功能：

1. **SDF处理**: sdf_io, sdf_utils, sdf_export, sdf_extrude, sdf_data_prep
2. **位图处理**: bitmap_pipeline, bitmap_pipeline_sdf
3. **颜色系统**: color_systems
4. **校准**: calibration, apriltag_utils, chroma_utils
5. **网格导出**: mesh_export
6. **工具**: bin_loader, model_analysis

迁移或修改时需要确保 oc_core_02 的相应模块可用。
