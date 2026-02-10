# gen_model_exporter_01 (模型导出器)

## 功能
负责从 `gen_vector_01` 生成的 SVG 多边形中重新构建 3D 网格，执行体积质量分析，并导出为 STL 和 3MF 格式。

## 运行
```bash
# 默认模式（C++后端）
pixi run python -m oc_prototypes_02.gen_model_exporter_01.main

# 使用Python后端
pixi run python -m oc_prototypes_02.gen_model_exporter_01.main --backend python

# 启用3D分析（较慢）
pixi run python -m oc_prototypes_02.gen_model_exporter_01.main --enable-3d-analysis

# 启用STL-多边形对比（较慢）
pixi run python -m oc_prototypes_02.gen_model_exporter_01.main --enable-compare

# 导出单层调试STL
pixi run python -m oc_prototypes_02.gen_model_exporter_01.main --debug-single-layer
```

## 功能说明
1. **SVG加载**: 读取 `gen_vector_01/out/04_polys` 下的 SVG 文件
2. **3D挤出**: 根据 `manifest.json` 中的层高和层数参数，将 2D 多边形挤出为 3D Mesh
3. **体积分析**: 计算重叠体积、空隙体积和总体积
4. **3D布尔运算**（可选）: 使用C++或Python进行精确的3D体积分析
5. **导出格式**:
   - **STL**: 为每个插槽（Slot）生成独立的 STL 文件
   - **3MF**: 将所有插槽合并为一个 3MF 文件，并保留预览颜色信息

## 参数

- `vtracer_out`: vtracer输出目录路径（位置参数，可选）
- `--backend`: 选择后端，`python` 或 `cpp`（默认: cpp）
- `--debug-single-layer`: 导出每层单独的STL文件（很慢，用于调试）
- `--enable-3d-analysis`: 启用3D布尔运算分析（很慢）
- `--enable-compare`: 启用STL-多边形对比（很慢）

## 输出

输出目录：`out/gen_model_exporter_01/{backend}/`

### 3D模型文件
- `06_export/{耗材名}.stl` - 各耗材的独立STL文件
- `06_export/model_ExportSystem_standard.3mf` - 合并的3MF文件

### 分析报告
- `06_export/volume_analysis_report.json` - 体积质量分析报告
  - `total_model_vol_mm3`: 总体积
  - `total_overlap_vol_mm3`: 重叠体积
  - `total_gap_vol_mm3`: 空隙体积
  - `overlap_ratio`: 重叠占比
  - `gap_ratio`: 空隙占比
  - `total_overlap_vol_3d_mm3`: 3D重叠体积（如启用3D分析）
  - `total_gap_vol_3d_mm3`: 3D空隙体积（如启用3D分析）

### 可视化
- `05_layer_total_contours/` - 每层总轮廓可视化（矢量阶段）
- `07_stl_poly_compare/` - STL与多边形对比结果（如启用对比）
- `06_export/debug_single_layer/` - 单层调试STL（如启用）

## 体积质量分析

### 2.5D分析（默认）
基于多边形面积计算：
- 重叠：同一层内多边形交集面积 × 层高
- 空隙：全局边界与层并集之差面积 × 层高

### 3D分析（可选，较慢）
使用布尔运算进行精确计算：
- **C++后端**: 使用 `opencolor_geometry` 模块的 `manifold_union` 和 `manifold_difference`
- **Python后端**: 使用 `trimesh` 的 `manifold` 引擎

## 后端选择

### C++后端（默认）
- 使用 `opencolor_geometry.pyd` 模块
- 基于 Manifold 库的高性能布尔运算
- 支持多线程（nogil版本）

### Python后端
- 使用 `trimesh` 库
- 依赖 `manifold` 引擎进行布尔运算
- 兼容性更好，但速度较慢

## 依赖

- 需要 `gen_vector_01` 生成的 SVG 多边形和 `manifest.json`
- 需要 `lib3mf` 库进行3MF导出
- 可选：C++几何模块 `opencolor_geometry`（用于加速3D分析）

## 互斥保证

模块在重建过程中执行防御性互斥裁剪：
- 即使vtracer阶段已保证互斥，仍作为最后一道防线
- 按顺序处理耗材，每个新色块与已占有区域求差
- 确保最终输出的STL文件间无重叠
