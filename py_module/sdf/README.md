# OpenColor SDF 模块

基于符号距离场（Signed Distance Field, SDF）的位图到3D网格转换算法模块。

## 简介

本模块实现了从2D位图到3D可打印网格的完整转换流程，核心特点：

- **SDF 轮廓重建**: 使用符号距离场算法从位图提取平滑、高质量的轮廓
- **多层挤出**: 支持多材料分层打印，每层独立生成几何体
- **互斥裁剪**: 自动处理不同材料间的边界，避免重叠和缝隙
- **多种轮廓后端**: 支持 bitmap2svg、vtracer、OpenCV 等多种轮廓提取方案

## 核心功能

### 1. 数据准备 (`sdf_data_prep`)
- 图像加载和预处理
- LUT（查找表）匹配
- 层体积数据生成

### 2. 多边形生成 (`sdf_polygon_gen`)
- 从位图 mask 提取轮廓
- SDF 平滑和简化
- 多边形裁剪和布尔运算

### 3. 网格挤出 (`sdf_extrude`)
- 2D 多边形拉伸为 3D 网格
- 层间对齐和合并
- 网格清理和优化

### 4. 导出 (`sdf_export`)
- STL 格式导出
- 3MF 多材料项目导出
- 质量报告生成

### 5. IO 工具 (`sdf_io`)
- SVG 文件加载和保存
- 几何对象栅格化
- C++ 加速支持

## 目录结构

```
src/oc_sdf/
├── __init__.py           # 包初始化
├── pipeline.py           # 主处理管道（bitmap_pipeline_sdf）
├── types.py              # 类型定义（SDFParams）
├── data_prep.py          # 数据准备
├── polygon_gen.py        # 多边形生成
├── extrude.py            # 网格挤出
├── export.py             # 文件导出
├── io.py                 # SVG/几何 IO
├── utils.py              # 工具函数
└── quality.py            # 质量分析
```

## 使用方法

### 基础用法

```python
from pathlib import Path
from oc_sdf.pipeline import process_bitmap_sdf
from oc_sdf.types import SDFParams
from bitmap_pipeline import BitmapParams

# 配置参数
bitmap_params = BitmapParams(
    color_system="RYBW",
    nozzle_width_mm=0.42,
    target_width_mm=60.0,
    layer_height_mm=0.2,
    n_layers=5,
)

sdf_params = SDFParams(
    smooth_sigma=1.5,
    simplify_eps=0.2,
    grid_scale=4,
    contour_backend="auto",
)

# 执行处理
results = process_bitmap_sdf(
    image_path="input.png",
    lut_path="lut.npy",
    params=bitmap_params,
    sdf_params=sdf_params,
    out_dir=Path("./output"),
)

# 输出包含:
# - results["preview_2d"]: 2D 预览图路径
# - results["preview_3d"]: 3D 预览 GLB 路径
# - results["stl_*"]: 各材料的 STL 文件路径
# - results["bambu_3mf"]: 3MF 项目文件路径（如果配置）
```

### 高级配置

```python
from oc_sdf.types import SDFParams

# 针对精细图形的配置
fine_params = SDFParams(
    smooth_sigma=1.2,           # 较小的平滑半径，保留更多细节
    simplify_eps=0.1,           # 更保守的简化
    grid_scale=4,               # 高分辨率网格
    contour_backend="vtracer",  # 使用 vtracer 获得更好曲线
    vtracer_mode="polygon",
    vtracer_corner_threshold=60,
)

# 针对大面积填充的配置
fill_params = SDFParams(
    smooth_sigma=2.0,           # 更大的平滑半径
    simplify_eps=0.5,           # 更激进的简化
    grid_scale=2,               # 降低分辨率以提高速度
    contour_backend="cv2",      # 使用 OpenCV 快速提取
)
```

## 依赖说明

### 必需依赖
- `numpy`: 数值计算
- `pillow`: 图像处理
- `trimesh`: 3D 网格操作
- `shapely`: 2D 几何运算
- `opencv-python`: 轮廓提取
- `svgpathtools`: SVG 解析
- `scipy`: 科学计算

### 可选依赖
- `vtracer`: 高质量的位图矢量化
- `rgbw_bitmap2svg`: 专用位图到 SVG 转换

安装可选依赖：
```bash
pip install oc_sdf[vtracer,bitmap2svg]
```

## 算法流程

```
输入位图
    ↓
[数据准备] → LUT 匹配 → 生成层 mask
    ↓
[多边形生成] → SDF 平滑 → 轮廓提取 → 多边形化
    ↓
[互斥裁剪] → 层间占用计算 → 边界裁剪
    ↓
[网格挤出] → 2D→3D 拉伸 → 层合并
    ↓
[导出] → STL / 3MF / 预览图
```

## 输出目录结构

```
output/
├── 00_input/               # 输入文件备份
│   ├── input.png
│   ├── lut.npy
│   └── params.json
├── 02_masks/               # 层 mask 图像
├── 03_vtracer/             # vtracer 中间输出（如使用）
├── 04_polys/               # 多边形 SVG
├── 05_gap/                 # 间隙填充数据
├── 06_export/              # 最终导出文件
├── preview_2d.png          # 2D 颜色预览
├── preview_3d.glb          # 3D 网格预览
├── mesh_report.json        # 网格质量报告
└── *_bambu.3mf             # Bambu Studio 项目文件
```

## 注意事项

1. **内存使用**: SDF 计算在高分辨率（grid_scale > 4）时可能消耗大量内存，建议根据图像尺寸调整
2. **轮廓质量**: 不同后端适用于不同场景，建议根据图形特点选择
3. **互斥裁剪**: 启用后会增加计算时间，但能确保不同材料间无重叠

## 开发环境

使用 [pixi](https://pixi.sh/) 管理：
```bash
pixi shell
```

运行测试：
```bash
pixi run python -m pytest tests/
```
