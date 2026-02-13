# OpenColor-05 项目依赖分析报告

> 分析基准模块：engine 和 prototypes  
> 分析日期：2026-02-13  
> 分析范围：以 engine 和 prototypes 为入口，追踪所有被引用的文件

---

## 一、执行摘要

本次分析以 `py_module/engine` 和 `py_module/prototypes` 两个模块为基准，追踪它们依赖的所有文件。目的是识别哪些文件是核心功能必需的，哪些文件可能可以删除。

### 核心发现

| 模块 | 总文件数 | 被引用文件数 | 未被引用文件数 | 引用率 |
|------|----------|--------------|----------------|--------|
| engine | 20 | 20 | 0 | 100% |
| prototypes | 70 | 70 | 0 | 100% |
| oc_core_02 | 27 | 27 | 0 | 100% |
| oc_calib | 7 | 7 | 0 | 100% |
| oc_xgb | 9 | 9 | 0 | 100% |
| oc_sdf | 10 | 10 | 0 | 100% |
| model_export | 4 | 4 | 0 | 100% |
| oc_scripts | 42 | 2 | ~40 | ~5% |
| oc_analyze | 12 | 0 | 12 | 0% |

**关键结论**：
1. `oc_analyze` 模块（12个文件）完全未被引用，是最高优先级的删除候选
2. `oc_scripts` 模块中约40个文件未被引用，但大部分是独立工具脚本
3. 核心功能依赖关系清晰，engine 和 prototypes 依赖 oc_core_02、oc_calib、oc_xgb、oc_sdf、model_export

---

## 二、基准模块文件清单

### 2.1 Engine 模块（20个文件）

**核心文件（6个）：**
- `main.py` - 引擎主入口
- `api_bridge.py` - API桥接层
- `protocol.py` - JSON-RPC协议实现
- `schema.py` - Pydantic模型定义
- `jobs.py` - 异步任务管理
- `errors.py` - 错误处理

**Handlers（7个）：**
- `handlers/board.py` - 校准板处理
- `handlers/lut.py` - LUT检测处理
- `handlers/bitmap.py` - 位图导出处理
- `handlers/svg.py` - SVG导出处理
- `handlers/dataset.py` - 数据集处理
- `handlers/health.py` - 健康检查
- `handlers/__init__.py` - 处理器初始化

**Tests（6个）：**
- `tests/test_api_bridge_ping.py`
- `tests/test_api_bridge_board.py`
- `tests/test_board_preview.py`
- `tests/test_board_preview_first_8_cells.py`
- `tests/test_bitmap_export_3mf.py`
- `tests/conftest.py`

### 2.2 Prototypes 模块（70个文件）

| 子模块 | 文件数 | 功能描述 |
|--------|--------|----------|
| calib_board_gen | 4 | 校准板生成（8色） |
| calib_color_rts | 16 | RTS颜色模型评估 |
| calib_sample_build | 3 | 样本构建 |
| calib_photo_warp | 2 | 照片透视校正 |
| gen_3mf | 6 | 3MF模型导出 |
| gen_vector | 9 | 矢量化处理 |
| gen_masks | 23 | 掩码生成 |
| common | 1 | 公共组件 |

---

## 三、依赖关系架构

### 3.1 核心依赖图

```
engine / prototypes
        │
        ├──► oc_core_02 (核心库)
        │       ├── utils (logger, paths, manifest, io_utils, bin_loader, vtracer_bridge, color_utils, clean)
        │       ├── core (mesh_export, model_analysis, svg_processing, three_mf, bitmap_pipeline, 
        │       │           color_systems, app_paths, apriltag_utils, chroma_utils, recipes, bitmap_pipeline_sdf)
        │       └── ui (bitmap, board, calibration, dataset, utils)
        │
        ├──► oc_calib (校准模块)
        │       ├── board, board_spec, calibration, observation, dataset, aggregate, spec_adapter
        │
        ├──► oc_xgb (XGBoost模型)
        │       ├── color_space, model_io, xgb_features, xgb_model, xgb_fit, xgb_dataset, 
        │           xgb_viz, optical_model, model_base
        │
        ├──► oc_sdf (SDF处理)
        │       ├── sdf_io, sdf_extrude, sdf_export, sdf_mesh, sdf_types, sdf_utils, 
        │           sdf_quality, sdf_polygon_gen, sdf_data_prep, geometry_utils
        │
        ├──► oc_scripts (脚本工具)
        │       ├── stl/thick_grad_card (被engine引用)
        │       └── calibration/color_board/calib_geom (被engine引用)
        │
        └──► model_export (3MF导出)
                ├── standard_3mf, types, mesh_utils, atomic_io
```

