"""
诊断模块

计算训练诊断指标，渲染测量板、预测板、误差热力图等可视化结果
支持多色盘分别渲染
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from oc_xgb.color_space import rgb01_to_lab, delta_e_cie76
from oc_proto.calib_color_rts.dataset_io import Cell



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _to_uint8_rgb(rgb01: np.ndarray) -> np.ndarray:
    """将 0-1 范围的 RGB 转换为 uint8 格式"""
    rgb = np.clip(rgb01, 0.0, 1.0)
    return (rgb * 255.0 + 0.5).astype(np.uint8)


def compute_diagnostics(
    cells_all: list[Cell],
    material_keys: list[str],
    feature_names: list[str],
    X_all: np.ndarray,
    pred_rgb: np.ndarray,
    out_dir: Path,
    palette_id: str = "",
) -> tuple[list[dict], dict]:
    """构建每个单元格的诊断信息和全局摘要
    
    Args:
        cells_all: 所有单元格数据列表
        material_keys: 材料键名列表
        feature_names: 特征名称列表
        X_all: 特征矩阵
        pred_rgb: 预测的 RGB 值
        out_dir: 输出目录
        palette_id: 色盘标识符
        
    Returns:
        (诊断列表, 摘要字典)
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    pred_u8 = pred_rgb.astype(np.uint8)
    
    # 测量值处理：如果有备份的真实测量值（用于跨色盘对比），优先使用备份值
    meas_u8_list = []
    for c in cells_all:
        if hasattr(c, "real_rgb_eval"):
            meas_u8_list.append(c.real_rgb_eval.astype(np.uint8))
        else:
            meas_u8_list.append(c.measured_rgb.astype(np.uint8))
    meas_u8 = np.stack(meas_u8_list, axis=0)
    
    # 目标 RGB（如果存在）
    target_u8 = []
    for c in cells_all:
        if c.target_rgb is not None:
            target_u8.append(c.target_rgb.astype(np.uint8))
        else:
            target_u8.append(np.zeros(3, dtype=np.uint8))
    target_u8 = np.stack(target_u8, axis=0)

    pred_mean = pred_u8.mean(axis=0)
    # ...
    # 与真实图像的 RGB 误差（0-255）
    diff_real = pred_u8.astype(np.float32) - meas_u8.astype(np.float32)
    err_rgb_real = np.linalg.norm(diff_real, axis=1)

    # 与训练数据（目标）的 RGB 误差
    diff_train = pred_u8.astype(np.float32) - target_u8.astype(np.float32)
    err_rgb_train = np.linalg.norm(diff_train, axis=1)

    # 与真实值的 Lab 误差
    meas_lab = rgb01_to_lab(meas_u8.astype(np.float32) / 255.0)
    pred_lab = rgb01_to_lab(pred_u8.astype(np.float32) / 255.0)
    err_de_real = delta_e_cie76(pred_lab, meas_lab)

    # 与训练值（目标）的 Lab 误差
    target_lab = rgb01_to_lab(target_u8.astype(np.float32) / 255.0)
    err_de_train = delta_e_cie76(pred_lab, target_lab)

    diags: list[dict] = []
    for i, c in enumerate(cells_all):
        has_recipe = bool(c.recipe)
        enabled = bool(c.enabled)
        
        # 真实误差
        e_rgb_real = float(err_rgb_real[i]) if (enabled and has_recipe) else 0.0
        e_de_real = float(err_de_real[i]) if (enabled and has_recipe) else 0.0
        
        # 训练误差
        e_rgb_train = float(err_rgb_train[i]) if (enabled and has_recipe and c.target_rgb is not None) else 0.0
        e_de_train = float(err_de_train[i]) if (enabled and has_recipe and c.target_rgb is not None) else 0.0
        
        diags.append(
            {
                "row": int(c.row),
                "col": int(c.col),
                "enabled": enabled,
                "has_recipe": has_recipe,
                "recipe": c.recipe,
                "layer_names": c.layer_names,
                "measured_rgb": meas_u8[i].tolist(),
                "predicted_rgb": pred_u8[i].tolist(),
                "target_rgb": (c.target_rgb.tolist() if c.target_rgb is not None else None),
                "error_rgb": e_rgb_real,        # 保持向后兼容
                "error_de": e_de_real,          # 保持向后兼容
                "error_rgb_real": e_rgb_real,
                "error_de_real": e_de_real,
                "error_rgb_train": e_rgb_train,
                "error_de_train": e_de_train,
                "palette_id": palette_id,
            }
        )

    # 对启用且有配方的单元格进行汇总
    mask = np.array([c.enabled and bool(c.recipe) for c in cells_all], dtype=bool)
    mask_target = np.array([c.enabled and bool(c.recipe) and c.target_rgb is not None for c in cells_all], dtype=bool)
    
    err_rgb_real_m = err_rgb_real[mask] if mask.any() else err_rgb_real
    err_de_real_m = err_de_real[mask] if mask.any() else err_de_real
    
    if mask_target.any():
        err_rgb_train_m = err_rgb_train[mask_target]
        err_de_train_m = err_de_train[mask_target]
    else:
        err_rgb_train_m = np.asarray([], dtype=np.float32)
        err_de_train_m = np.asarray([], dtype=np.float32)

    def pct(a: np.ndarray, q: float) -> float:
        """计算数组的百分位数"""
        if a.size == 0:
            return float("nan")
        return float(np.percentile(a, q))

    summary = {
        "palette_id": palette_id,
        "n_cells_total": int(len(cells_all)),
        "n_cells_fit": int(mask.sum()),
        
        # 真实值统计
        "mean_error_rgb_real": float(np.mean(err_rgb_real_m)) if err_rgb_real_m.size else float("nan"),
        "p95_error_rgb_real": pct(err_rgb_real_m, 95),
        "mean_deltaE76_real": float(np.mean(err_de_real_m)) if err_de_real_m.size else float("nan"),
        "p95_deltaE76_real": pct(err_de_real_m, 95),
        
        # 训练值统计
        "mean_error_rgb_train": float(np.mean(err_rgb_train_m)) if err_rgb_train_m.size else float("nan"),
        "p95_error_rgb_train": pct(err_rgb_train_m, 95),
        "mean_deltaE76_train": float(np.mean(err_de_train_m)) if err_de_train_m.size else float("nan"),
        "p95_deltaE76_train": pct(err_de_train_m, 95),
        
        # 向后兼容的遗留字段
        "mean_error_rgb": float(np.mean(err_rgb_real_m)) if err_rgb_real_m.size else float("nan"),
        "p95_error_rgb": pct(err_rgb_real_m, 95),
        "mean_deltaE76": float(np.mean(err_de_real_m)) if err_de_real_m.size else float("nan"),
        "p95_deltaE76": pct(err_de_real_m, 95),
        
        "feature_names": feature_names,
        "material_keys": material_keys,
    }

    coords = {(d["row"], d["col"]) for d in diags}
    if coords:
        rows = [r for r, _ in coords]
        cols = [c for _, c in coords]
        min_r, max_r = min(rows), max(rows)
        min_c, max_c = min(cols), max(cols)
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                if (r, c) in coords:
                    continue
                diags.append(
                    {
                        "row": int(r),
                        "col": int(c),
                        "enabled": False,
                        "has_recipe": False,
                        "recipe": {},
                        "layer_names": [],
                        "measured_rgb": [0, 0, 0],
                        "predicted_rgb": [0, 0, 0],
                        "error_rgb": 0.0,
                        "error_de": 0.0,
                        "target_rgb": None,
                        "palette_id": palette_id,
                    }
                )

    return diags, summary


