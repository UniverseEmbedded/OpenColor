"""联合优化模块 - ICM 顺序更新实现

本模块提供基于 ICM（逐像素顺序更新）的联合优化实现，以及可选的 C++ 加速封装。
"""

import time

import cv2
import numpy as np

from oc_core_02.core.color_systems import ColorSystem
from oc_core_02.utils.logger import get_logger
from oc_xgb.color_space import delta_e_cie76, rgb01_to_lab

from .joint_refinement_boundary import (
    _boundary_length_4,
    _boundary_mask_4,
    _build_components_by_label_4,
    _print_island_stats,
)
from .joint_refinement_cleanup import _remove_small_components_replace_with_neighbors
from .joint_refinement_filter import smooth_labels_by_guided_filter

logger = get_logger(__name__)


try:
    from oc_core_02.utils.bin_loader import import_cpp_extension

    _opencolor_solver = import_cpp_extension("opencolor_solver")
    ICMJointOptimizer = _opencolor_solver.ICMJointOptimizer
    _CPP_ICM_AVAILABLE = True
except ImportError as e:
    _CPP_ICM_AVAILABLE = False
    logger.warning(f"[警告] C++ ICM优化器不可用: {e}")


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
    use_cpp: bool = True,
) -> np.ndarray:
    """改进版联合优化 - 使用ICM顺序更新和结构保护"""
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
            raise RuntimeError(
                f"C++ ICM优化器执行失败: {e}。如果确实需要使用Python实现，请设置use_cpp=False。"
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

    edge_strength = np.zeros((h, w), dtype=np.float32)
    if structure_protect:
        sobel_x = cv2.Sobel(I, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(I, cv2.CV_32F, 0, 1, ksize=3)
        edge_strength = np.sqrt(sobel_x**2 + sobel_y**2)
        emax = np.max(edge_strength)
        if emax > 0:
            edge_strength = edge_strength / emax
        logger.info(
            f"[信息] 结构保护已启用: edge_threshold={structure_edge_threshold}, protect_strength={structure_protect_strength}"
        )

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
            logger.info(
                f"[信息] joint ICM 小连通域剔除(前置): L{z:02d} 开始, perim4_before={per0}"
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
                    logger.error(
                        f"[错误] joint ICM 小连通域剔除(前置)失败: L{z:02d}, 第{rp + 1}/{rem_passes}轮: {e}"
                    )
                    raise

                removed_comp = int(st.get("removed_components", 0))
                removed_px = int(st.get("removed_pixels", 0))
                if removed_comp <= 0 or removed_px <= 0:
                    if rp == 0:
                        logger.info(
                            f"[信息] joint ICM 小连通域剔除(前置): L{z:02d} 未发现面积<={rem_area}px的小色块"
                        )
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
        logger.info(
            f"[信息] joint ICM 小连通域剔除(前置)结束: 用时 {time.perf_counter() - t_pre0:.3f}s"
        )

    try:
        pred_base = solver._predict_batch(recipes[:, ::-1])
    except Exception as e:
        logger.error(f"[错误] joint ICM 基线预测失败: {e}")
        raise

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

    sig_mix = float(mix_sigma)
    if sig_mix > 0.0:
        kmix = int(max(3, 2 * int(3.0 * sig_mix) + 1))
        rad = (kmix - 1) // 2
        xs_k = np.arange(-rad, rad + 1, dtype=np.float32)
        g = np.exp(-0.5 * (xs_k / max(sig_mix, 1e-6)) ** 2)
        g = g / max(float(np.sum(g)), 1e-12)
        w0 = float(g[rad] * g[rad])
        m_u = roi.astype(np.float32)
        blur_m = cv2.GaussianBlur(
            m_u,
            (kmix, kmix),
            sigmaX=sig_mix,
            sigmaY=sig_mix,
            borderType=cv2.BORDER_REFLECT,
        )
        blur_m = np.maximum(blur_m, 1e-6)

        full_tgt_lab = np.zeros((h, w, 3), dtype=np.float32)
        full_tgt_lab[ys0, xs0] = np.asarray(tgt_lab_all, dtype=np.float32)
        tgt_num = cv2.GaussianBlur(
            full_tgt_lab * m_u[..., None],
            (kmix, kmix),
            sigmaX=sig_mix,
            sigmaY=sig_mix,
            borderType=cv2.BORDER_REFLECT,
        )
        tgt_blur_lab = tgt_num / blur_m[..., None]

        pred_num0 = cv2.GaussianBlur(
            full_pred_lab * m_u[..., None],
            (kmix, kmix),
            sigmaX=sig_mix,
            sigmaY=sig_mix,
            borderType=cv2.BORDER_REFLECT,
        )
        pred_blur_lab = pred_num0 / blur_m[..., None]

        base_mix = delta_e_cie76(
            tgt_blur_lab[ys0, xs0], pred_blur_lab[ys0, xs0]
        ).astype(np.float32, copy=False)
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

    for z in range(z0, z1):
        lz = recipes[:, int(z)].astype(np.int16, copy=True)
        full_lz = np.full((h, w), -1, dtype=np.int16)
        full_lz[ys0, xs0] = lz
        per0 = _boundary_length_4(full_lz, roi)
        moved_total = 0

        comp_id0, comp_sizes0, comp_scores0, island_total0, area_bins0 = (
            _build_components_by_label_4(full_lz, roi, n_slots=n_slots, alpha=float(island_alpha))
        )

        logger.info(f"[信息] joint ICM: L{z:02d} 开始, perim4_before={per0}")
        _print_island_stats(
            layer_tag=f"joint ICM L{z:02d} 初始",
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
                logger.info(
                    f"[信息] joint ICM: L{z:02d} 第{it + 1}/{p}轮候选均不在边界，提前结束"
                )
                break

            if max_cand > 0 and cand_idx.size > max_cand:
                rng = np.random.default_rng(12345 + int(z) * 100 + int(it))
                cand_idx = rng.choice(cand_idx, size=int(max_cand), replace=False)

            if icm_mode:
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
            logger.info(
                f"[信息] joint ICM: L{z:02d} 第{it + 1}/{p}轮 moved={moved}, perim4 {per0}->{per1}"
            )
            per0 = per1

        comp_id1, comp_sizes1, comp_scores1, island_total1, area_bins1 = (
            _build_components_by_label_4(
                full_lz,
                roi,
                n_slots=n_slots,
                alpha=float(island_alpha),
                with_bins=True,
            )
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
                "[警告] joint ICM 参数可能过激，已出现色准退化。建议降低 slack_de76 或 lambda_smooth。"
            )
    except Exception as e:
        logger.error(f"[错误] joint ICM 结束统计失败: {e}")
        raise

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
    moved = 0

    if structure_protect and cand_idx.size > 0:
        ys_c = ys0[cand_idx]
        xs_c = xs0[cand_idx]
        edge_vals = edge_strength[ys_c, xs_c]
        sort_idx = np.argsort(edge_vals)
        cand_idx = cand_idx[sort_idx]

    for idx in cand_idx:
        y = int(ys0[idx])
        x = int(xs0[idx])
        new_label = int(lz_prop[idx])
        old_label = int(lz[idx])

        if new_label == old_label:
            continue

        lambda_eff = lam
        if structure_protect:
            edge_val = edge_strength[y, x]
            lambda_eff = lam * (1.0 - structure_protect_strength * edge_val)

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

        rec_cur = recipes[idx].copy()
        rec_new = rec_cur.copy()
        rec_new[int(z)] = new_label

        try:
            pred_new = solver._predict_batch(rec_new[::-1].reshape(1, -1))
            pred_new = np.asarray(pred_new, dtype=np.float32).reshape(3)
        except Exception as e:
            logger.error(f"[错误] joint ICM 预测失败: L{z:02d} idx={int(idx)}, err={e}")
            raise

        pred_cur = pred_lab_pix[idx]
        tgt_lab = tgt_lab_all[idx]
        de_cur = delta_e_cie76(tgt_lab, pred_cur)
        de_new = delta_e_cie76(tgt_lab, pred_new)

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

        ok_slack = de_new <= (de_base_all[idx] + slack)

        mix_base_slack = max(0.0, mix_base_slack_de76)
        if mix_base_slack > 0.0:
            ok_mix = de_mix_new <= (de_mix_base_all[idx] + mix_base_slack)
        else:
            ok_mix = de_mix_new <= (de_mix_cur + mix_max_increase_de76)

        island_delta = 0.0

        delta = (
            mix_weight * (de_mix_new - de_mix_cur)
            + cw * (de_new - de_cur)
            + lambda_eff * (new_cost - cur_cost)
            + island_weight * island_delta
        )

        accept = ok_slack and ok_mix and (delta < 0.0)

        if accept:
            lz[idx] = new_label
            recipes[idx, int(z)] = new_label
            full_lz[y, x] = new_label
            pred_lab_pix[idx] = pred_new
            full_pred_lab[y, x] = pred_new

            if kmix > 0 and m_u is not None:
                pred_num = cv2.GaussianBlur(
                    full_pred_lab * m_u[..., None],
                    (kmix, kmix),
                    sigmaX=sig_mix,
                    sigmaY=sig_mix,
                    borderType=cv2.BORDER_REFLECT,
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
    ys_c = ys0[cand_idx]
    xs_c = xs0[cand_idx]

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

    if structure_protect:
        edge_vals = edge_strength[ys_c, xs_c]
        protect_factor = 1.0 - structure_protect_strength * edge_vals
        cur_cost *= protect_factor
        new_cost *= protect_factor

    rec_cur = recipes[cand_idx].copy()
    rec_new = rec_cur.copy()
    rec_new[:, int(z)] = lz_prop[cand_idx].astype(np.int32)

    try:
        pred_new = solver._predict_batch(rec_new[:, ::-1])
    except Exception as e:
        logger.error(f"[错误] 批量预测失败: {e}")
        raise

    pred_cur = pred_lab_pix[cand_idx]
    tgt_lab = tgt_lab_all[cand_idx]
    de_cur = delta_e_cie76(tgt_lab, pred_cur)
    de_new = delta_e_cie76(tgt_lab, pred_new)

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

    ok_slack = de_new <= (de_base_all[cand_idx] + slack)

    mix_base_slack = max(0.0, mix_base_slack_de76)
    if mix_base_slack > 0.0:
        ok_mix = de_mix_new <= (de_mix_base_all[cand_idx] + mix_base_slack)
    else:
        ok_mix = de_mix_new <= (de_mix_cur + mix_max_increase_de76)

    island_delta = np.zeros((cand_idx.size,), dtype=np.float32)

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
                borderType=cv2.BORDER_REFLECT,
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

    if hasattr(solver, "_solver"):
        cpp_solver = solver._solver
    else:
        raise TypeError("solver必须是HillClimbingSolverCpp实例或其子类")

    optimizer = ICMJointOptimizer(cpp_solver, n_slots, n_layers, h, w, config)
    z1 = n_layers if layer_end is None else layer_end

    result = optimizer.optimize(
        recipes,
        ys0,
        xs0,
        pix_rgb,
        I,
        roi,
        layer_start=int(layer_start),
        layer_end=int(z1),
    )

    logger.info("[信息] C++ ICM优化器执行完成")
    return np.asarray(result, dtype=np.int32)