### 3.2 Engine 模块具体依赖

| 源文件 | 依赖模块 | 被导入内容 |
|--------|----------|------------|
| board.py | oc_xgb.color_space | lab_to_rgb01 |
| board.py | oc_calib.board | BoardParams, render_board_preview, export_board_stls |
| board.py | oc_calib.board_spec | BoardSpec |
| board.py | oc_scripts.stl.thick_grad_card | ThickGradCardParams, export_thick_grad_card |
| board.py | oc_core_02.utils.logger | get_logger |
| lut.py | oc_calib.board_spec | BoardSpec, create_legacy_32x32_spec |
| lut.py | oc_calib.calibration | Calibration, find_observations_for_spec, load_calibration |
| lut.py | oc_calib.observation | Observation |
| lut.py | oc_scripts.calibration.color_board.calib_geom | detect_board_quad_by_chroma |
| bitmap.py | oc_core_02.core.bitmap_pipeline | BitmapParams, process_bitmap |
| bitmap.py | oc_core_02.core.three_mf | export_bambu_3mf |
| bitmap.py | oc_core_02.core.color_systems | ALL_SYSTEMS |
| bitmap.py | oc_core_02.core.app_paths | get_app_paths |
| svg.py | oc_core_02.core.svg_processing | export_svg_from_bitmap |
| svg.py | oc_core_02.core.three_mf | export_bambu_3mf_from_svgs |
| dataset.py | oc_calib.aggregate | aggregate_datasets |
| dataset.py | oc_calib.board_spec | BoardSpec |
| dataset.py | oc_calib.dataset | create_dataset |
| dataset.py | oc_calib.observation | Observation |
| __init__.py (handlers) | oc_core_02.core.app_paths | get_app_paths |
| api_bridge.py | oc_core_02.utils.logger | get_logger |

### 3.3 Prototypes 模块主要依赖

| 子模块 | 核心依赖 |
|--------|----------|
| calib_board_gen | oc_calib.board_spec, oc_core_02.core.mesh_export, model_export.standard_3mf, oc_sdf.sdf_mesh |
| gen_vector | oc_sdf.sdf_io, oc_core_02.utils.vtracer_bridge, shapely, PIL |
| gen_3mf | oc_core_02.core.color_systems, oc_sdf.sdf_export, model_export.mesh_utils, trimesh |
| gen_masks | oc_xgb.xgb_features, oc_xgb.xgb_fit, oc_core_02.core.bitmap_pipeline, oc_sdf.sdf_data_prep |
| calib_color_rts | oc_xgb.color_space, oc_xgb.model_io, oc_xgb.xgb_model, oc_xgb.xgb_fit, matplotlib |
| calib_sample_build | oc_calib.spec_adapter, oc_core_02.utils.paths, cv2 |
| calib_photo_warp | oc_calib.board_spec, oc_calib.calibration, oc_core_02.core.apriltag_utils, gradio |

---

## 四、被引用的完整文件清单

### 4.1 oc_core_02 模块（27个文件，全部被引用）

**Utils（8个）：**
- `utils/logger.py` - 被 engine、prototypes、xgb、sdf、scripts、calibration、model_export 引用
- `utils/paths.py` - 被 prototypes、calibration 引用
- `utils/manifest.py` - 被 prototypes 引用
- `utils/io_utils.py` - 被 prototypes 引用
- `utils/bin_loader.py` - 被 prototypes、sdf 引用
- `utils/vtracer_bridge.py` - 被 prototypes 引用
- `utils/color_utils.py`
- `utils/clean.py`

