"""gen_masks - 掩码生成主模块

本模块提供从输入图像生成打印掩码的完整流程，包括：
- 图像预处理（超分辨率、引导滤波、锐化）
- 颜色求解优化
- 多图层联合优化
- 后处理（卷积、引导滤波、岛屿抑制）
- 可视化和统计输出
"""

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
from PIL import Image

# 首先配置简洁的日志格式
from loguru import logger as _logger
_logger.remove()
_logger.add(sys.stderr, format="<level>{message}</level>", level="INFO", colorize=True)

from oc_core_02.core.color_systems import ColorSystem
from oc_core_02.utils.logger import get_logger
from oc_core_02.utils.paths import RESOURCES, get_out_dir, make_out_subdir_name_for_file
from oc_proto.gen_masks import _save_layer_total_contour_viz
from oc_proto.gen_masks import volumes_to_labels
from oc_proto.gen_masks.joint_refinement import _joint_refine_layers, _joint_refine_layers_icm
from oc_proto.gen_masks.main_preprocess import _load_model_and_setup, _preprocess_image
from oc_proto.gen_masks.main_solve import _solve_and_optimize, _postprocess_masks, _generate_preview_and_error
from oc_proto.gen_masks.solver_cpp_wrapper import CPP_AVAILABLE, create_solver
from oc_proto.gen_masks.stats import print_layer_stats
from oc_sdf.sdf_data_prep import generate_layer_volumes as _generate_layer_volumes
from oc_xgb.color_space import rgb01_to_lab, delta_e_cie76

logger = get_logger(__name__)

VERSION = "gen_masks"


