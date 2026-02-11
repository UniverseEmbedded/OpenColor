#!/usr/bin/env python3
"""RT层叠拟合/评估（非Kubelka-Munk模型）

严格工作流程：
  1) 仅在调色板A上拟合每种材料的参数（使用实测RGB值）
  2) 使用拟合参数预测/合成调色板B..E

注意：这不是Kubelka-Munk模型，不使用K/S或KM闭式解。
它将每一层视为具有有效(R,T)的非相干平板，通过多次反射叠加进行堆叠。

层叠加公式（考虑不透明背板反射率Rb，按通道计算）：
  R_next = r + (t^2 * R_prev) / (1 - r * R_prev)

参数化（每种材料，每个通道）：
  r = sigmoid(alpha)
  t = sigmoid(beta) * (1 - r)
这保证了 0<=r<=1，0<=t<=1-r。

我们在Lab空间中使用稳健的最小二乘法进行拟合。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from scipy.optimize import least_squares


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parent
# 启用项目模块导入
sys.path.insert(0, str(ROOT / "py_module" / "prototypes" / "src"))

from oc_proto.calib_color_model_fit.color_space import (
    rgb01_to_lab,
    delta_e_cie76,
)


def linear01_to_srgb01_f64(lin01: np.ndarray) -> np.ndarray:
    """sRGB EOTF转换，使用float64计算以保持有限差分灵敏度"""
    a = 0.055
    x = np.clip(np.asarray(lin01, dtype=np.float64), 0.0, 1.0)
    out = np.where(x <= 0.0031308, x * 12.92, (1 + a) * (x ** (1 / 2.4)) - a)
    return out


def srgb01_to_linear01_f64(srgb01: np.ndarray) -> np.ndarray:
    """sRGB逆EOTF转换，float64精度"""
    a = 0.055
    x = np.clip(np.asarray(srgb01, dtype=np.float64), 0.0, 1.0)
    out = np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)
    return out


def sigmoid(x: np.ndarray) -> np.ndarray:
    # 防止大数值时exp溢出
    x = np.clip(np.asarray(x, dtype=np.float64), -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-x))


def load_cells(dataset_json: Path) -> Tuple[List[List[str]], np.ndarray]:
    """返回序列（材料名称列表）和实测sRGB01值（N,3）"""
    import json

    ds = json.loads(dataset_json.read_text(encoding="utf-8", errors="replace"))
    cells = ds.get("cells", [])
    seqs: List[List[str]] = []
    rgb01: List[List[float]] = []
    for c in cells:
        if not bool(c.get("enabled", True)):
            continue
        rec = c.get("recipe") or {}
        if not rec:
            continue
        ln = c.get("layer_names")
        if not isinstance(ln, list) or len(ln) == 0:
            # 回退方案：从配方确定性地构建
            # 按数量降序然后按名称排序
            items = []
            for k, v in rec.items():
                try:
                    items.append((str(k), float(v)))
                except Exception:
                    pass
            items.sort(key=lambda kv: (-kv[1], kv[0]))
            ln = []
            for k, v in items:
                n = int(round(v))
                ln.extend([k] * max(0, n))
        seq = [str(x) for x in ln]
        meas = c.get("measured_rgb", [0, 0, 0])
        # 稳健的float到uint8舍入
        meas_f = np.array(meas, dtype=np.float32)
        meas_u8 = np.clip(meas_f + 0.5, 0, 255).astype(np.uint8)
        seqs.append(seq)
        rgb01.append((meas_u8.astype(np.float32) / 255.0).tolist())
    return seqs, np.asarray(rgb01, dtype=np.float32)


def normalize_seqs(
    seqs: List[List[str]], n_layers: int, empty_token: str = "EMPTY"
) -> List[List[str]]:
    """将序列归一化为固定层数"""
    out: List[List[str]] = []
    for s in seqs:
        s2 = list(s)
        if len(s2) < n_layers:
            s2 = s2 + [empty_token] * (n_layers - len(s2))
        elif len(s2) > n_layers:
            s2 = s2[:n_layers]
        out.append(s2)
    return out


def materials_from_seqs(seqs: List[List[str]], empty_token: str = "EMPTY") -> List[str]:
    """从序列中提取所有材料类型"""
    mats = set()
    for s in seqs:
        for m in s:
            mats.add(m)
    mats.add(empty_token)
    mats_list = sorted(mats)
    # 确保EMPTY排在第一位以便使用
    if empty_token in mats_list:
        mats_list.remove(empty_token)
        mats_list = [empty_token] + mats_list
    return mats_list


def pack_params(
    alpha: np.ndarray, beta: np.ndarray, gamma_rb: np.ndarray
) -> np.ndarray:
    """打包参数

    alpha/beta可以是(M,3)或(M,L,3)取决于模式
    """
    return np.concatenate(
        [
            np.asarray(alpha).ravel(),
            np.asarray(beta).ravel(),
            np.asarray(gamma_rb).ravel(),
        ]
    ).astype(np.float64)


def unpack_params(
    x: np.ndarray, n_mats: int, n_layers: int, layered: bool
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """解包参数

    如果layered=False：
      alpha,beta: (M,3)
    如果layered=True：
      alpha,beta: (M,L,3)
    gamma_rb: (3,)
    """
    x = np.asarray(x, dtype=np.float64)
    if layered:
        n = n_mats * n_layers * 3
        alpha = x[:n].reshape((n_mats, n_layers, 3))
        beta = x[n : 2 * n].reshape((n_mats, n_layers, 3))
        gamma = x[2 * n : 2 * n + 3].reshape((3,))
        return alpha, beta, gamma
    else:
        n = n_mats * 3
        alpha = x[:n].reshape((n_mats, 3))
        beta = x[n : 2 * n].reshape((n_mats, 3))
        gamma = x[2 * n : 2 * n + 3].reshape((3,))
        return alpha, beta, gamma


def seqs_to_idx_mat(
    seqs: List[List[str]],
    mats: List[str],
    order: str,
    empty_token: str = "EMPTY",
) -> np.ndarray:
    """将序列转换为int32索引矩阵(N,L)，按指定顺序排列"""
    mat2idx = {m: i for i, m in enumerate(mats)}
    N = len(seqs)
    if N == 0:
        return np.zeros((0, 0), dtype=np.int32)
    L = len(seqs[0])
    empty_idx = mat2idx.get(empty_token, 0)
    idx_mat = np.full((N, L), empty_idx, dtype=np.int32)
    for i, seq in enumerate(seqs):
        for j, m in enumerate(seq[:L]):
            idx_mat[i, j] = mat2idx.get(m, empty_idx)
    if order == "bottom_first":
        idx_mat = idx_mat[:, ::-1]
    return idx_mat


def forward_reflectance_linear_idx(
    idx_mat: np.ndarray,
    r: np.ndarray,
    t: np.ndarray,
    Rb_lin: np.ndarray,
) -> np.ndarray:
    """基于(N,L)索引和每种材料的r,t进行向量化层递归

    r,t可以是：
      - (M,3) 用于层不变参数
      - (M,L,3) 用于层相关参数
    """
    if idx_mat.size == 0:
        return np.zeros((0, 3), dtype=np.float64)
    N, L = idx_mat.shape
    R = np.repeat(Rb_lin, repeats=N, axis=0)  # (N,3)
    for j in range(L):
        idx = idx_mat[:, j]
        if r.ndim == 2:
            r1 = r[idx, :]
            t1 = t[idx, :]
        else:
            r1 = r[idx, j, :]
            t1 = t[idx, j, :]
        denom = 1.0 - r1 * R
        denom = np.clip(denom, 1e-6, 1e9)
        R = r1 + (t1 * t1) * R / denom
        R = np.clip(R, 0.0, 1.0)
    return np.clip(R, 0.0, 1.0)


def forward_reflectance_linear(
    seqs: List[List[str]],
    mats: List[str],
    alpha: np.ndarray,
    beta: np.ndarray,
    gamma_rb: np.ndarray,
    order: str,
    empty_token: str = "EMPTY",
) -> np.ndarray:
    """预测给定序列的线性反射率RGB01 (N,3)

    注意：此实现对样本进行向量化以提高速度。唯一的Python级循环是层索引循环（通常5层）
    """
    mat2idx = {m: i for i, m in enumerate(mats)}

    # 计算每种材料每个通道的r,t
    alpha = np.asarray(alpha, dtype=np.float64)
    beta = np.asarray(beta, dtype=np.float64)
    gamma_rb = np.asarray(gamma_rb, dtype=np.float64)

    r = sigmoid(alpha)  # (M,3)
    t = sigmoid(beta) * (1.0 - r)

    # 覆盖EMPTY：透明，无反射
    if empty_token in mat2idx:
        i0 = mat2idx[empty_token]
        r[i0, ...] = 0.0
        t[i0, ...] = 1.0

    rb = sigmoid(gamma_rb)[None, :]  # (1,3)
    # 在线性空间工作；将rb解释为线性反射率
    Rb_lin = rb.astype(np.float64)

    # 将序列转换为索引矩阵(N,L)
    N = len(seqs)
    if N == 0:
        return np.zeros((0, 3), dtype=np.float64)
    L = len(seqs[0])
    idx_mat = np.full((N, L), mat2idx.get(empty_token, 0), dtype=np.int32)
    for i, seq in enumerate(seqs):
        for j, m in enumerate(seq[:L]):
            idx_mat[i, j] = mat2idx.get(m, mat2idx.get(empty_token, 0))
    if order == "bottom_first":
        idx_mat = idx_mat[:, ::-1]

    # 向量化递归
    R = np.repeat(Rb_lin, repeats=N, axis=0)  # (N,3)
    for j in range(L):
        idx = idx_mat[:, j]
        r1 = r[idx, :]  # (N,3)
        t1 = t[idx, :]  # (N,3)
        denom = 1.0 - r1 * R
        denom = np.clip(denom, 1e-6, 1e9)
        R = r1 + (t1 * t1) * R / denom
        R = np.clip(R, 0.0, 1.0)

    return np.clip(R, 0.0, 1.0)


def forward_reflectance_srgb(
    seqs: List[List[str]],
    mats: List[str],
    alpha: np.ndarray,
    beta: np.ndarray,
    gamma_rb: np.ndarray,
    order: str,
    empty_token: str = "EMPTY",
) -> np.ndarray:
    """预测给定序列的sRGB01 (N,3)"""
    lin = forward_reflectance_linear(
        seqs, mats, alpha, beta, gamma_rb, order, empty_token=empty_token
    )
    srgb = linear01_to_srgb01_f64(lin)
    return np.clip(srgb, 0.0, 1.0).astype(np.float32)


def fit_on_A(
    seqs_A: List[List[str]],
    yA_srgb01: np.ndarray,
    mats: List[str],
    order: str,
    n_layers: int,
    layered: bool,
    reg: float,
    diff_step: float,
    max_nfev: int,
    huber_f_scale: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, float]]:
    """在调色板A上拟合参数"""
    n_mats = len(mats)

    # 预计算A的索引矩阵（拟合期间固定）
    idxA = seqs_to_idx_mat(seqs_A, mats, order=order, empty_token="EMPTY")

    # 初始化alpha/beta：小反射，高透射
    if layered:
        alpha0 = np.full((n_mats, n_layers, 3), -3.0, dtype=np.float32)
        beta0 = np.full((n_mats, n_layers, 3), 3.0, dtype=np.float32)
    else:
        alpha0 = np.full((n_mats, 3), -3.0, dtype=np.float32)
        beta0 = np.full((n_mats, 3), 3.0, dtype=np.float32)

    # 初始化rb接近0.7
    gamma0 = np.array([1.0, 1.0, 1.0], dtype=np.float32)  # sigmoid ~0.731

    x0 = pack_params(alpha0, beta0, gamma0)

    # 为避免每次评估时RGB->Lab转换（慢）以及由于内部float32转换导致的有限差分Jacobian灵敏度损失，
    # 我们在线性反射率空间拟合，仅在最终报告时转换为Lab
    yA_lin = srgb01_to_linear01_f64(yA_srgb01)

    def residual(x: np.ndarray) -> np.ndarray:
        alpha, beta, gamma = unpack_params(
            x, n_mats, n_layers=n_layers, layered=layered
        )
        # 计算每种材料每个通道的r,t（float64）
        r = sigmoid(alpha)
        t = sigmoid(beta) * (1.0 - r)
        # 强制EMPTY为透明
        r[0, ...] = 0.0
        t[0, ...] = 1.0

        Rb_lin = sigmoid(gamma)[None, :]
        pred_lin = forward_reflectance_linear_idx(idxA, r, t, Rb_lin)
        # 线性R空间中的残差，展平
        res = (pred_lin - yA_lin).reshape((-1,))
        # 对参数的轻量L2正则化以保持优化稳定
        res_reg = np.sqrt(reg) * x
        return np.concatenate([res, res_reg])

    res = least_squares(
        residual,
        x0,
        loss="huber",
        f_scale=huber_f_scale,
        max_nfev=max_nfev,
        # 使用显式有限差分步长。默认值可能太小，
        # 一旦前向模型为cv2 Lab转换转换为float32
        diff_step=diff_step,
        x_scale="jac",
        verbose=0,
    )

    alpha, beta, gamma = unpack_params(
        res.x, n_mats, n_layers=n_layers, layered=layered
    )

    # 计算A的deltaE
    # 通过预计算的idxA快速预测A
    r = sigmoid(alpha)
    t = sigmoid(beta) * (1.0 - r)
    r[0, ...] = 0.0
    t[0, ...] = 1.0
    predA_lin = forward_reflectance_linear_idx(idxA, r, t, sigmoid(gamma)[None, :])
    predA = linear01_to_srgb01_f64(predA_lin).astype(np.float32)
    deA = delta_e_cie76(rgb01_to_lab(predA), rgb01_to_lab(yA_srgb01))

    stats = {
        "A_mean": float(np.mean(deA)),
        "A_median": float(np.median(deA)),
        "A_p95": float(np.quantile(deA, 0.95)),
        "nfev": int(res.nfev),
        "cost": float(res.cost),
        "success": bool(res.success),
    }

    return alpha, beta, gamma, stats


def eval_palette(
    seqs: List[List[str]],
    y_srgb01: np.ndarray,
    mats: List[str],
    alpha: np.ndarray,
    beta: np.ndarray,
    gamma: np.ndarray,
    order: str,
) -> Dict[str, float]:
    """评估调色板性能"""
    pred = forward_reflectance_srgb(seqs, mats, alpha, beta, gamma, order=order)
    de = delta_e_cie76(rgb01_to_lab(pred), rgb01_to_lab(y_srgb01))
    return {
        "mean": float(np.mean(de)),
        "median": float(np.median(de)),
        "p95": float(np.quantile(de, 0.95)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data-root",
        type=str,
        required=True,
        help="指向calib_extracted/out的路径（包含Board_A..）",
    )
    ap.add_argument("--n-layers", type=int, default=5)
    ap.add_argument(
        "--layered",
        action="store_true",
        help="使用每层位置的材料参数（更灵活，可减少偏差但可能过拟合）",
    )
    ap.add_argument("--max-nfev", type=int, default=120)
    ap.add_argument(
        "--reg", type=float, default=1e-3, help="参数L2正则化权重（拟合空间）"
    )
    ap.add_argument(
        "--diff-step", type=float, default=0.05, help="Jacobian的有限差分步长"
    )
    ap.add_argument(
        "--huber-f-scale",
        type=float,
        default=0.05,
        help="Huber f_scale，以线性反射率单位计（拟合空间）",
    )
    args = ap.parse_args()

    data_root = Path(args.data_root)

    def ds_path(pid: str) -> Path:
        return data_root / f"Board_{pid}" / "dataset_cells.json"

    seqA, yA = load_cells(ds_path("A"))
    seqA = normalize_seqs(seqA, args.n_layers)

    # 仅从A构建材料（严格）。添加EMPTY
    mats = materials_from_seqs(seqA)

    # 仅使用A测试两种顺序
    results = []
    for order in ["top_first", "bottom_first"]:
        alpha, beta, gamma, st = fit_on_A(
            seqA,
            yA,
            mats,
            order=order,
            n_layers=args.n_layers,
            layered=args.layered,
            reg=args.reg,
            diff_step=args.diff_step,
            max_nfev=args.max_nfev,
            huber_f_scale=args.huber_f_scale,
        )
        results.append((st["A_mean"], order, alpha, beta, gamma, st))

    results.sort(key=lambda t: t[0])
    best = results[0]
    _, best_order, alpha, beta, gamma, stA = best

    logger.info("=== 仅在A上拟合 ===")
    logger.info(f"顺序: {best_order}")
    logger.info(
        f"A 平均dE76: {stA['A_mean']:.4f} | 中位数: {stA['A_median']:.4f} | p95: {stA['A_p95']:.4f}"
    )
    logger.info(
        f"nfev: {stA['nfev']} | 成功: {stA['success']} | 代价: {stA['cost']:.4f}"
    )

    # 评估B..E
    for pid in ["B", "C", "D", "E"]:
        seq, y = load_cells(ds_path(pid))
        seq = normalize_seqs(seq, args.n_layers)
        # 确保不在A中的材料映射到EMPTY
        seq = [[m if m in set(mats) else "EMPTY" for m in s] for s in seq]
        st = eval_palette(seq, y, mats, alpha, beta, gamma, order=best_order)
        logger.info(
            f"{pid} 平均dE76: {st['mean']:.4f} | 中位数: {st['median']:.4f} | p95: {st['p95']:.4f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
