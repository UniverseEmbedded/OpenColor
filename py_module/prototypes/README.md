# OpenColor Prototypes 模块使用指南

本文档介绍 `oc_proto` 包中各模块的功能和调用方式。

## 模块概述

| 模块名 | 功能描述 | 入口文件 |
|--------|----------|----------|
| `calib_board_gen` | 生成多色校准板规格和3MF打印文件 | `main.py` |
| `calib_photo_warp` | 校准照片透视变换工具 | `app.py` |
| `calib_sample_build` | 从校准照片提取颜色样本数据 | `main.py` |
| `calib_color_rts` | 颜色校准模型训练和评估 | `main.py` |
| `gen_masks` | 从图像生成打印掩码 | `main.py` |
| `gen_vector` | 掩码矢量化转换为SVG | `main.py` |
| `gen_3mf` | 将矢量多边形导出为3MF模型 | `main.py` |
| `common` | 共享工具函数和类 | 无独立入口 |

## 完整工作流程

```
校准流程:
calib_board_gen → calib_photo_warp → calib_sample_build → calib_color_rts

生成流程:
gen_masks → gen_vector → gen_3mf
```

---

## 1. calib_board_gen (校准板生成器)

生成多色校准板规格文件和3MF打印文件。

### 命令行调用

```bash
# 使用默认配置生成8色校准板
pixi run p2-calib-board-gen

# 生成2个校准板
pixi run p2-calib-board-gen --num_boards 2

# 使用4色配置(RYBW)
pixi run p2-calib-board-gen --profile rybw

# 使用3色配置(RGB)
pixi run p2-calib-board-gen --profile rgb

# 自定义格子尺寸和行列数
pixi run p2-calib-board-gen --cell-size 3.0 --rows 16 --cols 16

# 使用自定义颜色配置文件
pixi run p2-calib-board-gen --profile-file my_colors.json

# 命令行指定颜色
pixi run p2-calib-board-gen --colors "Red:255,0,0" "Green:0,255,0" "Blue:0,0,255"
```

### Python API 调用

```python
from oc_proto.calib_board_gen.main import run
from oc_proto.calib_board_gen.color_profiles import get_profile_manager

# 使用默认8色配置
run(num_boards=2)

# 使用4色配置
manager = get_profile_manager()
profile = manager.get_profile("rybw")
run(num_boards=1, profile=profile)

# 自定义参数
run(
    num_boards=1,
    profile=profile,
    layer_height_mm=0.12,
    cell_size_mm=4.0,
    data_rows=32,
    data_cols=32
)
```

### 可用预设配置

- `rgb` - RGB三原色(3色)
- `rybw` - RYBW四色(4色)
- `rgbw` - RGBW四色(4色)
- `rgbwk` - RGBWK五色(5色)
- `full_8` - 完整8色(8色，默认)

---

## 2. calib_photo_warp (照片透视变换)

对校准板照片进行透视校正。

### 命令行调用

```bash
# 启动交互式UI
pixi run p2-calib-photo-warp-ui

# 使用指定配置文件重建
pixi run p2-calib-photo-warp --rebuild --warp-json data/calibration/photos/warp-01.json
```

### Python API 调用

```python
from oc_proto.calib_photo_warp.app import main

# 启动交互式应用
main()
```

---

## 3. calib_sample_build (样本构建)

从校准照片中提取颜色样本数据，生成数据集文件。

### 命令行调用

```bash
# 批量自动扫描模式（默认）
pixi run p2-calib-sample-build

# 单次处理模式
pixi run python -m oc_proto.calib_sample_build.main \
    --warped path/to/board_warped.png \
    --spec path/to/board_spec.json \
    --patched path/to/observation_patched.json
```

### Python API 调用

```python
from oc_proto.calib_sample_build.main import run

# 批量处理
run()

# 单次处理
run(
    warped_path="path/to/board_warped.png",
    spec_path="path/to/board_spec.json",
    patched_path="path/to/observation_patched.json"
)
```

---

## 4. calib_color_rts (颜色校准模型拟合)

训练颜色校准模型并评估性能。

### 命令行调用

