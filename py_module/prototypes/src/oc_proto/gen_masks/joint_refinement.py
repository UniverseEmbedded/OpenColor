"""联合优化模块 - 主程序入口

本模块提供联合优化功能，包括：
- 边界计算和连通域分析
- 小连通域剔除和去噪
- 引导滤波和标签平滑
- 联合优化主流程

默认使用C++加速实现，如果C++模块不可用则抛出异常。
"""

import time
import traceback
from typing import Optional

import cv2
import numpy as np

from oc_core_02.core.color_systems import ColorSystem
from oc_core_02.utils.bin_loader import import_cpp_extension
from oc_core_02.utils.logger import get_logger
from oc_xgb.color_space import delta_e_cie76, rgb01_to_lab

# 尝试导入C++ ICM优化器
try:
    _opencolor_solver = import_cpp_extension("opencolor_solver")
    ICMJointOptimizer = _opencolor_solver.ICMJointOptimizer
    _CPP_ICM_AVAILABLE = True
except ImportError as e:
    _CPP_ICM_AVAILABLE = False
    logger = get_logger(__name__)
    logger.warning(f"[警告] C++ ICM优化器不可用: {e}")

from .joint_refinement_boundary import (
    _boundary_length_4,
    _boundary_mask_4,
    _build_components_by_label_4,
    _island_score_of_area,
    _perimeter_by_slot_4,
    _print_island_stats,
)
from .joint_refinement_cleanup import (
    _despeckle_single_pixels_4,
    _remove_small_components_replace_with_neighbors,
)
from .joint_refinement_filter import (
    _guided_filter_gray,
    smooth_labels_by_guided_filter,
)

logger = get_logger(__name__)

def joint_refinement(
    labels_by_layer: list[np.ndarray],
    *,
    full_mask: np.ndarray,
    slot_names: list[str],
    guidance_gray01: np.ndarray,
    remove_small_components: bool = True,
    max_area_px: int = 4,
    connectivity: int = 4,
    guided_filter_radius: int = 3,
    guided_filter_eps: float = 0.01,
    guided_filter_passes: int = 2,
    guided_filter_skip_first_layer: bool = True,
    guided_filter_min_soft_margin: float = 0.02,
    guided_filter_despickle_iters: int = 1,
    island_alpha: float = 1.0,
    verbose: bool = True,
) -> list[np.ndarray]:
    """联合优化主函数
    
    Args:
        labels_by_layer: 每层的标签图列表
        full_mask: 全局掩码
        slot_names: 颜色槽名称列表
        guidance_gray01: 引导图像（灰度，0-1范围）
        remove_small_components: 是否移除小连通域
        max_area_px: 小连通域最大面积阈值
        connectivity: 连通性 (4 或 8)
        guided_filter_radius: 引导滤波半径
        guided_filter_eps: 引导滤波正则化参数
        guided_filter_passes: 引导滤波迭代次数
        guided_filter_skip_first_layer: 是否跳过第一层
        guided_filter_min_soft_margin: 引导滤波最小软边距
        guided_filter_despickle_iters: 引导滤波去噪迭代次数
        island_alpha: 小色块分数指数
        verbose: 是否打印详细信息
    
    Returns:
        优化后的标签图列表
    """
    if verbose:
        logger.info("[信息] 开始联合优化流程...")
    
    n_slots = len(slot_names)
    if n_slots == 0:
        return labels_by_layer
    
    roi = np.asarray(full_mask, dtype=bool)
    
    out_layers = []
    for z, labels0 in enumerate(labels_by_layer):
        labels = np.asarray(labels0, dtype=np.int16).copy()
        labels[~roi] = -1
        
        if verbose:
            comp_id, comp_sizes, comp_scores, total_score, area_bins = _build_components_by_label_4(
                labels, roi, n_slots=n_slots, alpha=island_alpha, with_bins=True
            )
            _print_island_stats(
                layer_tag=f"L{z:02d}",
                area_bins=area_bins,
                total_score=total_score,
                alpha=island_alpha,
            )
        
        if remove_small_components and max_area_px > 0:
            labels, stats = _remove_small_components_replace_with_neighbors(
                labels, roi, n_slots=n_slots, max_area_px=max_area_px, connectivity=connectivity
            )
            if verbose:
                logger.info(f"[信息] L{z:02d} 移除小连通域: "
                    f"removed_components={stats['removed_components']}, removed_pixels={stats['removed_pixels']}"
                )
        
        labels, n_des = _despeckle_single_pixels_4(labels, roi, iters=1, n_slots=n_slots)
        if verbose and n_des > 0:
            logger.info(f"[信息] L{z:02d} 去除单像素噪声: {n_des} 像素")
        
        out_layers.append(labels)
    
    if guided_filter_radius > 0 and guided_filter_passes > 0:
        if verbose:
            logger.info("[信息] 开始引导滤波平滑...")
        out_layers = smooth_labels_by_guided_filter(
            out_layers,
            full_mask=full_mask,
            slot_names=slot_names,
            guidance_gray01=guidance_gray01,
            radius=guided_filter_radius,
            eps=guided_filter_eps,
            passes=guided_filter_passes,
            skip_first_layer=guided_filter_skip_first_layer,
            min_soft_margin=guided_filter_min_soft_margin,
            despickle_iters=guided_filter_despickle_iters,
        )
    
    if verbose:
        logger.info("[信息] 联合优化完成")
    
    return out_layers


def compute_boundary_mask(labels: np.ndarray, roi: np.ndarray) -> np.ndarray:
    """计算边界掩码"""
    return _boundary_mask_4(labels, roi)


def compute_perimeter_by_slot(labels: np.ndarray, roi: np.ndarray, n_slots: int) -> np.ndarray:
    """计算每个色块的周长"""
    return _perimeter_by_slot_4(labels, roi, n_slots=n_slots)


def compute_boundary_length(labels: np.ndarray, roi: np.ndarray) -> int:
    """计算4连通边线长度"""
    return _boundary_length_4(labels, roi)


def build_components_by_label(
    labels: np.ndarray,
    roi: np.ndarray,
    *,
    n_slots: int,
    alpha: float = 1.0,
    with_bins: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray]:
    """构建连通域信息
    
    Returns:
        comp_id: 每个像素所属的连通域ID (-1表示无)
        comp_sizes: 每个连通域的大小
        comp_scores: 每个连通域的分数
        total_score: 总分数
        area_bins: 面积分布统计
    """
    return _build_components_by_label_4(labels, roi, n_slots=n_slots, alpha=alpha, with_bins=with_bins)


def remove_small_components(
    labels: np.ndarray,
    roi: np.ndarray,
    *,
    n_slots: int,
    max_area_px: int = 4,
    connectivity: int = 4,
) -> tuple[np.ndarray, dict[str, int]]:
    """移除小连通域并用邻域颜色替换
    
    Returns:
        处理后的标签图和统计信息
    """
    return _remove_small_components_replace_with_neighbors(
        labels, roi, n_slots=n_slots, max_area_px=max_area_px, connectivity=connectivity
    )


def despeckle_single_pixels(
    labels: np.ndarray,
    roi: np.ndarray,
    *,
    iters: int = 1,
    n_slots: int,
) -> tuple[np.ndarray, int]:
    """去除单像素噪声
    
    Returns:
        处理后的标签图和去噪像素数
    """
    return _despeckle_single_pixels_4(labels, roi, iters=iters, n_slots=n_slots)


def guided_filter(
    guidance_gray01: np.ndarray,
    src01: np.ndarray,
    radius: int,
    eps: float,
) -> np.ndarray:
    """引导滤波实现"""
    return _guided_filter_gray(guidance_gray01, src01, radius, eps)


