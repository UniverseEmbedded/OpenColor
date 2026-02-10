# oc_xgb - OpenColor XGBoost 模块

## 简介

`oc_xgb` 是 OpenColor 项目的 XGBoost 机器学习模块，提供颜色预测和物理GPR模型拟合功能。

## 主要功能

### 1. XGBoost 模型 (`xgb_model.py`)
- `XGBParams`: XGBoost 模型参数配置
- `train_three_channel_regressors()`: 训练三通道回归器（Lab颜色空间）
- `predict_three_channel()`: 三通道预测
- `save_models()`: 保存模型到 JSON 文件

### 2. 物理GPR拟合 (`xgb_fit.py`)
- `PhysGPRConfig`: 物理GPR配置
- `OpticalParams`: 光学参数
- `PhysGPRModel`: 物理GPR模型
- `train_phys_gpr()`: 训练物理GPR模型
- `predict_phys_gpr_lab()`: 使用物理GPR模型预测Lab颜色

### 3. 特征工程 (`xgb_features.py`)
- `build_gpr_features()`: 构建GPR特征
- `build_layer_sequences()`: 构建层序列

### 4. 数据集处理 (`xgb_dataset.py`)
- 数据集加载和预处理

### 5. 颜色空间转换 (`xgb_colorspace.py`)
- RGB 与 Lab 颜色空间转换

### 6. 可视化 (`xgb_viz.py`)
- 模型结果可视化

## 安装

```bash
# 通过 pixi 安装
pixi install

# 或 pip 安装（开发模式）
pip install -e .
```

## 依赖

- numpy >= 1.26
- scipy >= 1.17.0
- xgboost >= 3.1.3
- pillow >= 10.0
- trimesh >= 4.11
- oc_core
- oc_engine
- oc_scripts

## 使用示例

```python
from oc_xgb.xgb_model import XGBParams, train_three_channel_regressors
from oc_xgb.xgb_fit import PhysGPRConfig, train_phys_gpr

# XGBoost 训练
params = XGBParams(use_gpu=True, n_estimators=800)
model_L, model_a, model_b = train_three_channel_regressors(X, Y, params)

# 物理GPR训练
cfg = PhysGPRConfig(n_layers=4, opt_steps=100)
model = train_phys_gpr(recipes, Y_lab, material_keys, cfg)
```

## 目录结构

```
src/oc_xgb/
├── __init__.py
├── xgb_model.py      # XGBoost 模型核心
├── xgb_fit.py        # 物理GPR拟合
├── xgb_features.py   # 特征工程
├── xgb_dataset.py    # 数据集处理
├── xgb_colorspace.py # 颜色空间
└── xgb_viz.py        # 可视化
```
