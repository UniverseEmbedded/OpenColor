"""联合优化模块 - 引导滤波和标签平滑

本模块提供引导滤波、标签平滑等功能
"""

import cv2
import numpy as np

from .joint_refinement_boundary import _boundary_length_4
from .joint_refinement_cleanup import _despeckle_single_pixels_4
from .main_utils import _guided_filter_gray



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
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
    despickle_iters: int = 1,
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

            change = roi & (labels >= 0) & confident & (best != labels)
            moved = int(np.count_nonzero(change))
            changed_soft_total += moved
            if moved <= 0:
                break
            labels[change] = best[change]
            moved_total += moved

        labels2, n_des = _despeckle_single_pixels_4(labels, roi, iters=int(despickle_iters), n_slots=n_slots)
        labels = labels2
        moved_total += int(n_des)

        per1 = _boundary_length_4(labels, roi)
        logger.info(f"[信息] L{z:02d} 引导滤波平滑完成: moved_px={moved_total}, soft_change_px={changed_soft_total}, "
            f"single_px_fixed={int(n_des)}, perim4_before={per0}, perim4_after={per1}, radius={r}, passes={p}, min_soft_margin={margin:.4f}"
        )
        out_layers.append(labels)

    return out_layers