```bash
# 使用默认数据集训练
pixi run p2-calib-color-rts

# 指定数据集
pixi run python -m oc_proto.calib_color_rts.main \
    --dataset data/dataset_cells.json \
    --out-dir out/calib_model

# 使用RTS光学模型（推荐）
pixi run python -m oc_proto.calib_color_rts.main --optical-model rts

# 禁用Vulkan加速
pixi run python -m oc_proto.calib_color_rts.main --no-vulkan

# 调整优化参数
pixi run python -m oc_proto.calib_color_rts.main \
    --opt-steps 500 \
    --opt-reg 0.01 \
    --gpr-noise 0.1

# 优化Saunderson参数
pixi run python -m oc_proto.calib_color_rts.main --optimize-k

# 启用训练集记忆模式（仅用于调试）
pixi run python -m oc_proto.calib_color_rts.main --memorize-mode train
```

### Python API 调用

```python
from oc_proto.calib_color_rts.main import run
from oc_proto.calib_color_rts.cli import FitArgs

# 使用默认参数
run()

# 自定义参数
args = FitArgs(
    dataset_path="data/dataset_cells.json",
    out_dir="out/calib_model",
    n_layers=5,
    opt_steps=500,
    optical_model="rts",
    use_vulkan=True
)
run(args=args)
```

---

## 5. gen_masks (掩码生成器)

从输入图像生成打印掩码。

### 命令行调用

```bash
# 使用默认图像(龙娘.png)
pixi run p2-gen-masks

# 指定图像
pixi run p2-gen-masks data/image/龙娘.png

# 指定输出目录
pixi run p2-gen-masks data/image/龙娘.png --output-dir out/masks

# 关闭超分辨率（加快处理）
pixi run p2-gen-masks --superres-off

# 启用首层联合优化
pixi run p2-gen-masks --joint-l0-enabled --joint-l0-passes 2

# 使用后处理模式
pixi run p2-gen-masks --postprocess island
pixi run p2-gen-masks --postprocess conv
pixi run p2-gen-masks --postprocess guided

# 启用锐化
pixi run p2-gen-masks --sharpen --sharpen-strength 1.5

# 自定义物理尺寸和层高
pixi run p2-gen-masks --board-mm 60.0 --layer-height-mm 0.12
```

### Python API 调用

```python
from oc_proto.gen_masks.main import run

# 使用默认图像
result = run()

# 指定图像
result = run(image_path="data/image/龙娘.png")

# 完整参数
result = run(
    image_path="data/image/龙娘.png",
    output_dir="out/masks",
    layer0_bias_enabled=True,
    superres_enabled=False,
    superres_scale=2,
    sharpening_enabled=True,
    sharpening_strength=1.5,
    postprocess_mode="island",
    board_mm=60.0,
    layer_height_mm=0.12,
    joint_l0_enabled=True,
    joint_l0_passes=2
)
```

---

## 6. gen_vector (矢量化器)

将掩码图像转换为SVG矢量多边形。

### 命令行调用

```bash
# 使用默认输入（自动寻找最新gen_masks输出）
pixi run p2-gen-vtracer

# 指定输入目录
pixi run python -m oc_proto.gen_vector.main --input out/gen_masks/xxx

# 使用vtracer后端（默认）
pixi run python -m oc_proto.gen_vector.main --vector-backend vtracer

# 使用OpenCV后端
pixi run python -m oc_proto.gen_vector.main --vector-backend cv2

# 禁用共享边界重采样
pixi run python -m oc_proto.gen_vector.main --no-resample

# 使用Python实现（而非C++）
pixi run python -m oc_proto.gen_vector.main --impl python

# 生成预览图
pixi run python -m oc_proto.gen_vector.main --preview-4x

# 调整并行任务数
pixi run python -m oc_proto.gen_vector.main --jobs 4 --union-jobs 2
```

### Python API 调用

```python
from oc_proto.gen_vector.main import run

# 使用默认输入
run()

# 指定输入
run(mask_input_dir="out/gen_masks/xxx")

# 完整参数
run(
    mask_input_dir="out/gen_masks/xxx",
    resample=True,
    impl="cpp",
    progress=True,
    jobs=0,  # 0表示自动
    union_jobs=0,
    preview_4x=True
)
```

---

## 7. gen_3mf (3MF模型导出器)

将矢量多边形转换为3D网格并导出为3MF文件。

### 命令行调用