def _joint_refine_layers(
    recipes_print_order_pix: np.ndarray,
    *,
    solver,
    cs: ColorSystem,
    ys: np.ndarray,
    xs: np.ndarray,
    pix_rgb01: np.ndarray,
    full_mask: np.ndarray,
    guidance_gray01: np.ndarray,
    proposal_radius: int,
    proposal_eps: float,
    proposal_min_soft_margin: float,
    proposal_despeckle_iters: int,
    passes: int,
    lambda_smooth: float,
    color_weight: float,
    slack_de76: float,
    edge_beta: float,
    max_candidates: int,
    layer_start: int = 0,
    layer_end: int | None = None,
    mix_sigma: float = 2.5,
    mix_weight: float = 6.0,
    mix_max_increase_de76: float = 0.0,
    mix_base_slack_de76: float = 0.0,
    island_weight: float = 0.35,
    island_alpha: float = 1.0,
    remove_islands_max_area_px: int = 0,
    remove_islands_connectivity: int = 8,
    remove_islands_passes: int = 1,
) -> np.ndarray:
    """联合优化多层配方

    基于色准、边长、叠色连续性和岛屿分数进行联合优化。
    移植自分支16的 _joint_refine_layers 函数。
    """
    recipes = np.asarray(recipes_print_order_pix, dtype=np.int32).copy()
    if recipes.ndim != 2:
        raise ValueError(f"recipes_print_order_pix 形状异常: {recipes.shape}")
    n_pix = int(recipes.shape[0])
    n_layers = int(recipes.shape[1])
    if n_pix <= 0 or n_layers <= 0:
        return recipes

    p = max(0, int(passes))
    if p <= 0:
        return recipes

    roi = np.asarray(full_mask, dtype=bool)
    I = np.asarray(guidance_gray01, dtype=np.float32)
    if I.shape[:2] != roi.shape[:2]:
        raise ValueError(f"guidance_gray01 尺寸不一致: {I.shape} vs {roi.shape}")

    n_slots = int(len(cs.slot_names))
    if n_slots <= 1:
        return recipes

    ys0 = np.asarray(ys, dtype=np.int32).reshape(-1)
    xs0 = np.asarray(xs, dtype=np.int32).reshape(-1)
    if ys0.size != n_pix or xs0.size != n_pix:
        raise ValueError(f"ys/xs 与 recipes 像素数不一致: {ys0.size},{xs0.size} vs {n_pix}")

    tgt_lab_all = rgb01_to_lab(np.asarray(pix_rgb01, dtype=np.float32))

    pos_to_k = np.full((int(roi.shape[0]), int(roi.shape[1])), -1, dtype=np.int32)
    pos_to_k[ys0, xs0] = np.arange(n_pix, dtype=np.int32)

    lam = float(lambda_smooth)
    cw = float(color_weight)
    slack = max(0.0, float(slack_de76))
    beta = max(0.0, float(edge_beta))
    max_cand = int(max_candidates)

    h = int(roi.shape[0])
    w = int(roi.shape[1])

    rem_area = int(remove_islands_max_area_px)
    rem_passes = max(0, int(remove_islands_passes))
    if rem_area > 0 and rem_passes > 0:
        logger.info(
            f"[信息] joint 小连通域剔除(前置)开始: "
            f"max_area_px<={rem_area}, connectivity={int(remove_islands_connectivity)}, passes={rem_passes}"
        )
        t_pre0 = time.perf_counter()
        for z in range(n_layers):
            lz = recipes[:, int(z)].astype(np.int16, copy=False)
            full_lz = np.full((h, w), -1, dtype=np.int16)
            full_lz[ys0, xs0] = lz
            per0 = _boundary_length_4(full_lz, roi)
            logger.info(f"[信息] joint 小连通域剔除(前置): L{z:02d} 开始, perim4_before={per0}")
            for rp in range(rem_passes):
                try:
                    full_lz2, st = _remove_small_components_replace_with_neighbors(
                        full_lz,
                        roi,
                        n_slots=n_slots,
                        max_area_px=rem_area,
                        connectivity=int(remove_islands_connectivity),
                    )
                except Exception as e:
                    logger.error(f"[错误] joint 小连通域剔除(前置)失败: L{z:02d}, 第{rp + 1}/{rem_passes}轮: {e}")
                    traceback.print_exc()
                    break

                removed_comp = int(st.get("removed_components", 0))
                removed_px = int(st.get("removed_pixels", 0))
                if removed_comp <= 0 or removed_px <= 0:
                    if rp == 0:
                        logger.info(f"[信息] joint 小连通域剔除(前置): L{z:02d} 未发现面积<={rem_area}px的小色块")
                    break

                full_lz = np.asarray(full_lz2, dtype=np.int16)
                lz2 = full_lz[ys0, xs0].astype(np.int16, copy=False)
                recipes[:, int(z)] = lz2.astype(np.int32, copy=False)

                per2 = _boundary_length_4(full_lz, roi)
                logger.info(
                    f"[信息] joint 小连通域剔除(前置): "
                    f"L{z:02d} 第{rp + 1}/{rem_passes}轮 removed_components={removed_comp}, removed_pixels={removed_px}, "
                    f"perim4 {per0}->{per2}"
                )
                per0 = per2
        logger.info(f"[信息] joint 小连通域剔除(前置)结束: 用时 {time.perf_counter() - t_pre0:.3f}s")

    try:
        pred_base = solver._predict_batch(recipes[:, ::-1])
    except Exception as e:
        logger.error(f"[错误] joint 全层联合优化基线预测失败: {e}")
        traceback.print_exc()
        return recipes

    pred_lab_pix = np.asarray(pred_base, dtype=np.float32)
    full_pred_lab = np.zeros((h, w, 3), dtype=np.float32)
    full_pred_lab[ys0, xs0] = pred_lab_pix

    de_base_all = delta_e_cie76(tgt_lab_all, pred_base).astype(np.float32, copy=False)
    base_mean = float(np.mean(de_base_all))
    base_med = float(np.median(de_base_all))
    base_p95 = float(np.quantile(de_base_all, 0.95))

    z0 = int(layer_start)
    z1 = int(n_layers if layer_end is None else layer_end)
    if z0 < 0:
        z0 = 0
    if z1 > n_layers:
        z1 = n_layers
    if z1 < z0:
        z1 = z0

    logger.info(
        f"[信息] joint 全层联合优化开始: "
        f"pixels={n_pix}, layers={n_layers}, slots={n_slots}, "
        f"passes={p}, lambda_smooth={lam:.4f}, color_weight={cw:.4f}, slack_de76={slack:.3f}(相对基线), edge_beta={beta:.3f}, layer_range=[{z0},{z1}), "
        f"mix_sigma={float(mix_sigma):.3f}, mix_weight={float(mix_weight):.3f}, mix_step_max_increase_de76={float(mix_max_increase_de76):.3f}, mix_base_slack_de76={float(mix_base_slack_de76):.3f}"
    )
    if int(remove_islands_max_area_px) > 0 and int(remove_islands_passes) > 0:
        logger.info(
            f"[信息] joint 小连通域剔除已启用: "
            f"max_area_px<={int(remove_islands_max_area_px)}, connectivity={int(remove_islands_connectivity)}, passes={int(remove_islands_passes)}"
        )
    logger.info(
        f"[信息] joint 全层联合优化基线色差: "
        f"meanΔE76={base_mean:.4f}, medianΔE76={base_med:.4f}, P95ΔE76={base_p95:.4f}"
    )

    sig_mix = float(mix_sigma)
    if sig_mix > 0.0:
        kmix = int(max(3, 2 * int(3.0 * sig_mix) + 1))
        rad = (kmix - 1) // 2
        xs_k = np.arange(-rad, rad + 1, dtype=np.float32)
        g = np.exp(-0.5 * (xs_k / max(sig_mix, 1e-6)) ** 2)
        g = g / max(float(np.sum(g)), 1e-12)
        w0 = float(g[rad] * g[rad])
        m_u = roi.astype(np.float32)
        blur_m = cv2.GaussianBlur(m_u, (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
        blur_m = np.maximum(blur_m, 1e-6)

        full_tgt_lab = np.zeros((h, w, 3), dtype=np.float32)
        full_tgt_lab[ys0, xs0] = np.asarray(tgt_lab_all, dtype=np.float32)
        tgt_num = cv2.GaussianBlur(full_tgt_lab * m_u[..., None], (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
        tgt_blur_lab = tgt_num / blur_m[..., None]

        pred_num0 = cv2.GaussianBlur(full_pred_lab * m_u[..., None], (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
        pred_blur_lab = pred_num0 / blur_m[..., None]

        base_mix = delta_e_cie76(tgt_blur_lab[ys0, xs0], pred_blur_lab[ys0, xs0]).astype(np.float32, copy=False)
        base_mix_mean = float(np.mean(base_mix))
        base_mix_med = float(np.median(base_mix))
        base_mix_p95 = float(np.quantile(base_mix, 0.95))
    else:
        kmix = 0
        w0 = 1.0
        blur_m = np.ones((h, w), dtype=np.float32)
        tgt_blur_lab = np.zeros((h, w, 3), dtype=np.float32)
        tgt_blur_lab[ys0, xs0] = np.asarray(tgt_lab_all, dtype=np.float32)
        pred_blur_lab = full_pred_lab.copy()

        base_mix_mean = base_mean
        base_mix_med = base_med
        base_mix_p95 = base_p95

    if sig_mix > 0.0:
        de_mix_base_all = np.asarray(base_mix, dtype=np.float32)
    else:
        de_mix_base_all = np.asarray(de_base_all, dtype=np.float32)

    logger.info(
        f"[信息] joint 混色(眯眼评估)基线色差: "
        f"sigma={sig_mix:.3f}, meanΔE76={base_mix_mean:.4f}, medianΔE76={base_mix_med:.4f}, P95ΔE76={base_mix_p95:.4f}"
    )

    for z in range(z0, z1):
        lz = recipes[:, int(z)].astype(np.int16, copy=True)
        full_lz = np.full((int(roi.shape[0]), int(roi.shape[1])), -1, dtype=np.int16)
        full_lz[ys0, xs0] = lz
        per0 = _boundary_length_4(full_lz, roi)
        moved_total = 0

        comp_id0, comp_sizes0, comp_scores0, island_total0, area_bins0 = _build_components_by_label_4(
            full_lz,
            roi,
            n_slots=n_slots,
            alpha=float(island_alpha),
        )

        logger.info(f"[信息] joint 全层联合优化: L{z:02d} 开始, perim4_before={per0}")
        _print_island_stats(
            layer_tag=f"joint L{z:02d} 初始",
            area_bins=area_bins0,
            total_score=float(island_total0),
            alpha=float(island_alpha),
        )
        for it in range(p):
            prop_layers = smooth_labels_by_guided_filter(
                [full_lz],
                full_mask=roi,
                slot_names=list(cs.slot_names),
                guidance_gray01=I,
                radius=int(proposal_radius),
                eps=float(proposal_eps),
                passes=1,
                skip_first_layer=False,
                min_soft_margin=float(proposal_min_soft_margin),
                despeckle_iters=int(proposal_despeckle_iters),
            )
            full_prop = np.asarray(prop_layers[0], dtype=np.int16)
            lz_prop = full_prop[ys0, xs0].astype(np.int16, copy=False)

            cand = (lz_prop != lz) & (lz_prop >= 0) & (lz_prop < n_slots)
            cand_idx = np.flatnonzero(cand)
            if cand_idx.size <= 0:
                logger.info(f"[信息] joint 全层联合优化: L{z:02d} 第{it + 1}/{p}轮无候选，提前结束")
                break

            bmask = _boundary_mask_4(full_lz, roi)
            cand_on_boundary = bmask[ys0[cand_idx], xs0[cand_idx]]
            cand_idx = cand_idx[cand_on_boundary]
            if cand_idx.size <= 0:
                logger.info(f"[信息] joint 全层联合优化: L{z:02d} 第{it + 1}/{p}轮候选均不在边界，提前结束")
                break

            if max_cand > 0 and cand_idx.size > max_cand:
                rng = np.random.default_rng(12345 + int(z) * 100 + int(it))
                cand_idx = rng.choice(cand_idx, size=int(max_cand), replace=False)

            ys_c = ys0[cand_idx]
            xs_c = xs0[cand_idx]

            comp_id_map, comp_sizes, comp_scores, _, _ = _build_components_by_label_4(
                full_lz,
                roi,
                n_slots=n_slots,
                alpha=float(island_alpha),
                with_bins=False,
            )

            cur_cost = np.zeros((cand_idx.size,), dtype=np.float32)
            new_cost = np.zeros((cand_idx.size,), dtype=np.float32)
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                yn = ys_c + int(dy)
                xn = xs_c + int(dx)
                inside = (yn >= 0) & (yn < h) & (xn >= 0) & (xn < w)
                if not bool(np.any(inside)):
                    continue
                yn2 = yn[inside]
                xn2 = xn[inside]
                nb_k = pos_to_k[yn2, xn2]
                ok_nb = nb_k >= 0
                if not bool(np.any(ok_nb)):
                    continue
                ii = np.flatnonzero(inside)[ok_nb]
                nb_k2 = nb_k[ok_nb]

                w_edge = np.exp(-beta * np.abs(I[ys_c[ii], xs_c[ii]] - I[yn2[ok_nb], xn2[ok_nb]]))
                nb_lab = lz[nb_k2]
                cur_diff = (lz[cand_idx[ii]] != nb_lab).astype(np.float32)
                new_diff = (lz_prop[cand_idx[ii]] != nb_lab).astype(np.float32)
                cur_cost[ii] += w_edge * cur_diff
                new_cost[ii] += w_edge * new_diff

            rec_cur = recipes[cand_idx].copy()
            rec_new = rec_cur.copy()
            rec_new[:, int(z)] = lz_prop[cand_idx].astype(np.int32)

            try:
                pred_new = solver._predict_batch(rec_new[:, ::-1])
            except Exception as e:
                logger.error(f"[错误] joint 全层联合优化预测失败: {e}")
                traceback.print_exc()
                return recipes

            pred_cur = pred_lab_pix[cand_idx]

            tgt_lab = tgt_lab_all[cand_idx]
            de_cur = delta_e_cie76(tgt_lab, pred_cur)
            de_new = delta_e_cie76(tgt_lab, pred_new)

            if kmix > 0:
                denom = blur_m[ys_c, xs_c]
                gain = (w0 / denom).astype(np.float32, copy=False)
                pred_blur_cur = pred_blur_lab[ys_c, xs_c]
                tgt_blur = tgt_blur_lab[ys_c, xs_c]
                dlab = (np.asarray(pred_new, dtype=np.float32) - pred_cur).astype(np.float32, copy=False)
                pred_blur_new = pred_blur_cur + dlab * gain[:, None]
                de_mix_cur = delta_e_cie76(tgt_blur, pred_blur_cur)
                de_mix_new = delta_e_cie76(tgt_blur, pred_blur_new)
            else:
                de_mix_cur = de_cur
                de_mix_new = de_new

            ok_slack = de_new <= (de_base_all[cand_idx] + slack)

            mix_base_slack = max(0.0, float(mix_base_slack_de76))
            if mix_base_slack > 0.0:
                ok_mix = de_mix_new <= (de_mix_base_all[cand_idx] + mix_base_slack)
            else:
                ok_mix = de_mix_new <= (de_mix_cur + float(mix_max_increase_de76))

            if int(comp_sizes.shape[0]) > 0:
                old_cid_raw = comp_id_map[ys_c, xs_c]
                old_ok = old_cid_raw >= 0
                old_cid = np.maximum(old_cid_raw, 0)
                old_size = comp_sizes[old_cid].astype(np.float32, copy=False)
                old_score_before = comp_scores[old_cid].astype(np.float32, copy=False)
                old_score_after = _island_score_of_area(np.maximum(old_size - 1.0, 0.0), alpha=float(island_alpha))
                delta_old = (old_score_after - old_score_before) * old_ok.astype(np.float32)

                new_lab = lz_prop[cand_idx].astype(np.int16, copy=False)
                id0 = np.full((cand_idx.size,), -1, dtype=np.int32)
                id1 = np.full((cand_idx.size,), -1, dtype=np.int32)
                id2 = np.full((cand_idx.size,), -1, dtype=np.int32)
                id3 = np.full((cand_idx.size,), -1, dtype=np.int32)

                yn = ys_c
                xn = xs_c + 1
                inside = (xn >= 0) & (xn < w)
                if bool(np.any(inside)):
                    yn2 = yn[inside]
                    xn2 = xn[inside]
                    ok = roi[yn2, xn2] & (full_lz[yn2, xn2] == new_lab[inside])
                    if bool(np.any(ok)):
                        ii = np.flatnonzero(inside)[ok]
                        id0[ii] = comp_id_map[yn2[ok], xn2[ok]]

                yn = ys_c
                xn = xs_c - 1
                inside = (xn >= 0) & (xn < w)
                if bool(np.any(inside)):
                    yn2 = yn[inside]
                    xn2 = xn[inside]
                    ok = roi[yn2, xn2] & (full_lz[yn2, xn2] == new_lab[inside])
                    if bool(np.any(ok)):
                        ii = np.flatnonzero(inside)[ok]
                        id1[ii] = comp_id_map[yn2[ok], xn2[ok]]

                yn = ys_c + 1
                xn = xs_c
                inside = (yn >= 0) & (yn < h)
                if bool(np.any(inside)):
                    yn2 = yn[inside]
                    xn2 = xn[inside]
                    ok = roi[yn2, xn2] & (full_lz[yn2, xn2] == new_lab[inside])
                    if bool(np.any(ok)):
                        ii = np.flatnonzero(inside)[ok]
                        id2[ii] = comp_id_map[yn2[ok], xn2[ok]]

                yn = ys_c - 1
                xn = xs_c
                inside = (yn >= 0) & (yn < h)
                if bool(np.any(inside)):
                    yn2 = yn[inside]
                    xn2 = xn[inside]
                    ok = roi[yn2, xn2] & (full_lz[yn2, xn2] == new_lab[inside])
                    if bool(np.any(ok)):
                        ii = np.flatnonzero(inside)[ok]
                        id3[ii] = comp_id_map[yn2[ok], xn2[ok]]

                ids = np.stack([id0, id1, id2, id3], axis=1)
                valid = ids >= 0
                ids0 = np.maximum(ids, 0)
                u = valid.copy()
                u[:, 1] &= (~valid[:, 0]) | (ids[:, 1] != ids[:, 0])
                u[:, 2] &= ((~valid[:, 0]) | (ids[:, 2] != ids[:, 0])) & ((~valid[:, 1]) | (ids[:, 2] != ids[:, 1]))
                u[:, 3] &= (
                    ((~valid[:, 0]) | (ids[:, 3] != ids[:, 0]))
                    & ((~valid[:, 1]) | (ids[:, 3] != ids[:, 1]))
                    & ((~valid[:, 2]) | (ids[:, 3] != ids[:, 2]))
                )

                nb_sizes = comp_sizes[ids0].astype(np.float32, copy=False)
                nb_scores = comp_scores[ids0].astype(np.float32, copy=False)
                sum_size = np.sum(nb_sizes * u.astype(np.float32), axis=1)
                sum_score_before = np.sum(nb_scores * u.astype(np.float32), axis=1)
                score_after = _island_score_of_area(sum_size + 1.0, alpha=float(island_alpha))
                delta_merge = score_after - sum_score_before
                island_delta = delta_old + delta_merge
            else:
                island_delta = np.zeros((cand_idx.size,), dtype=np.float32)

            delta = (
                float(mix_weight) * (de_mix_new - de_mix_cur)
                + cw * (de_new - de_cur)
                + lam * (new_cost - cur_cost)
                + float(island_weight) * island_delta
            )
            accept = ok_slack & ok_mix & (delta < 0.0)

            acc_idx = cand_idx[accept]
            moved = int(acc_idx.size)
            if moved <= 0:
                logger.info(
                    f"[信息] joint 全层联合优化: "
                    f"L{z:02d} 第{it + 1}/{p}轮无接受像素 (candidates={int(cand_idx.size)})"
                )
                continue

            moved_total += moved
            lz[acc_idx] = lz_prop[acc_idx]
            recipes[acc_idx, int(z)] = lz_prop[acc_idx].astype(np.int32)
            full_lz[ys0[acc_idx], xs0[acc_idx]] = lz_prop[acc_idx]

            pred_lab_pix[acc_idx] = np.asarray(pred_new, dtype=np.float32)[accept]
            full_pred_lab[ys0[acc_idx], xs0[acc_idx]] = pred_lab_pix[acc_idx]
            if kmix > 0:
                pred_num0 = cv2.GaussianBlur(full_pred_lab * m_u[..., None], (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
                pred_blur_lab = pred_num0 / blur_m[..., None]

            per1 = _boundary_length_4(full_lz, roi)
            logger.info(
                f"[信息] joint 全层联合优化: "
                f"L{z:02d} 第{it + 1}/{p}轮 accepted={moved}/{int(cand_idx.size)}, "
                f"meanΔE {float(np.mean(de_cur[accept])):.4f}->{float(np.mean(de_new[accept])):.4f}, "
                f"meanMixΔE {float(np.mean(de_mix_cur[accept])):.4f}->{float(np.mean(de_mix_new[accept])):.4f}, "
                f"meanSmooth {float(np.mean(cur_cost[accept])):.4f}->{float(np.mean(new_cost[accept])):.4f}, "
                f"meanIslandΔ {float(np.mean(island_delta[accept])):.6f}, "
                f"perim4 {per0}->{per1}"
            )
            per0 = per1

        comp_id1, comp_sizes1, comp_scores1, island_total1, area_bins1 = _build_components_by_label_4(
            full_lz,
            roi,
            n_slots=n_slots,
            alpha=float(island_alpha),
            with_bins=True,
        )
        logger.info(
            f"[信息] joint 全层联合优化: L{z:02d} 结束, perim4_after={per0}, moved_total={moved_total}, "
            f"island_score {float(island_total0):.6f}->{float(island_total1):.6f}"
        )
        _print_island_stats(
            layer_tag=f"joint L{z:02d} 结束",
            area_bins=area_bins1,
            total_score=float(island_total1),
            alpha=float(island_alpha),
        )

        rem_area = int(remove_islands_max_area_px)
        rem_passes = max(0, int(remove_islands_passes))
        if rem_area > 0 and rem_passes > 0:
            for rp in range(rem_passes):
                try:
                    full_lz2, st = _remove_small_components_replace_with_neighbors(
                        full_lz,
                        roi,
                        n_slots=n_slots,
                        max_area_px=rem_area,
                        connectivity=int(remove_islands_connectivity),
                    )
                except Exception as e:
                    logger.error(f"[错误] joint 小连通域剔除失败: L{z:02d}, 第{rp + 1}/{rem_passes}轮: {e}")
                    traceback.print_exc()
                    break

                removed_comp = int(st.get("removed_components", 0))
                removed_px = int(st.get("removed_pixels", 0))
                if removed_comp <= 0 or removed_px <= 0:
                    if rp == 0:
                        logger.info(f"[信息] joint 小连通域剔除: L{z:02d} 未发现面积<={rem_area}px的小色块")
                    break

                full_lz = np.asarray(full_lz2, dtype=full_lz.dtype)
                lz2 = full_lz[ys0, xs0].astype(np.int16, copy=False)
                changed_idx = np.flatnonzero(lz2 != lz)
                lz = lz2
                recipes[:, int(z)] = lz.astype(np.int32, copy=False)

                if changed_idx.size > 0:
                    try:
                        pred_chg = solver._predict_batch(recipes[changed_idx, ::-1])
                        pred_lab_pix[changed_idx] = np.asarray(pred_chg, dtype=np.float32)
                        full_pred_lab[ys0[changed_idx], xs0[changed_idx]] = pred_lab_pix[changed_idx]
                        if kmix > 0:
                            pred_num0 = cv2.GaussianBlur(
                                full_pred_lab * m_u[..., None],
                                (kmix, kmix),
                                sigmaX=sig_mix,
                                sigmaY=sig_mix,
                                borderType=cv2.BORDER_REFLECT,
                            )
                            pred_blur_lab = pred_num0 / blur_m[..., None]
                    except Exception as e:
                        logger.error(f"[错误] joint 小连通域剔除后预测更新失败: {e}")
                        traceback.print_exc()

                per2 = _boundary_length_4(full_lz, roi)
                _, _, _, island_total2, area_bins2 = _build_components_by_label_4(
                    full_lz,
                    roi,
                    n_slots=n_slots,
                    alpha=float(island_alpha),
                    with_bins=True,
                )
                logger.info(
                    f"[信息] joint 小连通域剔除: "
                    f"L{z:02d} 第{rp + 1}/{rem_passes}轮 removed_components={removed_comp}, removed_pixels={removed_px}, "
                    f"perim4 {per0}->{per2}, island_score {float(island_total1):.6f}->{float(island_total2):.6f}"
                )
                _print_island_stats(
                    layer_tag=f"joint L{z:02d} 剔除后",
                    area_bins=area_bins2,
                    total_score=float(island_total2),
                    alpha=float(island_alpha),
                )
                per0 = per2
                island_total1 = float(island_total2)

    rem_area = int(remove_islands_max_area_px)
    rem_passes = max(0, int(remove_islands_passes))
    if rem_area > 0 and rem_passes > 0:
        for z in range(0, z0):
            lz = recipes[:, int(z)].astype(np.int16, copy=False)
            full_lz = np.zeros((h, w), dtype=np.int16)
            full_lz[ys0, xs0] = lz
            per0 = _boundary_length_4(full_lz, roi)
            _, _, _, island_total1, area_bins1 = _build_components_by_label_4(
                full_lz,
                roi,
                n_slots=n_slots,
                alpha=float(island_alpha),
                with_bins=True,
            )
            logger.info(f"[信息] joint 小连通域剔除(非优化层): L{z:02d} 开始, perim4_before={per0}")
            _print_island_stats(
                layer_tag=f"joint L{z:02d} 剔除前",
                area_bins=area_bins1,
                total_score=float(island_total1),
                alpha=float(island_alpha),
            )
            for rp in range(rem_passes):
                try:
                    full_lz2, st = _remove_small_components_replace_with_neighbors(
                        full_lz,
                        roi,
                        n_slots=n_slots,
                        max_area_px=rem_area,
                        connectivity=int(remove_islands_connectivity),
                    )
                except Exception as e:
                    logger.error(f"[错误] joint 小连通域剔除失败(非优化层): L{z:02d}, 第{rp + 1}/{rem_passes}轮: {e}")
                    traceback.print_exc()
                    break

                removed_comp = int(st.get("removed_components", 0))
                removed_px = int(st.get("removed_pixels", 0))
                if removed_comp <= 0 or removed_px <= 0:
                    if rp == 0:
                        logger.info(f"[信息] joint 小连通域剔除(非优化层): L{z:02d} 未发现面积<={rem_area}px的小色块")
                    break

                full_lz = np.asarray(full_lz2, dtype=full_lz.dtype)
                lz2 = full_lz[ys0, xs0].astype(np.int16, copy=False)
                changed_idx = np.flatnonzero(lz2 != lz)
                lz = lz2
                recipes[:, int(z)] = lz.astype(np.int32, copy=False)

                if changed_idx.size > 0:
                    try:
                        pred_chg = solver._predict_batch(recipes[changed_idx, ::-1])
                        pred_lab_pix[changed_idx] = np.asarray(pred_chg, dtype=np.float32)
                        full_pred_lab[ys0[changed_idx], xs0[changed_idx]] = pred_lab_pix[changed_idx]
                        if kmix > 0:
                            pred_num0 = cv2.GaussianBlur(
                                full_pred_lab * m_u[..., None],
                                (kmix, kmix),
                                sigmaX=sig_mix,
                                sigmaY=sig_mix,
                                borderType=cv2.BORDER_REFLECT,
                            )
                            pred_blur_lab = pred_num0 / blur_m[..., None]
                    except Exception as e:
                        logger.error(f"[错误] joint 小连通域剔除后预测更新失败(非优化层): {e}")
                        traceback.print_exc()

                per2 = _boundary_length_4(full_lz, roi)
                _, _, _, island_total2, area_bins2 = _build_components_by_label_4(
                    full_lz,
                    roi,
                    n_slots=n_slots,
                    alpha=float(island_alpha),
                    with_bins=True,
                )
                logger.info(
                    f"[信息] joint 小连通域剔除(非优化层): "
                    f"L{z:02d} 第{rp + 1}/{rem_passes}轮 removed_components={removed_comp}, removed_pixels={removed_px}, "
                    f"perim4 {per0}->{per2}, island_score {float(island_total1):.6f}->{float(island_total2):.6f}"
                )
                _print_island_stats(
                    layer_tag=f"joint L{z:02d} 剔除后",
                    area_bins=area_bins2,
                    total_score=float(island_total2),
                    alpha=float(island_alpha),
                )
                per0 = per2
                island_total1 = float(island_total2)

    try:
        de_end_all = delta_e_cie76(tgt_lab_all, pred_lab_pix).astype(np.float32, copy=False)
        end_mean = float(np.mean(de_end_all))
        end_med = float(np.median(de_end_all))
        end_p95 = float(np.quantile(de_end_all, 0.95))

        if kmix > 0:
            pred_num_end = cv2.GaussianBlur(full_pred_lab * m_u[..., None], (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
            pred_blur_end = pred_num_end / blur_m[..., None]
            de_mix_end = delta_e_cie76(tgt_blur_lab[ys0, xs0], pred_blur_end[ys0, xs0]).astype(np.float32, copy=False)
            end_mix_mean = float(np.mean(de_mix_end))
            end_mix_med = float(np.median(de_mix_end))
            end_mix_p95 = float(np.quantile(de_mix_end, 0.95))
        else:
            end_mix_mean = end_mean
            end_mix_med = end_med
            end_mix_p95 = end_p95

        logger.info(
            f"[信息] joint 全层联合优化结束: "
            f"meanΔE76 {base_mean:.4f}->{end_mean:.4f}, "
            f"medianΔE76 {base_med:.4f}->{end_med:.4f}, "
            f"P95ΔE76 {base_p95:.4f}->{end_p95:.4f}"
        )
        if kmix > 0:
            logger.info(
                f"[信息] joint 混色(眯眼sigma={sig_mix:.2f})结束: "
                f"meanΔE76 {base_mix_mean:.4f}->{end_mix_mean:.4f}, "
                f"medianΔE76 {base_mix_med:.4f}->{end_mix_med:.4f}, "
                f"P95ΔE76 {base_mix_p95:.4f}->{end_mix_p95:.4f}"
            )
        if (end_mean > base_mean + 0.05) or (end_p95 > base_p95 + 0.10):
            logger.warning(
                "[警告] joint 参数可能过激，已出现色准退化。"
                "建议优先把 joint_l0_slack_de76 降到 0.05-0.20，"
                "把 joint_l0_lambda_smooth 降到 0.03-0.12，"
                "把 joint_l0_color_weight 提到 2.0-4.0，并优先使用 joint_l0_passes=1。"
            )
    except Exception as e:
        logger.error(f"[错误] joint 全层联合优化结束统计失败: {e}")
        traceback.print_exc()

    return recipes


def _joint_refine_layers_icm(
    recipes_print_order_pix: np.ndarray,
    *,
    solver,
    cs: ColorSystem,
    ys: np.ndarray,
    xs: np.ndarray,
    pix_rgb01: np.ndarray,
    full_mask: np.ndarray,
    guidance_gray01: np.ndarray,
    proposal_radius: int,
    proposal_eps: float,
    proposal_min_soft_margin: float,
    proposal_despeckle_iters: int,
    passes: int,
    lambda_smooth: float,
    color_weight: float,
    slack_de76: float,
    edge_beta: float,
    max_candidates: int,
    layer_start: int = 0,
    layer_end: int | None = None,
    mix_sigma: float = 2.5,
    mix_weight: float = 6.0,
    mix_max_increase_de76: float = 0.0,
    mix_base_slack_de76: float = 0.0,
    island_weight: float = 0.35,
    island_alpha: float = 1.0,
    remove_islands_max_area_px: int = 0,
    remove_islands_connectivity: int = 8,
    remove_islands_passes: int = 1,
    structure_protect: bool = True,
    structure_edge_threshold: float = 0.1,
    structure_protect_strength: float = 0.8,
    icm_mode: bool = True,
    use_cpp: bool = True,  # 默认使用C++实现
) -> np.ndarray:
    """改进版联合优化 - 使用ICM顺序更新和结构保护

    改进点：
    1. ICM顺序更新：逐个像素更新，解决并行接受的不一致性
    2. 结构保护：基于边缘检测降低平滑强度，保护线稿/细结构
    3. 更精确的blur更新：每次更新后重新计算局部blur

    Args:
        structure_protect: 是否启用结构保护
        structure_edge_threshold: 边缘检测阈值 (0-1)
        structure_protect_strength: 结构保护强度 (0-1)，越高保护越强
        icm_mode: 是否使用ICM顺序更新，False则使用原版的批量更新
        use_cpp: 是否使用C++加速实现（默认True，如果不可用则抛出异常）
    """
    # 默认使用C++实现
    if use_cpp:
        if not _CPP_ICM_AVAILABLE:
            raise RuntimeError(
                "C++ ICM优化器不可用。请确保opencolor_solver模块已正确编译和安装。"
                "如果确实需要使用Python实现，请设置use_cpp=False。"
            )
        try:
            return _joint_refine_layers_icm_cpp(
                recipes_print_order_pix,
                solver=solver,
                cs=cs,
                ys=ys,
                xs=xs,
                pix_rgb01=pix_rgb01,
                full_mask=full_mask,
                guidance_gray01=guidance_gray01,
                proposal_radius=proposal_radius,
                proposal_eps=proposal_eps,
                proposal_min_soft_margin=proposal_min_soft_margin,
                proposal_despeckle_iters=proposal_despeckle_iters,
                passes=passes,
                lambda_smooth=lambda_smooth,
                color_weight=color_weight,
                slack_de76=slack_de76,
                edge_beta=edge_beta,
                max_candidates=max_candidates,
                layer_start=layer_start,
                layer_end=layer_end,
                mix_sigma=mix_sigma,
                mix_weight=mix_weight,
                mix_max_increase_de76=mix_max_increase_de76,
                mix_base_slack_de76=mix_base_slack_de76,
                island_weight=island_weight,
                island_alpha=island_alpha,
                remove_islands_max_area_px=remove_islands_max_area_px,
                remove_islands_connectivity=remove_islands_connectivity,
                remove_islands_passes=remove_islands_passes,
                structure_protect=structure_protect,
                structure_edge_threshold=structure_edge_threshold,
                structure_protect_strength=structure_protect_strength,
                icm_mode=icm_mode,
            )
        except Exception as e:
            logger.error(f"[错误] C++ ICM优化器执行失败: {e}")
            traceback.print_exc()
            raise RuntimeError(
                f"C++ ICM优化器执行失败: {e}。"
                f"如果确实需要使用Python实现，请设置use_cpp=False。"
            ) from e
    recipes = np.asarray(recipes_print_order_pix, dtype=np.int32).copy()
    if recipes.ndim != 2:
        raise ValueError(f"recipes_print_order_pix 形状异常: {recipes.shape}")
    n_pix = int(recipes.shape[0])
    n_layers = int(recipes.shape[1])
    if n_pix <= 0 or n_layers <= 0:
        return recipes

    p = max(0, int(passes))
    if p <= 0:
        return recipes

    roi = np.asarray(full_mask, dtype=bool)
    I = np.asarray(guidance_gray01, dtype=np.float32)
    if I.shape[:2] != roi.shape[:2]:
        raise ValueError(f"guidance_gray01 尺寸不一致: {I.shape} vs {roi.shape}")

    n_slots = int(len(cs.slot_names))
    if n_slots <= 1:
        return recipes

    ys0 = np.asarray(ys, dtype=np.int32).reshape(-1)
    xs0 = np.asarray(xs, dtype=np.int32).reshape(-1)
    if ys0.size != n_pix or xs0.size != n_pix:
        raise ValueError(f"ys/xs 与 recipes 像素数不一致: {ys0.size},{xs0.size} vs {n_pix}")

    tgt_lab_all = rgb01_to_lab(np.asarray(pix_rgb01, dtype=np.float32))

    pos_to_k = np.full((int(roi.shape[0]), int(roi.shape[1])), -1, dtype=np.int32)
    pos_to_k[ys0, xs0] = np.arange(n_pix, dtype=np.int32)

    lam = float(lambda_smooth)
    cw = float(color_weight)
    slack = max(0.0, float(slack_de76))
    beta = max(0.0, float(edge_beta))
    max_cand = int(max_candidates)

    h = int(roi.shape[0])
    w = int(roi.shape[1])

    # 结构保护：计算边缘强度图
    edge_strength = np.zeros((h, w), dtype=np.float32)
    if structure_protect:
        # 使用Sobel算子检测边缘
        sobel_x = cv2.Sobel(I, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(I, cv2.CV_32F, 0, 1, ksize=3)
        edge_strength = np.sqrt(sobel_x**2 + sobel_y**2)
        # 归一化到0-1
        emax = np.max(edge_strength)
        if emax > 0:
            edge_strength = edge_strength / emax
        logger.info(f"[信息] 结构保护已启用: edge_threshold={structure_edge_threshold}, protect_strength={structure_protect_strength}")

    # 小连通域剔除（前置）
    rem_area = int(remove_islands_max_area_px)
    rem_passes = max(0, int(remove_islands_passes))
    if rem_area > 0 and rem_passes > 0:
        logger.info(
            f"[信息] joint ICM 小连通域剔除(前置)开始: "
            f"max_area_px<={rem_area}, connectivity={int(remove_islands_connectivity)}, passes={rem_passes}"
        )
        t_pre0 = time.perf_counter()
        for z in range(n_layers):
            lz = recipes[:, int(z)].astype(np.int16, copy=False)
            full_lz = np.full((h, w), -1, dtype=np.int16)
            full_lz[ys0, xs0] = lz
            per0 = _boundary_length_4(full_lz, roi)
            logger.info(f"[信息] joint ICM 小连通域剔除(前置): L{z:02d} 开始, perim4_before={per0}")
            for rp in range(rem_passes):
                try:
                    full_lz2, st = _remove_small_components_replace_with_neighbors(
                        full_lz,
                        roi,
                        n_slots=n_slots,
                        max_area_px=rem_area,
                        connectivity=int(remove_islands_connectivity),
                    )
                except Exception as e:
                    logger.error(f"[错误] joint ICM 小连通域剔除(前置)失败: L{z:02d}, 第{rp + 1}/{rem_passes}轮: {e}")
                    traceback.print_exc()
                    break

                removed_comp = int(st.get("removed_components", 0))
                removed_px = int(st.get("removed_pixels", 0))
                if removed_comp <= 0 or removed_px <= 0:
                    if rp == 0:
                        logger.info(f"[信息] joint ICM 小连通域剔除(前置): L{z:02d} 未发现面积<={rem_area}px的小色块")
                    break

                full_lz = np.asarray(full_lz2, dtype=np.int16)
                lz2 = full_lz[ys0, xs0].astype(np.int16, copy=False)
                recipes[:, int(z)] = lz2.astype(np.int32, copy=False)

                per2 = _boundary_length_4(full_lz, roi)
                logger.info(
                    f"[信息] joint ICM 小连通域剔除(前置): "
                    f"L{z:02d} 第{rp + 1}/{rem_passes}轮 removed_components={removed_comp}, removed_pixels={removed_px}, "
                    f"perim4 {per0}->{per2}"
                )
                per0 = per2
        logger.info(f"[信息] joint ICM 小连通域剔除(前置)结束: 用时 {time.perf_counter() - t_pre0:.3f}s")

    # 基线预测
    try:
        pred_base = solver._predict_batch(recipes[:, ::-1])
    except Exception as e:
        logger.error(f"[错误] joint ICM 基线预测失败: {e}")
        traceback.print_exc()
        return recipes

    pred_lab_pix = np.asarray(pred_base, dtype=np.float32)
    full_pred_lab = np.zeros((h, w, 3), dtype=np.float32)
    full_pred_lab[ys0, xs0] = pred_lab_pix

    de_base_all = delta_e_cie76(tgt_lab_all, pred_base).astype(np.float32, copy=False)
    base_mean = float(np.mean(de_base_all))
    base_med = float(np.median(de_base_all))
    base_p95 = float(np.quantile(de_base_all, 0.95))

    z0 = int(layer_start)
    z1 = int(n_layers if layer_end is None else layer_end)
    if z0 < 0:
        z0 = 0
    if z1 > n_layers:
        z1 = n_layers
    if z1 < z0:
        z1 = z0

    logger.info(
        f"[信息] joint ICM 联合优化开始: "
        f"pixels={n_pix}, layers={n_layers}, slots={n_slots}, "
        f"passes={p}, lambda_smooth={lam:.4f}, color_weight={cw:.4f}, slack_de76={slack:.3f}, "
        f"edge_beta={beta:.3f}, icm_mode={icm_mode}, layer_range=[{z0},{z1})"
    )
    logger.info(
        f"[信息] joint ICM 基线色差: "
        f"meanΔE76={base_mean:.4f}, medianΔE76={base_med:.4f}, P95ΔE76={base_p95:.4f}"
    )

    # 混色（眯眼评估）设置
    sig_mix = float(mix_sigma)
    if sig_mix > 0.0:
        kmix = int(max(3, 2 * int(3.0 * sig_mix) + 1))
        rad = (kmix - 1) // 2
        xs_k = np.arange(-rad, rad + 1, dtype=np.float32)
        g = np.exp(-0.5 * (xs_k / max(sig_mix, 1e-6)) ** 2)
        g = g / max(float(np.sum(g)), 1e-12)
        w0 = float(g[rad] * g[rad])
        m_u = roi.astype(np.float32)
        blur_m = cv2.GaussianBlur(m_u, (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
        blur_m = np.maximum(blur_m, 1e-6)

        full_tgt_lab = np.zeros((h, w, 3), dtype=np.float32)
        full_tgt_lab[ys0, xs0] = np.asarray(tgt_lab_all, dtype=np.float32)
        tgt_num = cv2.GaussianBlur(full_tgt_lab * m_u[..., None], (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
        tgt_blur_lab = tgt_num / blur_m[..., None]

        pred_num0 = cv2.GaussianBlur(full_pred_lab * m_u[..., None], (kmix, kmix), sigmaX=sig_mix, sigmaY=sig_mix, borderType=cv2.BORDER_REFLECT)
        pred_blur_lab = pred_num0 / blur_m[..., None]

        base_mix = delta_e_cie76(tgt_blur_lab[ys0, xs0], pred_blur_lab[ys0, xs0]).astype(np.float32, copy=False)
        base_mix_mean = float(np.mean(base_mix))
        base_mix_med = float(np.median(base_mix))
        base_mix_p95 = float(np.quantile(base_mix, 0.95))
    else:
        kmix = 0
        w0 = 1.0
        blur_m = np.ones((h, w), dtype=np.float32)
        tgt_blur_lab = np.zeros((h, w, 3), dtype=np.float32)
        tgt_blur_lab[ys0, xs0] = np.asarray(tgt_lab_all, dtype=np.float32)
        pred_blur_lab = full_pred_lab.copy()

        base_mix_mean = base_mean
        base_mix_med = base_med
        base_mix_p95 = base_p95

    if sig_mix > 0.0:
        de_mix_base_all = np.asarray(base_mix, dtype=np.float32)
    else:
        de_mix_base_all = np.asarray(de_base_all, dtype=np.float32)

    logger.info(
        f"[信息] joint ICM 混色基线色差: "
        f"sigma={sig_mix:.3f}, meanΔE76={base_mix_mean:.4f}, medianΔE76={base_mix_med:.4f}, P95ΔE76={base_mix_p95:.4f}"
    )

    # 主优化循环
    for z in range(z0, z1):
        lz = recipes[:, int(z)].astype(np.int16, copy=True)
        full_lz = np.full((h, w), -1, dtype=np.int16)
        full_lz[ys0, xs0] = lz
        per0 = _boundary_length_4(full_lz, roi)
        moved_total = 0

        comp_id0, comp_sizes0, comp_scores0, island_total0, area_bins0 = _build_components_by_label_4(
            full_lz,
            roi,
            n_slots=n_slots,
            alpha=float(island_alpha),
        )

        logger.info(f"[信息] joint ICM: L{z:02d} 开始, perim4_before={per0}")
        _print_island_stats(
            layer_tag=f"joint ICM L{z:02d} 初始",
            area_bins=area_bins0,
            total_score=float(island_total0),
            alpha=float(island_alpha),
        )

        for it in range(p):
            # 生成候选提案
            prop_layers = smooth_labels_by_guided_filter(
                [full_lz],
                full_mask=roi,
                slot_names=list(cs.slot_names),
                guidance_gray01=I,
                radius=int(proposal_radius),
                eps=float(proposal_eps),
                passes=1,
                skip_first_layer=False,
                min_soft_margin=float(proposal_min_soft_margin),
                despickle_iters=int(proposal_despeckle_iters),
            )
            full_prop = np.asarray(prop_layers[0], dtype=np.int16)
            lz_prop = full_prop[ys0, xs0].astype(np.int16, copy=False)

            cand = (lz_prop != lz) & (lz_prop >= 0) & (lz_prop < n_slots)
            cand_idx = np.flatnonzero(cand)
            if cand_idx.size <= 0:
                logger.info(f"[信息] joint ICM: L{z:02d} 第{it + 1}/{p}轮无候选，提前结束")
                break

            bmask = _boundary_mask_4(full_lz, roi)
            cand_on_boundary = bmask[ys0[cand_idx], xs0[cand_idx]]
            cand_idx = cand_idx[cand_on_boundary]
            if cand_idx.size <= 0:
                logger.info(f"[信息] joint ICM: L{z:02d} 第{it + 1}/{p}轮候选均不在边界，提前结束")
                break

            if max_cand > 0 and cand_idx.size > max_cand:
                rng = np.random.default_rng(12345 + int(z) * 100 + int(it))
                cand_idx = rng.choice(cand_idx, size=int(max_cand), replace=False)

            if icm_mode:
                # ICM顺序更新
                moved = _icm_update_layer(
                    recipes=recipes,
                    lz=lz,
                    full_lz=full_lz,
                    lz_prop=lz_prop,
                    cand_idx=cand_idx,
                    ys0=ys0,
                    xs0=xs0,
                    pos_to_k=pos_to_k,
                    pred_lab_pix=pred_lab_pix,
                    full_pred_lab=full_pred_lab,
                    tgt_lab_all=tgt_lab_all,
                    de_base_all=de_base_all,
                    de_mix_base_all=de_mix_base_all,
                    tgt_blur_lab=tgt_blur_lab,
                    pred_blur_lab=pred_blur_lab,
                    blur_m=blur_m,
                    w0=w0,
                    roi=roi,
                    I=I,
                    h=h,
                    w=w,
                    z=z,
                    n_slots=n_slots,
                    n_layers=n_layers,
                    solver=solver,
                    lam=lam,
                    cw=cw,
                    slack=slack,
                    beta=beta,
                    mix_weight=float(mix_weight),
                    mix_max_increase_de76=float(mix_max_increase_de76),
                    mix_base_slack_de76=float(mix_base_slack_de76),
                    island_weight=float(island_weight),
                    island_alpha=float(island_alpha),
                    kmix=kmix,
                    sig_mix=sig_mix,
                    m_u=m_u if kmix > 0 else None,
                    edge_strength=edge_strength,
                    structure_protect=structure_protect,
                    structure_protect_strength=structure_protect_strength,
                )
            else:
                # 批量更新（原版逻辑）
                moved = _batch_update_layer(
                    recipes=recipes,
                    lz=lz,
                    full_lz=full_lz,
                    lz_prop=lz_prop,
                    cand_idx=cand_idx,
                    ys0=ys0,
                    xs0=xs0,
                    pos_to_k=pos_to_k,
                    pred_lab_pix=pred_lab_pix,
                    full_pred_lab=full_pred_lab,
                    tgt_lab_all=tgt_lab_all,
                    de_base_all=de_base_all,
                    de_mix_base_all=de_mix_base_all,
                    tgt_blur_lab=tgt_blur_lab,
                    pred_blur_lab=pred_blur_lab,
                    blur_m=blur_m,
                    w0=w0,
                    roi=roi,
                    I=I,
                    h=h,
                    w=w,
                    z=z,
                    n_slots=n_slots,
                    n_layers=n_layers,
                    solver=solver,
                    lam=lam,
                    cw=cw,
                    slack=slack,
                    beta=beta,
                    mix_weight=float(mix_weight),
                    mix_max_increase_de76=float(mix_max_increase_de76),
                    mix_base_slack_de76=float(mix_base_slack_de76),
                    island_weight=float(island_weight),
                    island_alpha=float(island_alpha),
                    kmix=kmix,
                    sig_mix=sig_mix,
                    m_u=m_u if kmix > 0 else None,
                    edge_strength=edge_strength,
                    structure_protect=structure_protect,
                    structure_protect_strength=structure_protect_strength,
                )

            if moved <= 0:
                logger.info(f"[信息] joint ICM: L{z:02d} 第{it + 1}/{p}轮无接受像素")
                break

            moved_total += moved
            per1 = _boundary_length_4(full_lz, roi)
            logger.info(f"[信息] joint ICM: L{z:02d} 第{it + 1}/{p}轮 moved={moved}, perim4 {per0}->{per1}")
            per0 = per1

        # 层结束统计
        comp_id1, comp_sizes1, comp_scores1, island_total1, area_bins1 = _build_components_by_label_4(
            full_lz,
            roi,
            n_slots=n_slots,
            alpha=float(island_alpha),
            with_bins=True,
        )
        logger.info(
            f"[信息] joint ICM: L{z:02d} 结束, perim4_after={per0}, moved_total={moved_total}, "
            f"island_score {float(island_total0):.6f}->{float(island_total1):.6f}"
        )
        _print_island_stats(
            layer_tag=f"joint ICM L{z:02d} 结束",
            area_bins=area_bins1,
            total_score=float(island_total1),
            alpha=float(island_alpha),
        )

    # 最终统计
    try:
        de_end_all = delta_e_cie76(tgt_lab_all, pred_lab_pix).astype(np.float32, copy=False)
        end_mean = float(np.mean(de_end_all))
        end_med = float(np.median(de_end_all))
        end_p95 = float(np.quantile(de_end_all, 0.95))

        logger.info(
            f"[信息] joint ICM 联合优化结束: "
            f"meanΔE76 {base_mean:.4f}->{end_mean:.4f}, "
            f"medianΔE76 {base_med:.4f}->{end_med:.4f}, "
            f"P95ΔE76 {base_p95:.4f}->{end_p95:.4f}"
        )

        if (end_mean > base_mean + 0.05) or (end_p95 > base_p95 + 0.10):
            logger.warning(
                "[警告] joint ICM 参数可能过激，已出现色准退化。"
                "建议降低 slack_de76 或 lambda_smooth。"
            )
    except Exception as e:
        logger.error(f"[错误] joint ICM 结束统计失败: {e}")
        traceback.print_exc()

    return recipes


def _icm_update_layer(
    recipes: np.ndarray,
    lz: np.ndarray,
    full_lz: np.ndarray,
    lz_prop: np.ndarray,
    cand_idx: np.ndarray,
    ys0: np.ndarray,
    xs0: np.ndarray,
    pos_to_k: np.ndarray,
    pred_lab_pix: np.ndarray,
    full_pred_lab: np.ndarray,
    tgt_lab_all: np.ndarray,
    de_base_all: np.ndarray,
    de_mix_base_all: np.ndarray,
    tgt_blur_lab: np.ndarray,
    pred_blur_lab: np.ndarray,
    blur_m: np.ndarray,
    w0: float,
    roi: np.ndarray,
    I: np.ndarray,
    h: int,
    w: int,
    z: int,
    n_slots: int,
    n_layers: int,
    solver,
    lam: float,
    cw: float,
    slack: float,
    beta: float,
    mix_weight: float,
    mix_max_increase_de76: float,
    mix_base_slack_de76: float,
    island_weight: float,
    island_alpha: float,
    kmix: int,
    sig_mix: float,
    m_u: np.ndarray | None,
    edge_strength: np.ndarray,
    structure_protect: bool,
    structure_protect_strength: float,
) -> int:
    """ICM顺序更新单层的候选像素

    逐个像素评估和更新，每次更新后立即更新预测和blur。
    这解决了并行更新的不一致性问题。
    """
    moved = 0

    # 按边缘强度排序候选像素（先处理非边缘区域）
    if structure_protect and cand_idx.size > 0:
        ys_c = ys0[cand_idx]
        xs_c = xs0[cand_idx]
        edge_vals = edge_strength[ys_c, xs_c]
        # 边缘强度高的排在后面（优先处理非边缘）
        sort_idx = np.argsort(edge_vals)
        cand_idx = cand_idx[sort_idx]

    # 逐个处理候选
    for idx in cand_idx:
        y = int(ys0[idx])
        x = int(xs0[idx])
        new_label = int(lz_prop[idx])
        old_label = int(lz[idx])

        if new_label == old_label:
            continue

        # 结构保护：边缘区域降低平滑权重
        lambda_eff = lam
        if structure_protect:
            edge_val = edge_strength[y, x]
            # 边缘区域：降低平滑权重（保护结构）
            lambda_eff = lam * (1.0 - structure_protect_strength * edge_val)

        # 计算边长代价（4邻域）
        cur_cost = 0.0
        new_cost = 0.0
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            yn, xn = y + dy, x + dx
            if yn < 0 or yn >= h or xn < 0 or xn >= w:
                continue
            if not roi[yn, xn]:
                continue
            nb_k = pos_to_k[yn, xn]
            if nb_k < 0:
                continue
            nb_lab = int(lz[nb_k])
            w_edge = np.exp(-beta * abs(I[y, x] - I[yn, xn]))
            cur_cost += w_edge * (old_label != nb_lab)
            new_cost += w_edge * (new_label != nb_lab)

        # 预测新配方的颜色
        rec_cur = recipes[idx].copy()
        rec_new = rec_cur.copy()
        rec_new[int(z)] = new_label

        try:
            pred_new = solver._predict_batch(rec_new[::-1].reshape(1, -1))
            pred_new = np.asarray(pred_new, dtype=np.float32).reshape(3)
        except Exception:
            continue

        pred_cur = pred_lab_pix[idx]
        tgt_lab = tgt_lab_all[idx]

        # 色差
        de_cur = delta_e_cie76(tgt_lab, pred_cur)
        de_new = delta_e_cie76(tgt_lab, pred_new)

        # 混色（眯眼）色差
        if kmix > 0:
            denom = blur_m[y, x]
            gain = w0 / max(denom, 1e-6)
            pred_blur_cur = pred_blur_lab[y, x]
            tgt_blur = tgt_blur_lab[y, x]
            dlab = (pred_new - pred_cur).astype(np.float32)
            pred_blur_new = pred_blur_cur + dlab * gain
            de_mix_cur = delta_e_cie76(tgt_blur, pred_blur_cur)
            de_mix_new = delta_e_cie76(tgt_blur, pred_blur_new)
        else:
            de_mix_cur = de_cur
            de_mix_new = de_new

        # 硬约束
        ok_slack = de_new <= (de_base_all[idx] + slack)

        mix_base_slack = max(0.0, mix_base_slack_de76)
        if mix_base_slack > 0.0:
            ok_mix = de_mix_new <= (de_mix_base_all[idx] + mix_base_slack)
        else:
            ok_mix = de_mix_new <= (de_mix_cur + mix_max_increase_de76)

        # 简化的岛屿分数（单像素）
        island_delta = 0.0  # 简化处理，ICM模式下岛屿分数影响较小

        # 总代价变化
        delta = (
            mix_weight * (de_mix_new - de_mix_cur)
            + cw * (de_new - de_cur)
            + lambda_eff * (new_cost - cur_cost)
            + island_weight * island_delta
        )

        accept = ok_slack and ok_mix and (delta < 0.0)

        if accept:
            # 接受更新
            lz[idx] = new_label
            recipes[idx, int(z)] = new_label
            full_lz[y, x] = new_label
            pred_lab_pix[idx] = pred_new
            full_pred_lab[y, x] = pred_new

            # 立即更新blur（如果启用）
            if kmix > 0 and m_u is not None:
                pred_num = cv2.GaussianBlur(
                    full_pred_lab * m_u[..., None],
                    (kmix, kmix),
                    sigmaX=sig_mix,
                    sigmaY=sig_mix,
                    borderType=cv2.BORDER_REFLECT
                )
                pred_blur_lab[:] = pred_num / blur_m[..., None]

            moved += 1

    return moved


def _batch_update_layer(
    recipes: np.ndarray,
    lz: np.ndarray,
    full_lz: np.ndarray,
    lz_prop: np.ndarray,
    cand_idx: np.ndarray,
    ys0: np.ndarray,
    xs0: np.ndarray,
    pos_to_k: np.ndarray,
    pred_lab_pix: np.ndarray,
    full_pred_lab: np.ndarray,
    tgt_lab_all: np.ndarray,
    de_base_all: np.ndarray,
    de_mix_base_all: np.ndarray,
    tgt_blur_lab: np.ndarray,
    pred_blur_lab: np.ndarray,
    blur_m: np.ndarray,
    w0: float,
    roi: np.ndarray,
    I: np.ndarray,
    h: int,
    w: int,
    z: int,
    n_slots: int,
    n_layers: int,
    solver,
    lam: float,
    cw: float,
    slack: float,
    beta: float,
    mix_weight: float,
    mix_max_increase_de76: float,
    mix_base_slack_de76: float,
    island_weight: float,
    island_alpha: float,
    kmix: int,
    sig_mix: float,
    m_u: np.ndarray | None,
    edge_strength: np.ndarray,
    structure_protect: bool,
    structure_protect_strength: float,
) -> int:
    """批量更新单层的候选像素（原版逻辑，带结构保护）"""
    ys_c = ys0[cand_idx]
    xs_c = xs0[cand_idx]

    # 计算边长代价
    cur_cost = np.zeros((cand_idx.size,), dtype=np.float32)
    new_cost = np.zeros((cand_idx.size,), dtype=np.float32)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        yn = ys_c + int(dy)
        xn = xs_c + int(dx)
        inside = (yn >= 0) & (yn < h) & (xn >= 0) & (xn < w)
        if not bool(np.any(inside)):
            continue
        yn2 = yn[inside]
        xn2 = xn[inside]
        nb_k = pos_to_k[yn2, xn2]
        ok_nb = nb_k >= 0
        if not bool(np.any(ok_nb)):
            continue
        ii = np.flatnonzero(inside)[ok_nb]
        nb_k2 = nb_k[ok_nb]

        w_edge = np.exp(-beta * np.abs(I[ys_c[ii], xs_c[ii]] - I[yn2[ok_nb], xn2[ok_nb]]))
        nb_lab = lz[nb_k2]
        cur_diff = (lz[cand_idx[ii]] != nb_lab).astype(np.float32)
        new_diff = (lz_prop[cand_idx[ii]] != nb_lab).astype(np.float32)
        cur_cost[ii] += w_edge * cur_diff
        new_cost[ii] += w_edge * new_diff

    # 结构保护：边缘区域降低平滑权重
    if structure_protect:
        edge_vals = edge_strength[ys_c, xs_c]
        protect_factor = 1.0 - structure_protect_strength * edge_vals
        cur_cost *= protect_factor
        new_cost *= protect_factor

    # 批量预测
    rec_cur = recipes[cand_idx].copy()
    rec_new = rec_cur.copy()
    rec_new[:, int(z)] = lz_prop[cand_idx].astype(np.int32)

    try:
        pred_new = solver._predict_batch(rec_new[:, ::-1])
    except Exception as e:
        logger.error(f"[错误] 批量预测失败: {e}")
        return 0

    pred_cur = pred_lab_pix[cand_idx]
    tgt_lab = tgt_lab_all[cand_idx]
    de_cur = delta_e_cie76(tgt_lab, pred_cur)
    de_new = delta_e_cie76(tgt_lab, pred_new)

    # 混色色差
    if kmix > 0:
        denom = blur_m[ys_c, xs_c]
        gain = (w0 / np.maximum(denom, 1e-6)).astype(np.float32)
        pred_blur_cur = pred_blur_lab[ys_c, xs_c]
        tgt_blur = tgt_blur_lab[ys_c, xs_c]
        dlab = (np.asarray(pred_new, dtype=np.float32) - pred_cur).astype(np.float32)
        pred_blur_new = pred_blur_cur + dlab * gain[:, None]
        de_mix_cur = delta_e_cie76(tgt_blur, pred_blur_cur)
        de_mix_new = delta_e_cie76(tgt_blur, pred_blur_new)
    else:
        de_mix_cur = de_cur
        de_mix_new = de_new

    # 硬约束
    ok_slack = de_new <= (de_base_all[cand_idx] + slack)

    mix_base_slack = max(0.0, mix_base_slack_de76)
    if mix_base_slack > 0.0:
        ok_mix = de_mix_new <= (de_mix_base_all[cand_idx] + mix_base_slack)
    else:
        ok_mix = de_mix_new <= (de_mix_cur + mix_max_increase_de76)

    # 简化的岛屿分数
    island_delta = np.zeros((cand_idx.size,), dtype=np.float32)

    # 总代价
    delta = (
        mix_weight * (de_mix_new - de_mix_cur)
        + cw * (de_new - de_cur)
        + lam * (new_cost - cur_cost)
        + island_weight * island_delta
    )

    accept = ok_slack & ok_mix & (delta < 0.0)

    acc_idx = cand_idx[accept]
    moved = int(acc_idx.size)

    if moved > 0:
        lz[acc_idx] = lz_prop[acc_idx]
        recipes[acc_idx, int(z)] = lz_prop[acc_idx].astype(np.int32)
        full_lz[ys0[acc_idx], xs0[acc_idx]] = lz_prop[acc_idx]
        pred_lab_pix[acc_idx] = np.asarray(pred_new, dtype=np.float32)[accept]
        full_pred_lab[ys0[acc_idx], xs0[acc_idx]] = pred_lab_pix[acc_idx]

        if kmix > 0 and m_u is not None:
            pred_num = cv2.GaussianBlur(
                full_pred_lab * m_u[..., None],
                (kmix, kmix),
                sigmaX=sig_mix,
                sigmaY=sig_mix,
                borderType=cv2.BORDER_REFLECT
            )
            pred_blur_lab[:] = pred_num / blur_m[..., None]

    return moved


def _joint_refine_layers_icm_cpp(
    recipes_print_order_pix: np.ndarray,
    *,
    solver,
    cs: ColorSystem,
    ys: np.ndarray,
    xs: np.ndarray,
    pix_rgb01: np.ndarray,
    full_mask: np.ndarray,
    guidance_gray01: np.ndarray,
    proposal_radius: int,
    proposal_eps: float,
    proposal_min_soft_margin: float,
    proposal_despeckle_iters: int,
    passes: int,
    lambda_smooth: float,
    color_weight: float,
    slack_de76: float,
    edge_beta: float,
    max_candidates: int,
    layer_start: int = 0,
    layer_end: int | None = None,
    mix_sigma: float = 2.5,
    mix_weight: float = 6.0,
    mix_max_increase_de76: float = 0.0,
    mix_base_slack_de76: float = 0.0,
    island_weight: float = 0.35,
    island_alpha: float = 1.0,
    remove_islands_max_area_px: int = 0,
    remove_islands_connectivity: int = 8,
    remove_islands_passes: int = 1,
    structure_protect: bool = True,
    structure_edge_threshold: float = 0.1,
    structure_protect_strength: float = 0.8,
    icm_mode: bool = True,
) -> np.ndarray:
    """C++ ICM优化器包装函数
    
    将Python参数转换为C++优化器所需的格式并调用。
    """
    # ICMJointOptimizer 已经在模块级别导入
    
    # 确保复制输入数组，因为C++优化器会修改它
    recipes = np.asarray(recipes_print_order_pix, dtype=np.int32).copy()
    if recipes.ndim != 2:
        raise ValueError(f"recipes_print_order_pix 形状异常: {recipes.shape}")
    n_pix = int(recipes.shape[0])
    n_layers = int(recipes.shape[1])
    
    if n_pix <= 0 or n_layers <= 0:
        return recipes
    
    roi = np.asarray(full_mask, dtype=np.uint8)
    I = np.asarray(guidance_gray01, dtype=np.float32)
    
    if I.shape[:2] != roi.shape[:2]:
        raise ValueError(f"guidance_gray01 尺寸不一致: {I.shape} vs {roi.shape}")
    
    n_slots = int(len(cs.slot_names))
    h, w = int(roi.shape[0]), int(roi.shape[1])
    
    ys0 = np.asarray(ys, dtype=np.int32).reshape(-1)
    xs0 = np.asarray(xs, dtype=np.int32).reshape(-1)
    pix_rgb = np.asarray(pix_rgb01, dtype=np.float32)
    
    # 构建配置字典
    config = {
        "passes": int(passes),
        "lambda_smooth": float(lambda_smooth),
        "color_weight": float(color_weight),
        "slack_de76": float(slack_de76),
        "edge_beta": float(edge_beta),
        "max_candidates": int(max_candidates),
        "proposal_radius": int(proposal_radius),
        "proposal_eps": float(proposal_eps),
        "proposal_min_soft_margin": float(proposal_min_soft_margin),
        "proposal_despickle_iters": int(proposal_despeckle_iters),
        "mix_sigma": float(mix_sigma),
        "mix_weight": float(mix_weight),
        "mix_max_increase_de76": float(mix_max_increase_de76),
        "mix_base_slack_de76": float(mix_base_slack_de76),
        "island_weight": float(island_weight),
        "island_alpha": float(island_alpha),
        "remove_islands_max_area_px": int(remove_islands_max_area_px),
        "remove_islands_connectivity": int(remove_islands_connectivity),
        "remove_islands_passes": int(remove_islands_passes),
        "structure_protect": bool(structure_protect),
        "structure_protect_strength": float(structure_protect_strength),
    }
    
    logger.info(f"[信息] 使用C++ ICM优化器: n_slots={n_slots}, n_layers={n_layers}, size={h}x{w}")
    
    # 获取底层的C++求解器对象
    # solver 可能是 HillClimbingSolverCpp 包装器，需要获取其内部的 _solver
    if hasattr(solver, '_solver'):
        cpp_solver = solver._solver
    else:
        raise TypeError("solver必须是HillClimbingSolverCpp实例或其子类")
    
    # 创建优化器并执行
    optimizer = ICMJointOptimizer(cpp_solver, n_slots, n_layers, h, w, config)
    
    z1 = n_layers if layer_end is None else layer_end
    
    result = optimizer.optimize(
        recipes, ys0, xs0, pix_rgb, I, roi,
        layer_start=int(layer_start),
        layer_end=int(z1)
    )
    
    logger.info("[信息] C++ ICM优化器执行完成")
    
    return np.asarray(result, dtype=np.int32)


__all__ = [
    "joint_refinement",
    "_joint_refine_layers",
    "_joint_refine_layers_icm",
    "compute_boundary_mask",
    "compute_perimeter_by_slot",
    "compute_boundary_length",
    "build_components_by_label",
    "remove_small_components",
    "despeckle_single_pixels",
    "guided_filter",
]