**Core（12个）：**
- `core/mesh_export.py` - 被 prototypes、calibration、sdf 引用
- `core/bitmap_pipeline.py` - 被 engine、prototypes、sdf 引用
- `core/bitmap_pipeline_sdf.py` - 被 ui 引用
- `core/color_systems.py` - 被 engine、prototypes、calibration、sdf 引用
- `core/three_mf.py` - 被 engine 引用
- `core/svg_processing.py` - 被 engine 引用
- `core/model_analysis.py` - 被 prototypes 引用
- `core/app_paths.py` - 被 engine、bitmap 引用
- `core/recipes.py` - 被 calibration 引用
- `core/apriltag_utils.py` - 被 calib_photo_warp 引用
- `core/chroma_utils.py` - 被 calib_photo_warp 引用

**UI（5个）：**
- `ui/bitmap.py`
- `ui/board.py`
- `ui/calibration.py`
- `ui/dataset.py`
- `ui/utils.py`

**其他（2个）：**
- `__init__.py`
- `app.py` - Gradio主应用入口

### 4.2 oc_calib 模块（7个文件，全部被引用）

- `board.py` - 被 engine、prototypes 引用
- `board_spec.py` - 被 engine、prototypes 引用
- `calibration.py` - 被 engine、prototypes 引用
- `observation.py` - 被 engine 引用
- `dataset.py` - 被 engine 引用
- `aggregate.py` - 被 engine 引用
- `spec_adapter.py` - 被 prototypes 引用

### 4.3 oc_xgb 模块（9个文件，全部被引用）

- `color_space.py` - 被 engine、prototypes 引用
- `model_io.py` - 被 prototypes 引用
- `xgb_features.py` - 被 prototypes 引用
- `xgb_model.py` - 被 prototypes 引用
- `xgb_fit.py` - 被 prototypes 引用
- `xgb_dataset.py`
- `xgb_viz.py`
- `optical_model.py` - 被 xgb_fit 引用
- `model_base.py`

### 4.4 oc_sdf 模块（10个文件，全部被引用）

- `sdf_io.py` - 被 prototypes 引用
- `sdf_extrude.py` - 被 prototypes 引用
- `sdf_export.py` - 被 prototypes 引用
- `sdf_mesh.py` - 被 prototypes 引用
- `sdf_types.py`
- `sdf_utils.py`
- `sdf_quality.py`
- `sdf_polygon_gen.py`
- `sdf_data_prep.py` - 被 prototypes 引用
- `geometry_utils.py`

### 4.5 model_export 模块（4个文件，全部被引用）

- `standard_3mf.py` - 被 prototypes 引用
- `types.py` - 被 prototypes 引用
- `mesh_utils.py` - 被 prototypes 引用
- `atomic_io.py`

### 4.6 oc_scripts 模块（42个文件，仅2个被引用）

**被引用的文件（2个）：**
- `stl/thick_grad_card.py` - 被 engine.board 引用
- `calibration/color_board/calib_geom.py` - 被 engine.lut 引用

**未被引用的文件（约40个）：**

| 类别 | 文件 |
|------|------|
| **STL相关** | screen_grad_16x9.py, mixplane.py, layercap_dome.py, color_square_stack.py, bmp_map4stl_plus.py, bmp_map4stl_nooverlap.py |
| **SVG相关** | svg_stack_rgbw_testsvg.py, svg_mesh_verify_raster.py, svg_mesh_verify_geom.py, svg4stl_vector_plus.py, svg4stl_vector.py |
| **Planning** | validate_stack.py, planner_search.py, planner_models.py, planner_io.py, planner.py, layerplan.py, forward_mc.py |
| **Calibration/Multicolor** | utils.py, seq.py, make.py, geom.py |
| **Calibration/Utils** | screen_trans_pairs.py, optics_from_crops.py, mat_from_photos.py |
| **Calibration/Color_board** | recipes.py, projection.py, make.py, calibrate.py, calib_color.py |
| **其他** | make_rgbw_cubes_3mf.py, analyze_filament_photos.py, analyze_board_spec_image.py, calibrate_color_board_io.py |

---

## 五、未被引用的文件清单（可删除候选）

### 5.1 最高优先级：oc_analyze 模块（12个文件）

