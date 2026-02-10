"""gen_masks - 求解和后处理模块

本模块提供颜色求解、联合优化、后处理等功能
"""

import json
import traceback
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from oc_core_02.core.color_systems import ColorSystem
from oc_core_02.utils.logger import get_logger
from oc_proto.gen_masks import (
    labels_to_volumes,
    volumes_to_labels,
    smooth_labels_by_convolution,
    smooth_labels_by_guided_filter,
)
from oc_proto.gen_masks.island_suppress import suppress_small_islands as suppress_small_islands_v2
from oc_proto.gen_masks.optimizer import _bias_first_print_layer_to_target
from oc_proto.gen_masks.stats import print_layer_perimeter_stats
from oc_proto.gen_masks.visualization import create_difference_visualization
from oc_xgb.color_space import lab_to_rgb01

logger = get_logger(__name__)
def _solve_and_optimize(
    rgb_for_solver_u8: np.ndarray,
    mask_match: np.ndarray,
    solver,
    cs: ColorSystem,
    n_layers: int,
    h: int,
    w: int,
    input_dir: Path,
    layer0_bias_enabled: bool = True,
    first_print_layer_bias_enabled: bool = False,
    first_print_layer_bias_slack_de76: float = 0.3,
    joint_l0_enabled: bool = False,
    joint_l0_passes: int = 1,
    joint_l0_lambda_smooth: float = 0.05,
    joint_l0_color_weight: float = 3.0,
    joint_l0_slack_de76: float = 0.15,
    joint_l0_edge_beta: float = 0.0,
    joint_l0_max_candidates: int = 0,
    joint_l0_proposal_radius: int = 4,
    joint_l0_proposal_eps: float = 0.001,
    joint_l0_proposal_min_soft_margin: float = 0.02,
    joint_l0_proposal_despeckle_iters: int = 1,
    joint_l0_mix_sigma: float = 2.5,
    joint_l0_mix_weight: float = 6.0,
    joint_l0_mix_max_increase_de76: float = 0.0,
    joint_l0_mix_base_slack_de76: float = 0.0,
    joint_l0_island_weight: float = 0.35,
    joint_l0_island_alpha: float = 1.0,
    joint_l0_remove_islands_max_area_px: int = 0,
    joint_l0_remove_islands_connectivity: int = 8,
    joint_l0_remove_islands_passes: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """求解和优化配方
    
    Returns:
        recipe_digits: 配方数字
        unique_pix: 唯一像素
        inverse: 反向索引
        ys: 前景像素的y坐标
        xs: 前景像素的x坐标
        rgb01: 归一化RGB图像
    """
    ys, xs = np.where(mask_match)
    if int(len(ys)) == 0:
        raise RuntimeError("前景像素为空：请检查输入图是否全透明，或背景移除/阈值设置是否错误")

    rgb01 = rgb_for_solver_u8.astype(np.float32) / 255.0
    pix = rgb01[ys, xs]

    unique_pix, inverse = np.unique(pix, axis=0, return_inverse=True)
    logger.info(f"[信息] 待求解像素数={int(pix.shape[0])}，唯一颜色数={int(unique_pix.shape[0])}")

    unique_recipe_indices_solved = None
    cache_path = input_dir / "solver_cache_unique_pix_recipes.npz"
    if cache_path.exists():
        try:
            data = np.load(cache_path)
            up0 = np.asarray(data["unique_pix"], dtype=np.float32)
            rec0 = np.asarray(data["recipes_solved"], dtype=np.int32)
            n_layers0 = int(data.get("n_layers", rec0.shape[1] if rec0.ndim == 2 else -1))
            if up0.shape == unique_pix.shape and rec0.ndim == 2 and int(rec0.shape[0]) == int(unique_pix.shape[0]) and int(rec0.shape[1]) == int(n_layers) and int(n_layers0) == int(n_layers):
                if bool(np.allclose(up0, unique_pix.astype(np.float32), atol=1e-7, rtol=0.0)):
                    unique_recipe_indices_solved = rec0
                    logger.info(f"[信息] 命中求解缓存: {cache_path.name}")
        except Exception as e:
            logger.error(f"[错误] 读取求解缓存失败，将重新求解: {e}")
            traceback.print_exc()

    if unique_recipe_indices_solved is None:
        logger.info("[信息] 开始使用C++求解器实时求解配方...")
        unique_recipe_indices_solved = solver.solve(unique_pix)
        try:
            np.savez_compressed(
                cache_path,
                unique_pix=unique_pix.astype(np.float32),
                recipes_solved=np.asarray(unique_recipe_indices_solved, dtype=np.int32),
                n_layers=int(n_layers),
            )
            logger.info(f"[信息] 已写出求解缓存: {cache_path.name}")
        except Exception as e:
            logger.error(f"[错误] 写出求解缓存失败: {e}")
            traceback.print_exc()

    unique_recipe_indices_print = unique_recipe_indices_solved.copy()
    idxs = inverse.astype(np.int32, copy=False)
    recipe_digits = unique_recipe_indices_print

    # 首层贴近原图优化
    if bool(first_print_layer_bias_enabled):
        logger.info(f"[优化] 首层贴近原图优化: enabled=True, slack_de76={float(first_print_layer_bias_slack_de76):.3f}")
        unique_recipe_indices_print = _bias_first_print_layer_to_target(
            unique_pix,
            unique_recipe_indices_print,
            solver,
            cs,
            enabled=True,
            final_slack_de76=float(first_print_layer_bias_slack_de76),
            weights=None,
        )
        recipe_digits = unique_recipe_indices_print

    return recipe_digits, unique_pix, inverse, ys, xs, rgb01


def _postprocess_masks(
    volumes_raw: dict,
    cs: ColorSystem,
    full_mask: np.ndarray,
    n_layers: int,
    postprocess_mode: str,
    postprocess_conv_kernel: int = 3,
    postprocess_conv_passes: int = 1,
    postprocess_conv_min_majority_frac: float = 0.52,
    postprocess_conv_min_vote_margin: int = 2,
    postprocess_guided_radius: int = 4,
    postprocess_guided_eps: float = 0.001,
    postprocess_guided_passes: int = 1,
    postprocess_guided_min_soft_margin: float = 0.02,
    postprocess_guided_despeckle_iters: int = 1,
    postprocess_island_min_area_px: int = 4,
    postprocess_island_max_gap_px: int = 0,
    postprocess_island_connectivity: int = 8,
    postprocess_island_passes: int = 1,
    rgb_u8: np.ndarray = None,
) -> dict:
    """后处理掩码
    
    Returns:
        volumes: 后处理后的体积数据
    """
    if postprocess_mode not in {"none", "conv", "guided", "joint", "island"}:
        raise ValueError(f"不支持的 postprocess_mode: {postprocess_mode}")

    volumes = volumes_raw
    if postprocess_mode != "none":
        logger.info(f"[后处理] 模式: {postprocess_mode}")
        labels_by_layer = volumes_to_labels(volumes_raw, cs, full_mask, n_layers)
        
        # 卷积平滑
        if postprocess_mode == "conv":
            labels_by_layer = smooth_labels_by_convolution(
                labels_by_layer,
                full_mask=full_mask,
                slot_names=list(cs.slot_names),
                kernel_size=int(postprocess_conv_kernel),
                passes=int(postprocess_conv_passes),
                skip_first_layer=False,
                min_majority_frac=float(postprocess_conv_min_majority_frac),
                min_vote_margin=int(postprocess_conv_min_vote_margin),
            )
        
        # 引导滤波平滑
        if postprocess_mode in {"guided", "joint"}:
            if rgb_u8 is None:
                raise ValueError("引导滤波需要 rgb_u8 参数")
            guidance_gray = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
            labels_by_layer = smooth_labels_by_guided_filter(
                labels_by_layer,
                full_mask=full_mask,
                slot_names=list(cs.slot_names),
                guidance_gray01=guidance_gray,
                radius=int(postprocess_guided_radius),
                eps=float(postprocess_guided_eps),
                passes=int(postprocess_guided_passes),
                skip_first_layer=False,
                min_soft_margin=float(postprocess_guided_min_soft_margin),
                despeckle_iters=int(postprocess_guided_despeckle_iters),
            )
        
        # 岛屿抑制
        if postprocess_mode in {"island", "joint"}:
            labels_by_layer = suppress_small_islands_v2(
                labels_by_layer,
                full_mask=full_mask,
                slot_names=list(cs.slot_names),
                min_island_area_px=int(postprocess_island_min_area_px),
                max_gap_area_px=int(postprocess_island_max_gap_px),
                connectivity=int(postprocess_island_connectivity),
                passes=int(postprocess_island_passes),
            )
        
        # 转换回体积数据
        volumes = labels_to_volumes(labels_by_layer, cs, n_layers)
        
        # 打印边线统计
        print_layer_perimeter_stats(
            labels_by_layer,
            full_mask=full_mask,
            slot_names=list(cs.slot_names),
            title="后处理后",
        )

    return volumes


def _generate_preview_and_error(
    rgb_u8: np.ndarray,
    unique_recipe_indices_solved: np.ndarray,
    unique_recipe_indices_print: np.ndarray,
    inverse: np.ndarray,
    ys: np.ndarray,
    xs: np.ndarray,
    full_mask: np.ndarray,
    solver,
    h: int,
    w: int,
    out_run_dir: Path,
) -> None:
    """生成预览和误差图"""
    try:
        pred_labs_front = solver._predict_batch(np.asarray(unique_recipe_indices_solved, dtype=np.int32))
        pred_rgb01_front = lab_to_rgb01(pred_labs_front)
        pred_front_u8 = np.clip(pred_rgb01_front * 255.0 + 0.5, 0, 255).astype(np.uint8)
        pred_full_front = rgb_u8.copy()
        pred_full_front[ys, xs] = pred_front_u8[inverse]
        Image.fromarray(pred_full_front).save(out_run_dir / "01_preview_predicted.png")

        recipes_back_view = np.asarray(unique_recipe_indices_print, dtype=np.int32)[:, ::-1]
        pred_labs_back = solver._predict_batch(recipes_back_view)
        pred_rgb01_back = lab_to_rgb01(pred_labs_back)
        pred_back_u8 = np.clip(pred_rgb01_back * 255.0 + 0.5, 0, 255).astype(np.uint8)
        pred_full_back = rgb_u8.copy()
        pred_full_back[ys, xs] = pred_back_u8[inverse]
        Image.fromarray(pred_full_back).save(out_run_dir / "01_preview_back_predicted.png")

        sign = (pred_full_front.astype(np.int32) - pred_full_back.astype(np.int32)).mean(axis=2)
        mag = np.clip(np.abs(sign) * 4.0, 0.0, 255.0).astype(np.uint8)
        sign_viz = np.zeros((h, w, 3), dtype=np.uint8)
        pos = sign > 0
        neg = sign < 0
        sign_viz[pos, 0] = mag[pos]
        sign_viz[neg, 2] = mag[neg]
        Image.fromarray(sign_viz).save(out_run_dir / "01_preview_front_vs_back_sign.png")

        create_difference_visualization(rgb_u8, pred_full_front, str(out_run_dir / "01_error_heatmap_predicted.png"))
        diff = (rgb_u8.astype(np.int32) - pred_full_front.astype(np.int32))
        diff_abs = np.abs(diff).astype(np.float32)
        diff_abs[~full_mask] = 0.0
        err = {
            "mean_abs_rgb": [float(x) for x in diff_abs.reshape(-1, 3).mean(axis=0)],
            "max_abs_rgb": [int(x) for x in diff_abs.reshape(-1, 3).max(axis=0)],
            "mean_abs": float(diff_abs.mean()),
            "max_abs": float(diff_abs.max()),
        }
        (out_run_dir / "01_error_stats_predicted.json").write_text(json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"[错误] 生成预测预览/误差图失败: {e}")
        traceback.print_exc()
        raise
