"""岛屿抑制模块

提供标签平滑、小色块抑制、空洞填充等功能。
"""

from __future__ import annotations

import traceback

import cv2
import numpy as np

from .joint_refinement_boundary import _boundary_length_4
from .joint_refinement_cleanup import _despeckle_single_pixels_4
from .main_utils import _guided_filter_gray



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def smooth_labels_by_convolution(
    labels_by_layer: list[np.ndarray],
    *,
    full_mask: np.ndarray,
    slot_names: list[str],
    kernel_size: int,
    passes: int,
    skip_first_layer: bool,
    min_majority_frac: float = 0.52,
    min_vote_margin: int = 2,
) -> list[np.ndarray]:
    """使用卷积平滑标签"""
    k = int(kernel_size)
    if k <= 1:
        return labels_by_layer
    if k % 2 == 0:
        k += 1
        logger.warning(f"[警告] kernel_size 必须是奇数，已调整为 {k}")
    p = max(1, int(passes))
    n_slots = int(len(slot_names))
    roi = np.asarray(full_mask, dtype=bool)
    total_votes = int(k * k)
    maj_frac = float(min_majority_frac)
    if not (0.0 < maj_frac <= 1.0):
        logger.warning(f"[警告] min_majority_frac 参数非法: {min_majority_frac}，将使用 0.52")
        maj_frac = 0.52
    min_maj_votes = int(np.ceil(total_votes * maj_frac - 1e-9))
    margin = max(1, int(min_vote_margin))

    out_layers: list[np.ndarray] = []
    for z, labels0 in enumerate(labels_by_layer):
        labels = np.asarray(labels0, dtype=np.int16).copy()
        labels[~roi] = -1
        if bool(skip_first_layer) and int(z) == 0:
            out_layers.append(labels)
            continue

        per0 = _boundary_length_4(labels, roi)
        moved_total = 0
        for _ in range(p):
            counts = []
            for s in range(n_slots):
                m = (labels == np.int16(s)).astype(np.float32)
                c = cv2.boxFilter(m, ddepth=-1, ksize=(k, k), normalize=False)
                counts.append(c)
            counts_stack = np.stack(counts, axis=0)
            best = np.argmax(counts_stack, axis=0).astype(np.int16)
            best_count = np.max(counts_stack, axis=0)

            cur_count = np.zeros_like(best_count, dtype=best_count.dtype)
            for s in range(n_slots):
                ms = labels == np.int16(s)
                if bool(np.any(ms)):
                    cur_count[ms] = counts_stack[s][ms]

            can_change = (
                roi
                & (labels >= 0)
                & (best != labels)
                & (best_count >= float(min_maj_votes))
                & ((best_count - cur_count) >= float(margin))
            )
            change = can_change
            moved = int(np.count_nonzero(change))
            if moved <= 0:
                break
            labels[change] = best[change]
            moved_total += moved

        per1 = _boundary_length_4(labels, roi)
        logger.info(f"[信息] L{z:02d} 卷积平滑完成: moved_px={moved_total}, perim4_before={per0}, perim4_after={per1}, "
            f"kernel={k}, passes={p}, min_majority_votes={min_maj_votes}/{total_votes}, min_vote_margin={margin}"
        )
        out_layers.append(labels)

    return out_layers