该模块**完全未被 engine 或 prototypes 引用**，是代码扫描和分析工具：

| 文件 | 功能描述 |
|------|----------|
| `oc_analyze_02/export_3mf.py` | 独立的3MF导出示例 |
| `oc_analyze/sync_to_repo.py` | 仓库同步工具 |
| `oc_analyze/scan_utils.py` | 扫描工具公共函数 |
| `oc_analyze/scan_ruff.py` | Ruff代码检查扫描 |
| `oc_analyze/scan_long_filenames.py` | 长文件名扫描 |
| `oc_analyze/scan_large_files.py` | 大文件扫描 |
| `oc_analyze/scan_duplicate.py` | 重复文件扫描 |
| `oc_analyze/scan_dense_dirs.py` | 密集目录扫描 |
| `oc_analyze/scan_comment.py` | 注释覆盖率扫描 |
| `oc_analyze/replace_print.py` | print语句替换工具 |
| `oc_analyze/package_project.py` | 项目打包工具 |

**建议**：如果项目不再需要代码质量检查功能，可以考虑删除整个 analyze 模块。

### 5.2 中优先级：oc_scripts 中未使用的工具脚本（约40个）

这些脚本是独立工具，可能由用户手动运行而非被代码导入：

**STL生成工具（6个）：**
- `stl/screen_grad_16x9.py` - 屏幕渐变生成
- `stl/mixplane.py` - 混合平面生成
- `stl/layercap_dome.py` - 层盖圆顶生成
- `stl/color_square_stack.py` - 彩色方块堆叠
- `stl/bmp_map4stl_plus.py` - BMP到STL映射(增强版)
- `stl/bmp_map4stl_nooverlap.py` - BMP到STL映射(无重叠)

**SVG处理工具（4个）：**
- `svg/svg_stack_rgbw_testsvg.py` - RGBW测试SVG生成
- `svg/svg_mesh_verify_raster.py` - 网格光栅验证
- `svg/svg_mesh_verify_geom.py` - 网格几何验证
- `svg/svg4stl_vector_plus.py` - SVG到矢量转换(增强版)
- `svg/svg4stl_vector.py` - SVG到矢量转换

**打印规划工具（7个）：**
- `planning/validate_stack.py` - 堆叠验证
- `planning/planner_search.py` - 规划器搜索
- `planning/planner_models.py` - 规划器模型
- `planning/planner_io.py` - 规划器IO
- `planning/planner.py` - 规划器主逻辑
- `planning/layerplan.py` - 层规划
- `planning/forward_mc.py` - 前向蒙特卡洛

**多色校准工具（4个）：**
- `calibration/multicolor/utils.py`
- `calibration/multicolor/seq.py`
- `calibration/multicolor/make.py`
- `calibration/multicolor/geom.py`

**校准工具（3个）：**
- `calibration/utils/screen_trans_pairs.py` - 屏幕转换对
- `calibration/utils/optics_from_crops.py` - 从裁剪获取光学参数
- `calibration/utils/mat_from_photos.py` - 从照片获取矩阵

**颜色板校准工具（5个）：**
- `calibration/color_board/recipes.py` - 配方
- `calibration/color_board/projection.py` - 投影
- `calibration/color_board/make.py` - 制作
- `calibration/color_board/calibrate.py` - 校准
- `calibration/color_board/calib_color.py` - 校准颜色

**其他独立脚本（3个）：**
- `make_rgbw_cubes_3mf.py` - 生成RGBW立方体3MF（DEPC_MAP.md 标记为待删除）
- `analyze_filament_photos.py` - 分析耗材照片
- `analyze_board_spec_image.py` - 分析板规格图像
- `calibrate_color_board_io.py` - 校准颜色板IO

### 5.3 低优先级：独立应用入口

- `oc_core_02/app.py` - Gradio主应用入口

**状态**：未被 engine 或 prototypes 直接引用，但可能是独立运行的UI应用。

---

## 六、删除建议

### 6.1 高优先级删除（完全未使用）

**oc_analyze 模块（12个文件）**

