import json
import os

import numpy as np



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# --- 颜色转换 (sRGB D65) ---

def srgb_to_linear(u):
    """sRGB 到线性 RGB 转换"""
    u = np.clip(u, 0.0, 1.0)
    a = 0.055
    return np.where(u <= 0.04045, u/12.92, ((u + a)/(1+a))**2.4)

def linear_to_srgb(u):
    """线性 RGB 到 sRGB 转换"""
    u = np.clip(u, 0.0, 1.0)
    a = 0.055
    return np.where(u <= 0.0031308, 12.92*u, (1+a)*(u**(1/2.4)) - a)

# sRGB 线性 -> XYZ (D65)
M_RGB2XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
], dtype=np.float64)
WHITE_D65 = np.array([0.95047, 1.00000, 1.08883], dtype=np.float64)

def rgb_srgb_to_lab(rgb_srgb):
    """sRGB 到 CIELAB 颜色空间转换
    
    rgb_srgb: (N,3) 范围 0..1
    """
    rgb_lin = srgb_to_linear(rgb_srgb.astype(np.float64))
    xyz = rgb_lin @ M_RGB2XYZ.T
    xyz_n = xyz / WHITE_D65
    eps = 216/24389  # 0.008856
    k = 24389/27     # 903.3
    def f(t):
        return np.where(t > eps, np.cbrt(t), (k*t + 16)/116)
    fx, fy, fz = f(xyz_n[:,0]), f(xyz_n[:,1]), f(xyz_n[:,2])
    L = 116*fy - 16
    a = 500*(fx - fy)
    b = 200*(fy - fz)
    return np.stack([L,a,b], axis=1)

def deltaE76(lab1, lab2):
    """CIE76 色差计算"""
    return np.linalg.norm(lab1 - lab2, axis=1)

# --- 数据加载 ---

def load_palette(path, L=5):
    """加载调色板数据
    
    Args:
        path: JSON 文件路径
        L: 层数
    """
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
        if len(ln) < L:
            ln += ['EMPTY']*(L-len(ln))
        else:
            ln = ln[:L]
        meas_u8 = np.clip(np.array(c['measured_rgb'], dtype=np.float64) + 0.5, 0, 255).astype(np.uint8)
        meas = meas_u8.astype(np.float64)/255.0
        cells.append((ln, meas))
    return cells

def build_mats(palettes):
    """构建材料集合"""
    mats = set(['EMPTY'])
    for cells in palettes.values():
        for ln,_ in cells:
            mats.update(ln)
    return sorted(mats)

# --- 模型 ---

def fit_od(seqs, y_srgb, mats, ridge=1e-2, eps=1e-6):
    """拟合光学密度 (OD) 模型 - 一元项
    
    log(线性 RGB) = X @ 系数
    """
    y_lin = srgb_to_linear(y_srgb)
    y_log = np.log(np.clip(y_lin, eps, 1.0))
    mi = {m:i for i,m in enumerate(mats)}
    L = len(seqs[0]); M = len(mats)
    P = 1 + L*M
    N = len(seqs)
    X = np.zeros((N,P), dtype=np.float64)
    X[:,0] = 1.0
    for i,seq in enumerate(seqs):
        for p,m in enumerate(seq):
            X[i, 1 + p*M + mi[m]] += 1.0
    XtX = X.T @ X
    reg = ridge*np.eye(P)
    reg[0,0] = 0.0
    A = XtX + reg
    Xt = X.T
    coef = np.zeros((P,3), dtype=np.float64)
    for ch in range(3):
        coef[:,ch] = np.linalg.solve(A, Xt @ y_log[:,ch])
    return coef, mi

def predict_od(seqs, coef, mi, mats):
    """使用 OD 模型预测颜色"""
    L = len(seqs[0]); M = len(mats)
    P = coef.shape[0]
    N = len(seqs)
    X = np.zeros((N,P), dtype=np.float64)
    X[:,0] = 1.0
    for i,seq in enumerate(seqs):
        for p,m in enumerate(seq):
            X[i, 1 + p*M + mi.get(m, mi['EMPTY'])] += 1.0
    y_log = X @ coef
    y_lin = np.exp(y_log)
    y_srgb = linear_to_srgb(y_lin)
    return np.clip(y_srgb, 0, 1)


