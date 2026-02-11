"""
XGBoost模型工具模块

提供XGBoost训练、预测、保存功能
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np

try:
    import xgboost as xgb
except Exception as e:  # pragma: no cover
    xgb = None
    _xgb_import_error = e


@dataclass
class XGBParams:
    """XGBoost 模型参数配置"""

    use_gpu: bool = True  # 是否使用 GPU 加速
    max_depth: int = 6  # 树的最大深度
    n_estimators: int = 800  # 估计器数量（树的数量）
    learning_rate: float = 0.05  # 学习率
    subsample: float = 0.9  # 样本采样比例
    colsample_bytree: float = 0.9  # 特征采样比例
    reg_lambda: float = 1.0  # L2 正则化系数
    min_child_weight: float = 1.0  # 叶子节点最小样本权重和
    gamma: float = 0.0  # 节点分裂所需的最小损失减少
    random_state: int = 42  # 随机种子


def _base_params(p: XGBParams) -> Dict[str, Any]:
    """将 XGBParams 转换为 XGBoost 参数字典"""
    params: Dict[str, Any] = dict(
        max_depth=int(p.max_depth),
        n_estimators=int(p.n_estimators),
        learning_rate=float(p.learning_rate),
        subsample=float(p.subsample),
        colsample_bytree=float(p.colsample_bytree),
        reg_lambda=float(p.reg_lambda),
        min_child_weight=float(p.min_child_weight),
        gamma=float(p.gamma),
        objective="reg:squarederror",
        random_state=int(p.random_state),
        n_jobs=0,
    )
    if p.use_gpu:
        # 对于较新版本的 XGBoost (2.0+)，使用 device="cuda" 和 tree_method="hist"
        params.update(dict(tree_method="hist", device="cuda"))
    else:
        params.update(dict(tree_method="hist", device="cpu"))
    return params


def require_xgboost():
    """检查 XGBoost 是否已安装，如未安装则抛出异常"""
    if xgb is None:  # pragma: no cover
        raise RuntimeError(
            "xgboost is not installed (or failed to import). "
            "Install it in your environment, e.g. `pixi add xgboost` or `pip install xgboost`."
        ) from _xgb_import_error


def train_three_channel_regressors(
    X: np.ndarray,
    Y: np.ndarray,
    params: XGBParams,
) -> Tuple[Any, Any, Any]:
    """为 Y[:,0], Y[:,1], Y[:,2] 训练三个独立的回归器

    Args:
        X: 特征矩阵 (n_samples, n_features)
        Y: 目标值矩阵 (n_samples, 3)，通常是 Lab 颜色空间的三个通道
        params: XGBoost 参数配置

    Returns:
        三个训练好的 XGBoost 回归器（分别对应 L, a, b 通道）
    """
    require_xgboost()
    X = np.asarray(X, dtype=np.float32)
    Y = np.asarray(Y, dtype=np.float32)
    assert Y.shape[1] == 3

    base = _base_params(params)
    models = []
    for ch in range(3):
        m = xgb.XGBRegressor(**base)
        m.fit(X, Y[:, ch])
        models.append(m)
    return models[0], models[1], models[2]


def predict_three_channel(
    models: Tuple[Any, Any, Any],
    X: np.ndarray,
) -> np.ndarray:
    """使用三个独立的回归器进行三通道预测

    Args:
        models: 三个 XGBoost 回归器元组
        X: 特征矩阵 (n_samples, n_features)

    Returns:
        预测值矩阵 (n_samples, 3)
    """
    X = np.asarray(X, dtype=np.float32)
    preds = [models[i].predict(X).astype(np.float32) for i in range(3)]
    return np.stack(preds, axis=1).astype(np.float32)


def save_models(models: Tuple[Any, Any, Any], out_dir, prefix: str = "xgb_lab"):
    """保存三个 XGBoost 模型到 JSON 文件

    Args:
        models: 三个 XGBoost 回归器元组
        out_dir: 输出目录
        prefix: 文件名前缀

    Returns:
        保存的文件路径列表
    """
    require_xgboost()
    out_dir = str(out_dir)
    paths = []
    for i, name in enumerate(["L", "a", "b"]):
        path = f"{out_dir}/{prefix}_{name}.json"
        models[i].save_model(path)
        paths.append(path)
    return paths
