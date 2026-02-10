"""Reconcile模块 - 提供栅格域多边形对齐功能

用于将矢量化的多边形重新对齐到栅格域，解决多边形之间的重叠和间隙问题。
"""

import traceback

import numpy as np
from shapely.ops import unary_union

from oc_core_02.utils.logger import get_logger
from oc_core_02.utils.vtracer_bridge import vectorize_mask_to_mm_polys
from oc_sdf.geometry_utils import _to_polygonal

logger = get_logger(__name__)

def _reconcile_layer_polys_by_raster(
    *,
    layer_polys: dict,
    full_mask_poly,
    full_mask_bin_hi: np.ndarray,
    slot_names_no_bg: list[str],
    background_slot: str,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
    scale: int,
    grid_size: float,
    use_cpp: bool,
    progress: bool,
    tag: str,
    cv2_simplify_mm: float,
    cv2_min_area_px: int,
) -> dict:
    """通过栅格化对齐图层多边形
    
    将多边形栅格化到高分辨率图像，基于覆盖竞争确定每个像素的归属，
    然后重新矢量化，确保多边形之间无重叠、无间隙。
    
    参数:
        layer_polys: 层多边形字典 {槽位名: 多边形}
        full_mask_poly: 完整掩码多边形
        full_mask_bin_hi: 高分辨率完整掩码二值图
        slot_names_no_bg: 非背景槽位名称列表
        background_slot: 背景槽位名称
        board_mm: 板尺寸（毫米）
        pixel_w: 像素宽度
        pixel_h: 像素高度
        scale: 超采样倍数
        grid_size: 网格大小（毫米）
        use_cpp: 是否使用C++加速
        progress: 是否显示进度
        tag: 标签名称
        cv2_simplify_mm: OpenCV简化容差（毫米）
        cv2_min_area_px: OpenCV最小面积阈值（像素）
        
    返回:
        对齐后的层多边形字典
    """
    # 参数校验
    if full_mask_poly is None or getattr(full_mask_poly, "is_empty", True):
        return layer_polys
    if full_mask_bin_hi is None or int(full_mask_bin_hi.size) == 0:
        return layer_polys
    if not slot_names_no_bg:
        return layer_polys
    if not background_slot:
        return layer_polys

    # 计算高分辨率尺寸
    s = int(scale) if scale is not None else 4
    if s < 1:
        s = 1

    h_hi = int(pixel_h) * s
    w_hi = int(pixel_w) * s
    if int(full_mask_bin_hi.shape[0]) != h_hi or int(full_mask_bin_hi.shape[1]) != w_hi:
        logger.warning(f"[警告] reconcile 参考 full_mask 尺寸不一致，已跳过: got={full_mask_bin_hi.shape}, expect=({h_hi},{w_hi})")
        return layer_polys

    px_per_mm_hi = float(w_hi) / float(board_mm)

    # 栅格化每个槽位的多边形
    coverages = []
    for slot_name in slot_names_no_bg:
        poly = layer_polys.get(slot_name)
        if poly is None or getattr(poly, "is_empty", True):
            coverages.append(np.zeros((h_hi, w_hi), dtype=np.float32))
            continue
        from oc_sdf.sdf_io import rasterize_geometry_soft
        m = rasterize_geometry_soft(poly, w_hi, h_hi, float(board_mm), float(px_per_mm_hi), supersample=1)
        if m is None:
            coverages.append(np.zeros((h_hi, w_hi), dtype=np.float32))
        else:
            coverages.append(np.asarray(m, dtype=np.float32))

    # 基于覆盖竞争确定像素归属
    stack = np.stack(coverages, axis=0)
    maxv = stack.max(axis=0)
    arg = stack.argmax(axis=0).astype(np.int16)

    # 只在掩码内部进行标签分配
    labels = np.full((h_hi, w_hi), -1, dtype=np.int16)
    inside = np.asarray(full_mask_bin_hi, dtype=bool)
    labels[inside] = np.where(maxv[inside] > 0.0, arg[inside], -1)

    # 重新矢量化每个槽位
    out = {}
    min_area_hi = int(cv2_min_area_px) * (s * s)
    for idx, slot_name in enumerate(slot_names_no_bg):
        mu8 = np.zeros((h_hi, w_hi), dtype=np.uint8)
        mu8[(labels == int(idx))] = np.uint8(255)
        if int(np.count_nonzero(mu8)) < 2:
            continue
        polys = vectorize_mask_to_mm_polys(
            mu8,
            backend="cv2",
            vtracer_params=None,
            cv2_simplify_mm=float(cv2_simplify_mm),
            cv2_min_area_px=int(min_area_hi),
            board_mm=float(board_mm),
            pixel_w=int(w_hi),
            pixel_h=int(h_hi),
            debug_dir=None,
            slot_name=f"{tag}_reconcile_{slot_name}",
            use_cpp=use_cpp,
            progress=progress,
        )
        if not polys:
            continue
        g = unary_union(polys)
        if getattr(g, "is_empty", True):
            continue
        if not getattr(g, "is_valid", True):
            g = g.buffer(0)
        if not getattr(g, "is_empty", True):
            out[slot_name] = g

    # 计算背景区域
    if out:
        try:
            occ = unary_union(list(out.values()))
            if not getattr(occ, "is_valid", True):
                occ = occ.buffer(0)
            bg = _to_polygonal(full_mask_poly.difference(occ))
            if (not getattr(bg, "is_empty", True)) and (not getattr(bg, "is_valid", True)):
                bg = bg.buffer(0)
            if not getattr(bg, "is_empty", True):
                out[background_slot] = bg
        except Exception as e:
            logger.error(f"[警告] reconcile 计算背景失败: {tag}，原因={e}")
            traceback.print_exc()
            out[background_slot] = _to_polygonal(full_mask_poly)
    else:
        out[background_slot] = _to_polygonal(full_mask_poly)

    # 确保多边形之间互斥（无重叠）
    from .exclusive_clipper import _make_layer_exclusive
    ordered = list(slot_names_no_bg) + [background_slot]
    out = _make_layer_exclusive(out, ordered, float(grid_size), use_cpp=use_cpp, progress=progress, tag=f"{tag}_reconcile")
    return out