def _render_single_board(
    diags: list[dict],
    cell_size: int = 64,
    flip_first_layer: bool = False,
    flip_all: bool = False,
    error_key: str = "error_rgb"
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """
    渲染单个板子的图像
    
    Args:
        diags: 诊断数据列表
        cell_size: 单元格大小（像素）
        flip_first_layer: 是否翻转首层
        flip_all: 是否翻转全部
        error_key: 误差键名
        
    Returns:
        (测量图, 预测图, 目标图, 首层图, 热力图, 最大误差)
    """
    # 首层可视化材料颜色映射
    MATERIAL_COLORS = {
        "WHITE": (255, 255, 255),
        "RED": (255, 0, 0),
        "BLUE": (0, 0, 255),
        "GREEN": (0, 255, 0),
        "CYAN": (0, 255, 255),
        "MAGENTA": (255, 0, 255),
        "YELLOW": (255, 255, 0),
        "BLACK": (40, 40, 40),
        "GRAY": (128, 128, 128),
        "ORANGE": (255, 165, 0),
        "PURPLE": (128, 0, 128),
        "BROWN": (165, 42, 42),
    }

    def get_material_color(name: str) -> tuple[int, int, int]:
        """获取材料颜色，未知材料生成稳定的随机颜色"""
        name = str(name).upper()
        if name in MATERIAL_COLORS:
            return MATERIAL_COLORS[name]
        # 为未知材料生成稳定的随机颜色
        import hashlib
        h = int(hashlib.md5(name.encode()).hexdigest(), 16)
        return (h & 0xFF, (h >> 8) & 0xFF, (h >> 16) & 0xFF)

    # 优先从启用且有配方的单元格确定边界框
    rows = [d["row"] for d in diags if d.get("enabled") and d.get("has_recipe")]
    cols = [d["col"] for d in diags if d.get("enabled") and d.get("has_recipe")]
    if not rows or not cols:
        rows = [d["row"] for d in diags]
        cols = [d["col"] for d in diags]

    min_r, max_r = min(rows), max(rows)
    min_c, max_c = min(cols), max(cols)

    H = (max_r - min_r + 1) * cell_size
    W = (max_c - min_c + 1) * cell_size

    meas = np.zeros((H, W, 3), dtype=np.uint8)
    pred = np.zeros((H, W, 3), dtype=np.uint8)
    tgt = np.zeros((H, W, 3), dtype=np.uint8)
    first_layer = np.zeros((H, W, 3), dtype=np.uint8)
    err = np.zeros((H, W), dtype=np.float32)

    # 计算最大误差用于归一化
    errs = [float(d.get(error_key, 0.0)) for d in diags if d.get("enabled") and d.get("has_recipe")]
    max_err = max(errs) if errs else 1.0
    if max_err < 1e-6:
        max_err = 1.0

    for d in diags:
        r, c = int(d["row"]), int(d["col"])
        if not (min_r <= r <= max_r and min_c <= c <= max_c):
            continue
            
        rr, cc = r - min_r, c - min_c
        y1, y2 = rr * cell_size, (rr + 1) * cell_size
        x1, x2 = cc * cell_size, (cc + 1) * cell_size

        enabled = bool(d.get("enabled", True))
        has_recipe = bool(d.get("has_recipe", False))

        if not enabled:
            meas[y1:y2, x1:x2] = (60, 60, 60)
            pred[y1:y2, x1:x2] = (60, 60, 60)
            tgt[y1:y2, x1:x2] = (60, 60, 60)
            first_layer[y1:y2, x1:x2] = (60, 60, 60)
            continue

        m = d.get("measured_rgb") or [0, 0, 0]
        p = d.get("predicted_rgb") or [0, 0, 0]
        t = d.get("target_rgb") or [0, 0, 0]

        meas[y1:y2, x1:x2] = (int(m[0]), int(m[1]), int(m[2]))
        pred[y1:y2, x1:x2] = (int(p[0]), int(p[1]), int(p[2]))
        tgt[y1:y2, x1:x2] = (int(t[0]), int(t[1]), int(t[2]))

        # 首层可视化
        ln = d.get("layer_names")
        if isinstance(ln, list) and len(ln) > 0:
            first_mat = ln[0]  # 假设索引 0 是首层
            first_layer[y1:y2, x1:x2] = get_material_color(first_mat)
        else:
            first_layer[y1:y2, x1:x2] = (0, 0, 0)

        if enabled and has_recipe:
            err[y1:y2, x1:x2] = float(d.get(error_key, 0.0)) / max_err
        else:
            err[y1:y2, x1:x2] = 0.0

        cv2.rectangle(meas, (x1, y1), (x2, y2), (40, 40, 40), 1)
        cv2.rectangle(pred, (x1, y1), (x2, y2), (40, 40, 40), 1)
        cv2.rectangle(tgt, (x1, y1), (x2, y2), (40, 40, 40), 1)
        cv2.rectangle(first_layer, (x1, y1), (x2, y2), (40, 40, 40), 1)

    # 使用 JET 色图生成热力图
    heat_u8 = np.clip(err * 255.0, 0, 255).astype(np.uint8)
    heat_bgr = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)

    # 添加颜色条
    bar_w = max(32, cell_size // 2)
    bar = np.zeros((H, bar_w, 3), dtype=np.uint8)
    for y in range(H):
        v = 1.0 - (y / max(1, H - 1))
        c = cv2.applyColorMap(np.array([[int(v * 255)]], dtype=np.uint8), cv2.COLORMAP_JET)[0, 0]
        bar[y, :, :] = c
    heat_bgr = np.concatenate([heat_bgr, bar], axis=1)
    cv2.putText(
        heat_bgr,
        f"max {max_err:.1f}",
        (5, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        heat_bgr,
        "min 0",
        (5, H - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    if flip_all:
        meas = cv2.flip(meas, 1)
        pred = cv2.flip(pred, 1)
        tgt = cv2.flip(tgt, 1)
        first_layer = cv2.flip(first_layer, 1)
        heat_bgr = cv2.flip(heat_bgr, 1)
    elif flip_first_layer:
        first_layer = cv2.flip(first_layer, 1)

    return meas, pred, tgt, first_layer, heat_bgr, max_err


def render_boards(diags: list[dict], out_dir: Path, cell_size: int = 64, flip_first_layer: bool = False, flip_all: bool = False) -> None:
    """渲染测量/预测板和误差热力图"""
    # 使用真实误差（相对于测量值）渲染
    meas, pred, tgt, first_layer, heat_real, _ = _render_single_board(
        diags, cell_size, flip_first_layer, flip_all, error_key="error_rgb_real"
    )
    # 使用训练误差（相对于目标值）渲染
    _, _, _, _, heat_train, _ = _render_single_board(
        diags, cell_size, flip_first_layer, flip_all, error_key="error_rgb_train"
    )

    meas_bgr = cv2.cvtColor(meas, cv2.COLOR_RGB2BGR)
    pred_bgr = cv2.cvtColor(pred, cv2.COLOR_RGB2BGR)
    first_layer_bgr = cv2.cvtColor(first_layer, cv2.COLOR_RGB2BGR)

    cv2.imwrite(str(out_dir / "measured_board.png"), meas_bgr)
    cv2.imwrite(str(out_dir / "predicted_board.png"), pred_bgr)
    # 注意：target_board 已禁用，因为合成阶段和评估阶段使用不同的层序列生成逻辑，导致内容不一致
    # cv2.imwrite(str(out_dir / "target_board.png"), tgt_bgr)
    cv2.imwrite(str(out_dir / "first_layer_board.png"), first_layer_bgr)
    cv2.imwrite(str(out_dir / "error_heatmap_real.png"), heat_real)
    cv2.imwrite(str(out_dir / "error_heatmap_train.png"), heat_train)
    # 向后兼容
    cv2.imwrite(str(out_dir / "error_heatmap.png"), heat_real)


def render_boards_for_palette(
    diags: list[dict],
    out_dir: Path,
    palette_id: str,
    cell_size: int = 64,
    flip_first_layer: bool = False,
    flip_all: bool = False
) -> None:
    """
    为指定色盘渲染测量板、预测板、误差热力图等可视化结果
    """
    # 使用真实误差（相对于测量值）渲染
    meas, pred, tgt, first_layer, heat_real, _ = _render_single_board(
        diags, cell_size, flip_first_layer, flip_all, error_key="error_rgb_real"
    )
    # 使用训练误差（相对于目标值）渲染
    _, _, _, _, heat_train, _ = _render_single_board(
        diags, cell_size, flip_first_layer, flip_all, error_key="error_rgb_train"
    )

    meas_bgr = cv2.cvtColor(meas, cv2.COLOR_RGB2BGR)
    pred_bgr = cv2.cvtColor(pred, cv2.COLOR_RGB2BGR)
    first_layer_bgr = cv2.cvtColor(first_layer, cv2.COLOR_RGB2BGR)

    # 使用带色盘ID的文件名保存
    cv2.imwrite(str(out_dir / f"measured_board_{palette_id}.png"), meas_bgr)
    cv2.imwrite(str(out_dir / f"predicted_board_{palette_id}.png"), pred_bgr)
    # 注意：target_board 已禁用，因为合成阶段和评估阶段使用不同的层序列生成逻辑，导致内容不一致
    # cv2.imwrite(str(out_dir / f"target_board_{palette_id}.png"), tgt_bgr)
    cv2.imwrite(str(out_dir / f"first_layer_board_{palette_id}.png"), first_layer_bgr)
    cv2.imwrite(str(out_dir / f"error_heatmap_real_{palette_id}.png"), heat_real)
    cv2.imwrite(str(out_dir / f"error_heatmap_train_{palette_id}.png"), heat_train)
    # 向后兼容
    cv2.imwrite(str(out_dir / f"error_heatmap_{palette_id}.png"), heat_real)

    logger.info(f"[诊断] 色盘 {palette_id} 的可视化结果已保存（包括 Real 和 Train 两种误差图）")
