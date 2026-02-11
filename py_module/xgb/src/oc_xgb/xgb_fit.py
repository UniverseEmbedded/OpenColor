"""
物理GPR拟合模块
实现物理模型(Adding-Doubling算法)与GPR残差修正的联合训练
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from oc_xgb.color_space import rgb01_to_lab, lab_to_rgb01
from oc_xgb.optical_model import (
    OpticalParams as RawOpticalParams,
    NumpyFourFluxModel,
    VulkanFourFluxModel,
)
from .xgb_features import build_gpr_features, build_layer_sequences


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PhysGPRConfig:
    n_layers: int
    opt_steps: int
    opt_reg: float
    gpr_noise: float
    gpr_lengthscale: float
    gpr_signal: float
    gpr_jitter: float
    use_vulkan: bool = True  # 默认使用 Vulkan
    k1: float = 0.04  # Saunderson 参数 1 (默认 0.04)
    k2: float = 0.0  # Saunderson 参数 2 (默认 0.0)
    backing: float = 0.98  # 背景反射率 (默认 0.98)
    optimize_k: bool = False
    pure_weight: float = 10.0
    optical_model: str = "four_flux"  # 光学模型类型: "four_flux" (默认), "tmm"
    layer_names_order: str = "bottom_first"


@dataclass
class OpticalParams:
    material_keys: list[str]
    mu_a: np.ndarray  # 吸收系数 (M, 3)
    mu_s: np.ndarray  # 散射系数 (M, 3)
    g: np.ndarray  # 各向异性因子 (M, 3)
    n_layers: int
    k1: float = 0.0
    k2: float = 0.0
    backing: float = 0.98

    def to_raw(self) -> RawOpticalParams:
        return RawOpticalParams(mu_a=self.mu_a, mu_s=self.mu_s, g=self.g)

    @classmethod
    def from_raw(
        cls,
        raw: RawOpticalParams,
        material_keys: list[str],
        n_layers: int,
        k1: float = 0.0,
        k2: float = 0.0,
        backing: float = 0.98,
    ) -> OpticalParams:
        return cls(
            material_keys=material_keys,
            mu_a=raw.mu_a,
            mu_s=raw.mu_s,
            g=raw.g,
            n_layers=n_layers,
            k1=k1,
            k2=k2,
            backing=backing,
        )


@dataclass
class GPRModel:
    X_train: np.ndarray
    L: np.ndarray | None  # 训练时使用，预测时可选
    alpha: np.ndarray
    y_mean: float
    y_std: float
    x_mean: np.ndarray
    x_std: np.ndarray
    lengthscale: float
    signal_var: float
    noise: float


@dataclass
class PhysGPRModel:
    optical: OpticalParams
    gpr_L: GPRModel
    gpr_a: GPRModel
    gpr_b: GPRModel
    feature_names: list[str]


def get_optical_model(use_vulkan: bool = True, model_type: str = "tmm"):
    """
    获取光学模型实例

    Args:
        use_vulkan: 是否使用Vulkan加速（仅对four_flux有效）
        model_type: 模型类型，"tmm"(默认) 或 "four_flux"
    """
    import warnings

    if model_type == "tmm":
        warnings.warn(
            "TMM模型已废弃，请使用RTS模型代替", DeprecationWarning, stacklevel=2
        )
        raise ValueError(f"已废弃的光学模型类型: {model_type}")
    elif model_type == "four_flux":
        warnings.warn(
            "FourFlux模型已废弃，请使用RTS模型代替", DeprecationWarning, stacklevel=2
        )
        # 使用FourFlux模型
        if use_vulkan:
            return VulkanFourFluxModel()
        return NumpyFourFluxModel()
    else:
        raise ValueError(f"未知的光学模型类型: {model_type}")


def predict_ad_rgb01(
    sequences: list[list[str]],
    material_keys: list[str],
    params: OpticalParams,
    backing: float | None = None,
    use_vulkan: bool = True,
    k1: float | None = None,
    k2: float | None = None,
    model_type: str = "four_flux",
) -> np.ndarray:
    model = get_optical_model(use_vulkan, model_type=model_type)
    b = backing if backing is not None else params.backing
    k1_v = k1 if k1 is not None else params.k1
    k2_v = k2 if k2 is not None else params.k2
    return model.predict_rgb(
        sequences, material_keys, params.to_raw(), backing=b, k1=k1_v, k2=k2_v
    )


def fit_optical_params(
    sequences: list[list[str]],
    y_lab: np.ndarray,
    material_keys: list[str],
    cfg: PhysGPRConfig,
) -> OpticalParams:
    import warnings

    if cfg.optical_model in ("tmm", "four_flux"):
        warnings.warn(
            f"{cfg.optical_model} 模型已废弃，建议使用RTS模型以获得更好的黑色表现",
            DeprecationWarning,
            stacklevel=2,
        )
    model = get_optical_model(cfg.use_vulkan, model_type=cfg.optical_model)

    # 构造初始参数
    m = len(material_keys)
    mu_a = np.zeros((m, 3), dtype=np.float32)
    mu_s = np.zeros((m, 3), dtype=np.float32)
    g = np.zeros((m, 3), dtype=np.float32)

    # 简单的启发式初始化
    # 修复：使用反比关系确保黑色材料有足够高的吸收系数
    rgb01 = lab_to_rgb01(y_lab)
    for i, mat in enumerate(material_keys):
        mat_u = str(mat).upper()
        mask = np.array(
            [all(str(name).upper() == mat_u for name in seq) for seq in sequences],
            dtype=bool,
        )
        mean = rgb01[mask].mean(axis=0) if np.any(mask) else rgb01.mean(axis=0)
        mean = np.clip(mean, 0.0, 1.0)

        # 吸收系数：反射率越低，吸收越强
        # 使用反比关系：k ≈ 1 / (reflectance + epsilon)
        # 白色(reflectance≈1) -> k≈1.0 (低吸收)
        # 黑色(reflectance≈0) -> k≈100 (高吸收)
        mu_a[i] = np.log(np.clip(1.0 / (mean + 0.01), 0.1, 100.0))

        # 散射系数：白色高散射，黑色低散射
        mu_s[i] = np.log(np.clip(0.2 + 0.8 * mean, 1e-3, 10.0))

        # 各向异性因子
        g[i] = np.clip((mean - 0.5) * 4.0, -4.0, 4.0)

    initial_params = RawOpticalParams(mu_a=mu_a, mu_s=mu_s, g=g)
    weights = np.ones(len(sequences), dtype=np.float32)
    if cfg.pure_weight > 1.0:
        for i, seq in enumerate(sequences):
            if not seq:
                continue
            first = str(seq[0]).upper()
            if all(str(name).upper() == first for name in seq):
                weights[i] = float(cfg.pure_weight)

    # 根据模型类型执行不同的拟合逻辑
    if cfg.optical_model == "tmm":
        logger.info("[calib_color_model_fit] TMM 模型启用混合拟合策略")

        # TMM使用两阶段拟合：
        # 1. 先进行全局尺度调整（快速收敛）
        # 2. 再进行逐材料微调（精细调整）

        rng = np.random.default_rng(0)
        y_lab_arr = np.asarray(y_lab, dtype=np.float32)
        n_total = len(sequences)
        if n_total <= 0:
            raw_fitted = initial_params
            fitted_k1 = cfg.k1
            fitted_k2 = cfg.k2
            return OpticalParams.from_raw(
                raw_fitted,
                material_keys,
                cfg.n_layers,
                k1=fitted_k1,
                k2=fitted_k2,
                backing=cfg.backing,
            )

        # 阶段1：全局尺度调整
        is_pure = np.array(
            [
                (len(seq) > 0)
                and all(str(x).upper() == str(seq[0]).upper() for x in seq)
                for seq in sequences
            ],
            dtype=bool,
        )
        pure_idx = np.flatnonzero(is_pure)
        mix_idx = np.flatnonzero(~is_pure)

        sel_idx = pure_idx
        if mix_idx.size > 0:
            extra = rng.choice(mix_idx, size=min(300, int(mix_idx.size)), replace=False)
            sel_idx = np.concatenate([sel_idx, extra]) if sel_idx.size > 0 else extra
        if sel_idx.size == 0:
            sel_idx = np.arange(n_total, dtype=np.int32)
        if sel_idx.size > 600:
            sel_idx = rng.choice(sel_idx, size=600, replace=False)

        sel_idx = np.asarray(sel_idx, dtype=np.int32)
        sel_sequences = [sequences[int(i)] for i in sel_idx]
        sel_y_lab = y_lab_arr[sel_idx]

        model_cpu = get_optical_model(use_vulkan=False, model_type="tmm")

        def _objective_global(x: np.ndarray) -> float:
            log_k_scale = float(x[0])
            log_d_scale = float(x[1])
            mu_a_adj = (initial_params.mu_a + log_k_scale).astype(np.float32)
            mu_s_adj = (initial_params.mu_s + log_d_scale).astype(np.float32)

            params_adj = RawOpticalParams(
                mu_a=mu_a_adj, mu_s=mu_s_adj, g=initial_params.g
            )
            pred_rgb01 = model_cpu.predict_rgb(
                sel_sequences,
                material_keys,
                params_adj,
                backing=cfg.backing,
                k1=cfg.k1,
                k2=cfg.k2,
            )
            pred_lab = rgb01_to_lab(pred_rgb01)
            de = pred_lab - sel_y_lab
            de = np.sqrt(np.sum(de * de, axis=1))
            loss = float(np.mean(de))
            reg = 0.02 * (log_k_scale * log_k_scale + log_d_scale * log_d_scale)
            return loss + reg

        x0 = np.array([0.0, 0.0], dtype=np.float64)
        try:
            res = minimize(
                _objective_global,
                x0,
                method="Powell",
                bounds=[(-3.0, 3.0), (-3.0, 3.0)],
                options={"maxiter": 40, "disp": False},
            )
            log_k_scale = float(res.x[0])
            log_d_scale = float(res.x[1])
            logger.info(
                "[calib_color_model_fit] TMM 全局尺度拟合完成: "
                f"k_scale={np.exp(log_k_scale):.6f}, d_scale={np.exp(log_d_scale):.6f}, "
                f"loss={float(res.fun):.6f}"
            )
        except Exception as e:
            logger.error(f"[calib_color_model_fit] TMM 全局尺度拟合失败: {e}")
            log_k_scale = 0.0
            log_d_scale = 0.0

        # 应用全局调整后的参数
        adjusted_params = RawOpticalParams(
            mu_a=(initial_params.mu_a + log_k_scale).astype(np.float32),
            mu_s=(initial_params.mu_s + log_d_scale).astype(np.float32),
            g=initial_params.g,
        )

        # 阶段2：逐材料微调（仅对纯色样本进行）
        # 使用启发式方法调整每种材料的参数
        final_mu_a = adjusted_params.mu_a.copy()
        final_mu_s = adjusted_params.mu_s.copy()

        for i, mat in enumerate(material_keys):
            mat_upper = str(mat).upper()
            # 找到该材料的纯色样本
            pure_mask = np.array(
                [
                    (len(seq) > 0) and all(str(s).upper() == mat_upper for s in seq)
                    for seq in sequences
                ]
            )
            if not np.any(pure_mask):
                continue

            pure_idx_mat = np.flatnonzero(pure_mask)
            # 只取前5个样本避免过拟合
            if len(pure_idx_mat) > 5:
                pure_idx_mat = pure_idx_mat[:5]

            seq_mat = [sequences[int(idx)] for idx in pure_idx_mat]
            y_lab_mat = y_lab_arr[pure_idx_mat]

            def _objective_material(x: np.ndarray) -> float:
                mu_a_new = final_mu_a.copy()
                mu_s_new = final_mu_s.copy()
                mu_a_new[i] = x[:3].astype(np.float32)
                mu_s_new[i] = x[3:6].astype(np.float32)

                p = RawOpticalParams(mu_a=mu_a_new, mu_s=mu_s_new, g=adjusted_params.g)
                pred_rgb = model_cpu.predict_rgb(
                    seq_mat, material_keys, p, backing=cfg.backing, k1=cfg.k1, k2=cfg.k2
                )
                pred_lab = rgb01_to_lab(pred_rgb)
                de = pred_lab - y_lab_mat
                de = np.sqrt(np.sum(de * de, axis=1))
                return float(np.mean(de))

            x0_mat = np.concatenate([final_mu_a[i], final_mu_s[i]]).astype(np.float64)
            try:
                res_mat = minimize(
                    _objective_material,
                    x0_mat,
                    method="Powell",
                    bounds=[(-6.0, 6.0)] * 6,
                    options={"maxiter": 20, "disp": False},
                )
                final_mu_a[i] = res_mat.x[:3].astype(np.float32)
                final_mu_s[i] = res_mat.x[3:6].astype(np.float32)
            except Exception as e:
                logger.error(f"[calib_color_model_fit] 材料 {mat} 微调失败: {e}")

        raw_fitted = RawOpticalParams(
            mu_a=final_mu_a, mu_s=final_mu_s, g=adjusted_params.g
        )
        fitted_k1 = cfg.k1
        fitted_k2 = cfg.k2
        logger.info("[calib_color_model_fit] TMM 逐材料微调完成")
    else:
        # FourFlux模型使用完整的拟合流程
        raw_fitted, fitted_k1, fitted_k2 = model.fit(
            sequences,
            y_lab,
            material_keys,
            initial_params,
            maxiter=cfg.opt_steps,
            lr=1e-2,  # JAX 使用的步长
            k1=cfg.k1,
            k2=cfg.k2,
            backing=cfg.backing,
            optimize_k=cfg.optimize_k,
            reg=cfg.opt_reg,
            sample_weight=weights,
        )

    return OpticalParams.from_raw(
        raw_fitted,
        material_keys,
        cfg.n_layers,
        k1=fitted_k1,
        k2=fitted_k2,
        backing=cfg.backing,
    )


def _fit_gpr(X: np.ndarray, y: np.ndarray, cfg: PhysGPRConfig) -> GPRModel:
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32).reshape(-1)
    x_mean = X.mean(axis=0)
    x_std = X.std(axis=0)
    x_std = np.where(x_std < 1e-6, 1.0, x_std)
    Xs = (X - x_mean) / x_std

    y_mean = float(np.mean(y))
    y_std = float(np.std(y)) if float(np.std(y)) > 1e-6 else 1.0
    ys = (y - y_mean) / y_std

    if cfg.gpr_lengthscale > 0:
        lengthscale = float(cfg.gpr_lengthscale)
    else:
        diff = Xs[:, None, :] - Xs[None, :, :]
        d2 = np.sum(diff * diff, axis=2)
        lengthscale = float(np.sqrt(np.median(d2) + 1e-6))

    signal_var = (
        float(cfg.gpr_signal) if cfg.gpr_signal > 0 else float(np.var(ys) + 1e-6)
    )
    noise = float(cfg.gpr_noise)

    diff = Xs[:, None, :] - Xs[None, :, :]
    d2 = np.sum(diff * diff, axis=2)
    K = signal_var * np.exp(-0.5 * d2 / (lengthscale * lengthscale))

    jitter = float(cfg.gpr_jitter)
    for _ in range(6):
        try:
            L = np.linalg.cholesky(
                K + (noise + jitter) * np.eye(K.shape[0], dtype=np.float32)
            )
            break
        except Exception:
            jitter *= 10.0
    else:
        raise RuntimeError("GPR 矩阵分解失败，请调大噪声或检查输入数据")

    alpha = np.linalg.solve(L.T, np.linalg.solve(L, ys))
    return GPRModel(
        X_train=Xs,
        L=L,
        alpha=alpha,
        y_mean=y_mean,
        y_std=y_std,
        x_mean=x_mean,
        x_std=x_std,
        lengthscale=lengthscale,
        signal_var=signal_var,
        noise=noise + jitter,
    )


def _predict_gpr(model: GPRModel, X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=np.float32)
    Xs = (X - model.x_mean) / model.x_std
    diff = Xs[:, None, :] - model.X_train[None, :, :]
    d2 = np.sum(diff * diff, axis=2)
    K_s = model.signal_var * np.exp(-0.5 * d2 / (model.lengthscale * model.lengthscale))
    y = K_s @ model.alpha
    max_k = np.max(K_s, axis=1)
    denom = float(model.signal_var) if float(model.signal_var) > 1e-12 else 1.0
    w = np.clip(max_k / denom, 0.0, 1.0)
    return (y * model.y_std + model.y_mean * w).astype(np.float32)


def train_phys_gpr(
    recipes: list[dict[str, float]],
    Y_lab: np.ndarray,
    material_keys: list[str],
    cfg: PhysGPRConfig,
    metadata: list[dict] | None = None,
) -> PhysGPRModel:
    sequences = build_layer_sequences(
        recipes, material_keys, cfg.n_layers, layer_names_order=cfg.layer_names_order
    )
    logger.info("[calib_color_model_fit] 开始拟合物理参数")
    optical = fit_optical_params(sequences, Y_lab, material_keys, cfg)
    base_rgb01 = predict_ad_rgb01(
        sequences,
        material_keys,
        optical,
        use_vulkan=cfg.use_vulkan,
        backing=optical.backing,
        k1=optical.k1,
        k2=optical.k2,
        model_type=cfg.optical_model,
    )
    base_lab = rgb01_to_lab(base_rgb01)
    X_features, feature_names = build_gpr_features(
        recipes,
        material_keys,
        base_lab,
        n_layers=cfg.n_layers,
        layer_names_order=cfg.layer_names_order,
        k1=optical.k1,
        k2=optical.k2,
        backing=optical.backing,
    )

    # 检查特征冲突
    from collections import defaultdict

    feature_to_indices = defaultdict(list)
    for idx, row in enumerate(X_features):
        feature_to_indices[tuple(row.tolist())].append(idx)

    conflict_groups = {k: v for k, v in feature_to_indices.items() if len(v) > 1}

    if conflict_groups:
        total_conflicting_samples = sum(len(v) for v in conflict_groups.values())
        logger.warning(
            f"[calib_color_model_fit] 警告: 发现特征冲突！{len(X_features)} 个样本中存在 {len(conflict_groups)} 组冲突，共涉及 {total_conflicting_samples} 个格子。"
        )

        if metadata:
            logger.info("[calib_color_model_fit] --- 前 10 组冲突详情 ---")
            sorted_groups = sorted(
                conflict_groups.items(), key=lambda x: len(x[1]), reverse=True
            )
            for i, (feat, indices) in enumerate(sorted_groups[:10]):
                samples = []
                for idx in indices:
                    m = metadata[idx]
                    samples.append(f"[盘{m['palette']} ({m['row']},{m['col']})]")

                rep_recipe = recipes[indices[0]]
                clean_recipe = {
                    k: v for k, v in rep_recipe.items() if not k.startswith("_")
                }
                logger.info(
                    f"  冲突组 {i + 1} ({len(indices)}个重复): {', '.join(samples)} | 配方内容: {clean_recipe}"
                )

    resid = Y_lab - base_lab

    logger.info("[calib_color_model_fit] 开始训练 GPR 残差模型")
    gpr_L = _fit_gpr(X_features, resid[:, 0], cfg)
    gpr_a = _fit_gpr(X_features, resid[:, 1], cfg)
    gpr_b = _fit_gpr(X_features, resid[:, 2], cfg)

    # 验证训练集上的拟合效果
    pred_resid_L = _predict_gpr(gpr_L, X_features)
    pred_resid_a = _predict_gpr(gpr_a, X_features)
    pred_resid_b = _predict_gpr(gpr_b, X_features)
    pred_resid = np.stack([pred_resid_L, pred_resid_a, pred_resid_b], axis=1)

    final_lab = base_lab + pred_resid
    err = np.sqrt(np.sum((Y_lab - final_lab) ** 2, axis=1))
    logger.info(
        f"[calib_color_model_fit] 训练集平均 DeltaE: {np.mean(err):.4f}, 最大 DeltaE: {np.max(err):.4f}"
    )

    return PhysGPRModel(
        optical=optical,
        gpr_L=gpr_L,
        gpr_a=gpr_a,
        gpr_b=gpr_b,
        feature_names=feature_names,
    )


def predict_phys_gpr_lab(
    model: PhysGPRModel,
    sequences: list[list[str]],
    X_features: np.ndarray,
    use_vulkan: bool = True,
    optical_model: str = "four_flux",
) -> np.ndarray:
    """
    联合模型预测: 物理模型输出 + GPR 残差修正
    """
    # 1. 物理模型预测 (sRGB -> Linear -> sRGB)
    base_rgb01 = predict_ad_rgb01(
        sequences,
        model.optical.material_keys,
        model.optical,
        use_vulkan=use_vulkan,
        backing=model.optical.backing,
        k1=model.optical.k1,
        k2=model.optical.k2,
        model_type=optical_model,
    )
    base_lab = rgb01_to_lab(base_rgb01)

    # 2. GPR 残差预测
    def predict_gpr(gpr: GPRModel, X: np.ndarray):
        # 归一化输入
        X_norm = (X - gpr.x_mean) / (gpr.x_std + 1e-9)

        # 计算核矩阵
        # K(X, X_train)
        sq_dist = (
            np.sum(X_norm**2, axis=1).reshape(-1, 1)
            + np.sum(gpr.X_train**2, axis=1)
            - 2 * np.dot(X_norm, gpr.X_train.T)
        )
        K = gpr.signal_var * np.exp(-0.5 * sq_dist / (gpr.lengthscale**2))

        y_pred_norm = K @ gpr.alpha
        return y_pred_norm * gpr.y_std + gpr.y_mean

    res_L = predict_gpr(model.gpr_L, X_features)
    res_a = predict_gpr(model.gpr_a, X_features)
    res_b = predict_gpr(model.gpr_b, X_features)

    # 3. 合并
    pred_lab = base_lab.copy()
    pred_lab[:, 0] += res_L
    pred_lab[:, 1] += res_a
    pred_lab[:, 2] += res_b

    return pred_lab
