"""联合优化模块 - 边界计算和连通域分析

本模块提供边界长度计算、连通域分析等功能
"""

import cv2
import numpy as np


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _boundary_length_4(labels: np.ndarray, roi: np.ndarray) -> int:
    """计算4连通边线长度"""
    lab = np.asarray(labels)
    r = np.asarray(roi, dtype=bool)
    h, w = int(lab.shape[0]), int(lab.shape[1])
    if h <= 1 or w <= 1:
        return 0
    e1 = (lab[:, 1:] != lab[:, :-1]) & r[:, 1:] & r[:, :-1]
    e2 = (lab[1:, :] != lab[:-1, :]) & r[1:, :] & r[:-1, :]
    return int(np.count_nonzero(e1) + np.count_nonzero(e2))


def _perimeter_by_slot_4(
    labels: np.ndarray, roi: np.ndarray, *, n_slots: int
) -> np.ndarray:
    """计算每个色块的周长"""
    lab = np.asarray(labels)
    r = np.asarray(roi, dtype=bool)
    h, w = int(lab.shape[0]), int(lab.shape[1])
    out = np.zeros((max(0, int(n_slots)),), dtype=np.int64)
    if h <= 0 or w <= 0 or int(n_slots) <= 0:
        return out

    for s in range(int(n_slots)):
        m = (lab == int(s)) & r
        if not bool(np.any(m)):
            continue

        e1_in = (
            r[:, 1:] & r[:, :-1] & ((lab[:, 1:] == int(s)) ^ (lab[:, :-1] == int(s)))
        )
        e2_in = (
            r[1:, :] & r[:-1, :] & ((lab[1:, :] == int(s)) ^ (lab[:-1, :] == int(s)))
        )

        e1_out = (r[:, 1:] ^ r[:, :-1]) & (
            (lab[:, 1:] == int(s)) & r[:, 1:] | (lab[:, :-1] == int(s)) & r[:, :-1]
        )
        e2_out = (r[1:, :] ^ r[:-1, :]) & (
            (lab[1:, :] == int(s)) & r[1:, :] | (lab[:-1, :] == int(s)) & r[:-1, :]
        )

        border = 0
        border += int(np.count_nonzero(m[0, :]))
        border += int(np.count_nonzero(m[-1, :]))
        border += int(np.count_nonzero(m[:, 0]))
        border += int(np.count_nonzero(m[:, -1]))

        out[int(s)] = int(
            np.count_nonzero(e1_in)
            + np.count_nonzero(e2_in)
            + np.count_nonzero(e1_out)
            + np.count_nonzero(e2_out)
            + border
        )

    return out


def _boundary_mask_4(labels: np.ndarray, roi2: np.ndarray) -> np.ndarray:
    """计算边界掩码"""
    lab = np.asarray(labels)
    r2 = np.asarray(roi2, dtype=bool)
    out = np.zeros_like(r2, dtype=bool)
    if int(r2.shape[0]) <= 0 or int(r2.shape[1]) <= 0:
        return out
    out[:, 1:] |= (lab[:, 1:] != lab[:, :-1]) & r2[:, 1:] & r2[:, :-1]
    out[:, :-1] |= (lab[:, 1:] != lab[:, :-1]) & r2[:, 1:] & r2[:, :-1]
    out[1:, :] |= (lab[1:, :] != lab[:-1, :]) & r2[1:, :] & r2[:-1, :]
    out[:-1, :] |= (lab[1:, :] != lab[:-1, :]) & r2[1:, :] & r2[:-1, :]
    return out


def _island_score_of_area(area: np.ndarray, *, alpha: float) -> np.ndarray:
    """计算小色块分数（面积越小分数越高）"""
    a = np.asarray(area, dtype=np.float32)
    aa = np.maximum(a, 0.0)
    al = float(alpha)
    if al <= 0.0:
        return (aa > 0.0).astype(np.float32)
    return (aa > 0.0).astype(np.float32) / np.maximum(aa**al, 1e-12)


def _build_components_by_label_4(
    labels: np.ndarray,
    roi2: np.ndarray,
    *,
    n_slots: int,
    alpha: float,
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
    lab = np.asarray(labels, dtype=np.int16)
    roi = np.asarray(roi2, dtype=bool)
    h, w = int(roi.shape[0]), int(roi.shape[1])
    comp_id = np.full((h, w), -1, dtype=np.int32)
    sizes: list[np.ndarray] = []
    scores: list[np.ndarray] = []
    area_bins = np.zeros((8,), dtype=np.int64)

    offset = 0
    for s in range(int(n_slots)):
        m = (roi & (lab == int(s))).astype(np.uint8)
        if not bool(np.any(m)):
            continue
        n, cc, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        if int(n) <= 1:
            continue
        area = stats[1:, cv2.CC_STAT_AREA].astype(np.int32, copy=False)
        sc = _island_score_of_area(area, alpha=float(alpha)).astype(
            np.float32, copy=False
        )
        sizes.append(area.astype(np.int32, copy=False))
        scores.append(sc)

        if bool(with_bins):
            for a in area.tolist():
                aa = int(a)
                if aa <= 1:
                    area_bins[0] += 1
                elif aa <= 2:
                    area_bins[1] += 1
                elif aa <= 3:
                    area_bins[2] += 1
                elif aa <= 4:
                    area_bins[3] += 1
                elif aa <= 8:
                    area_bins[4] += 1
                elif aa <= 16:
                    area_bins[5] += 1
                elif aa <= 32:
                    area_bins[6] += 1
                else:
                    area_bins[7] += 1
        cc2 = cc.astype(np.int32, copy=False)
        inside = cc2 > 0
        if bool(np.any(inside)):
            comp_id[inside] = (offset + (cc2[inside] - 1)).astype(np.int32, copy=False)
        offset += int(n) - 1

    if offset <= 0:
        comp_sizes = np.zeros((0,), dtype=np.int32)
        comp_scores = np.zeros((0,), dtype=np.float32)
        total = 0.0
        return comp_id, comp_sizes, comp_scores, float(total), area_bins

    comp_sizes = np.concatenate(sizes, axis=0).astype(np.int32, copy=False)
    comp_scores = np.concatenate(scores, axis=0).astype(np.float32, copy=False)
    total = float(np.sum(comp_scores))
    return comp_id, comp_sizes, comp_scores, float(total), area_bins


def _print_island_stats(
    *,
    layer_tag: str,
    area_bins: np.ndarray,
    total_score: float,
    alpha: float,
) -> None:
    """打印小色块统计信息"""
    b = np.asarray(area_bins, dtype=np.int64).reshape(-1)
    total_cnt = int(np.sum(b))
    logger.info(
        f"[信息] {layer_tag} 小色块统计: 总色块数={total_cnt}, "
        f"<=1={int(b[0])},<=2={int(b[1])},<=3={int(b[2])},<=4={int(b[3])},<=8={int(b[4])},<=16={int(b[5])},<=32={int(b[6])},>32={int(b[7])}, "
        f"加权分数(alpha={float(alpha):.3f})={float(total_score):.6f}"
    )
