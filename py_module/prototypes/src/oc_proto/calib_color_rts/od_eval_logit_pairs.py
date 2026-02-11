"""Logit+相邻对颜色模型拟合评估模块 - 使用相邻层对作为特征"""

import json
import os

import numpy as np


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def srgb_to_linear(u):
    """将sRGB值转换为线性RGB值"""
    u = np.clip(u, 0, 1)
    a = 0.055
    return np.where(u <= 0.04045, u / 12.92, ((u + a) / (1 + a)) ** 2.4)


def linear_to_srgb(u):
    """将线性RGB值转换为sRGB值"""
    u = np.clip(u, 0, 1)
    a = 0.055
    return np.where(u <= 0.0031308, 12.92 * u, (1 + a) * (u ** (1 / 2.4)) - a)


# sRGB到XYZ的转换矩阵（D65白点）
M_RGB2XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ],
    dtype=np.float64,
)
# D65白点XYZ值
WHITE_D65 = np.array([0.95047, 1.0, 1.08883], dtype=np.float64)


def rgb_srgb_to_lab(rgb):
    """将sRGB颜色转换为CIELAB颜色空间"""
    rgb_lin = srgb_to_linear(rgb.astype(np.float64))
    xyz = rgb_lin @ M_RGB2XYZ.T
    xyz_n = xyz / WHITE_D65
    eps = 216 / 24389
    k = 24389 / 27

    def f(t):
        return np.where(t > eps, np.cbrt(t), (k * t + 16) / 116)

    fx, fy, fz = f(xyz_n[:, 0]), f(xyz_n[:, 1]), f(xyz_n[:, 2])
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return np.stack([L, a, b], axis=1)


def deltaE76(a, b):
    """计算CIE76色差（欧氏距离）"""
    return np.linalg.norm(a - b, axis=1)


def load_palette(path, L=5):
    """从JSON文件加载调色板数据"""
    d = json.load(open(path, "r"))
    cells = []
    for c in d["cells"]:
        if not c.get("enabled", True):
            continue
        if not c.get("has_recipe", True):
            continue
        ln = c.get("layer_names")
        if not ln:
            continue
        ln = list(ln)
        # 填充或截断到固定层数
        if len(ln) < L:
            ln += ["EMPTY"] * (L - len(ln))
        else:
            ln = ln[:L]
        meas_u8 = np.clip(
            np.array(c["measured_rgb"], dtype=np.float64) + 0.5, 0, 255
        ).astype(np.uint8)
        meas = meas_u8.astype(np.float64) / 255.0
        cells.append((ln, meas))
    return cells


def build_mats(palettes):
    """构建所有使用到的材料集合"""
    mats = set(["EMPTY"])
    for cells in palettes.values():
        for ln, _ in cells:
            mats.update(ln)
    return sorted(mats)


def build_X_adj_pairs(seqs, mats):
    """构建相邻对特征矩阵

    特征包括：
    - 偏置项（1）
    - 一元特征（每层每种材料）
    - 相邻对特征（相邻层之间的材料对）
    """
    mi = {m: i for i, m in enumerate(mats)}
    L = len(seqs[0])
    M = len(mats)
    P = 1 + L * M + (L - 1) * M * M  # 总特征数
    X = np.zeros((len(seqs), P), dtype=np.float64)
    X[:, 0] = 1.0  # 偏置项
    unary_start = 1
    pair_start = 1 + L * M
    for i, seq in enumerate(seqs):
        # 填充一元特征
        for p, m in enumerate(seq):
            X[i, unary_start + p * M + mi.get(m, mi["EMPTY"])] += 1.0
        # 填充相邻对特征
        for p in range(L - 1):
            a = mi.get(seq[p], mi["EMPTY"])
            b = mi.get(seq[p + 1], mi["EMPTY"])
            X[i, pair_start + p * M * M + a * M + b] += 1.0
    return X


def fit_logit_adj_pairs(seqs, y_srgb, mats, ridge=1e-1, eps=1e-5):
    """使用Logit变换和相邻对特征拟合颜色模型"""
    y_lin = srgb_to_linear(y_srgb)
    y_lin = np.clip(y_lin, eps, 1 - eps)
    # Logit变换
    y_z = np.log(y_lin / (1 - y_lin))
    X = build_X_adj_pairs(seqs, mats)
    P = X.shape[1]
    XtX = X.T @ X
    reg = ridge * np.eye(P)
    reg[0, 0] = 0  # 不正则化偏置项
    A = XtX + reg
    coef = np.zeros((P, 3), dtype=np.float64)
    Xt = X.T
    for ch in range(3):
        coef[:, ch] = np.linalg.solve(A, Xt @ y_z[:, ch])
    return coef


def predict_logit_adj_pairs(seqs, coef, mats):
    """使用Logit+相邻对模型进行预测"""
    X = build_X_adj_pairs(seqs, mats)
    z = X @ coef
    # 逆Logit变换
    y_lin = 1 / (1 + np.exp(-z))
    y_srgb = linear_to_srgb(y_lin)
    return np.clip(y_srgb, 0, 1)


def stats(meas, pred):
    """计算预测误差的统计信息"""
    lab_m = rgb_srgb_to_lab(meas)
    lab_p = rgb_srgb_to_lab(pred)
    de = deltaE76(lab_m, lab_p)
    return {
        "mean": float(de.mean()),
        "median": float(np.median(de)),
        "p95": float(np.quantile(de, 0.95)),
        "max": float(de.max()),
    }


def main():
    """主函数 - 加载数据并评估模型"""
    base = "/mnt/data/calib_extracted/out"
    palettes = {
        pid: load_palette(os.path.join(base, f"Board_{pid}", "dataset_cells.json"))
        for pid in ["A", "B", "C", "D", "E"]
    }
    mats = build_mats(palettes)
    seqA = [ln for ln, _ in palettes["A"]]
    measA = np.stack([rgb for _, rgb in palettes["A"]], axis=0)
    # 测试不同的正则化强度
    for ridge in [0.01, 0.1, 1.0, 3.0]:
        coef = fit_logit_adj_pairs(seqA, measA, mats, ridge=ridge)
        logger.info("== logit+adjpairs ridge", ridge, "==")
        for pid, cells in palettes.items():
            seq = [ln for ln, _ in cells]
            meas = np.stack([rgb for _, rgb in cells], axis=0)
            pred = predict_logit_adj_pairs(seq, coef, mats)
            s = stats(meas, pred)
            logger.info(pid, s)
        logger.info("")


if __name__ == "__main__":
    main()
