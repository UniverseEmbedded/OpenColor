# gen_vector_01 (矢量化器)

优化目标：

1. 减少产生的svg和png输入的偏差
2. 输出的svg的顶点越少越好，边长越少越好

## 功能
这个原型实现了"纯 vtracer"矢量化管线，将位图掩码转换为SVG矢量多边形。支持共享边界重采样和质量检测。

## 如何运行
```bash
# 默认模式（启用重采样）
pixi run python -m oc_prototypes_02.gen_vector_01.main

# 禁用重采样
pixi run python -m oc_prototypes_02.gen_vector_01.main --no-resample

# 指定输入目录
pixi run python -m oc_prototypes_02.gen_vector_01.main --input <path/to/gen_masks_01/out>
```

## 实现逻辑
1. **输入同步**: 从 `gen_masks_01/out/02_masks` 同步掩码文件
2. **矢量化**: 调用 `vtracer` 库对 Mask 进行矢量化，强制使用 `polygon` 模式（直线段）
3. **互斥裁剪**: 强制执行色块间互斥，防止vtracer原始输出重叠
4. **重采样**（可选）: 对共享边界进行整体优化，减少几何误差
5. **背景填充**: 根据全局参考边界计算背景色块
6. **质量检测**: 检测位图和矢量阶段的覆盖/空缺/重叠问题

## 参数

- `--input`: 指定 `gen_masks_01` 的输出目录（默认自动寻找）
- `--resample`: 启用共享边界重采样（默认启用）
- `--no-resample`: 禁用共享边界重采样

## 输出

输出目录：`out/gen_vector_01/`

### 同步的掩码
- `02_masks/` - 从输入同步的掩码文件

### 矢量化结果
- `04_polys/` - 最终的SVG多边形文件
  - `L{层号}_{耗材名}_poly_final.svg` - 各层各耗材的最终多边形
  - `L{层号}_{耗材名}_poly_raster.png` - 1x硬栅格化结果
  - `L{层号}_{耗材名}_poly_raster_4x.png` - 4x软栅格化结果（抗锯齿）
  - `L{层号}_poly_4x_preview.png` - 层彩色预览图（4x）
  - `full_mask_ref_poly_final.svg` - 全局参考边界

### 清单文件
- `manifest.json` - 包含vtracer参数、板子尺寸、层数、耗材列表等

## 质量检测

模块会自动执行两层质量检测：

### 位图阶段检测
- 检测掩码间的重叠区域
- 检测相对于full_mask的空缺区域
- 输出统计信息

### 矢量阶段检测（4x）
- 使用软栅格化（抗锯齿）进行更精确的检测
- 检测矢量化后的重叠和空缺
- 生成可视化报告

## vtracer参数

- `mode`: polygon（强制直线段模式）
- `filter_speckle`: 0（不过滤小斑点）
- `corner_threshold`: 60（角点检测阈值）
- `length_threshold`: 4（线段长度阈值）

## 依赖

- 需要 `gen_masks_01` 生成的掩码文件和 `mask_manifest.json`
- 依赖 `vtracer` 库进行矢量化
- 依赖 `shapely` 进行多边形操作
