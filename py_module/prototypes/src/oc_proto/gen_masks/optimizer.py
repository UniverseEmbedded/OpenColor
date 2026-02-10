"""颜色优化模块 - 提供首层颜色偏向优化功能"""

import traceback
from typing import Tuple, List

import numpy as np



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _bias_first_print_layer_to_target(
    unique_target_rgb01: np.ndarray,
    recipes_print_order: np.ndarray,
    solver,
    cs,
    *,
    enabled: bool,
    final_slack_de76: float,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """首层贴近原图优化
    
    基于训练好的物理模型，评估不同首层选择对最终色差的影响，
    在允许的最终色差松弛范围内，选择使首层颜色最接近目标图像颜色的配方。
    
    Args:
        unique_target_rgb01: 唯一目标颜色数组 (N, 3) float32 0-1
        recipes_print_order: 打印顺序配方索引 (N, n_layers) int32
        solver: 求解器对象，用于预测
        cs: ColorSystem 颜色系统
        enabled: 是否启用优化
        final_slack_de76: 允许最终色差恶化的松弛量
        weights: 各颜色的权重（用于加权统计）
    
    Returns:
        优化后的打印顺序配方索引 (N, n_layers) int32
    """
    if not bool(enabled):
        return recipes_print_order
    
    recipes0 = np.asarray(recipes_print_order)
    if recipes0.ndim != 2 or int(recipes0.shape[1]) <= 0:
        return recipes_print_order

    # 获取调色板颜色
    rgb_lut_u8 = np.asarray([cs.slot_preview_rgb[n] for n in cs.slot_names], dtype=np.uint8)
    palette_rgb01 = rgb_lut_u8.astype(np.float32) / 255.0
    
    # 导入颜色空间转换函数
    from ..calib_color_rts.color_space import rgb01_to_lab, delta_e_cie76
    
    palette_lab = rgb01_to_lab(palette_rgb01)

    tgt_rgb01 = np.asarray(unique_target_rgb01, dtype=np.float32)
    tgt_lab = rgb01_to_lab(tgt_rgb01)

    n = int(tgt_lab.shape[0])
    n_slots = int(palette_lab.shape[0])
    if n <= 0 or n_slots <= 1:
        return recipes_print_order

    recipes = recipes0.astype(np.int32, copy=True)
    slots = np.arange(n_slots, dtype=np.int32)
    
    # 构建候选配方：每个配方的首层分别替换为所有可能的颜色
    cand = np.repeat(recipes, n_slots, axis=0)
    cand[:, 0] = np.tile(slots, n)

    try:
        # 预测所有候选配方的最终颜色（注意：solver期望底层优先顺序）
        pred_lab = solver._predict_batch(cand[:, ::-1])
    except Exception as e:
        logger.error(f"[错误] 首层贴近原图优化失败(预测阶段): {e}")
        traceback.print_exc()
        return recipes_print_order

    # 计算最终色差
    tgt_rep = np.repeat(tgt_lab, n_slots, axis=0)
    de_final = delta_e_cie76(tgt_rep, pred_lab).reshape(n, n_slots)

    # 计算首层与目标的色差
    pal_rep = np.tile(palette_lab, (n, 1))
    de_l0 = delta_e_cie76(tgt_rep, pal_rep).reshape(n, n_slots)

    slack = max(0.0, float(final_slack_de76))

    # 基于当前选择的基线色差
    old_s = recipes[:, 0].astype(np.int32, copy=False)
    base_final = de_final[np.arange(n), old_s][:, None]
    
    # 筛选出在松弛范围内的候选
    ok = de_final <= (base_final + slack)
    de_l0_masked = np.where(ok, de_l0, np.inf)
    best_s = np.argmin(de_l0_masked, axis=1).astype(np.int32)

    # 处理没有有效候选的情况
    bad = ~np.isfinite(np.min(de_l0_masked, axis=1))
    if bool(np.any(bad)):
        best_s[bad] = np.argmin(de_final[bad], axis=1).astype(np.int32)

    changed = old_s != best_s
    changed_n = int(np.count_nonzero(changed))
    
    if changed_n > 0:
        before_l0 = de_l0[np.arange(n), old_s]
        after_l0 = de_l0[np.arange(n), best_s]
        before_f = de_final[np.arange(n), old_s]
        after_f = de_final[np.arange(n), best_s]

        w = None
        if weights is not None:
            w = np.asarray(weights, dtype=np.float64)
            if w.ndim != 1 or int(w.shape[0]) != n:
                w = None
            elif float(np.sum(w)) <= 0.0:
                w = None

        if w is None:
            mean_before_l0 = float(np.mean(before_l0))
            mean_after_l0 = float(np.mean(after_l0))
            mean_before_f = float(np.mean(before_f))
            mean_after_f = float(np.mean(after_f))
        else:
            sw = float(np.sum(w))
            mean_before_l0 = float(np.sum(before_l0 * w) / sw)
            mean_after_l0 = float(np.sum(after_l0 * w) / sw)
            mean_before_f = float(np.sum(before_f * w) / sw)
            mean_after_f = float(np.sum(after_f * w) / sw)

        logger.info("[信息] 首层贴近原图优化完成: "
            f"changed={changed_n}/{n}, "
            f"mean_l0_de76 {mean_before_l0:.4f}->{mean_after_l0:.4f}, "
            f"mean_final_de76 {mean_before_f:.4f}->{mean_after_f:.4f}, "
            f"final_slack_de76={slack:.3f}"
        )
    else:
        logger.info(f"[信息] 首层贴近原图优化完成: 未发生修改 (final_slack_de76={slack:.3f})")

    recipes[:, 0] = best_s
    return recipes


def optimize_first_layer_color(
    image_u8: np.ndarray,
    first_layer_mask: np.ndarray,
    target_white: bool = True,
    white_rgb: Tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """优化首层颜色（简单版本，保持兼容性）
    
    Args:
        image_u8: 输入图像
        first_layer_mask: 首层掩码
        target_white: 是否偏向白色
        white_rgb: 白色目标值

    Returns:
        优化后的图像
    """
    if not target_white:
        return image_u8.copy()

    mask_bool = first_layer_mask > 127 if first_layer_mask.dtype == np.uint8 else first_layer_mask.astype(bool)

    result = image_u8.copy()
    if not np.any(mask_bool):
        return result

    # 简单的颜色偏移（偏白）
    result_float = result.astype(np.float32)
    result_float[mask_bool] = result_float[mask_bool] * 0.9 + 25.5  # 向白色偏移10%

    return np.clip(result_float, 0, 255).astype(np.uint8)


def compute_color_distance(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """计算两个颜色之间的欧氏距离"""
    return np.linalg.norm(np.array(rgb1) - np.array(rgb2))


def find_closest_palette_color(rgb: Tuple[int, int, int], palette: List[Tuple[int, int, int]]) -> Tuple[int, int, int]:
    """在调色板中找到最接近的颜色"""
    min_dist = float("inf")
    closest = palette[0]

    for pal_rgb in palette:
        dist = compute_color_distance(rgb, pal_rgb)
        if dist < min_dist:
            min_dist = dist
            closest = pal_rgb

    return closest


def quantize_to_palette(image_u8: np.ndarray, palette: List[Tuple[int, int, int]]) -> np.ndarray:
    """将图像量化到指定调色板"""
    h, w = image_u8.shape[:2]
    result = np.zeros_like(image_u8)

    for y in range(h):
        for x in range(w):
            rgb = tuple(image_u8[y, x])
            closest = find_closest_palette_color(rgb, palette)
            result[y, x] = closest

    return result
