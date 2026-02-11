"""
评估管线模块
运行完整的模型评估流程：在多个色盘上评估训练好的模型性能
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares

from oc_core_02.utils.logger import get_logger
from oc_proto.calib_color_rts.cli import FitArgs, VERSION
from oc_proto.calib_color_rts.cli import parse_args
from oc_proto.calib_color_rts.dataset_io import (
    load_dataset,
    Dataset,
    apply_bw_calibration_inverse,
)
from oc_proto.calib_color_rts.diagnostics import compute_diagnostics, render_boards
from oc_proto.calib_color_rts.runner import run_fit, synthesize_palettes_from_a
from oc_xgb.color_space import rgb01_to_lab, lab_to_rgb01
from oc_xgb.model_io import load_model
from oc_xgb.xgb_features import build_gpr_features, build_layer_sequences
from oc_xgb.xgb_fit import predict_phys_gpr_lab, predict_ad_rgb01, PhysGPRConfig

logger = get_logger(__name__)


def _rts_sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=np.float64), -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-x))


def _rts_srgb01_to_linear01_f64(srgb01: np.ndarray) -> np.ndarray:
    a = 0.055
    x = np.clip(np.asarray(srgb01, dtype=np.float64), 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)


def _rts_linear01_to_srgb01_f64(lin01: np.ndarray) -> np.ndarray:
    a = 0.055
    x = np.clip(np.asarray(lin01, dtype=np.float64), 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, (1 + a) * (x ** (1 / 2.4)) - a)


def _rts_normalize_seq(seq: list[str], n_layers: int) -> list[str]:
    out = [str(x).upper() for x in (seq or []) if str(x).strip()]
    if len(out) < n_layers:
        out += ["EMPTY"] * (n_layers - len(out))
    else:
        out = out[:n_layers]
    return out


def _rts_build_seq_from_recipe(recipe: dict, n_layers: int) -> list[str]:
    items: list[tuple[str, float]] = []
    for k, v in (recipe or {}).items():
        if str(k).startswith("_"):
            continue
        try:
            items.append((str(k).upper(), float(v)))
        except Exception:
            continue
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    seq: list[str] = []
    for k, v in items:
        n = int(round(v))
        if n <= 0:
            continue
        seq.extend([k] * n)
        if len(seq) >= n_layers:
            break
    return _rts_normalize_seq(seq, n_layers)


def _rts_sequences_for_dataset(ds: Dataset, n_layers: int) -> list[list[str]]:
    seqs: list[list[str]] = []
    for c in ds.cells:
        if isinstance(getattr(c, "layer_names", None), list) and len(c.layer_names) > 0:
            seqs.append(_rts_normalize_seq(list(c.layer_names), n_layers))
            continue
        if bool(getattr(c, "recipe", None)):
            seqs.append(_rts_build_seq_from_recipe(c.recipe, n_layers))
            continue
        seqs.append(["EMPTY"] * n_layers)
    return seqs


def _rts_idx_mat(
    seqs: list[list[str]], mats: list[str], layer_names_order: str
) -> np.ndarray:
    mat2idx = {m: i for i, m in enumerate(mats)}
    empty_idx = mat2idx.get("EMPTY", 0)
    N = len(seqs)
    L = len(seqs[0]) if seqs else 0
    idx = np.full((N, L), empty_idx, dtype=np.int32)
    for i, seq in enumerate(seqs):
        for j, m in enumerate(seq[:L]):
            idx[i, j] = mat2idx.get(str(m).upper(), empty_idx)
    if layer_names_order == "bottom_first":
        idx = idx[:, ::-1]
    return idx


def _rts_fit_model(
    train_ds: Dataset, n_layers: int, layer_names_order: str, max_nfev: int, reg: float
) -> dict:
    train_cells = [c for c in train_ds.cells if c.enabled and bool(c.recipe)]
    if not train_cells:
        raise RuntimeError("训练色盘A中没有可用训练样本")

    seqs_train = []
    y_train_srgb01 = []
    for c in train_cells:
        if isinstance(getattr(c, "layer_names", None), list) and len(c.layer_names) > 0:
            seqs_train.append(_rts_normalize_seq(list(c.layer_names), n_layers))
        else:
            seqs_train.append(_rts_build_seq_from_recipe(c.recipe, n_layers))
        y_train_srgb01.append((c.measured_rgb.astype(np.float64) / 255.0).tolist())
    y_train_srgb01 = np.asarray(y_train_srgb01, dtype=np.float64)

    mats_set: set[str] = set(["EMPTY"])
    for s in seqs_train:
        for m in s:
            mats_set.add(str(m).upper())
    mats = sorted(mats_set)
    if "EMPTY" in mats:
        mats.remove("EMPTY")
    mats = ["EMPTY"] + mats

    idx_train = _rts_idx_mat(seqs_train, mats, layer_names_order=layer_names_order)
    y_train_lin = _rts_srgb01_to_linear01_f64(y_train_srgb01)

    n_mats = len(mats)

    # 修复：为不同材料设置合理的初始值
    # alpha控制反射率：alpha越大，反射率越高
    # beta控制透射率：beta越大，透射率越高
    alpha0 = np.full((n_mats, 3), -3.0, dtype=np.float64)  # 默认低反射
    beta0 = np.full((n_mats, 3), 3.0, dtype=np.float64)  # 默认高透射

    # 根据材料名称设置特定的初始值
    for i, mat in enumerate(mats):
        mat_upper = mat.upper()
        if mat_upper == "BLACK":
            # 黑色：极低反射率，极低透射率（高吸收）
            alpha0[i] = [-5.0, -5.0, -5.0]  # sigmoid(-5) ≈ 0.007
            beta0[i] = [-5.0, -5.0, -5.0]  # sigmoid(-5) ≈ 0.007
        elif mat_upper == "WHITE":
            # 白色：高反射率，高透射率（高散射）
            alpha0[i] = [2.0, 2.0, 2.0]  # sigmoid(2) ≈ 0.88
            beta0[i] = [2.0, 2.0, 2.0]  # sigmoid(2) ≈ 0.88
        elif mat_upper in ("RED", "GREEN", "BLUE", "CYAN", "MAGENTA", "YELLOW"):
            # 彩色材料：中等反射率，中等透射率
            alpha0[i] = [0.0, 0.0, 0.0]  # sigmoid(0) = 0.5
            beta0[i] = [1.0, 1.0, 1.0]  # sigmoid(1) ≈ 0.73

    # 修复：gamma应该初始化为0（对应sigmoid(0)=0.5，中性灰色底层）
    # 而不是1.0（对应sigmoid(1)=0.73，偏白的底层）
    gamma0 = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    x0 = np.concatenate([alpha0.ravel(), beta0.ravel(), gamma0.ravel()], axis=0)

    def unpack(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x = np.asarray(x, dtype=np.float64)
        n = n_mats * 3
        alpha = x[:n].reshape((n_mats, 3))
        beta = x[n : 2 * n].reshape((n_mats, 3))
        gamma = x[2 * n : 2 * n + 3].reshape((3,))
        return alpha, beta, gamma

    def residual(x: np.ndarray) -> np.ndarray:
        alpha, beta, gamma = unpack(x)
        r = _rts_sigmoid(alpha)
        t = _rts_sigmoid(beta) * (1.0 - r)
        r[0, :] = 0.0
        t[0, :] = 1.0

        R = np.repeat(_rts_sigmoid(gamma)[None, :], repeats=idx_train.shape[0], axis=0)
        for j in range(idx_train.shape[1]):
            midx = idx_train[:, j]
            r1 = r[midx, :]
            t1 = t[midx, :]
            denom = np.clip(1.0 - r1 * R, 1e-6, 1e9)
            R = r1 + (t1 * t1) * R / denom
        res = (R - y_train_lin).ravel()
        res_reg = np.sqrt(reg) * x
        return np.concatenate([res, res_reg], axis=0)

    logger.info(
        f"[Eval] RTS: 开始拟合参数 (样本数={len(train_cells)}, 材料数={len(mats)})"
    )

    # 使用带边界的优化，为BLACK设置合理的边界约束
    # 而不是完全固定，这样可以在初始值附近微调
    black_idx = mats.index("BLACK") if "BLACK" in mats else None

    # 设置参数边界
    n_params = len(x0)
    lower_bounds = np.full(n_params, -10.0)  # 默认下界
    upper_bounds = np.full(n_params, 10.0)  # 默认上界

    if black_idx is not None:
        # 为BLACK设置更严格的边界，确保它保持低反射率/透射率
        # alpha参数位置: [black_idx*3 : black_idx*3+3]
        # beta参数位置: [n_mats*3 + black_idx*3 : n_mats*3 + black_idx*3+3]
        for c in range(3):
            # 限制alpha在[-6, -3]范围内（对应反射率0.002~0.047）
            lower_bounds[black_idx * 3 + c] = -6.0
            upper_bounds[black_idx * 3 + c] = -3.0
            # 限制beta在[-6, -3]范围内（对应透射率0.002~0.047）
            lower_bounds[n_mats * 3 + black_idx * 3 + c] = -6.0
            upper_bounds[n_mats * 3 + black_idx * 3 + c] = -3.0
        logger.info(f"[Eval] RTS: 为BLACK设置边界约束 (索引={black_idx})")

    # 修复：为gamma设置边界约束，防止优化到极端值
    # gamma参数位置: [2*n_mats*3 : 2*n_mats*3 + 3]
    gamma_start = 2 * n_mats * 3
    for c in range(3):
        # 限制gamma在[-3, 3]范围内（对应反射率0.047~0.95）
        lower_bounds[gamma_start + c] = -3.0
        upper_bounds[gamma_start + c] = 3.0
    logger.info(f"[Eval] RTS: 为gamma设置边界约束 [-3, 3]")

    res = least_squares(
        residual,
        x0,
        loss="huber",
        f_scale=0.05,
        max_nfev=int(max_nfev),
        diff_step=0.05,
        x_scale="jac",
        verbose=0,
        bounds=(lower_bounds, upper_bounds),
    )

    alpha, beta, gamma = unpack(res.x)

    pred_lin = _rts_predict_linear_idx(idx_train, alpha, beta, gamma)
    pred_srgb01 = _rts_linear01_to_srgb01_f64(pred_lin)
    de = np.linalg.norm(
        rgb01_to_lab(pred_srgb01.astype(np.float32))
        - rgb01_to_lab(y_train_srgb01.astype(np.float32)),
        axis=1,
    )
    stats = {
        "train_mean_deltaE76": float(np.mean(de)),
        "train_p95_deltaE76": float(np.quantile(de, 0.95)),
        "nfev": int(res.nfev),
        "cost": float(res.cost),
        "success": bool(res.success),
    }
    logger.info(
        f"[Eval] RTS: 拟合完成: mean dE={stats['train_mean_deltaE76']:.4f}, p95 dE={stats['train_p95_deltaE76']:.4f}, nfev={stats['nfev']}"
    )

    return {
        "mats": mats,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "layer_names_order": layer_names_order,
        "n_layers": int(n_layers),
        "fit_stats": stats,
    }


def _rts_predict_linear_idx(
    idx_mat: np.ndarray, alpha: np.ndarray, beta: np.ndarray, gamma: np.ndarray
) -> np.ndarray:
    r = _rts_sigmoid(alpha)
    t = _rts_sigmoid(beta) * (1.0 - r)
    r[0, :] = 0.0
    t[0, :] = 1.0

    R = np.repeat(_rts_sigmoid(gamma)[None, :], repeats=idx_mat.shape[0], axis=0)
    for j in range(idx_mat.shape[1]):
        midx = idx_mat[:, j]
        r1 = r[midx, :]
        t1 = t[midx, :]
        denom = np.clip(1.0 - r1 * R, 1e-6, 1e9)
        R = r1 + (t1 * t1) * R / denom
        R = np.clip(R, 0.0, 1.0)
    return np.clip(R, 0.0, 1.0)


def _rts_predict_u8_for_dataset(ds: Dataset, rts_model: dict) -> np.ndarray:
    seqs = _rts_sequences_for_dataset(ds, n_layers=int(rts_model["n_layers"]))
    idx = _rts_idx_mat(
        seqs, rts_model["mats"], layer_names_order=str(rts_model["layer_names_order"])
    )
    pred_lin = _rts_predict_linear_idx(
        idx, rts_model["alpha"], rts_model["beta"], rts_model["gamma"]
    )
    pred_srgb01 = _rts_linear01_to_srgb01_f64(pred_lin).astype(np.float32)
    pred_u8 = (pred_srgb01 * 255.0 + 0.5).astype(np.uint8)
    return pred_u8


def _rts_synthesize_palettes(
    datasets_map: dict,
    train_palette_id: str,
    rts_model: dict,
    force_synthesis_ids: list = None,
):
    """使用RTS模型为指定色盘生成合成target_rgb数据

    Args:
        datasets_map: 色盘ID到Dataset的映射
        train_palette_id: 训练色盘ID（作为参考）
        rts_model: RTS模型字典
        force_synthesis_ids: 强制生成的色盘ID列表
    """
    train_ds = datasets_map.get(train_palette_id)
    if train_ds is None:
        logger.warning(f"[警告] 找不到训练色盘 {train_palette_id}，跳过合成")
        return

    for pid in force_synthesis_ids or []:
        ds = datasets_map.get(pid)
        if ds is None:
            logger.warning(f"[警告] 找不到色盘 {pid}，跳过合成")
            continue

        logger.info(f"[Eval] RTS: 为色盘 {pid} 生成合成target_rgb...")

        # 使用RTS模型预测
        pred_u8 = _rts_predict_u8_for_dataset(ds, rts_model)

        # 更新每个cell的target_rgb (保持为numpy数组以兼容后续处理)
        for i, cell in enumerate(ds.cells):
            if i < len(pred_u8):
                cell.target_rgb = pred_u8[i]

        logger.info(f"[Eval] RTS: 色盘 {pid} 合成完成，共 {len(pred_u8)} 个格子")


def evaluate_on_palette_rts(rts_model: dict, ds: Dataset, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    model_mats = set(str(k).upper() for k in rts_model["mats"])
    ds_mats = set()
    for c in ds.cells:
        if c.recipe:
            for k in c.recipe.keys():
                if not str(k).startswith("_"):
                    ds_mats.add(str(k).upper())
        for ln in getattr(c, "layer_names", []) or []:
            ds_mats.add(str(ln).upper())
    missing_mats = ds_mats - model_mats
    if missing_mats:
        logger.warning(
            f"[Eval] 警告: 色盘 {ds.palette_id} 包含RTS未见过的材料: {missing_mats}"
        )
        logger.info(
            f"[Eval] 这些材料在预测时将被视为 EMPTY (透明)，可能导致预测图趋于单色。"
        )
    else:
        logger.info(f"[Eval] 材料一致性检查通过 (共 {len(ds_mats)} 种材料)")

    pred_u8 = _rts_predict_u8_for_dataset(ds, rts_model)

    if ds.black_offset > 0 or ds.white_offset > 0:
        for i in range(len(pred_u8)):
            pred_u8[i] = apply_bw_calibration_inverse(
                pred_u8[i], ds.black_offset, ds.white_offset
            )
        logger.info(
            f"[Eval] 已应用黑白校准逆向映射: b={ds.black_offset}, w={ds.white_offset}"
        )

    diags, summary = compute_diagnostics(
        cells_all=ds.cells,
        material_keys=rts_model["mats"],
        feature_names=[],
        X_all=np.zeros((len(ds.cells), 0), dtype=np.float32),
        pred_rgb=pred_u8,
        out_dir=out_dir,
    )

    flip_all = True
    render_boards(diags, out_dir, flip_first_layer=True, flip_all=flip_all)
    return diags, summary


def load_all_palettes(
    data_dir: Path, black_offset: float = 0.0, white_offset: float = 0.0
) -> list[Dataset]:
    """加载目录下所有的 dataset_cells_*.json 文件

    Args:
        data_dir: 数据目录
        black_offset: 黑场偏移量
        white_offset: 白场偏移量
    """
    datasets = []
    # 查找 dataset_cells.json 或 dataset_cells_*.json
    paths = list(data_dir.glob("dataset_cells*.json"))
    paths.sort()

    for p in paths:
        # 尝试从文件名推断 palette_id，例如 dataset_cells_A.json -> A
        # 如果是 dataset_cells.json，则默认为 A
        palette_id = p.stem.replace("dataset_cells_", "").replace("dataset_cells", "A")
        ds = load_dataset(
            p,
            palette_id=palette_id,
            black_offset=black_offset,
            white_offset=white_offset,
        )
        datasets.append(ds)

        # 检查是否包含真实测量数据 (A-E 为真实，F-H 为合成)
        # 即使 F-H 文件里有数据，根据用户说明也应视为合成
        is_real_palette = palette_id.upper() in ["A", "B", "C", "D", "E"]
        ds.is_synthetic = not is_real_palette

        data_type = "真实图片" if is_real_palette else "外推合成"
        calib_info = (
            f" [BW校准: b={black_offset}, w={white_offset}]"
            if (black_offset > 0 or white_offset > 0)
            else ""
        )
        logger.info(
            f"[Eval] 已加载色盘: {palette_id} ({len(ds.cells)} 个格子) - 类型: {data_type}{calib_info}"
        )

    return datasets


def evaluate_on_palette(model, ds: Dataset, cfg, out_dir: Path, rgb_bias: list[float]):
    """在单个色盘上运行评估并生成图像

    Args:
        model: 训练好的模型
        ds: 数据集
        cfg: 配置
        out_dir: 输出目录
        rgb_bias: RGB偏差
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 检查材料一致性
    model_mats = set(k.upper() for k in model.optical.material_keys)
    ds_mats = set()
    for c in ds.cells:
        if c.recipe:
            for k in c.recipe.keys():
                if not str(k).startswith("_"):
                    ds_mats.add(str(k).upper())
        # 也要检查 layer_names
        for ln in getattr(c, "layer_names", []) or []:
            ds_mats.add(str(ln).upper())

    missing_mats = ds_mats - model_mats
    if missing_mats:
        logger.warning(
            f"[Eval] 警告: 色盘 {ds.palette_id} 包含模型未见过的材料: {missing_mats}"
        )
        logger.info(
            f"[Eval] 这些材料在预测时将被视为透明/背景色，可能导致预测图趋于单色。"
        )
    else:
        logger.info(f"[Eval] 材料一致性检查通过 (共 {len(ds_mats)} 种材料)")

    recipes = []
    for c in ds.cells:
        r = dict(c.recipe)
        r["_layer_names"] = getattr(c, "layer_names", [])
        recipes.append(r)

    sequences = build_layer_sequences(
        recipes,
        model.optical.material_keys,
        cfg.n_layers,
        layer_names_order=cfg.layer_names_order,
    )
    base_rgb01 = predict_ad_rgb01(
        sequences,
        model.optical.material_keys,
        model.optical,
        use_vulkan=cfg.use_vulkan,
        backing=model.optical.backing,
        k1=model.optical.k1,
        k2=model.optical.k2,
        model_type=cfg.optical_model,
    )
    base_lab = rgb01_to_lab(base_rgb01)
    X, _ = build_gpr_features(
        recipes,
        model.optical.material_keys,
        base_lab,
        n_layers=cfg.n_layers,
        layer_names_order=cfg.layer_names_order,
        k1=model.optical.k1,
        k2=model.optical.k2,
        backing=model.optical.backing,
    )

    pred_lab = predict_phys_gpr_lab(
        model,
        sequences,
        X,
        use_vulkan=cfg.use_vulkan,
        optical_model=cfg.optical_model,
    )
    pred_rgb01 = lab_to_rgb01(pred_lab)
    pred_u8 = (pred_rgb01 * 255.0 + 0.5).astype(np.uint8)

    # 应用黑白校准的逆向映射（输出后）
    if ds.black_offset > 0 or ds.white_offset > 0:
        for i in range(len(pred_u8)):
            pred_u8[i] = apply_bw_calibration_inverse(
                pred_u8[i], ds.black_offset, ds.white_offset
            )
        logger.info(
            f"[Eval] 已应用黑白校准逆向映射: b={ds.black_offset}, w={ds.white_offset}"
        )

    logger.info(f"[Eval] 使用原始预测值（无自适应校正）")

    diags, summary = compute_diagnostics(
        cells_all=ds.cells,
        material_keys=model.optical.material_keys,
        feature_names=model.feature_names,
        X_all=X,
        pred_rgb=pred_u8,
        out_dir=out_dir,
    )

    # 所有色盘遵循统一逻辑：根据物理摆放进行左右翻转渲染
    flip_all = True
    render_boards(diags, out_dir, flip_first_layer=True, flip_all=flip_all)
    return diags, summary