def _generate_postprocess_preview(
    volumes: dict,
    cs: ColorSystem,
    solver,
    rgb_u8: np.ndarray,
    full_mask: np.ndarray,
    h: int,
    w: int,
    out_run_dir: Path,
    suffix: str = "after_postprocess",
) -> None:
    """生成后处理后的预测预览图

    Args:
        volumes: 体积数据字典 {slot_name: (n_layers, h, w)}
        cs: 颜色系统
        solver: C++求解器
        rgb_u8: 原始RGB图像
        full_mask: 全局掩码
        h, w: 图像尺寸
        out_run_dir: 输出目录
        suffix: 文件名后缀
    """
    from oc_xgb.color_space import lab_to_rgb01

    n_layers = len(list(volumes.values())[0])
    n_slots = len(cs.slot_names)

    # 构建配方数组 (n_pixels, n_layers)
    # 只处理前景像素
    ys, xs = np.where(full_mask)
    n_pix = ys.size
    logger.info(f"[预览生成] 前景像素数: {n_pix}, 层数: {n_layers}")

    # 构建配方: 对于每个像素，每层选择哪个slot
    # 注意：generate_layer_volumes / solver 侧的层序都是 bottom_first：第 0 层是底层，第 n_layers-1 层是顶层
    logger.info(f"[预览生成] 开始构建配方数组...")
    recipes = np.zeros((n_pix, n_layers), dtype=np.int32)
    for z in range(n_layers):
        for slot_idx, slot_name in enumerate(cs.slot_names):
            vol = volumes[slot_name][z]
            # 该slot在该层的掩码为True的位置
            mask_slot = vol[ys, xs]
            recipes[mask_slot, z] = slot_idx

    # 预测
    logger.info(f"[预览生成] 开始预测 {n_pix} 个像素的颜色...")
    pred_labs = solver._predict_batch(recipes)
    logger.info(f"[预览生成] 预测完成，转换颜色空间...")
    pred_rgb01 = lab_to_rgb01(pred_labs)
    pred_u8 = np.clip(pred_rgb01 * 255.0 + 0.5, 0, 255).astype(np.uint8)

    # 组装回全图
    pred_full = rgb_u8.copy()
    pred_full[ys, xs] = pred_u8

    # 保存
    Image.fromarray(pred_full).save(out_run_dir / f"01_preview_predicted_{suffix}.png")

    # 同时生成误差热图
    from oc_proto.gen_masks.main_solve import create_difference_visualization
    create_difference_visualization(
        rgb_u8, pred_full, str(out_run_dir / f"01_error_heatmap_{suffix}.png")
    )

    # 保存误差统计
    diff = (rgb_u8.astype(np.int32) - pred_full.astype(np.int32))
    diff_abs = np.abs(diff).astype(np.float32)
    diff_abs[~full_mask] = 0.0
    err = {
        "mean_abs_rgb": [float(x) for x in diff_abs.reshape(-1, 3).mean(axis=0)],
        "max_abs_rgb": [int(x) for x in diff_abs.reshape(-1, 3).max(axis=0)],
        "mean_abs": float(diff_abs.mean()),
        "max_abs": float(diff_abs.max()),
    }
    import json
    (out_run_dir / f"01_error_stats_{suffix}.json").write_text(
        json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _save_layer_total_contour_viz_full(
    out_dir: Path, cs: ColorSystem, volumes: dict, full_mask: np.ndarray, n_layers: int
) -> None:
    """保存每层总轮廓可视化"""
    viz_dir = out_dir / "03_layer_total_contours"
    if viz_dir.exists():
        import shutil
        shutil.rmtree(viz_dir)
    viz_dir.mkdir(parents=True, exist_ok=True)

    roi = (full_mask.astype(np.uint8) > 0)
    h, w = roi.shape

    logger.info(f"开始生成每层总轮廓可视化 (位图阶段): {viz_dir}")
    for z in range(n_layers):
        count_u8 = np.zeros((h, w), dtype=np.uint8)
        for slot_name in cs.slot_names:
            m = volumes.get(slot_name)
            if m is None:
                continue
            count_u8 += m[z].astype(np.uint8)

        gap = (roi > 0) & (count_u8 == 0)
        overlap = (roi > 0) & (count_u8 > 1)
        covered = (roi > 0) & (count_u8 >= 1)

        vis = np.zeros((h, w, 3), dtype=np.uint8)
        vis[:] = (24, 24, 24)
        vis[roi == 0] = (0, 0, 0)
        vis[covered] = (60, 160, 60)
        vis[gap] = (220, 90, 40)
        vis[overlap] = (40, 40, 220)

        union_u8 = (covered.astype(np.uint8) * 255)
        gap_u8 = (gap.astype(np.uint8) * 255)
        overlap_u8 = (overlap.astype(np.uint8) * 255)

        contours_union, _ = cv2.findContours(union_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_gap, _ = cv2.findContours(gap_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_overlap, _ = cv2.findContours(overlap_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cv2.drawContours(vis, contours_union, -1, (235, 235, 235), 1)
        cv2.drawContours(vis, contours_gap, -1, (255, 140, 90), 1)
        cv2.drawContours(vis, contours_overlap, -1, (90, 90, 255), 1)

        out_path = viz_dir / f"L{z:02d}_bitmap_total_overlap_gap.png"
        cv2.imwrite(str(out_path), vis)
        logger.info(f"  L{z:02d}: 已保存 {out_path.name} (覆盖={int(np.count_nonzero(covered))}, 空缺={int(np.count_nonzero(gap))}, 重叠={int(np.count_nonzero(overlap))})"
        )


def _analyze_solved_palette_vs_solver_input(
    out_dir: Path,
    *,
    n_layers: int,
    preview_out_w: int,
    preview_out_h: int,
    solved_palette_subdir: str = "05_layer_solved_palette_after_postprocess",
) -> None:
    """分析 solved_palette 与求解输入的偏差"""
    from oc_proto.gen_masks.filters import _gaussian_blur_masked_rgb_u8

    solver_input_path = out_dir / "00_input" / "03_preprocessed_for_solver.png"
    full_mask_path = out_dir / "02_masks" / "full_mask.png"
    solved_dir = out_dir / str(solved_palette_subdir)

    if not solver_input_path.exists():
        raise FileNotFoundError(f"未找到求解输入图: {solver_input_path}")
    if not full_mask_path.exists():
        raise FileNotFoundError(f"未找到 full_mask: {full_mask_path}")
    if not solved_dir.exists():
        raise FileNotFoundError(f"未找到 solved_palette 目录: {solved_dir}")

    out_an_dir = out_dir / "06_solved_palette_vs_solver_input"
    out_an_dir.mkdir(parents=True, exist_ok=True)

    tgt_u8 = np.array(Image.open(solver_input_path).convert("RGB"), dtype=np.uint8)
    tgt_u8 = cv2.flip(tgt_u8, 1)

    mask_u8 = np.array(Image.open(full_mask_path).convert("L"), dtype=np.uint8)
    mask_u8 = cv2.flip(mask_u8, 1)
    mask = mask_u8 > 127

    if tgt_u8.shape[0] != preview_out_h or tgt_u8.shape[1] != preview_out_w:
        tgt_u8 = np.array(Image.fromarray(tgt_u8).resize((preview_out_w, preview_out_h), resample=Image.Resampling.BILINEAR), dtype=np.uint8)
    if mask.shape[0] != preview_out_h or mask.shape[1] != preview_out_w:
        mask_u8_r = np.array(Image.fromarray(mask_u8).resize((preview_out_w, preview_out_h), resample=Image.Resampling.NEAREST), dtype=np.uint8)
        mask = mask_u8_r > 127

    logger.info(f"开始计算 solved_palette vs 求解输入(03_preprocessed_for_solver) 的偏差: {out_an_dir}")
    for z in range(int(n_layers)):
        sp_path = solved_dir / f"L{z:02d}_solved_palette.png"
        if not sp_path.exists():
            logger.warning(f"[警告] 缺少 {sp_path.name}，跳过")
            continue

        sp_u8 = np.array(Image.open(sp_path).convert("RGB"), dtype=np.uint8)
        if sp_u8.shape[:2] != (preview_out_h, preview_out_w):
            sp_u8 = np.array(Image.fromarray(sp_u8).resize((preview_out_w, preview_out_h), resample=Image.Resampling.NEAREST), dtype=np.uint8)

        if not bool(np.any(mask)):
            logger.warning(f"[警告] full_mask 为空，无法计算 L{z:02d} 偏差")
            continue

        tgt_rgb01 = tgt_u8[mask].astype(np.float32) / 255.0
        sp_rgb01 = sp_u8[mask].astype(np.float32) / 255.0
        tgt_lab = rgb01_to_lab(tgt_rgb01)
        sp_lab = rgb01_to_lab(sp_rgb01)
        de = delta_e_cie76(tgt_lab, sp_lab)

        stats = {
            "像素数": int(de.shape[0]),
            "平均ΔE76": float(np.mean(de)),
            "中位数ΔE76": float(np.median(de)),
            "最大ΔE76": float(np.max(de)),
            "P90ΔE76": float(np.quantile(de, 0.90)),
            "P95ΔE76": float(np.quantile(de, 0.95)),
            "P99ΔE76": float(np.quantile(de, 0.99)),
        }

        logger.info(f"[偏差统计] L{z:02d}_solved_palette vs 03_preprocessed_for_solver ΔE76:")
        for k, v in stats.items():
            if k == "像素数":
                logger.info(f"  - {k}: {v}")
            else:
                logger.info(f"  - {k}: {v:.4f}")

        mix_sigma = 2.5
        mix_tag = f"{mix_sigma:.2f}".replace(".", "p")
        tgt_blur = _gaussian_blur_masked_rgb_u8(tgt_u8, mask, sigma=mix_sigma)
        sp_blur = _gaussian_blur_masked_rgb_u8(sp_u8, mask, sigma=mix_sigma)
        tgt_blur_rgb01 = tgt_blur[mask].astype(np.float32) / 255.0
        sp_blur_rgb01 = sp_blur[mask].astype(np.float32) / 255.0
        de_mix = delta_e_cie76(rgb01_to_lab(tgt_blur_rgb01), rgb01_to_lab(sp_blur_rgb01))
        stats_mix = {
            "像素数": int(de_mix.shape[0]),
            "平均ΔE76": float(np.mean(de_mix)),
            "中位数ΔE76": float(np.median(de_mix)),
            "最大ΔE76": float(np.max(de_mix)),
            "P90ΔE76": float(np.quantile(de_mix, 0.90)),
            "P95ΔE76": float(np.quantile(de_mix, 0.95)),
            "P99ΔE76": float(np.quantile(de_mix, 0.99)),
            "高斯sigma": float(mix_sigma),
        }

        logger.info(f"[混色偏差统计] L{z:02d}_solved_palette vs 03_preprocessed_for_solver (眯眼高斯sigma={mix_sigma:.2f}) ΔE76:")
        for k, v in stats_mix.items():
            if k == "像素数":
                logger.info(f"  - {k}: {v}")
            elif k == "高斯sigma":
                logger.info(f"  - {k}: {v:.2f}")
            else:
                logger.info(f"  - {k}: {v:.4f}")

        de_map = np.zeros((preview_out_h, preview_out_w), dtype=np.float32)
        de_map[mask] = de
        heat_clip = float(stats["P95ΔE76"]) if float(stats["P95ΔE76"]) > 1e-6 else 1.0
        heat = np.clip(de_map / heat_clip, 0.0, 1.0)
        heat_u8 = (heat * 255.0 + 0.5).astype(np.uint8)
        heat_bgr = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        heat_rgb = cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)
        heat_rgb[~mask] = 0

        heat_path = out_an_dir / f"L{z:02d}_de76_heatmap.png"
        Image.fromarray(heat_rgb).save(heat_path)
        with open(out_an_dir / f"L{z:02d}_de76_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        de_map_mix = np.zeros((preview_out_h, preview_out_w), dtype=np.float32)
        de_map_mix[mask] = de_mix
        heat_clip_mix = float(stats_mix["P95ΔE76"]) if float(stats_mix["P95ΔE76"]) > 1e-6 else 1.0
        heat_mix = np.clip(de_map_mix / heat_clip_mix, 0.0, 1.0)
        heat_mix_u8 = (heat_mix * 255.0 + 0.5).astype(np.uint8)
        heat_mix_bgr = cv2.applyColorMap(heat_mix_u8, cv2.COLORMAP_JET)
        heat_mix_rgb = cv2.cvtColor(heat_mix_bgr, cv2.COLOR_BGR2RGB)
        heat_mix_rgb[~mask] = 0
        heat_mix_path = out_an_dir / f"L{z:02d}_de76_mix_{mix_tag}_heatmap.png"
        Image.fromarray(heat_mix_rgb).save(heat_mix_path)
        with open(out_an_dir / f"L{z:02d}_de76_mix_{mix_tag}_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats_mix, f, indent=2, ensure_ascii=False)

        logger.info(f"  L{z:02d}: 已保存 {heat_path.name}、L{z:02d}_de76_stats.json、"
            f"{heat_mix_path.name}、L{z:02d}_de76_mix_{mix_tag}_stats.json"
        )


def run(
    image_path: str | None = None,
    *,
    layer0_bias_enabled: bool = True,
    superres_enabled: bool = True,
    superres_scale: int = 2,
    sharpening_enabled: bool = False,
    sharpening_strength: float = 1.5,
    postprocess_mode: str = "joint",
    output_dir: Optional[str] = None,
    board_mm: float = 60.0,
    layer_height_mm: float = 0.12,
    # 首层贴近原图优化参数
    first_print_layer_bias_enabled: bool = False,
    first_print_layer_bias_slack_de76: float = 0.3,
    # 联合优化参数
    joint_l0_enabled: bool = False,
    joint_l0_use_icm: bool = True,  # 使用ICM顺序更新模式
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
    # 结构保护参数
    joint_l0_structure_protect: bool = True,
    joint_l0_structure_protect_strength: float = 0.8,
    # 后处理参数
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
) -> Dict:
    """
    运行掩码生成流程
    """
    if image_path is None:
        image_path = str(RESOURCES["img_dragon_girl"])

    src_path = Path(image_path).resolve()
    logger.info(f"[{VERSION}] 开始处理图像: {src_path}")

    if not src_path.exists():
        logger.error(f"[错误] 输入图像不存在: {src_path}")
        return {"error": "找不到输入图像"}

    prototype_dir = Path(__file__).resolve().parent
    out_dir_base = get_out_dir(prototype_dir)

    run_id = make_out_subdir_name_for_file(src_path)

    # 加载模型并设置输出目录
    out_run_dir, model_dir, model, cs, n_layers, params = _load_model_and_setup(
        src_path, out_dir_base, output_dir, run_id
    )

    # 设置参数
    params.n_layers = n_layers
    params.layer_height_mm = float(layer_height_mm)
    params.target_width_mm = float(board_mm)
    params.nozzle_width_mm = float(board_mm) / 1920.0
    params.auto_bg_remove = False

    # 创建子目录
    input_dir = out_run_dir / "00_input"
    mask_dir = out_run_dir / "02_masks"
    layer_total_dir = out_run_dir / "03_layer_total_contours"
    layer_viz_dir = out_run_dir / "04_layer_solved_palette"
    layer_viz_after_dir = out_run_dir / "05_layer_solved_palette_after_postprocess"
    for d in [input_dir, mask_dir, layer_total_dir, layer_viz_dir, layer_viz_after_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 保存参数
    with open(input_dir / "params.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "bitmap_params": params.__dict__,
                "model_dir": str(model_dir),
                "slot_names": list(cs.slot_names),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    # 预处理图像
    rgb_u8, a_u8, mask_match, h, w = _preprocess_image(
        src_path,
        input_dir,
        superres_enabled=superres_enabled,
        superres_scale=superres_scale,
        sharpening_enabled=sharpening_enabled,
        sharpening_strength=sharpening_strength,
    )

    # 首层颜色偏向
    rgb_for_solver_u8 = rgb_u8.copy()
    if layer0_bias_enabled:
        logger.info("[预处理] 启用首层颜色偏向（偏白）")
        try:
            from oc_proto.gen_masks.optimizer import optimize_first_layer_color
            rgb_for_solver_u8 = optimize_first_layer_color(rgb_for_solver_u8, mask_match)
        except Exception as e:
            logger.error(f"[错误] 首层颜色偏向失败: {e}")
            traceback.print_exc()
            raise

    try:
        Image.fromarray(rgb_for_solver_u8).save(input_dir / "03_preprocessed_for_solver.png")
    except Exception as e:
        logger.error(f"[错误] 写出求解输入图失败: {e}")
        traceback.print_exc()
        raise

    # 创建求解器
    if not CPP_AVAILABLE:
        raise RuntimeError("当前环境无法导入 opencolor_solver.pyd，无法按要求使用C++求解器")

    solver = create_solver(model, use_cpp=True, force_cpp=True)

    # 求解和优化
    recipe_digits, unique_pix, inverse, ys, xs, rgb01 = _solve_and_optimize(
        rgb_for_solver_u8,
        mask_match,
        solver,
        cs,
        n_layers,
        h,
        w,
        input_dir,
        layer0_bias_enabled=layer0_bias_enabled,
        first_print_layer_bias_enabled=first_print_layer_bias_enabled,
        first_print_layer_bias_slack_de76=first_print_layer_bias_slack_de76,
        joint_l0_enabled=joint_l0_enabled,
        joint_l0_passes=joint_l0_passes,
        joint_l0_lambda_smooth=joint_l0_lambda_smooth,
        joint_l0_color_weight=joint_l0_color_weight,
        joint_l0_slack_de76=joint_l0_slack_de76,
        joint_l0_edge_beta=joint_l0_edge_beta,
        joint_l0_max_candidates=joint_l0_max_candidates,
        joint_l0_proposal_radius=joint_l0_proposal_radius,
        joint_l0_proposal_eps=joint_l0_proposal_eps,
        joint_l0_proposal_min_soft_margin=joint_l0_proposal_min_soft_margin,
        joint_l0_proposal_despeckle_iters=joint_l0_proposal_despeckle_iters,
        joint_l0_mix_sigma=joint_l0_mix_sigma,
        joint_l0_mix_weight=joint_l0_mix_weight,
        joint_l0_mix_max_increase_de76=joint_l0_mix_max_increase_de76,
        joint_l0_mix_base_slack_de76=joint_l0_mix_base_slack_de76,
        joint_l0_island_weight=joint_l0_island_weight,
        joint_l0_island_alpha=joint_l0_island_alpha,
        joint_l0_remove_islands_max_area_px=joint_l0_remove_islands_max_area_px,
        joint_l0_remove_islands_connectivity=joint_l0_remove_islands_connectivity,
        joint_l0_remove_islands_passes=joint_l0_remove_islands_passes,
    )

    # 生成求解后的配色预览
    rgb_lut = np.asarray([cs.slot_preview_rgb[n] for n in cs.slot_names], dtype=np.uint8)
    for z in range(n_layers):
        digits_z = recipe_digits[inverse, int(z)].astype(np.int32, copy=False)
        layer_img = np.ones((h, w, 3), dtype=np.uint8) * 255
        layer_img[ys, xs] = rgb_lut[digits_z]
        Image.fromarray(layer_img).save(layer_viz_dir / f"L{z:02d}_solved_palette.png")

    full_mask = np.zeros((h, w), dtype=bool)
    full_mask[ys, xs] = True

    # 生成预测预览
    _generate_preview_and_error(
        rgb_u8,
        recipe_digits,
        recipe_digits,
        inverse,
        ys,
        xs,
        full_mask,
        solver,
        h,
        w,
        out_run_dir,
    )

    # 生成体积数据
    volumes_raw = _generate_layer_volumes(params, cs, ys, xs, inverse, h, w, recipe_digits=recipe_digits)

    # 联合优化
    if bool(joint_l0_enabled) and int(n_layers) > 0:
        logger.info(f"[优化] 首层联合优化: enabled=True, passes={int(joint_l0_passes)}, use_icm={bool(joint_l0_use_icm)}")

        guidance_gray = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0

        # recipe_digits 的形状是 (n_unique_colors, n_layers)
        # 需要通过 inverse 扩展到每个像素 (n_pixels, n_layers)
        pix_rgb01_foreground = rgb01[ys, xs]
        recipes_per_pixel = recipe_digits[inverse]  # 形状: (n_pixels, n_layers)

        try:
            if joint_l0_use_icm:
                # 使用改进的ICM模式（顺序更新+结构保护）
                recipes_per_pixel = _joint_refine_layers_icm(
                    recipes_per_pixel,
                    solver=solver,
                    cs=cs,
                    ys=ys,
                    xs=xs,
                    pix_rgb01=pix_rgb01_foreground,
                    full_mask=full_mask,
                    guidance_gray01=guidance_gray,
                    proposal_radius=int(joint_l0_proposal_radius),
                    proposal_eps=float(joint_l0_proposal_eps),
                    proposal_min_soft_margin=float(joint_l0_proposal_min_soft_margin),
                    proposal_despeckle_iters=int(joint_l0_proposal_despeckle_iters),
                    passes=int(joint_l0_passes),
                    lambda_smooth=float(joint_l0_lambda_smooth),
                    color_weight=float(joint_l0_color_weight),
                    slack_de76=float(joint_l0_slack_de76),
                    edge_beta=float(joint_l0_edge_beta),
                    max_candidates=int(joint_l0_max_candidates),
                    layer_start=0,
                    layer_end=1,
                    mix_sigma=float(joint_l0_mix_sigma),
                    mix_weight=float(joint_l0_mix_weight),
                    mix_max_increase_de76=float(joint_l0_mix_max_increase_de76),
                    mix_base_slack_de76=float(joint_l0_mix_base_slack_de76),
                    island_weight=float(joint_l0_island_weight),
                    island_alpha=float(joint_l0_island_alpha),
                    remove_islands_max_area_px=int(joint_l0_remove_islands_max_area_px),
                    remove_islands_connectivity=int(joint_l0_remove_islands_connectivity),
                    remove_islands_passes=int(joint_l0_remove_islands_passes),
                    structure_protect=bool(joint_l0_structure_protect),
                    structure_protect_strength=float(joint_l0_structure_protect_strength),
                    icm_mode=True,
                )
            else:
                # 使用原版批量更新模式
                recipes_per_pixel = _joint_refine_layers(
                    recipes_per_pixel,
                    solver=solver,
                    cs=cs,
                    ys=ys,
                    xs=xs,
                    pix_rgb01=pix_rgb01_foreground,
                    full_mask=full_mask,
                    guidance_gray01=guidance_gray,
                    proposal_radius=int(joint_l0_proposal_radius),
                    proposal_eps=float(joint_l0_proposal_eps),
                    proposal_min_soft_margin=float(joint_l0_proposal_min_soft_margin),
                    proposal_despeckle_iters=int(joint_l0_proposal_despeckle_iters),
                    passes=int(joint_l0_passes),
                    lambda_smooth=float(joint_l0_lambda_smooth),
                    color_weight=float(joint_l0_color_weight),
                    slack_de76=float(joint_l0_slack_de76),
                    edge_beta=float(joint_l0_edge_beta),
                    max_candidates=int(joint_l0_max_candidates),
                    layer_start=0,
                    layer_end=1,
                    mix_sigma=float(joint_l0_mix_sigma),
                    mix_weight=float(joint_l0_mix_weight),
                    mix_max_increase_de76=float(joint_l0_mix_max_increase_de76),
                    mix_base_slack_de76=float(joint_l0_mix_base_slack_de76),
                    island_weight=float(joint_l0_island_weight),
                    island_alpha=float(joint_l0_island_alpha),
                    remove_islands_max_area_px=int(joint_l0_remove_islands_max_area_px),
                    remove_islands_connectivity=int(joint_l0_remove_islands_connectivity),
                    remove_islands_passes=int(joint_l0_remove_islands_passes),
                )

            # 将优化后的像素级配方映射回唯一颜色级配方
            # 对于每个唯一颜色，找到对应的所有像素，取众数
            logger.info(f"[信息] 开始将像素级配方映射回唯一颜色级配方...")
            logger.info(f"[信息] 唯一颜色数: {len(recipe_digits)}, 像素数: {len(recipes_per_pixel)}")

            n_colors = int(len(recipe_digits))
            n_slots = int(len(cs.slot_names))
            rp = np.asarray(recipes_per_pixel, dtype=np.int32)
            inv = np.asarray(inverse, dtype=np.int64).reshape(-1)
            if rp.ndim != 2 or inv.ndim != 1 or int(rp.shape[0]) != int(inv.shape[0]):
                raise RuntimeError(f"配方映射输入形状异常: recipes_per_pixel={rp.shape}, inverse={inv.shape}")
            if n_colors <= 0 or n_slots <= 0:
                raise RuntimeError(f"配方映射参数异常: n_colors={n_colors}, n_slots={n_slots}")

            cpu_recipe_digits = np.zeros((n_colors, int(rp.shape[1])), dtype=np.int32)
            for z in range(int(rp.shape[1])):
                counts = np.zeros((n_colors, n_slots), dtype=np.int32)
                slot_idx = rp[:, z].astype(np.int64, copy=False)
                ok = (slot_idx >= 0) & (slot_idx < n_slots) & (inv >= 0) & (inv < n_colors)
                if bool(np.any(ok)):
                    np.add.at(counts, (inv[ok], slot_idx[ok]), 1)
                cpu_recipe_digits[:, z] = np.argmax(counts, axis=1).astype(np.int32, copy=False)
            recipe_digits = cpu_recipe_digits
            logger.info("[信息] CPU配方映射完成")

            try:
                volumes_raw = _generate_layer_volumes(
                    params,
                    cs,
                    ys,
                    xs,
                    inverse,
                    h,
                    w,
                    recipe_digits=recipe_digits,
                )
                logger.info("[信息] 已使用联合优化后的配方重新生成体积数据")
            except Exception as e2:
                logger.error(f"[错误] 联合优化后重新生成体积数据失败: {e2}")
                raise

            try:
                from oc_core_02.utils.bin_loader import import_cpp_extension

                solver_mod = import_cpp_extension("opencolor_solver")
                if not hasattr(solver_mod, "VulkanRecipeMapper"):
                    raise RuntimeError("VulkanRecipeMapper不可用")

                logger.info("[信息] 使用Vulkan GPU加速配方映射...")
                mapper = solver_mod.VulkanRecipeMapper()
                gpu_recipe_digits = mapper.map_recipes(
                    rp,
                    inv.astype(np.int32, copy=False),
                    n_colors,
                    n_slots,
                )
                gpu_recipe_digits = np.asarray(gpu_recipe_digits, dtype=np.int32)
                if gpu_recipe_digits.shape != cpu_recipe_digits.shape:
                    raise RuntimeError(f"GPU配方映射输出形状异常: {gpu_recipe_digits.shape} != {cpu_recipe_digits.shape}")

                sample_n = int(min(2048, n_colors))
                if sample_n > 0:
                    rng = np.random.default_rng(20260210)
                    sample_idx = rng.choice(n_colors, size=sample_n, replace=False) if n_colors > sample_n else np.arange(n_colors)
                    mismatch = int(np.count_nonzero(gpu_recipe_digits[sample_idx] != cpu_recipe_digits[sample_idx]))
                    mismatch_ratio = float(mismatch) / float(sample_idx.size * cpu_recipe_digits.shape[1])
                    if mismatch_ratio > 0.001:
                        raise RuntimeError(f"GPU配方映射疑似错误: mismatch_ratio={mismatch_ratio:.6f}")

                recipe_digits = gpu_recipe_digits
                logger.info("[信息] GPU配方映射完成")
            except Exception as e:
                logger.warning(f"[警告] GPU配方映射不可用或不可信，已使用CPU结果: {e}")

            # 更新体积数据
            volumes_raw = _generate_layer_volumes(params, cs, ys, xs, inverse, h, w, recipe_digits=recipe_digits)
            logger.info("[信息] 首层联合优化完成，已更新体积数据")

            # 保存联合优化后的配色预览（专用输出文件夹）
            layer_viz_joint_dir = out_run_dir / "04b_layer_solved_palette_after_joint"
            layer_viz_joint_dir.mkdir(parents=True, exist_ok=True)
            for z in range(n_layers):
                rgb_lut = np.asarray([cs.slot_preview_rgb[n] for n in cs.slot_names], dtype=np.uint8)
                layer_slot = np.full((h, w), 0, dtype=np.int32)
                for i, slot_name in enumerate(cs.slot_names):
                    layer_slot[volumes_raw[slot_name][z]] = int(i)
                layer_img = np.ones((h, w, 3), dtype=np.uint8) * 255
                layer_img[full_mask] = rgb_lut[layer_slot[full_mask]]
                Image.fromarray(layer_img).save(layer_viz_joint_dir / f"L{z:02d}_solved_palette.png")
            logger.info(f"[信息] 已保存联合优化后的配色预览到: {layer_viz_joint_dir}")

            # 生成联合优化后的预测预览图
            try:
                _generate_postprocess_preview(
                    volumes_raw, cs, solver, rgb_u8, full_mask, h, w, out_run_dir,
                    suffix="after_joint"
                )
                logger.info(f"[信息] 已生成联合优化后的预测预览图")
            except Exception as e2:
                logger.error(f"[警告] 生成联合优化后的预测预览图失败: {e2}")
                traceback.print_exc()

        except Exception as e:
            logger.error(f"[错误] 首层联合优化失败: {e}")
            traceback.print_exc()

    # 后处理
    volumes = _postprocess_masks(
        volumes_raw,
        cs,
        full_mask,
        n_layers,
        postprocess_mode,
        postprocess_conv_kernel=postprocess_conv_kernel,
        postprocess_conv_passes=postprocess_conv_passes,
        postprocess_conv_min_majority_frac=postprocess_conv_min_majority_frac,
        postprocess_conv_min_vote_margin=postprocess_conv_min_vote_margin,
        postprocess_guided_radius=postprocess_guided_radius,
        postprocess_guided_eps=postprocess_guided_eps,
        postprocess_guided_passes=postprocess_guided_passes,
        postprocess_guided_min_soft_margin=postprocess_guided_min_soft_margin,
        postprocess_guided_despeckle_iters=postprocess_guided_despeckle_iters,
        postprocess_island_min_area_px=postprocess_island_min_area_px,
        postprocess_island_max_gap_px=postprocess_island_max_gap_px,
        postprocess_island_connectivity=postprocess_island_connectivity,
        postprocess_island_passes=postprocess_island_passes,
        rgb_u8=rgb_u8,
    )

    # 保存每层掩码和可视化
    for z in range(n_layers):
        layer_total = np.zeros((h, w), dtype=np.uint8)
        for slot_name in cs.slot_names:
            mu8 = (volumes[slot_name][z].astype(np.uint8) * 255)
            if int(np.count_nonzero(mu8)) == 0:
                continue
            layer_total = np.maximum(layer_total, mu8)
            Image.fromarray(mu8).save(mask_dir / f"L{z:02d}_{slot_name}_mask.png")
        _save_layer_total_contour_viz(src_path.stem, z, layer_total, str(layer_total_dir / f"L{z:02d}_bitmap_total_overlap_gap.png"))
        if int(np.count_nonzero(layer_total)) > 0:
            print_layer_stats(z, layer_total, prefix="[统计] ")

        # 保存后处理后的配色预览
        rgb_lut = np.asarray([cs.slot_preview_rgb[n] for n in cs.slot_names], dtype=np.uint8)
        layer_slot = np.full((h, w), 0, dtype=np.int32)
        for i, slot_name in enumerate(cs.slot_names):
            layer_slot[volumes[slot_name][z]] = int(i)
        layer_img = np.ones((h, w, 3), dtype=np.uint8) * 255
        layer_img[full_mask] = rgb_lut[layer_slot[full_mask]]
        Image.fromarray(layer_img).save(layer_viz_after_dir / f"L{z:02d}_solved_palette.png")

    Image.fromarray((full_mask.astype(np.uint8) * 255)).save(mask_dir / "full_mask.png")

    # 保存总轮廓可视化
    _save_layer_total_contour_viz_full(out_run_dir, cs, volumes, full_mask, n_layers)

    # 生成后处理后的预测预览图
    try:
        _generate_postprocess_preview(
            volumes, cs, solver, rgb_u8, full_mask, h, w, out_run_dir,
            suffix="after_postprocess"
        )
        logger.info(f"[信息] 已生成后处理后的预测预览图")
    except Exception as e:
        logger.error(f"[警告] 生成后处理后的预测预览图失败: {e}")
        traceback.print_exc()

    # 分析偏差
    try:
        _analyze_solved_palette_vs_solver_input(
            out_run_dir,
            n_layers=n_layers,
            preview_out_w=w,
            preview_out_h=h,
            solved_palette_subdir="05_layer_solved_palette_after_postprocess",
        )
    except Exception as e:
        logger.error(f"[警告] 偏差分析失败: {e}")
        traceback.print_exc()

    # 保存清单
    manifest = {
        "version": VERSION,
        "image_name": src_path.name,
        "image_path": str(src_path),
        "pixel_w": int(w),
        "pixel_h": int(h),
        "board_mm": float(board_mm),
        "n_layers": int(n_layers),
        "layer_height_mm": float(layer_height_mm),
        "slot_names": list(cs.slot_names),
        "slot_preview_rgb": {k: [int(x) for x in cs.slot_preview_rgb[k]] for k in cs.slot_names},
        "mask_postprocess": {
            "layer0_bias_enabled": bool(layer0_bias_enabled),
            "first_print_layer_bias_enabled": bool(first_print_layer_bias_enabled),
            "first_print_layer_bias_slack_de76": float(first_print_layer_bias_slack_de76),
            "joint_l0_enabled": bool(joint_l0_enabled),
            "joint_l0_passes": int(joint_l0_passes),
            "joint_l0_lambda_smooth": float(joint_l0_lambda_smooth),
            "joint_l0_color_weight": float(joint_l0_color_weight),
            "joint_l0_slack_de76": float(joint_l0_slack_de76),
            "joint_l0_edge_beta": float(joint_l0_edge_beta),
            "mode": str(postprocess_mode),
            "postprocess_conv_kernel": int(postprocess_conv_kernel),
            "postprocess_conv_passes": int(postprocess_conv_passes),
            "postprocess_guided_radius": int(postprocess_guided_radius),
            "postprocess_guided_eps": float(postprocess_guided_eps),
            "postprocess_guided_passes": int(postprocess_guided_passes),
            "postprocess_island_min_area_px": int(postprocess_island_min_area_px),
            "postprocess_island_connectivity": int(postprocess_island_connectivity),
        },
    }

    with open(out_run_dir / "mask_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info(f"[{VERSION}] 处理完成，输出目录: {out_run_dir}")

    return {
        "output_dir": str(out_run_dir),
        "preprocessed_path": str(input_dir / "preprocessed.png"),
        "run_id": run_id,
    }


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description=f"{VERSION} - 掩码生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m oc_proto.gen_masks.main
  python -m oc_proto.gen_masks.main D:\\data\\image.png
  python -m oc_proto.gen_masks.main --image-path D:\\data\\image.png
  python -m oc_proto.gen_masks.main --joint-l0-enabled --joint-l0-passes 2
        """,
    )

    parser.add_argument("image", nargs="?", help="输入图像路径(留空使用默认龙娘.png)")
    parser.add_argument("--image-path", dest="image_path", type=str, default=None, help="输入图像路径(优先级高于位置参数)")
    parser.add_argument("--output-dir", "-o", help="输出目录(会在其下创建 <文件名>_<hash6> 子目录)")
    parser.add_argument("--layer0-bias-off", action="store_true", help="关闭首层颜色偏向")
    parser.add_argument("--superres-off", action="store_true", help="关闭超分辨率")
    parser.add_argument("--scale", type=int, default=2, help="超分辨率缩放倍数")
    parser.add_argument("--sharpen", action="store_true", help="启用锐化")
    parser.add_argument("--sharpen-strength", type=float, default=1.5, help="锐化强度")
    parser.add_argument("--postprocess", default="joint", choices=["none", "conv", "guided", "joint", "island"], help="后处理模式")
    parser.add_argument("--board-mm", type=float, default=60.0, help="物理尺寸(mm)，用于下游矢量化")
    parser.add_argument("--layer-height-mm", type=float, default=0.12, help="层高(mm)，用于下游导出")

    # 首层贴近原图优化参数
    parser.add_argument("--first-print-layer-bias", action="store_true", help="启用首层贴近原图优化")
    parser.add_argument("--first-print-layer-bias-slack", type=float, default=0.3, help="首层贴近原图优化松弛量")

    # 联合优化参数
    parser.add_argument("--joint-l0-enabled", action="store_true", help="启用首层联合优化")
    parser.add_argument("--joint-l0-use-icm", action="store_true", default=True, help="使用ICM顺序更新模式（默认启用）")
    parser.add_argument("--joint-l0-use-batch", action="store_true", help="使用批量更新模式（旧版）")
    parser.add_argument("--joint-l0-passes", type=int, default=1, help="首层联合优化迭代次数")
    parser.add_argument("--joint-l0-lambda-smooth", type=float, default=0.05, help="平滑度权重")
    parser.add_argument("--joint-l0-color-weight", type=float, default=3.0, help="色准权重")
    parser.add_argument("--joint-l0-slack-de76", type=float, default=0.15, help="色差松弛量")
    parser.add_argument("--joint-l0-edge-beta", type=float, default=0.0, help="边缘保护系数")
    parser.add_argument("--joint-l0-max-candidates", type=int, default=0, help="最大候选像素数")
    parser.add_argument("--joint-l0-proposal-radius", type=int, default=4, help="提案生成引导滤波半径")
    parser.add_argument("--joint-l0-proposal-eps", type=float, default=0.001, help="提案生成引导滤波eps")
    parser.add_argument("--joint-l0-proposal-min-soft-margin", type=float, default=0.02, help="提案生成最小软边距")
    parser.add_argument("--joint-l0-proposal-despeckle-iters", type=int, default=1, help="提案生成去噪迭代次数")
    parser.add_argument("--joint-l0-mix-sigma", type=float, default=2.5, help="混色评估高斯核sigma")
    parser.add_argument("--joint-l0-mix-weight", type=float, default=6.0, help="混色差权重")
    parser.add_argument("--joint-l0-mix-max-increase-de76", type=float, default=0.0, help="混色差最大增加量")
    parser.add_argument("--joint-l0-mix-base-slack-de76", type=float, default=0.0, help="混色差基线松弛量")
    parser.add_argument("--joint-l0-island-weight", type=float, default=0.35, help="小色块权重")
    parser.add_argument("--joint-l0-island-alpha", type=float, default=1.0, help="小色块面积指数")
    parser.add_argument("--joint-l0-remove-islands-max-area-px", type=int, default=0, help="剔除小连通域最大面积")
    parser.add_argument("--joint-l0-remove-islands-connectivity", type=int, default=8, help="剔除小连通域连通性")
    parser.add_argument("--joint-l0-remove-islands-passes", type=int, default=1, help="剔除小连通域迭代次数")
    # 结构保护参数
    parser.add_argument("--joint-l0-structure-protect", action="store_true", default=True, help="启用结构保护（默认启用）")
    parser.add_argument("--joint-l0-structure-protect-off", action="store_true", help="关闭结构保护")
    parser.add_argument("--joint-l0-structure-protect-strength", type=float, default=0.8, help="结构保护强度(0-1)")

    # 后处理参数
    parser.add_argument("--postprocess-conv-kernel", type=int, default=3, help="卷积平滑核大小")
    parser.add_argument("--postprocess-conv-passes", type=int, default=1, help="卷积平滑迭代次数")
    parser.add_argument("--postprocess-conv-min-majority-frac", type=float, default=0.52, help="卷积平滑最小多数比例")
    parser.add_argument("--postprocess-conv-min-vote-margin", type=int, default=2, help="卷积平滑最小投票边距")
    parser.add_argument("--postprocess-guided-radius", type=int, default=4, help="引导滤波半径")
    parser.add_argument("--postprocess-guided-eps", type=float, default=0.001, help="引导滤波eps")
    parser.add_argument("--postprocess-guided-passes", type=int, default=1, help="引导滤波迭代次数")
    parser.add_argument("--postprocess-guided-min-soft-margin", type=float, default=0.02, help="引导滤波最小软边距")
    parser.add_argument("--postprocess-guided-despeckle-iters", type=int, default=1, help="引导滤波去噪迭代次数")
    parser.add_argument("--postprocess-island-min-area-px", type=int, default=4, help="小色块最小面积")
    parser.add_argument("--postprocess-island-max-gap-px", type=int, default=0, help="小空洞最大面积")
    parser.add_argument("--postprocess-island-connectivity", type=int, default=8, help="岛屿抑制连通性")
    parser.add_argument("--postprocess-island-passes", type=int, default=1, help="岛屿抑制迭代次数")

    args = parser.parse_args()

    chosen_image = args.image_path if args.image_path else args.image

    result = run(
        image_path=chosen_image,
        layer0_bias_enabled=(not bool(args.layer0_bias_off)),
        superres_enabled=(not bool(args.superres_off)),
        superres_scale=args.scale,
        sharpening_enabled=args.sharpen,
        sharpening_strength=args.sharpen_strength,
        postprocess_mode=args.postprocess,
        output_dir=args.output_dir,
        board_mm=args.board_mm,
        layer_height_mm=args.layer_height_mm,
        first_print_layer_bias_enabled=args.first_print_layer_bias,
        first_print_layer_bias_slack_de76=args.first_print_layer_bias_slack,
        joint_l0_enabled=args.joint_l0_enabled,
        joint_l0_use_icm=(args.joint_l0_use_icm and not args.joint_l0_use_batch),
        joint_l0_passes=args.joint_l0_passes,
        joint_l0_lambda_smooth=args.joint_l0_lambda_smooth,
        joint_l0_color_weight=args.joint_l0_color_weight,
        joint_l0_slack_de76=args.joint_l0_slack_de76,
        joint_l0_edge_beta=args.joint_l0_edge_beta,
        joint_l0_max_candidates=args.joint_l0_max_candidates,
        joint_l0_proposal_radius=args.joint_l0_proposal_radius,
        joint_l0_proposal_eps=args.joint_l0_proposal_eps,
        joint_l0_proposal_min_soft_margin=args.joint_l0_proposal_min_soft_margin,
        joint_l0_proposal_despeckle_iters=args.joint_l0_proposal_despeckle_iters,
        joint_l0_mix_sigma=args.joint_l0_mix_sigma,
        joint_l0_mix_weight=args.joint_l0_mix_weight,
        joint_l0_mix_max_increase_de76=args.joint_l0_mix_max_increase_de76,
        joint_l0_mix_base_slack_de76=args.joint_l0_mix_base_slack_de76,
        joint_l0_island_weight=args.joint_l0_island_weight,
        joint_l0_island_alpha=args.joint_l0_island_alpha,
        joint_l0_remove_islands_max_area_px=args.joint_l0_remove_islands_max_area_px,
        joint_l0_remove_islands_connectivity=args.joint_l0_remove_islands_connectivity,
        joint_l0_remove_islands_passes=args.joint_l0_remove_islands_passes,
        joint_l0_structure_protect=(args.joint_l0_structure_protect and not args.joint_l0_structure_protect_off),
        joint_l0_structure_protect_strength=args.joint_l0_structure_protect_strength,
        postprocess_conv_kernel=args.postprocess_conv_kernel,
        postprocess_conv_passes=args.postprocess_conv_passes,
        postprocess_conv_min_majority_frac=args.postprocess_conv_min_majority_frac,
        postprocess_conv_min_vote_margin=args.postprocess_conv_min_vote_margin,
        postprocess_guided_radius=args.postprocess_guided_radius,
        postprocess_guided_eps=args.postprocess_guided_eps,
        postprocess_guided_passes=args.postprocess_guided_passes,
        postprocess_guided_min_soft_margin=args.postprocess_guided_min_soft_margin,
        postprocess_guided_despeckle_iters=args.postprocess_guided_despeckle_iters,
        postprocess_island_min_area_px=args.postprocess_island_min_area_px,
        postprocess_island_max_gap_px=args.postprocess_island_max_gap_px,
        postprocess_island_connectivity=args.postprocess_island_connectivity,
        postprocess_island_passes=args.postprocess_island_passes,
    )

    if "error" in result:
        logger.error(f"[错误] 处理失败: {result['error']}")
        import sys
        sys.exit(1)
    else:
        logger.info(f"[完成] 输出目录: {result['output_dir']}")


if __name__ == "__main__":
    main()
