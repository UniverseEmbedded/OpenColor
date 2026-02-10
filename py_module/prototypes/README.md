# OpenColor Prototypes

管线，一个目录一个环节，在修改UI之前先修改管线来做原型测试

对于gen_model_exporter_01和gen_vector_01，要求如下：

1. 所有STL文件体积小于100MB
2. 脚本执行速度需要足够快，每个环节在300秒以下
3. 最终输出的所有STL之间不要出现任何重叠与空隙，中间产物svg也一样
4. SVG（以及STL）和位图的偏差（重叠与空隙）需要足够小，每一层的所有SVG的重叠和空隙也要足够小

---

该目录包含 OpenColor 项目的所有原型开发环节，版本号为 `oc_prototypes_02`。

## 目录结构

- `src/oc_prototypes_02/`: 原型源码目录
  - `calib_board_gen_01/`: 校准板生成 - 生成8色校准板的规格文件和3MF打印文件
  - `calib_photo_warp_01/`: 照片透视校正 - 通过AprilTag或手动4点进行色盘照片的透视校正
  - `calib_sample_build_01/`: 样本数据集构建 - 从校正后的照片提取颜色样本，生成训练数据集
  - `calib_color_model_fit_01/`: 色彩模型拟合 - 使用物理模型+GPR残差修正训练颜色预测模型
  - `gen_masks_01/`: 掩码生成 - 基于训练好的模型进行实时配色求解，生成各层掩码
  - `gen_vector_01/`: 矢量化 - 将掩码转换为SVG矢量多边形，执行重采样和质量检测
  - `gen_model_exporter_01/`: 模型导出 - 从SVG多边形重建3D网格，导出STL和3MF格式
  - `common/`: 通用工具模块 - 路径管理、清单记录、IO工具、规格适配器等
- `pyproject.toml`: 模块定义与依赖管理
- `pixi.toml`: 环境配置

## 核心设计原则

1. **环节闭环**: 每个子目录代表一个独立的算法或UI环节，可独立运行
2. **输入/输出分离**:
   - `data/`: 存放该环节所需的测试资源（由 `common.paths.ensure_data` 自动拷贝）
   - `out/`: 存放运行产物，包括 `manifest.json` 记录运行参数和结果
3. **独立运行**: 每个环节可通过 `python -m oc_prototypes_02.<folder>.main` 或 `app` 独立启动
4. **Manifest记录**: 所有环节运行后生成 `manifest.json` 以保证可追溯性
5. **数据流衔接**: 各环节通过文件系统衔接，上游环节的输出作为下游环节的输入

## 典型工作流程

```
calib_board_gen_01 → calib_photo_warp_01 → calib_sample_build_01 → calib_color_model_fit_01
                                                                              ↓
gen_model_exporter_01 ← gen_vector_01 ← gen_masks_01 ←——————————————————————┘
```

### 1. 生成校准板
```bash
pixi run python -m oc_prototypes_02.calib_board_gen_01.main --num_boards 2
```

### 2. 照片透视校正
```bash
pixi run python -m oc_prototypes_02.calib_photo_warp_01.app
```

### 3. 构建样本数据集
```bash
pixi run python -m oc_prototypes_02.calib_sample_build_01.main
```

### 4. 训练色彩模型
```bash
pixi run python -m oc_prototypes_02.calib_color_model_fit_01.main
```

### 5. 生成打印掩码
```bash
pixi run python -m oc_prototypes_02.gen_masks_01.main
```

### 6. 矢量化处理
```bash
pixi run python -m oc_prototypes_02.gen_vector_01.main
```

### 7. 导出3D模型
```bash
pixi run python -m oc_prototypes_02.gen_model_exporter_01.main
```

## 开发指南

- **新增原型**: 复制现有目录结构，包含 `main.py` 或 `app.py`、`README.md`、`__init__.py`
- **依赖管理**: 如果原型引入新库，请更新 `pyproject.toml`
- **资源管理**: 在 `common/paths.py` 的 `RESOURCES` 字典中注册新资源
- **数据流规范**: 每个环节应读取上游 `out/manifest.json`，输出本环节 `out/manifest.json`

## 模块依赖关系

| 模块 | 依赖上游 | 被下游依赖 |
|------|----------|------------|
| calib_board_gen_01 | - | calib_photo_warp_01, calib_sample_build_01 |
| calib_photo_warp_01 | calib_board_gen_01 | calib_sample_build_01 |
| calib_sample_build_01 | calib_photo_warp_01 | calib_color_model_fit_01 |
| calib_color_model_fit_01 | calib_sample_build_01 | gen_masks_01 |
| gen_masks_01 | calib_color_model_fit_01 | gen_vector_01 |
| gen_vector_01 | gen_masks_01 | gen_model_exporter_01 |
| gen_model_exporter_01 | gen_vector_01 | - |