def run_eval_pipeline(
    train_palette_id: str, data_dir: Path, out_root: Path, fit_args: FitArgs
):
    """运行完整的评估管线

    输出目录结构：
    - out/models/{optical_model}_{implementation}/ (仅放 json 模型文件)
    - out/evaluation/{optical_model}_{implementation}/ (评估过程产物)
    """
    # 构建子目录名称: 例如 "four_flux_vulkan" 或 "tmm_numpy"
    impl_str = "vulkan" if fit_args.use_vulkan else "numpy"
    subdir_name = f"{fit_args.optical_model}_{impl_str}"

    pkg_dir = Path(__file__).resolve().parent
    out_base = pkg_dir / "out"
    eval_out_root = out_base / "evaluation" / subdir_name
    models_out_root = out_base / "models" / subdir_name
    eval_out_root.mkdir(parents=True, exist_ok=True)
    models_out_root.mkdir(parents=True, exist_ok=True)

    logger.info(f"\n[Eval] === 启动评估流程 ===")
    logger.info(f"[Eval] 算法: {fit_args.optical_model}, 实现: {impl_str}")
    logger.info(f"[Eval] 评估输出目录: {eval_out_root}")
    logger.info(f"[Eval] 模型输出目录: {models_out_root}")

    # 加载数据（应用黑白校准）
    all_ds = load_all_palettes(
        data_dir, black_offset=fit_args.black_offset, white_offset=fit_args.white_offset
    )
    if not all_ds:
        logger.error("[Error] 未找到任何数据集文件。")
        return

    # 强制使用色盘A作为唯一真实训练色盘（用于物理参数拟合与GPR残差训练）
    if train_palette_id.upper() != "A":
        logger.info(
            f"[Eval] 注意：当前强制使用色盘A进行训练（忽略传入的 train_palette_id={train_palette_id}）"
        )
    train_palette_id = "A"
    train_ds = next((ds for ds in all_ds if ds.palette_id.upper() == "A"), all_ds[0])
    logger.info(f"[Eval] 目标训练色盘: {train_ds.palette_id}")

    # 打印色盘分类和数据用法
    logger.info(f"[Eval] 数据分类与用法说明:")
    for ds in all_ds:
        pid = ds.palette_id.upper()
        if pid == train_ds.palette_id.upper():
            usage = "真实图片 + 参与训练 (物理参数拟合 & GPR残差训练)"
        elif pid in ["B", "C", "D", "E"]:
            usage = "真实图片仅用于评估对比；同时生成合成对照(target_rgb)用于展示与误差分析（不参与训练）"
        else:
            usage = "仅用于评估/展示（如需要会自动补全合成 measured_rgb），不参与训练"

        dtype = "真实图片" if not getattr(ds, "is_synthetic", False) else "合成规格"
        logger.info(f"  - 色盘 {pid}: 类型={dtype}, 用法={usage}")

    # 区分真实数据和待合成数据
    real_palettes = []
    synthetic_palettes = []
    for ds in all_ds:
        if not getattr(ds, "is_synthetic", False):
            real_palettes.append(ds.palette_id)
        else:
            synthetic_palettes.append(ds.palette_id)

    logger.info(f"[Eval] 包含真实图片的色盘: {', '.join(real_palettes)}")
    logger.info(f"[Eval] 将通过外推合成的色盘: {', '.join(synthetic_palettes)}")

    datasets_map = {ds.palette_id: ds for ds in all_ds}
    if fit_args.optical_model == "rts":
        # 修复：RTS模型模式下，先训练模型，然后用RTS模型生成B~E的合成数据
        logger.info(f"[Eval] RTS: 将使用RTS模型生成B~E的 target_rgb 作为合成对照")
        # 注意：RTS模型的合成数据生成在训练后完成，见下面的代码
        pass
    else:
        cfg_phys = PhysGPRConfig(
            n_layers=fit_args.n_layers,
            opt_steps=fit_args.opt_steps,
            opt_reg=fit_args.opt_reg,
            gpr_noise=fit_args.gpr_noise,
            gpr_lengthscale=fit_args.gpr_lengthscale,
            gpr_signal=fit_args.gpr_signal,
            gpr_jitter=fit_args.gpr_jitter,
            use_vulkan=fit_args.use_vulkan,
            k1=fit_args.k1,
            k2=fit_args.k2,
            backing=fit_args.backing,
            optimize_k=fit_args.optimize_k,
            pure_weight=fit_args.pure_weight,
            optical_model=fit_args.optical_model,
            layer_names_order=fit_args.layer_names_order,
        )
        synthesize_palettes_from_a(
            datasets_map, "A", cfg_phys, force_synthesis_ids=["B", "C", "D", "E"]
        )

    def _export_model_artifacts(train_dir: Path, models_dir: Path) -> None:
        meta_path = train_dir / "color_model.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"找不到训练输出的模型元数据: {meta_path}")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        files = meta.get("files")
        if files is None:
            files = {}
        if not isinstance(files, dict):
            raise TypeError(f"模型元数据中的 files 字段类型错误: {type(files)}")

        models_dir.mkdir(parents=True, exist_ok=True)

        out_files: dict = {}
        for k, rel in files.items():
            src = train_dir / str(rel)
            if not src.exists():
                raise FileNotFoundError(f"模型文件不存在: {src}")
            dst_name = Path(str(rel)).name
            dst = models_dir / dst_name
            shutil.copy2(src, dst)
            out_files[str(k)] = dst_name

        meta["files"] = out_files
        (models_dir / "color_model.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"[Eval] 已导出模型到: {models_dir}")

    train_out = eval_out_root / f"train_{train_ds.palette_id}"
    if fit_args.optical_model == "rts":
        train_out.mkdir(parents=True, exist_ok=True)
        rts_model = _rts_fit_model(
            train_ds,
            n_layers=int(fit_args.n_layers),
            layer_names_order=str(fit_args.layer_names_order),
            max_nfev=int(fit_args.opt_steps),
            reg=float(max(fit_args.opt_reg, 1e-3)),
        )
        rts_meta = {
            "version": VERSION,
            "optical_model": "rts",
            "implementation": impl_str,
            "train_palette_id": "A",
            "n_layers": int(rts_model["n_layers"]),
            "layer_names_order": str(rts_model["layer_names_order"]),
            "material_keys": list(rts_model["mats"]),
            "fit_stats": dict(rts_model["fit_stats"]),
            "params": {
                "alpha": np.asarray(rts_model["alpha"], dtype=np.float64).tolist(),
                "beta": np.asarray(rts_model["beta"], dtype=np.float64).tolist(),
                "gamma": np.asarray(rts_model["gamma"], dtype=np.float64).tolist(),
            },
        }
        model_path = models_out_root / "rts_model.json"
        model_path.write_text(
            json.dumps(rts_meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"[Eval] RTS: 模型已保存: {model_path}")

        # 修复：使用RTS模型生成B~E的合成数据
        logger.info(f"[Eval] RTS: 使用训练好的RTS模型生成B~E的target_rgb...")
        _rts_synthesize_palettes(
            datasets_map, "A", rts_model, force_synthesis_ids=["B", "C", "D", "E"]
        )

        rgb_bias = [0.0, 0.0, 0.0]
        cfg = fit_args
    else:
        fit_args.dataset = data_dir / f"dataset_cells_{train_ds.palette_id}.json"
        if not fit_args.dataset.exists():
            fit_args.dataset = data_dir / "dataset_cells.json"

        fit_args.out_dir = train_out
        fit_args.memorize_mode = "off"

        run_fit(fit_args)

        model = load_model(train_out)
        meta = json.loads((train_out / "color_model.json").read_text(encoding="utf-8"))
        rgb_bias = meta.get("rgb_bias")
        if not isinstance(rgb_bias, list) or len(rgb_bias) != 3:
            rgb_bias = [0.0, 0.0, 0.0]
        cfg = fit_args

        try:
            _export_model_artifacts(train_out, models_out_root)
        except Exception as e:
            logger.error(f"[错误] 导出模型产物到 out/models 失败: {e}")
            raise

    all_summaries = []
    all_de_errors_real = []
    all_de_errors_train = []
    palette_ids = []

    for ds in all_ds:
        logger.info(f"[Eval] 正在评估色盘: {ds.palette_id}...")
        p_out = eval_out_root / f"eval_{ds.palette_id}"
        if fit_args.optical_model == "rts":
            diags, summary = evaluate_on_palette_rts(rts_model, ds, p_out)
        else:
            diags, summary = evaluate_on_palette(model, ds, cfg, p_out, rgb_bias)

        all_summaries.append(summary)
        palette_ids.append(ds.palette_id)

        de_real = [
            d["error_de_real"] for d in diags if d["enabled"] and d["has_recipe"]
        ]
        de_train = [
            d["error_de_train"] for d in diags if d["enabled"] and d["has_recipe"]
        ]
        all_de_errors_real.append(de_real)
        all_de_errors_train.append(de_train)

    generate_summary_plots(
        palette_ids, all_de_errors_real, all_de_errors_train, eval_out_root
    )

    impl_str = "vulkan" if fit_args.use_vulkan else "numpy"
    generate_report(
        train_ds.palette_id,
        palette_ids,
        all_summaries,
        all_ds,
        eval_out_root,
        optical_model=fit_args.optical_model,
        implementation=impl_str,
    )


def generate_summary_plots(
    palette_ids, all_de_errors_real, all_de_errors_train, out_dir: Path
):
    """生成汇总统计图表"""
    plt.figure(figsize=(15, 7))

    # 1. DeltaE76 误差分布 (Box Plot)
    plt.subplot(1, 2, 1)

    # 准备并排的箱线图数据
    positions = np.arange(len(palette_ids))
    width = 0.3

    bp_real = plt.boxplot(
        all_de_errors_real,
        positions=positions - width / 2,
        widths=width,
        patch_artist=True,
        label="vs Real Image",
    )
    bp_train = plt.boxplot(
        all_de_errors_train,
        positions=positions + width / 2,
        widths=width,
        patch_artist=True,
        label="vs Training Data",
    )

    # 设置颜色
    for patch in bp_real["boxes"]:
        patch.set_facecolor("lightblue")
    for patch in bp_train["boxes"]:
        patch.set_facecolor("lightgreen")

    plt.xticks(positions, palette_ids)
    plt.title("DeltaE76 Error Distribution: Real vs Train")
    plt.ylabel("DeltaE76")
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # 2. 平均误差对比 (Bar Chart)
    plt.subplot(1, 2, 2)
    means_real = [np.mean(e) if e else 0 for e in all_de_errors_real]
    means_train = [np.mean(e) if e else 0 for e in all_de_errors_train]

    x = np.arange(len(palette_ids))
    plt.bar(x - width / 2, means_real, width, label="Mean dE (Real)", color="steelblue")
    plt.bar(
        x + width / 2, means_train, width, label="Mean dE (Train)", color="forestgreen"
    )

    plt.xticks(x, palette_ids)
    plt.title("Mean DeltaE76: Real vs Train")
    plt.ylabel("Mean DeltaE76")
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(out_dir / "summary_stats.png")
    plt.close()
    logger.info(f"[Eval] 汇总图表已保存至: {out_dir / 'summary_stats.png'}")


def generate_report(
    train_id,
    palette_ids,
    summaries,
    all_ds,
    out_dir: Path,
    optical_model: str = "",
    implementation: str = "",
):
    """生成 REPORT.md"""
    report = []
    report.append(f"# Color Model 评估报告\n")
    report.append(f"## 实验配置\n")
    if optical_model:
        report.append(f"- **光学模型**: {optical_model}")
    if implementation:
        report.append(f"- **计算实现**: {implementation}")
    report.append(f"- **训练色盘**: {train_id} (主要物理参数来源)")
    report.append(f"- **评估范围**: {', '.join(palette_ids)}")
    report.append(f"- **数据类型与用法说明**:\n")

    for ds in all_ds:
        pid = ds.palette_id.upper()
        if pid == train_id.upper():
            usage = "真实图片 + 参与训练"
        elif pid in ["B", "C", "D", "E"]:
            usage = "合成数据训练 + 真实图片对比 (跨色盘物理外推验证)"
        else:
            usage = "合成数据训练"
        report.append(f"  - **色盘 {pid}**: {usage}")

    report.append(f"\n- **偏差指标说明**:\n")
    report.append(
        f"  - **vs Real**: 模型输出与该色盘**真实图片**（或备份的真实数据）的 DeltaE76 偏差。"
    )
    report.append(
        f"  - **vs Train**: 模型输出与该色盘**训练目标**（可能是合成值）的 DeltaE76 偏差。\n"
    )

    report.append(f"## 汇总结果\n")
    report.append(f"![Summary Stats](summary_stats.png)\n")

    report.append(
        f"| 色盘 ID | 数据类型 | 平均 dE (Real) | P95 dE (Real) | 平均 dE (Train) | P95 dE (Train) |"
    )
    report.append(f"| --- | --- | --- | --- | --- | --- |")

    for pid, s, ds in zip(palette_ids, summaries, all_ds):
        dtype = "合成" if getattr(ds, "is_synthetic", False) else "真实"
        report.append(
            f"| {pid} | {dtype} | {s['mean_deltaE76_real']:.4f} | {s['p95_deltaE76_real']:.4f} | {s['mean_deltaE76_train']:.4f} | {s['p95_deltaE76_train']:.4f} |"
        )

    report.append(f"\n## 详细说明\n")
    report.append(
        f"1. **模型输出与真实图片的偏差 (Real)**: 反映了模型在实际应用中的表现，包含打印误差、测量误差和模型拟合误差。"
    )
    report.append(
        f"2. **模型输出与生成的训练数据的偏差 (Train)**: 仅反映模型对物理公式和配方的拟合能力。"
    )
    report.append(
        f"3. **对比分析**: 如果 Train 偏差远小于 Real 偏差，说明模型拟合良好，主要误差来自物理设备（打印/测量）的一致性。"
    )

    (out_dir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    logger.info(f"[Eval] 报告已生成: {out_dir / 'REPORT.md'}")


if __name__ == "__main__":
    # 简单的入口，用于演示
    args = parse_args()
    data_dir = args.dataset.parent
    out_root = args.out_dir / "evaluation"

    # 假设我们默认用色盘A训练
    # 实际使用时可以通过命令行参数指定
    run_eval_pipeline(
        train_palette_id="A", data_dir=data_dir, out_root=out_root, fit_args=args
    )