def fit_od_pairs(seqs, y_srgb, mats, ridge=1e-1, eps=1e-6):
    """拟合 OD 模型 - 包含相邻对项
    
    log(线性 RGB) = 偏置 + 一元项 + 相邻对项
    """
    y_lin = srgb_to_linear(y_srgb)
    y_log = np.log(np.clip(y_lin, eps, 1.0))
    mi = {m:i for i,m in enumerate(mats)}
    L = len(seqs[0]); M = len(mats)
    P = 1 + L*M + (L-1)*M*M
    N = len(seqs)
    X = np.zeros((N,P), dtype=np.float64)
    X[:,0] = 1.0
    unary_start = 1
    pair_start = 1 + L*M
    for i,seq in enumerate(seqs):
        for p,m in enumerate(seq):
            X[i, unary_start + p*M + mi[m]] += 1.0
        for p in range(L-1):
            a = mi[seq[p]]; b = mi[seq[p+1]]
            X[i, pair_start + p*M*M + a*M + b] += 1.0
    XtX = X.T @ X
    reg = ridge*np.eye(P)
    reg[0,0] = 0.0
    A = XtX + reg
    Xt = X.T
    coef = np.zeros((P,3), dtype=np.float64)
    for ch in range(3):
        coef[:,ch] = np.linalg.solve(A, Xt @ y_log[:,ch])
    return coef, mi

def predict_od_pairs(seqs, coef, mi, mats):
    """使用包含对项的 OD 模型预测颜色"""
    L = len(seqs[0]); M = len(mats)
    P = coef.shape[0]
    N = len(seqs)
    X = np.zeros((N,P), dtype=np.float64)
    X[:,0] = 1.0
    unary_start = 1
    pair_start = 1 + L*M
    for i,seq in enumerate(seqs):
        for p,m in enumerate(seq):
            X[i, unary_start + p*M + mi.get(m, mi['EMPTY'])] += 1.0
        for p in range(L-1):
            a = mi.get(seq[p], mi['EMPTY']); b = mi.get(seq[p+1], mi['EMPTY'])
            X[i, pair_start + p*M*M + a*M + b] += 1.0
    y_log = X @ coef
    y_lin = np.exp(y_log)
    y_srgb = linear_to_srgb(y_lin)
    return np.clip(y_srgb, 0, 1)


def stats(meas_srgb, pred_srgb):
    """计算预测统计信息"""
    lab_m = rgb_srgb_to_lab(meas_srgb)
    lab_p = rgb_srgb_to_lab(pred_srgb)
    de = deltaE76(lab_m, lab_p)
    return {
        'mean': float(de.mean()),
        'median': float(np.median(de)),
        'p95': float(np.quantile(de, 0.95)),
        'max': float(de.max()),
    }


def main():
    """主函数：评估 OD 模型性能"""
    base = '/mnt/data/calib_extracted/out'
    palettes = {pid: load_palette(os.path.join(base, f'Board_{pid}', 'dataset_cells.json')) for pid in ['A','B','C','D','E']}
    mats = build_mats(palettes)
    # 准备 A 板数据
    seqA = [ln for ln,_ in palettes['A']]
    measA = np.stack([rgb for _,rgb in palettes['A']], axis=0)

    # OD 一元模型
    coef, mi = fit_od(seqA, measA, mats, ridge=1e-2)
    logger.info('== OD-unary (log-linear) ==')
    for pid,cells in palettes.items():
        seq = [ln for ln,_ in cells]
        meas = np.stack([rgb for _,rgb in cells], axis=0)
        pred = predict_od(seq, coef, mi, mats)
        logger.info(pid, stats(meas, pred))

    # OD + 对项
    coefp, mip = fit_od_pairs(seqA, measA, mats, ridge=1e-1)
    logger.info('\n== OD-unary+adj-pairs (log-linear) ==')
    for pid,cells in palettes.items():
        seq = [ln for ln,_ in cells]
        meas = np.stack([rgb for _,rgb in cells], axis=0)
        pred = predict_od_pairs(seq, coefp, mip, mats)
        logger.info(pid, stats(meas, pred))

if __name__ == '__main__':
    main()
