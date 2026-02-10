# calib_color_model_fit_01 (物理GPR混合模型)

## 功能
该模块为校准板拟合颜色预测模型，使用**物理模型 + GPR残差修正**的混合架构。支持多色盘（A-H）数据加载和分别可视化。

## 模型架构

本版本使用**物理驱动的机器学习方法**：
- **物理模型**: Adding-Doubling算法（四通道模型）或 TMM（传输矩阵法）
  - 拟合耗材的光学参数（吸收系数 μ_a、散射系数 μ_s、各向异性因子 g）
  - 支持两种实现：NumPy (Python) 和 Vulkan (C++)
- **GPR残差修正**: 高斯过程回归修正物理模型的系统误差
  - 在 CIE Lab 空间（比 sRGB 更符合感知规律）进行残差学习
  - 分别为 L / a / b 三个通道训练独立的 GPR 模型

## 支持的算法和实现

| 算法 | 描述 | 实现 | 状态 |
|------|------|------|------|
| `rts` | RT-Stacking 模型 | NumPy (Python) | **推荐** |
| `four_flux` | 四通道 Adding-Doubling 模型 | NumPy (Python) / Vulkan (C++) | **已废弃** |
| `tmm` | 传输矩阵法（相干-非相干混合） | NumPy (Python) / Vulkan (C++) | **已废弃** |

> **注意**: `four_flux` 和 `tmm` 模型已废弃，仅保留用于历史对照。建议使用 `rts` 模型，它在黑色表现等方面有更好的稳定性。

## 运行

### 主训练流程

```bash
pixi run python -m oc_prototypes_02.calib_color_model_fit_01.main \
  --dataset <path/to/calib_sample_build_01/out/dataset_cells.json> \
  --out-dir <out>
```

#### 常用参数

- `--optical-model {four_flux,tmm,rts}` - 选择光学模型（默认: rts，推荐）
- `--no-vulkan` - 禁用 Vulkan 加速，使用 NumPy 实现
- `--n-layers` - 层数（默认: 5）
- `--opt-steps` - 光学参数优化步数（默认: 300）
- `--optimize-k` - 拟合时优化 Saunderson k1/k2 参数
- `--memorize-mode {train,off}` - 训练集"背诵"模式（默认: off）
- `--black-offset` - 黑场偏移量（0-255范围，默认0）
- `--white-offset` - 白场偏移量（0-255范围，默认0）

#### 示例

```bash
# 使用RTS模型（推荐）
pixi run python -m oc_prototypes_02.calib_color_model_fit_01.main --optical-model rts

# 优化 Saunderson 参数
pixi run python -m oc_prototypes_02.calib_color_model_fit_01.main --optimize-k

# 启用黑白校准
pixi run python -m oc_prototypes_02.calib_color_model_fit_01.main --black-offset 32 --white-offset 32

# 【已废弃】使用 TMM 模型 + Vulkan 加速
# pixi run python -m oc_prototypes_02.calib_color_model_fit_01.main --optical-model tmm

# 【已废弃】使用四通道模型 + NumPy 实现
# pixi run python -m oc_prototypes_02.calib_color_model_fit_01.main --optical-model four_flux --no-vulkan
```

### 数据准备

模块会自动从 `calib_sample_build_01/out` 同步数据集：
- 自动查找 `dataset_cells.json`（色盘A）和 `dataset_cells_B.json` 到 `dataset_cells_H.json`
- 如果缺失，会自动运行 `calib_board_gen_01` 生成规格并创建Mock数据
- 仅使用色盘A的真实数据训练，其他色盘用于评估对照

## 输出

### 主训练输出

- `color_model.json` - 元数据 + 模型文件名
- `phys_gpr_model.npz` - 物理GPR模型（包含光学参数和GPR残差模型）
- `fit_diagnostics.json` - 每个格子的详细诊断数据
- `fit_summary.json` - 全局统计摘要（误差、DeltaE等）
- `measured_board_*.png` - 各色盘测量值可视化
- `predicted_board_*.png` - 各色盘预测值可视化
- `error_heatmap_*.png` - 各色盘误差热力图
- `memorizer.json` - 训练集背诵映射（仅在 --memorize-mode=train 时生成）
- `manifest.json` - 运行元数据

### 模型文件格式

模型保存为 NPZ 格式，包含：
- `optical/` - 光学参数（mu_a, mu_s, g, n_layers, material_keys等）
- `gpr_L/`, `gpr_a/`, `gpr_b/` - 三个通道的GPR模型参数
- `feature_names` - 特征名称列表

## 模块说明

### 核心模块

| 文件 | 功能 |
|------|------|
| `main.py` | 主入口，解析参数并执行训练 |
| `cli.py` | 命令行接口，参数解析和默认数据准备 |
| `runner.py` | 训练运行器，执行完整拟合流程，支持多色盘 |
| `xgb_fit.py` | 物理GPR拟合核心，包含光学参数拟合和GPR训练 |
| `optical_model.py` | 四通道模型实现（NumPy/Vulkan） |
| `models/tmm_model.py` | TMM传输矩阵法模型实现 |
| `models/phys_gpr_model.py` | 物理GPR混合模型封装 |

### 数据IO模块

| 文件 | 功能 |
|------|------|
| `dataset_io.py` | 数据集加载和保存，支持黑白校准 |
| `model_io.py` | 模型序列化和反序列化 |
| `xgb_features.py` | 特征工程，层序列构建 |

### 诊断和可视化

| 文件 | 功能 |
|------|------|
| `diagnostics.py` | 诊断计算和可视化，支持多色盘 |
| `color_space.py` | 颜色空间转换（RGB/Lab） |

## 物理模型说明

### 四通道模型 (Four-Flux)

基于 Adding-Doubling 算法，考虑四个辐射通量：
- 前向直射 (I+)
- 后向直射 (I-)
- 前向漫射 (J+)
- 后向漫射 (J-)

物理参数：
- μ_a: 吸收系数
- μ_s: 散射系数
- g: 各向异性因子（Henyey-Greenstein相位函数）

### TMM 模型 (Transfer Matrix Method)

传输矩阵法，基于严格电磁理论：
- 相干模式：考虑干涉效应，适用于光滑界面、透明层
- 非相干模式：考虑强度叠加，适用于粗糙界面、散射层
- 混合模式：根据层厚和粗糙度自动选择

物理参数：
- n: 折射率（实部）
- k: 消光系数（虚部，与吸收相关）
- d: 层厚度

### Saunderson 修正

两种模型都支持 Saunderson 表面反射修正：
- k1: 表面反射系数（入射光在表面的反射）
- k2: 内部反射系数（从内部射向表面的光被反射回内部的比例）

公式：`R_measured = k1 + (1-k1)(1-k2)R_internal / (1 - k2*R_internal)`

## 多色盘支持

- 色盘A：真实测量数据，用于训练模型参数
- 色盘B-E：可选的真实数据，用于评估模型泛化能力
- 色盘F-H：如缺失数据，自动生成合成数据

训练时仅使用色盘A的数据，避免评估时出现"数据泄露"的假象。
