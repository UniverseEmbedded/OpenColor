# gen_masks_01 (掩码生成器)

## 功能
该模块负责从输入图像生成分层打印所需的掩码（Masks）。支持基于训练好的色彩模型进行实时配色求解，生成各层各耗材的掩码图和预览图。

## 主要功能

- **图像预处理**: 处理透明度和背景移除，应用镜像翻转（底面打印模式）
- **配色求解**: 使用 `calib_color_model_fit_01` 生成的物理GPR模型进行实时求解
- **掩码生成**: 为每一层生成各个通道的二值掩码图
- **预览生成**: 生成预测的最终打印效果预览图（正面/反面）
- **误差分析**: 计算并可视化预测与目标的色差（DeltaE76）

## 运行方式

```bash
pixi run python -m oc_prototypes_02.gen_masks_01.main
```

### 可选参数

- `--resource`: 指定要处理的资源 Key（默认为 `img_dragon_girl`）

## 输出内容

输出文件保存在 `out/gen_masks_01/` 目录下：

### 输入备份
- `00_input/` - 包含输入的图像和参数文件

### 预览图
- `01_preview_predicted.png` - 预测的打印效果预览（正面）
- `01_preview_back_predicted.png` - 反面预览（包含GPR修正）
- `01_preview_front_vs_back_sign.png` - 正反面差异对比图
- `01_error_heatmap_predicted.png` - 误差热力图
- `01_error_stats_predicted.json` - 误差统计信息

### 掩码文件
- `02_masks/` - 包含所有层的分色掩码图
  - `L{层号}_{耗材名}_mask.png` - 各层各耗材的掩码
  - `full_mask.png` - 整体掩码

### 层可视化
- `03_layer_total_contours/` - 每层总轮廓可视化（显示覆盖/空缺/重叠）
- `04_layer_solved_palette/` - 每层求解配色预览图

### 清单文件
- `mask_manifest.json` - 描述掩码信息的清单文件，供下游环节使用

## 求解器

模块强制使用C++加速求解器（`opencolor_solver.pyd`）：
- 基于物理GPR模型的正向预测
- Lab颜色空间中的最近邻搜索
- 支持配方去重和缓存优化

## 依赖

- 需要 `calib_color_model_fit_01` 生成的训练好的模型
- 自动查找 `calib_color_model_fit_01/out/*/color_model.json`
- 优先使用包含 `four_flux` 的模型

## 底面打印模式

由于采用底面打印（从第一层往上堆叠，最后翻转观看）：
- 输入图像会自动进行左右翻转（镜像）
- 求解后的配方会反转层序
- 预览图会翻转回成品正面方向用于对比
