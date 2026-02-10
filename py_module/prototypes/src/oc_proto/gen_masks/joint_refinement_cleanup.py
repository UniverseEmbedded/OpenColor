"""联合优化模块 - 小连通域剔除和去噪

本模块提供小连通域剔除、单像素去噪等功能
"""

import cv2
import numpy as np


def _remove_small_components_replace_with_neighbors(
    lab: np.ndarray,
    roi: np.ndarray,
    *,
    n_slots: int,
    max_area_px: int,
    connectivity: int,
) -> tuple[np.ndarray, dict[str, int]]:
    """移除小连通域并用邻域颜色替换
    
    Args:
        lab: 标签图
        roi: 感兴趣区域
        n_slots: 颜色槽数量
        max_area_px: 最大面积阈值
        connectivity: 连通性 (4 或 8)
    
    Returns:
        处理后的标签图和统计信息
    """
    lab0 = np.asarray(lab)
    roi0 = np.asarray(roi, dtype=bool)
    if lab0.ndim != 2:
        raise ValueError(f"lab 形状异常: {lab0.shape}")
    if roi0.shape != lab0.shape:
        raise ValueError(f"roi 尺寸不一致: {roi0.shape} vs {lab0.shape}")
    if int(max_area_px) <= 0:
        return lab0.astype(lab0.dtype, copy=True), {"removed_components": 0, "removed_pixels": 0}
    conn = int(connectivity)
    if conn not in (4, 8):
        raise ValueError(f"connectivity 仅支持 4 或 8，当前: {connectivity}")
    ns = int(n_slots)
    if ns <= 1:
        return lab0.astype(lab0.dtype, copy=True), {"removed_components": 0, "removed_pixels": 0}

    out = lab0.astype(np.int32, copy=True)
    removed_components = 0
    removed_pixels = 0

    if conn == 4:
        kernel = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)
    else:
        kernel = np.ones((3, 3), dtype=np.uint8)

    h = int(out.shape[0])
    w = int(out.shape[1])
    pad = 2
    
    for s in range(ns):
        m = (roi0 & (out == int(s))).astype(np.uint8, copy=False)
        if not bool(np.any(m)):
            continue
        n, cc, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=conn)
        if int(n) <= 1:
            continue
        for cid in range(1, int(n)):
            area = int(stats[cid, cv2.CC_STAT_AREA])
            if area > int(max_area_px):
                continue

            x = int(stats[cid, cv2.CC_STAT_LEFT])
            y = int(stats[cid, cv2.CC_STAT_TOP])
            ww = int(stats[cid, cv2.CC_STAT_WIDTH])
            hh = int(stats[cid, cv2.CC_STAT_HEIGHT])
            if ww <= 0 or hh <= 0:
                continue

            y0 = max(0, y - pad)
            y1 = min(h, y + hh + pad)
            x0 = max(0, x - pad)
            x1 = min(w, x + ww + pad)

            cc_p = cc[y0:y1, x0:x1]
            comp = (cc_p == int(cid))
            if not bool(np.any(comp)):
                continue

            comp_u8 = comp.astype(np.uint8, copy=False)
            roi_p = roi0[y0:y1, x0:x1]
            out_p = out[y0:y1, x0:x1]

            dil1 = cv2.dilate(comp_u8, kernel, iterations=1).astype(bool)
            ring = dil1 & (~comp) & roi_p
            nb = out_p[ring]

            if nb.size <= 0:
                dil2 = cv2.dilate(comp_u8, kernel, iterations=2).astype(bool)
                ring2 = dil2 & (~dil1) & roi_p
                nb = out_p[ring2]

            if nb.size <= 0:
                continue

            nb = nb[(nb >= 0) & (nb < ns)]
            if nb.size <= 0:
                continue

            counts = np.bincount(nb.astype(np.int32, copy=False), minlength=ns)
            rep = int(np.argmax(counts))
            if rep == int(s):
                continue

            out_p[comp] = rep
            removed_components += 1
            removed_pixels += area

    return out.astype(lab0.dtype, copy=False), {"removed_components": int(removed_components), "removed_pixels": int(removed_pixels)}


def _despeckle_single_pixels_4(labels: np.ndarray, roi: np.ndarray, *, iters: int, n_slots: int) -> tuple[np.ndarray, int]:
    """去除单像素噪声"""
    lab0 = np.asarray(labels)
    r = np.asarray(roi, dtype=bool)
    h, w = int(lab0.shape[0]), int(lab0.shape[1])
    if h <= 2 or w <= 2:
        return lab0, 0
    out = lab0.copy()
    total = 0
    k = max(0, int(iters))
    if k <= 0:
        return out, 0

    for _ in range(k):
        center = out[1:-1, 1:-1]
        rr = r[1:-1, 1:-1] & r[:-2, 1:-1] & r[2:, 1:-1] & r[1:-1, :-2] & r[1:-1, 2:]
        if not bool(np.any(rr)):
            break

        up = out[:-2, 1:-1]
        dn = out[2:, 1:-1]
        lf = out[1:-1, :-2]
        rt = out[1:-1, 2:]
        iso = rr & (center >= 0) & (center != up) & (center != dn) & (center != lf) & (center != rt)
        n_iso = int(np.count_nonzero(iso))
        if n_iso <= 0:
            break

        neigh = np.stack([up, dn, lf, rt], axis=0).astype(np.int32)
        cand = neigh[:, iso]
        if cand.size <= 0:
            break

        ns = max(1, int(n_slots))
        counts = np.zeros((ns, int(cand.shape[1])), dtype=np.uint8)
        for t in range(4):
            v = cand[t]
            ok = (v >= 0) & (v < ns)
            if bool(np.any(ok)):
                counts[v[ok], np.nonzero(ok)[0]] += 1
        best = np.argmax(counts, axis=0).astype(np.int16)

        tmp = center.copy()
        tmp[iso] = best
        out[1:-1, 1:-1] = tmp
        total += n_iso

    return out, total