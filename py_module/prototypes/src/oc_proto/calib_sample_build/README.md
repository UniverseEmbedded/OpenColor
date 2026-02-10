# calib_sample_build_01

## 功能
负责将"矫正后的色盘图"、"色盘规格 spec"汇总成一个可训练的数据集。支持批量处理多个色盘，并自动进行黑白场校准。

## 运行
```bash
# 批量自动扫描模式（默认）
pixi run python -m oc_prototypes_02.calib_sample_build_01.main

# 单次处理模式
pixi run python -m oc_prototypes_02.calib_sample_build_01.main --warped <path> --spec <path> --patched <path>
```

## 批量处理流程
1. 优先处理 `Board_A` 获取全局黑白参考点
2. 使用该参考点校准所有其他色盘
3. 为每个色盘生成独立的数据集

## 功能说明
1. **网格切分**: 读取 `warped` 图，根据 `spec` 推断 `rows/cols`，将图片均匀切分成网格
2. **采样处理**: 对每个格子进行采样：
   - **ROI 确定**: 默认取格子中心区域进行均值采样
   - **颜色提取**: 从 ROI 区域取均值色 (BGR→RGB)
3. **数据关联**: 从 `spec` 中提取 `target_rgb` 和 `recipe` 配方信息
4. **黑白校准**: 自动寻找纯白/纯黑参考格子进行线性校准
5. **重复检测**: 检查是否存在物理属性完全相同的重复格子

## 输入
- `--photos-root`: 包含多个 Board_XXX 目录的根路径（默认：`data/calibration/photos_02`）
- `--warped`: 透视矫正后的图片路径（单次模式）
- `--spec`: 色盘规格 `board_spec.json` 路径（单次模式）
- `--patched`: `observation_patched.json` 路径（可选，单次模式）

## 输出（每个色盘）
- `out/Board_X/dataset_cells.json` - 每格的详细记录数据集
- `out/Board_X/sample_preview.png` - 采样 ROI 预览图 (绿=启用)
- `out/Board_X/preview_before_calib.png` - 校准前预览图
- `out/Board_X/preview_after_calib.png` - 校准后预览图
- `out/Board_X/first_layer.png` - 首层材质可视化
- `out/Board_X/enabled_mask.png` - 启用格子掩码
- `out/Board_X/manifest.json` - 包含校准参数和统计信息

## 坐标映射说明
- 物理摆放逻辑：(0,0) 对应图像的右上角
- 因此水平方向需要镜像翻转以正确映射
- 支持15x15逻辑网格在17x17物理网格中的居中偏移
