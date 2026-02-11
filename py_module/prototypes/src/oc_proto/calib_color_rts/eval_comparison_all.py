"""
综合评估对比脚本
对比 eval_pipeline.py 中的现有模型与四个新脚本中的新模型性能。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 项目模块导入
from oc_proto.calib_color_rts.cli import FitArgs
from oc_xgb.color_space import rgb01_to_lab, lab_to_rgb01
from oc_proto.calib_color_rts.dataset_io import (
    load_dataset,
    Dataset,
    filter_training_cells,
)
from oc_proto.calib_color_rts.diagnostics import (
    compute_diagnostics,
    render_boards_for_palette,
)
from oc_xgb.xgb_fit import (
    PhysGPRConfig,
    train_phys_gpr,
    predict_phys_gpr_lab,
    build_layer_sequences,
    build_gpr_features,
)


# --- 通用颜色转换工具 (sRGB D65) ---


def srgb_to_linear(u):
    u = np.clip(u, 0.0, 1.0)
    a = 0.055
    return np.where(u <= 0.04045, u / 12.92, ((u + a) / (1 + a)) ** 2.4)


def linear_to_srgb(u):
    u = np.clip(u, 0.0, 1.0)
    a = 0.055
    return np.where(u <= 0.0031308, 12.92 * u, (1 + a) * (u ** (1 / 2.4)) - a)


def deltaE76(lab1, lab2):
    return np.linalg.norm(lab1 - lab2, axis=1)


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=np.float64), -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-x))


# --- 数据准备辅助函数 ---


def prepare_sequences(ds: Dataset, material_keys: list[str], n_layers: int = 5):
    """从 Dataset 中提取序列和测量的 RGB"""
    seqs = []
    rgb01 = []
    for c in ds.cells:
        if not c.enabled or not c.recipe:
            continue
        ln = list(c.layer_names or [])
        if len(ln) < n_layers:
            ln += ["EMPTY"] * (n_layers - len(ln))
        else:
            ln = ln[:n_layers]
        seqs.append(ln)
        rgb01.append(c.measured_rgb.astype(np.float32) / 255.0)
    return seqs, np.array(rgb01)


def build_all_mats(datasets: list[Dataset]):
    mats = set(["EMPTY"])
    for ds in datasets:
        for c in ds.cells:
            if c.layer_names:
                mats.update(c.layer_names)
    return sorted(list(mats))


# --- 模型类定义 ---


class BaseExtraModel:
    def fit(self, train_ds: Dataset, all_mats: list[str]):
        pass

    def predict(self, ds: Dataset):
        pass


class ODUnaryModel(BaseExtraModel):
    def __init__(self, ridge=1e-2):
        self.ridge = ridge
        self.coef = None
        self.mats = None
        self.mi = None
        self.n_layers = 5

    def fit(self, train_ds: Dataset, all_mats: list[str]):
        seqs, y_srgb = prepare_sequences(train_ds, all_mats, self.n_layers)
        self.mats = all_mats
        self.mi = {m: i for i, m in enumerate(self.mats)}

        y_lin = srgb_to_linear(y_srgb)
        y_log = np.log(np.clip(y_lin, 1e-6, 1.0))

        L = self.n_layers
        M = len(self.mats)
        P = 1 + L * M
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, 1 + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0

        XtX = X.T @ X
        reg = self.ridge * np.eye(P)
        reg[0, 0] = 0.0
        A = XtX + reg
        self.coef = np.zeros((P, 3), dtype=np.float64)
        Xt = X.T
        for ch in range(3):
            self.coef[:, ch] = np.linalg.solve(A, Xt @ y_log[:, ch])

    def predict(self, ds: Dataset):
        seqs, _ = prepare_sequences(ds, self.mats, self.n_layers)
        L = self.n_layers
        M = len(self.mats)
        P = self.coef.shape[0]
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, 1 + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0
        y_log = X @ self.coef
        y_lin = np.exp(y_log)
        return np.clip(linear_to_srgb(y_lin), 0, 1)


class ODAdjPairsModel(BaseExtraModel):
    def __init__(self, ridge=1e-1):
        self.ridge = ridge
        self.coef = None
        self.mats = None
        self.mi = None
        self.n_layers = 5

    def fit(self, train_ds: Dataset, all_mats: list[str]):
        seqs, y_srgb = prepare_sequences(train_ds, all_mats, self.n_layers)
        self.mats = all_mats
        self.mi = {m: i for i, m in enumerate(self.mats)}

        y_lin = srgb_to_linear(y_srgb)
        y_log = np.log(np.clip(y_lin, 1e-6, 1.0))

        L = self.n_layers
        M = len(self.mats)
        P = 1 + L * M + (L - 1) * M * M
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        unary_start = 1
        pair_start = 1 + L * M
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, unary_start + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0
            for p in range(L - 1):
                a = self.mi.get(seq[p], self.mi["EMPTY"])
                b = self.mi.get(seq[p + 1], self.mi["EMPTY"])
                X[i, pair_start + p * M * M + a * M + b] += 1.0

        XtX = X.T @ X
        reg = self.ridge * np.eye(P)
        reg[0, 0] = 0.0
        A = XtX + reg
        self.coef = np.zeros((P, 3), dtype=np.float64)
        Xt = X.T
        for ch in range(3):
            self.coef[:, ch] = np.linalg.solve(A, Xt @ y_log[:, ch])

    def predict(self, ds: Dataset):
        seqs, _ = prepare_sequences(ds, self.mats, self.n_layers)
        L = self.n_layers
        M = len(self.mats)
        P = self.coef.shape[0]
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        unary_start = 1
        pair_start = 1 + L * M
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, unary_start + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0
            for p in range(L - 1):
                a = self.mi.get(seq[p], self.mi["EMPTY"])
                b = self.mi.get(seq[p + 1], self.mi["EMPTY"])
                X[i, pair_start + p * M * M + a * M + b] += 1.0
        y_log = X @ self.coef
        y_lin = np.exp(y_log)
        return np.clip(linear_to_srgb(y_lin), 0, 1)


class ODFullPairsModel(BaseExtraModel):
    def __init__(self, ridge=5e-1):
        self.ridge = ridge
        self.coef = None
        self.mats = None
        self.mi = None
        self.n_layers = 5

    def fit(self, train_ds: Dataset, all_mats: list[str]):
        seqs, y_srgb = prepare_sequences(train_ds, all_mats, self.n_layers)
        self.mats = all_mats
        self.mi = {m: i for i, m in enumerate(self.mats)}

        y_lin = srgb_to_linear(y_srgb)
        y_log = np.log(np.clip(y_lin, 1e-6, 1.0))

        L = self.n_layers
        M = len(self.mats)
        self.pairs = [(p, q) for p in range(L) for q in range(p + 1, L)]
        P = 1 + L * M + len(self.pairs) * M * M
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        unary_start = 1
        pair_start = 1 + L * M
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, unary_start + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0
            for k, (p, q) in enumerate(self.pairs):
                a = self.mi.get(seq[p], self.mi["EMPTY"])
                b = self.mi.get(seq[q], self.mi["EMPTY"])
                X[i, pair_start + k * M * M + a * M + b] += 1.0

        XtX = X.T @ X
        reg = self.ridge * np.eye(P)
        reg[0, 0] = 0.0
        A = XtX + reg
        self.coef = np.zeros((P, 3), dtype=np.float64)
        Xt = X.T
        for ch in range(3):
            self.coef[:, ch] = np.linalg.solve(A, Xt @ y_log[:, ch])

    def predict(self, ds: Dataset):
        seqs, _ = prepare_sequences(ds, self.mats, self.n_layers)
        L = self.n_layers
        M = len(self.mats)
        P = self.coef.shape[0]
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        unary_start = 1
        pair_start = 1 + L * M
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, unary_start + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0
            for k, (p, q) in enumerate(self.pairs):
                a = self.mi.get(seq[p], self.mi["EMPTY"])
                b = self.mi.get(seq[q], self.mi["EMPTY"])
                X[i, pair_start + k * M * M + a * M + b] += 1.0
        y_log = X @ self.coef
        y_lin = np.exp(y_log)
        return np.clip(linear_to_srgb(y_lin), 0, 1)


class LogitAdjPairsModel(BaseExtraModel):
    def __init__(self, ridge=1.0):
        self.ridge = ridge
        self.coef = None
        self.mats = None
        self.mi = None
        self.n_layers = 5

    def fit(self, train_ds: Dataset, all_mats: list[str]):
        seqs, y_srgb = prepare_sequences(train_ds, all_mats, self.n_layers)
        self.mats = all_mats
        self.mi = {m: i for i, m in enumerate(self.mats)}

        y_lin = srgb_to_linear(y_srgb)
        eps = 1e-5
        y_lin = np.clip(y_lin, eps, 1 - eps)
        y_z = np.log(y_lin / (1 - y_lin))

        L = self.n_layers
        M = len(self.mats)
        P = 1 + L * M + (L - 1) * M * M
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        unary_start = 1
        pair_start = 1 + L * M
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, unary_start + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0
            for p in range(L - 1):
                a = self.mi.get(seq[p], self.mi["EMPTY"])
                b = self.mi.get(seq[p + 1], self.mi["EMPTY"])
                X[i, pair_start + p * M * M + a * M + b] += 1.0

        XtX = X.T @ X
        reg = self.ridge * np.eye(P)
        reg[0, 0] = 0.0
        A = XtX + reg
        self.coef = np.zeros((P, 3), dtype=np.float64)
        Xt = X.T
        for ch in range(3):
            self.coef[:, ch] = np.linalg.solve(A, Xt @ y_z[:, ch])

    def predict(self, ds: Dataset):
        seqs, _ = prepare_sequences(ds, self.mats, self.n_layers)
        L = self.n_layers
        M = len(self.mats)
        P = self.coef.shape[0]
        N = len(seqs)
        X = np.zeros((N, P), dtype=np.float64)
        X[:, 0] = 1.0
        unary_start = 1
        pair_start = 1 + L * M
        for i, seq in enumerate(seqs):
            for p, m in enumerate(seq):
                X[i, unary_start + p * M + self.mi.get(m, self.mi["EMPTY"])] += 1.0
            for p in range(L - 1):
                a = self.mi.get(seq[p], self.mi["EMPTY"])
                b = self.mi.get(seq[p + 1], self.mi["EMPTY"])
                X[i, pair_start + p * M * M + a * M + b] += 1.0
        z = X @ self.coef
        y_lin = 1 / (1 + np.exp(-z))
        return np.clip(linear_to_srgb(y_lin), 0, 1)


class RTStackingModel(BaseExtraModel):
    def __init__(self, reg=1e-3, layered=False):
        self.reg = reg
        self.layered = layered
        self.alpha = None
        self.beta = None
        self.gamma = None
        self.mats = None
        self.mi = None
        self.n_layers = 5
        self.order = "bottom_first"

    def fit(self, train_ds: Dataset, all_mats: list[str]):
        seqs, y_srgb = prepare_sequences(train_ds, all_mats, self.n_layers)
        self.mats = all_mats
        self.mi = {m: i for i, m in enumerate(self.mats)}
        n_mats = len(self.mats)
        N = len(seqs)

        idx_mat = np.full((N, self.n_layers), self.mi["EMPTY"], dtype=np.int32)
        for i, seq in enumerate(seqs):
            for j, m in enumerate(seq):
                idx_mat[i, j] = self.mi.get(m, self.mi["EMPTY"])
        if self.order == "bottom_first":
            idx_mat = idx_mat[:, ::-1]

        y_lin = srgb_to_linear(y_srgb)

        def pack(a, b, g):
            return np.concatenate([a.ravel(), b.ravel(), g.ravel()]).astype(np.float64)

        def unpack(x):
            if self.layered:
                n = n_mats * self.n_layers * 3
                a = x[:n].reshape((n_mats, self.n_layers, 3))
                b = x[n : 2 * n].reshape((n_mats, self.n_layers, 3))
                g = x[2 * n :].reshape((3,))
            else:
                n = n_mats * 3
                a = x[:n].reshape((n_mats, 3))
                b = x[n : 2 * n].reshape((n_mats, 3))
                g = x[2 * n :].reshape((3,))
            return a, b, g

        if self.layered:
            a0 = np.full((n_mats, self.n_layers, 3), -3.0)
            b0 = np.full((n_mats, self.n_layers, 3), 3.0)
        else:
            a0 = np.full((n_mats, 3), -3.0)
            b0 = np.full((n_mats, 3), 3.0)
        g0 = np.array([1.0, 1.0, 1.0])
        x0 = pack(a0, b0, g0)

        def residual(x):
            a, b, g = unpack(x)
            r = sigmoid(a)
            t = sigmoid(b) * (1.0 - r)
            # EMPTY
            i0 = self.mi["EMPTY"]
            if self.layered:
                r[i0, :, :] = 0.0
                t[i0, :, :] = 1.0
            else:
                r[i0, :] = 0.0
                t[i0, :] = 1.0

            rb = sigmoid(g)[None, :]
            R = np.repeat(rb, repeats=N, axis=0)
            for j in range(self.n_layers):
                idx = idx_mat[:, j]
                if self.layered:
                    r1, t1 = r[idx, j, :], t[idx, j, :]
                else:
                    r1, t1 = r[idx, :], t[idx, :]
                denom = np.clip(1.0 - r1 * R, 1e-6, 1e9)
                R = r1 + (t1 * t1) * R / denom
            res = (R - y_lin).ravel()
            return np.concatenate([res, np.sqrt(self.reg) * x])

        res = least_squares(residual, x0, loss="huber", f_scale=0.05, max_nfev=100)
        self.alpha, self.beta, self.gamma = unpack(res.x)

    def predict(self, ds: Dataset):
        seqs, _ = prepare_sequences(ds, self.mats, self.n_layers)
        N = len(seqs)
        idx_mat = np.full((N, self.n_layers), self.mi["EMPTY"], dtype=np.int32)
        for i, seq in enumerate(seqs):
            for j, m in enumerate(seq):
                idx_mat[i, j] = self.mi.get(m, self.mi["EMPTY"])
        if self.order == "bottom_first":
            idx_mat = idx_mat[:, ::-1]

        r = sigmoid(self.alpha)
        t = sigmoid(self.beta) * (1.0 - r)
        i0 = self.mi["EMPTY"]
        if self.layered:
            r[i0, :, :] = 0.0
            t[i0, :, :] = 1.0
        else:
            r[i0, :] = 0.0
            t[i0, :] = 1.0

        rb = sigmoid(self.gamma)[None, :]
        R = np.repeat(rb, repeats=N, axis=0)
        for j in range(self.n_layers):
            idx = idx_mat[:, j]
            if self.layered:
                r1, t1 = r[idx, j, :], t[idx, j, :]
            else:
                r1, t1 = r[idx, :], t[idx, :]
            denom = np.clip(1.0 - r1 * R, 1e-6, 1e9)
            R = r1 + (t1 * t1) * R / denom
        return np.clip(linear_to_srgb(R), 0, 1)


# --- 包装 PhysGPR 模型 ---


class PhysGPRModelWrapper(BaseExtraModel):
    def __init__(self, optical_model="four_flux"):
        self.optical_model = optical_model
        self.model = None
        self.cfg = None
        self.material_keys = None

    def fit(self, train_ds: Dataset, all_mats: list[str]):
        # 使用默认的 FitArgs
        args = FitArgs(
            dataset=Path("fake.json"),
            out_dir=Path("out_temp"),
            n_layers=5,
            opt_steps=300,
            opt_reg=1e-6,
            gpr_noise=1e-7,
            gpr_lengthscale=0.1,
            gpr_signal=1.0,
            gpr_jitter=1e-9,
            use_vulkan=False,  # 为了稳定，对比时统一用 numpy
            optical_model=self.optical_model,
        )
        self.cfg = PhysGPRConfig(
            n_layers=args.n_layers,
            opt_steps=args.opt_steps,
            opt_reg=args.opt_reg,
            gpr_noise=args.gpr_noise,
            gpr_lengthscale=args.gpr_lengthscale,
            gpr_signal=args.gpr_signal,
            gpr_jitter=args.gpr_jitter,
            use_vulkan=args.use_vulkan,
            optical_model=args.optical_model,
        )

        train_cells = filter_training_cells(train_ds)
        recipes = [c.recipe for c in train_cells]
        y_lab = np.stack(
            [
                rgb01_to_lab(c.measured_rgb.astype(np.float32) / 255.0)
                for c in train_cells
            ]
        )
        # 展平 y_lab 确保它是 (N, 3)
        if y_lab.ndim == 3:
            y_lab = y_lab.reshape(-1, 3)
        self.material_keys = all_mats

        # 训练
        self.model = train_phys_gpr(recipes, y_lab, self.material_keys, self.cfg)

    def predict(self, ds: Dataset):
        recipes = [c.recipe for c in ds.cells]
        seqs = build_layer_sequences(
            recipes,
            self.material_keys,
            self.cfg.n_layers,
            layer_names_order=self.cfg.layer_names_order,
        )

        # 提取基础 Lab (用于 GPR 特征)
        # 注意：这里需要 build_gpr_features，而它需要 base_lab
        from oc_xgb.xgb_fit import predict_ad_rgb01

        base_rgb01 = predict_ad_rgb01(
            seqs,
            self.material_keys,
            self.model.optical,
            use_vulkan=self.cfg.use_vulkan,
            model_type=self.cfg.optical_model,
        )
        base_lab = rgb01_to_lab(base_rgb01)

        X, _ = build_gpr_features(
            recipes,
            self.material_keys,
            base_lab,
            n_layers=self.cfg.n_layers,
            layer_names_order=self.cfg.layer_names_order,
            k1=self.model.optical.k1,
            k2=self.model.optical.k2,
            backing=self.model.optical.backing,
        )

        pred_lab = predict_phys_gpr_lab(
            self.model,
            seqs,
            X,
            use_vulkan=self.cfg.use_vulkan,
            optical_model=self.cfg.optical_model,
        )
        return np.clip(lab_to_rgb01(pred_lab), 0, 1)


# --- 主程序 ---


def main():
    parser = argparse.ArgumentParser(description="综合评估对比")
    parser.add_argument("--data-dir", type=str, required=True, help="数据集所在目录")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    # 1. 加载数据集 A, B, C, D, E
    palettes = {}
    for pid in ["A", "B", "C", "D", "E"]:
        p = data_dir / f"dataset_cells_{pid}.json"
        if pid == "A" and not p.exists():
            p = data_dir / "dataset_cells.json"
        if p.exists():
            palettes[pid] = load_dataset(p, palette_id=pid)
            logger.info(f"已加载色盘 {pid}: {len(palettes[pid].cells)} 个格子")

    if "A" not in palettes:
        logger.error("错误: 必须包含训练色盘 A")
        return

    all_ds = list(palettes.values())
    all_mats = build_all_mats(all_ds)
    logger.info(f"总材料数: {len(all_mats)}")

    # 2. 定义要评估的模型
    models = {
        "PhysGPR-FourFlux": PhysGPRModelWrapper(optical_model="four_flux"),
        "PhysGPR-TMM": PhysGPRModelWrapper(optical_model="tmm"),
        "OD-Unary": ODUnaryModel(),
        "OD-AdjPairs": ODAdjPairsModel(),
        "OD-FullPairs": ODFullPairsModel(),
        "Logit-AdjPairs": LogitAdjPairsModel(),
        "RT-Stacking": RTStackingModel(),
    }

    results = {}  # {model_name: {pid: mean_de}}

    for name, model in models.items():
        logger.info(f"\n--- 正在评估模型: {name} ---")
        try:
            model.fit(palettes["A"], all_mats)
            model_results = {}
            for pid, ds in palettes.items():
                pred_rgb01 = model.predict(ds)

                # 获取该数据集的真实测量的 Lab
                _, meas_rgb01 = prepare_sequences(ds, all_mats)
                meas_lab = rgb01_to_lab(meas_rgb01)
                pred_lab = rgb01_to_lab(pred_rgb01)

                de = deltaE76(meas_lab, pred_lab)
                model_results[pid] = {
                    "mean": float(np.mean(de)),
                    "p95": float(np.quantile(de, 0.95)),
                }
                logger.info(
                    f"  色盘 {pid}: Mean dE = {model_results[pid]['mean']:.4f}, P95 = {model_results[pid]['p95']:.4f}"
                )

                # 针对 RT-Stacking 算法生成可视化图片
                if name == "RT-Stacking":
                    out_dir = Path("out")
                    out_eval = out_dir / "evaluation"
                    out_viz = out_dir / "visualization"
                    out_eval.mkdir(parents=True, exist_ok=True)
                    out_viz.mkdir(parents=True, exist_ok=True)

                    pred_u8 = (pred_rgb01 * 255.0 + 0.5).astype(np.uint8)
                    diags, _ = compute_diagnostics(
                        cells_all=ds.cells,
                        material_keys=all_mats,
                        feature_names=[],
                        X_all=np.zeros((len(ds.cells), 0)),
                        pred_rgb=pred_u8,
                        out_dir=out_eval,
                        palette_id=pid,
                    )
                    render_boards_for_palette(
                        diags, out_viz, palette_id=pid, flip_first_layer=True
                    )

            results[name] = model_results
        except Exception as e:
            logger.error(f"  模型 {name} 运行失败: {e}")
            import traceback

            traceback.print_exc()

    # 3. 输出汇总表格
    logger.info("\n" + "=" * 80)
    logger.info(
        f"{'模型名称':<20} | {'A (Train)':<12} | {'B':<12} | {'C':<12} | {'D':<12} | {'E':<12}"
    )
    logger.info("-" * 80)
    for name in models.keys():
        if name not in results:
            continue
        row = f"{name:<20} | "
        for pid in ["A", "B", "C", "D", "E"]:
            if pid in results[name]:
                row += f"{results[name][pid]['mean']:<12.4f} | "
            else:
                row += f"{'N/A':<12} | "
        logger.info(row)
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
