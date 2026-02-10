"""全对颜色模型拟合评估模块 - 使用所有层对作为特征"""

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
M_RGB2XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041]
], dtype=np.float64)
# D65白点XYZ值
WHITE_D65 = np.array([0.95047, 1.0, 1.08883], dtype=np.float64)


def rgb_srgb_to_lab(rgb):
    """将sRGB颜色转换为CIELAB颜色空间"""
    rgb_lin = srgb_to_linear(rgb.astype(np.float64))
    xyz = rgb_lin @ M_RGB2XYZ.T
    xyz_n = xyz / WHITE_D65
    eps = 216 / 24389
    k = 24389 / 27
    f = lambda t: np.where(t > eps, np.cbrt(t), (k * t + 16) / 116)
    fx, fy, fz = f(xyz_n[:, 0]), f(xyz_n[:, 1]), f(xyz_n[:, 2])
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return np.stack([L, a, b], axis=1)


def deltaE76(l1, l2):
    """计算CIE76色差（欧氏距离）"""
    return np.linalg.norm(l1 - l2, axis=1)


def load_palette(path, L=5):
    """从JSON文件加载调色板数据"""
    d = json.load(open(path, 'r'))
    cells = []
    for c in d['cells']:
        if not c.get('enabled', True):
            continue
        if not c.get('has_recipe', True):
            continue
        ln = c.get('layer_names')
        if not ln:
            continue
        ln = list(ln)
        # 填充或截断到固定层数
        if len(ln) < L:
            ln += ['EMPTY'] * (L - len(ln))
        else:
            ln = ln[:L]
        meas_u8 = np.clip(np.array(c['measured_rgb'], dtype=np.float64) + 0.5, 0, 255).astype(np.uint8)
        meas = meas_u8.astype(np.float64) / 255.0
        cells.append((ln, meas))
    return cells


def build_mats(palettes):
    """构建所有使用到的材料集合"""
    mats = set(['EMPTY'])
    for cells in palettes.values():
        for ln, _ in cells:
            mats.update(ln)
    return sorted(mats)


def stats(meas, pred):
    """计算预测误差的统计信息"""
    de = deltaE76(rgb_srgb_to_lab(meas), rgb_srgb_to_lab(pred))
    return {
        'mean': float(de.mean()),
        'median': float(np.median(de)),
        'p95': float(np.quantile(de, 0.95)),
        'max': float(de.max())
    }


def fit_fullpairs(seqs, y_srgb, mats, ridge=1e-1, eps=1e-6):
    """
    使用全对特征拟合颜色模型

    特征包括：
    - 偏置项（1）
    - 一元特征（每层每种材料）
    - 成对特征（所有层对组合的材料对）
    """
    y_lin = srgb_to_linear(y_srgb)
    y_log = np.log(np.clip(y_lin, eps, 1.0))
    mi = {m: i for i, m in enumerate(mats)}
    L = len(seqs[0])
    M = len(mats)
    # 所有可能的层对
    pairs = [(p, q) for p in range(L) for q in range(p + 1, L)]
    P = 1 + L * M + len(pairs) * M * M  # 总特征数
    N = len(seqs)
    X = np.zeros((N, P), dtype=np.float64)
    X[:, 0] = 1.0  # 偏置项
    unary_start = 1
    pair_start = 1 + L * M
    for i, seq in enumerate(seqs):
        # 填充一元特征
        for p, m in enumerate(seq):
            X[i, unary_start + p * M + mi[m]] += 1.0
        # 填充成对特征
        for k, (p, q) in enumerate(pairs):
            a = mi[seq[p]]
            b = mi[seq[q]]
            X[i, pair_start + k * M * M + a * M + b] += 1.0
    XtX = X.T @ X
    reg = ridge * np.eye(P, dtype=np.float64)
    reg[0, 0] = 0  # 不正则化偏置项
    A = XtX + reg
    Xt = X.T
    coef = np.zeros((P, 3), dtype=np.float64)
    for ch in range(3):
        coef[:, ch] = np.linalg.solve(A, Xt @ y_log[:, ch])
    return coef, mi, pairs


def predict_fullpairs(seqs, coef, mi, mats, pairs):
    """使用全对模型进行预测"""
    L = len(seqs[0])
    M = len(mats)
    P = coef.shape[0]
    N = len(seqs)
    X = np.zeros((N, P), dtype=np.float64)
    X[:, 0] = 1.0
    unary_start = 1
    pair_start = 1 + L * M
    for i, seq in enumerate(seqs):
        for p, m in enumerate(seq):
            X[i, unary_start + p * M + mi.get(m, mi['EMPTY'])] += 1.0
        for k, (p, q) in enumerate(pairs):
            a = mi.get(seq[p], mi['EMPTY'])
            b = mi.get(seq[q], mi['EMPTY'])
            X[i, pair_start + k * M * M + a * M + b] += 1.0
    y_log = X @ coef
    y_srgb = linear_to_srgb(np.exp(y_log))
    return np.clip(y_srgb, 0, 1)


def main():
    """主函数 - 加载数据并评估模型"""
    base = '/mnt/data/calib_extracted/out'
    palettes = {pid: load_palette(os.path.join(base, f'Board_{pid}', 'dataset_cells.json'))
                for pid in ['A', 'B', 'C', 'D', 'E']}
    mats = build_mats(palettes)
    seqA = [ln for ln, _ in palettes['A']]
    measA = np.stack([rgb for _, rgb in palettes['A']], axis=0)
    coef, mi, pairs = fit_fullpairs(seqA, measA, mats, ridge=5e-1)
    logger.info('params', coef.shape[0], 'mats', len(mats), 'pairs', len(pairs))
    for pid, cells in palettes.items():
        seq = [ln for ln, _ in cells]
        meas = np.stack([rgb for _, rgb in cells], axis=0)
        pred = predict_fullpairs(seq, coef, mi, mats, pairs)
        logger.info(pid, stats(meas, pred))


if __name__ == '__main__':
    main()