```bash
# 使用默认输入（自动寻找最新gen_vector输出）
pixi run p2-gen-3mf

# 指定输入目录
pixi run python -m oc_proto.gen_3mf.main --input out/gen_vector/xxx

# 禁用C++加速
pixi run python -m oc_proto.gen_3mf.main --no-cpp

# 仅禁用C++布尔运算
pixi run python -m oc_proto.gen_3mf.main --no-cpp-union

# 启用体素修复
pixi run python -m oc_proto.gen_3mf.main --voxel-repair

# 禁用网格修复
pixi run python -m oc_proto.gen_3mf.main --no-repair

# 禁用网格简化
pixi run python -m oc_proto.gen_3mf.main --no-simplify

# 仅导出STL（不导出3MF）
pixi run python -m oc_proto.gen_3mf.main --no-3mf

# 仅导出3MF（不导出STL）
pixi run python -m oc_proto.gen_3mf.main --no-stl

# 调整并行任务数
pixi run python -m oc_proto.gen_3mf.main --jobs 4
```

### Python API 调用

```python
from oc_proto.gen_3mf.main import run

# 使用默认输入
run()

# 指定输入
run(poly_input_dir="out/gen_vector/xxx")

# 完整参数
run(
    poly_input_dir="out/gen_vector/xxx",
    use_cpp=True,
    use_cpp_union=True,
    repair=True,
    simplify=True,
    voxel_repair=False,
    export_stl=True,
    export_3mf=True,
    jobs=0,  # 0表示自动
    progress=True
)
```

---

## 完整示例：从图像到3MF

### 命令行方式

```bash
# 步骤1: 生成掩码
pixi run p2-gen-masks data/image/龙娘.png --superres-off --postprocess island

# 步骤2: 矢量化（自动寻找上一步输出）
pixi run p2-gen-vtracer

# 步骤3: 导出3MF（自动寻找上一步输出）
pixi run p2-gen-3mf
```

### Python方式

```python
from oc_proto.gen_masks.main import run as gen_masks
from oc_proto.gen_vector.main import run as gen_vector
from oc_proto.gen_3mf.main import run as gen_3mf

# 步骤1: 生成掩码
masks_result = gen_masks(
    image_path="data/image/龙娘.png",
    superres_enabled=False,
    postprocess_mode="island"
)
mask_dir = masks_result["output_dir"]

# 步骤2: 矢量化
vector_result = gen_vector(mask_input_dir=mask_dir)
vector_dir = vector_result["output_dir"]

# 步骤3: 导出3MF
gen_3mf(poly_input_dir=vector_dir)
```

---

## 完整示例：校准流程

### 命令行方式

```bash
# 步骤1: 生成校准板
pixi run p2-calib-board-gen --num_boards 2 --profile rybw

# 步骤2: 照片透视变换（交互式）
pixi run p2-calib-photo-warp-ui

# 步骤3: 构建样本数据集
pixi run p2-calib-sample-build

# 步骤4: 训练颜色模型
pixi run p2-calib-color-rts
```

### Python方式

```python
from oc_proto.calib_board_gen.main import run as gen_board
from oc_proto.calib_photo_warp.app import main as warp_app
from oc_proto.calib_sample_build.main import run as build_samples
from oc_proto.calib_color_rts.main import run as train_model

# 步骤1: 生成校准板
gen_board(num_boards=2, profile="rybw")

# 步骤2: 照片透视变换（交互式）
warp_app()

# 步骤3: 构建样本数据集
build_samples()

# 步骤4: 训练颜色模型
train_model()
```

---

## 快捷命令汇总

| 任务 | 快捷命令 |
|------|----------|
| 生成校准板 | `pixi run p2-calib-board-gen` |
| 照片透视变换 | `pixi run p2-calib-photo-warp-ui` |
| 构建样本 | `pixi run p2-calib-sample-build` |
| 训练颜色模型 | `pixi run p2-calib-color-rts` |
| 生成掩码 | `pixi run p2-gen-masks` |
| 矢量化 | `pixi run p2-gen-vtracer` |
| 导出3MF | `pixi run p2-gen-3mf` |
| 完整校准流程 | `pixi run p2-run-calib` |
| 完整生成流程 | `pixi run p2-run-gen` |
| 清理校准数据 | `pixi run p2-clean-calib` |
| 清理生成数据 | `pixi run p2-clean-gen` |
| 清理所有数据 | `pixi run p2-clean-all` |

---

## 注意事项

1. **依赖关系**: `gen_vector` 需要 `gen_masks` 的输出，`gen_3mf` 需要 `gen_vector` 的输出
2. **自动查找**: 如果不指定输入目录，模块会自动寻找最新的上游输出
3. **C++加速**: 默认启用C++加速，如遇问题可添加 `--no-cpp` 或 `--impl python` 禁用
4. **日志输出**: 所有模块使用 `loguru` 输出日志，可通过环境变量控制日志级别