def smooth_labels_by_guided_filter(
    labels_by_layer: list[np.ndarray],
    *,
    full_mask: np.ndarray,
    slot_names: list[str],
    guidance_gray01: np.ndarray,
    radius: int,
    eps: float,
    passes: int,
    skip_first_layer: bool,
    min_soft_margin: float = 0.02,
    despeckle_iters: int = 1,
    edge_aware: bool = True,
    edge_threshold: float = 0.22,
) -> list[np.ndarray]:
    """使用引导滤波平滑标签"""
    r = int(radius)
    if r <= 0:
        return labels_by_layer
    p = max(1, int(passes))
    n_slots = int(len(slot_names))
    if n_slots <= 1:
        return labels_by_layer
    roi = np.asarray(full_mask, dtype=bool)
    I = np.asarray(guidance_gray01, dtype=np.float32)
    if I.shape[:2] != roi.shape[:2]:
        raise ValueError(f"guidance_gray01 尺寸不一致: {I.shape} vs {roi.shape}")

    use_edge = bool(edge_aware)
    thr = float(edge_threshold)
    if not (0.0 <= thr <= 1.0):
        logger.warning(f"[警告] edge_threshold 参数非法: {edge_threshold}，将使用 0.22")
        thr = 0.22
    if use_edge:
        sobel_x = cv2.Sobel(I, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(I, cv2.CV_32F, 0, 1, ksize=3)
        edge_strength = np.sqrt(sobel_x * sobel_x + sobel_y * sobel_y)
        emax = float(np.max(edge_strength))
        if emax > 0.0:
            edge_strength = edge_strength / emax
    else:
        edge_strength = None

    margin = max(0.0, float(min_soft_margin))
    out_layers: list[np.ndarray] = []
    
    for z, labels0 in enumerate(labels_by_layer):
        labels = np.asarray(labels0, dtype=np.int16).copy()
        labels[~roi] = -1
        if bool(skip_first_layer) and int(z) == 0:
            out_layers.append(labels)
            continue

        per0 = _boundary_length_4(labels, roi)
        moved_total = 0
        changed_soft_total = 0
        
        for _ in range(p):
            soft = []
            for s in range(n_slots):
                m = (labels == np.int16(s)).astype(np.float32)
                q = _guided_filter_gray(I, m, r, float(eps))
                soft.append(q)
            soft_stack = np.stack(soft, axis=0)
            best = np.argmax(soft_stack, axis=0).astype(np.int16)

            part = np.partition(soft_stack, -2, axis=0)
            top2 = part[-2]
            top1 = part[-1]
            confident = (top1 - top2) >= margin

            if edge_strength is not None:
                can_smooth = edge_strength <= thr
                change = roi & can_smooth & (labels >= 0) & confident & (best != labels)
            else:
                change = roi & (labels >= 0) & confident & (best != labels)
            moved = int(np.count_nonzero(change))
            changed_soft_total += moved
            if moved <= 0:
                break
            labels[change] = best[change]
            moved_total += moved

        labels2, n_des = _despeckle_single_pixels_4(labels, roi, iters=int(despeckle_iters), n_slots=n_slots)
        labels = labels2
        moved_total += int(n_des)

        per1 = _boundary_length_4(labels, roi)
        logger.info(f"[信息] L{z:02d} 引导滤波平滑完成: moved_px={moved_total}, soft_change_px={changed_soft_total}, "
            f"single_px_fixed={int(n_des)}, perim4_before={per0}, perim4_after={per1}, radius={r}, passes={p}, "
            f"min_soft_margin={margin:.4f}"
        )
        out_layers.append(labels)

    return out_layers


def volumes_to_labels(volumes: dict, cs, full_mask: np.ndarray, n_layers: int) -> list[np.ndarray]:
    """将体积数据转换为标签图
    
    Args:
        volumes: 体积数据字典 {slot_name: (n_layers, h, w) bool}
        cs: ColorSystem 颜色系统
        full_mask: 完整掩码
        n_layers: 层数
    
    Returns:
        每层标签图列表
    """
    h, w = int(full_mask.shape[0]), int(full_mask.shape[1])
    labels_by_layer: list[np.ndarray] = []
    for z in range(int(n_layers)):
        labels = np.full((h, w), -1, dtype=np.int16)
        count = np.zeros((h, w), dtype=np.uint8)
        for s, slot_name in enumerate(cs.slot_names):
            m = volumes.get(slot_name)
            if m is None:
                continue
            mm = np.asarray(m[z], dtype=bool)
            count += mm.astype(np.uint8)
            labels[mm] = np.int16(s)

        roi = np.asarray(full_mask, dtype=bool)
        overlap = int(np.count_nonzero(roi & (count > 1)))
        gap = int(np.count_nonzero(roi & (count == 0)))
        if overlap > 0 or gap > 0:
            logger.warning(f"[警告] L{z:02d} 位图分区存在问题: overlap_px={overlap}, gap_px={gap}")
        labels_by_layer.append(labels)
    return labels_by_layer


def labels_to_volumes(labels_by_layer: list[np.ndarray], cs, n_layers: int) -> dict[str, np.ndarray]:
    """将标签图转换为体积数据
    
    Args:
        labels_by_layer: 每层标签图列表
        cs: ColorSystem 颜色系统
        n_layers: 层数
    
    Returns:
        体积数据字典 {slot_name: (n_layers, h, w) bool}
    """
    if not labels_by_layer:
        return {name: np.zeros((int(n_layers), 1, 1), dtype=bool) for name in cs.slot_names}
    h, w = int(labels_by_layer[0].shape[0]), int(labels_by_layer[0].shape[1])
    out: dict[str, np.ndarray] = {name: np.zeros((int(n_layers), h, w), dtype=bool) for name in cs.slot_names}
    for z in range(int(n_layers)):
        lab = labels_by_layer[z]
        for s, slot_name in enumerate(cs.slot_names):
            out[slot_name][z] = (lab == int(s))
    return out


def _pick_neighbor_label(labels: np.ndarray, comp_mask_u8: np.ndarray, *, n_slots: int) -> int | None:
    """选择邻居标签（用于小洞填充和小色块替换）"""
    k = np.ones((3, 3), dtype=np.uint8)
    dil = cv2.dilate(comp_mask_u8, k, iterations=1)
    border = (dil > 0) & (comp_mask_u8 == 0)
    if not bool(np.any(border)):
        return None
    neigh = labels[border]
    neigh = neigh[(neigh >= 0) & (neigh < int(n_slots))]
    if neigh.size <= 0:
        return None
    counts = np.bincount(neigh.astype(np.int32), minlength=int(n_slots))
    best = int(np.argmax(counts))
    if int(counts[best]) <= 0:
        return None
    return best


def suppress_small_islands(
    labels_by_layer: list[np.ndarray],
    *,
    full_mask: np.ndarray,
    slot_names: list[str],
    min_island_area_px: int,
    max_gap_area_px: int,
    connectivity: int,
    passes: int,
) -> list[np.ndarray]:
    """抑制小岛屿（小色块）和填充小空洞
    
    Args:
        labels_by_layer: 每层标签图列表
        full_mask: 完整掩码
        slot_names: 颜色槽名称列表
        min_island_area_px: 最小岛屿面积（小于此面积的岛屿将被替换）
        max_gap_area_px: 最大空洞面积（小于此面积的空洞将被填充）
        connectivity: 连通性 (4 或 8)
        passes: 迭代次数
    
    Returns:
        处理后的标签图列表
    """
    if int(min_island_area_px) <= 0 and int(max_gap_area_px) <= 0:
        return labels_by_layer
    n_slots = int(len(slot_names))
    conn = int(connectivity)
    if conn not in (4, 8):
        logger.warning(f"[警告] 连通性参数非法: {connectivity}，将使用 8")
        conn = 8
    roi = np.asarray(full_mask, dtype=bool)

    out_layers: list[np.ndarray] = []
    for z, labels0 in enumerate(labels_by_layer):
        labels = np.asarray(labels0, dtype=np.int16).copy()
        labels[~roi] = -1
        total_moved = 0
        total_components = 0
        total_removed = 0
        total_gap_filled = 0

        for _p in range(max(1, int(passes))):
            moved_pass = 0
            removed_pass = 0
            components_pass = 0

            # 小洞填充
            if int(max_gap_area_px) > 0:
                gap_mask = (roi & (labels < 0)).astype(np.uint8)
                if int(np.count_nonzero(gap_mask)) > 0:
                    try:
                        num_g, cc_g, stats_g, _ = cv2.connectedComponentsWithStats(gap_mask, connectivity=conn)
                        for cid in range(1, int(num_g)):
                            area = int(stats_g[cid, cv2.CC_STAT_AREA])
                            if area > int(max_gap_area_px):
                                continue
                            comp = (cc_g == cid)
                            if not bool(np.any(comp)):
                                continue
                            nb = _pick_neighbor_label(labels, comp.astype(np.uint8), n_slots=n_slots)
                            if nb is None:
                                continue
                            labels[comp] = np.int16(nb)
                            total_gap_filled += int(area)
                    except Exception as e:
                        logger.error(f"[错误] L{z:02d} 小洞填充失败: {e}")
                        traceback.print_exc()

            # 小色块剔除
            if int(min_island_area_px) > 0:
                for s in range(n_slots):
                    mask = (labels == np.int16(s)).astype(np.uint8)
                    if int(np.count_nonzero(mask)) <= 0:
                        continue
                    try:
                        num, cc, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=conn)
                    except Exception as e:
                        logger.error(f"[错误] 连通域分析失败: L{z:02d} slot={slot_names[s]}，原因={e}")
                        traceback.print_exc()
                        continue
                    if int(num) <= 1:
                        continue
                    components_pass += int(num) - 1

                    for cid in range(1, int(num)):
                        area = int(stats[cid, cv2.CC_STAT_AREA])
                        if area >= int(min_island_area_px):
                            continue
                        comp = (cc == cid)
                        if not bool(np.any(comp)):
                            continue
                        nb = _pick_neighbor_label(labels, comp.astype(np.uint8), n_slots=n_slots)
                        if nb is None:
                            continue
                        labels[comp] = np.int16(nb)
                        moved_pass += int(area)
                        removed_pass += 1

            if moved_pass <= 0:
                break
            total_moved += moved_pass
            total_removed += removed_pass
            total_components += components_pass

        if total_moved > 0 or total_gap_filled > 0:
            logger.info(f"[信息] L{z:02d} 小块剔除完成: moved_px={total_moved}, filled_gap_px={total_gap_filled}, "
                f"removed_cc={total_removed}, scanned_cc={total_components}, min_area_px={int(min_island_area_px)}, "
                f"max_gap_px={int(max_gap_area_px)}, passes={int(passes)}"
            )

        out_layers.append(labels)

    return out_layers