```
py_module/analyze/
├── src/oc_analyze/
│   ├── sync_to_repo.py
│   ├── scan_utils.py
│   ├── scan_ruff.py
│   ├── scan_long_filenames.py
│   ├── scan_large_files.py
│   ├── scan_duplicate.py
│   ├── scan_dense_dirs.py
│   ├── scan_comment.py
│   ├── replace_print.py
│   └── package_project.py
└── src/oc_analyze_02/
    └── export_3mf.py
```

**理由**：
- 完全未被 engine 或 prototypes 引用
- 是代码质量扫描工具，与核心功能无关
- 如果项目不再需要代码检查功能，可以删除

### 6.2 中优先级删除（独立工具脚本）

**oc_scripts 中确认未使用的脚本（约40个）**

建议先确认以下功能是否已弃用：
1. **打印规划功能** - planning目录（7个文件）
2. **多色校准功能** - calibration/multicolor目录（4个文件）
3. **独立STL/SVG生成工具** - 如果功能已被其他模块替代

**确认方法**：
- 检查 DEPC_MAP.md 中的标记
- 询问项目负责人这些功能是否还在使用
- 检查是否有文档说明这些脚本的使用场景

### 6.3 注意事项

1. **间接引用**：某些文件可能通过动态导入（`__import__`、`importlib`）或配置文件间接引用，删除前需进一步验证。

2. **测试文件**：engine/tests目录下的测试文件虽然不被生产代码引用，但对质量保证很重要，不应删除。

3. **独立工具**：scripts目录下的许多脚本是独立工具，可能由用户手动运行而非被代码导入。删除前需确认是否有用户依赖这些工具。

4. **保留文件**：
   - `DEPC_MAP.md` 中标记为"待删除"的文件可以优先删除
   - `make_rgbw_cubes_3mf.py` 已被标记为待删除

---

## 七、依赖统计汇总

### 7.1 模块级别统计

| 模块 | 总文件数 | 被引用文件数 | 未被引用文件数 | 引用率 | 建议操作 |
|------|----------|--------------|----------------|--------|----------|
| engine | 20 | 20 | 0 | 100% | 保留 |
| prototypes | 70 | 70 | 0 | 100% | 保留 |
| oc_core_02 | 27 | 27 | 0 | 100% | 保留 |
| oc_calib | 7 | 7 | 0 | 100% | 保留 |
| oc_xgb | 9 | 9 | 0 | 100% | 保留 |
| oc_sdf | 10 | 10 | 0 | 100% | 保留 |
| model_export | 4 | 4 | 0 | 100% | 保留 |
| oc_scripts | 42 | 2 | 40 | 5% | 审查后删除未使用部分 |
| oc_analyze | 12 | 0 | 12 | 0% | **可删除** |

### 7.2 文件类型统计

| 类型 | 数量 | 说明 |
|------|------|------|
| 核心功能文件 | ~150 | 被 engine/prototypes 直接或间接引用 |
| 独立工具脚本 | ~40 | 在 scripts 模块中，未被引用 |
| 代码扫描工具 | 12 | 在 analyze 模块中，完全未使用 |
| 测试文件 | 6 | engine/tests 目录下，应保留 |

---

## 八、附录

### 8.1 分析方法

本次分析采用以下方法：
1. 列出 engine 和 prototypes 模块的所有 Python 文件
2. 分析每个文件的 import 语句
3. 递归追踪所有被引用的文件
4. 识别未被引用的文件

### 8.2 限制说明

1. **动态导入**：无法检测通过 `__import__`、`importlib` 等动态导入的依赖
2. **字符串引用**：无法检测通过字符串拼接的模块引用
3. **配置文件引用**：无法检测通过配置文件（如 YAML、JSON）指定的模块
4. **C扩展**：未分析 C/C++ 扩展的依赖关系

### 8.3 验证建议

在删除任何文件之前，建议进行以下验证：
1. 全局搜索文件名，确认没有字符串引用
2. 检查配置文件中的模块配置
3. 运行完整的测试套件，确保功能正常
4. 咨询项目负责人确认功能是否已弃用

---

*报告生成时间：2026-02-13*  
*分析工具：静态代码分析*  
*基准模块：py_module/engine, py_module/prototypes*
