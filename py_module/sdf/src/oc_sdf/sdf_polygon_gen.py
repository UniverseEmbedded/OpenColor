"""SDF多边形生成模块 - 提供层多边形生成功能"""

from pathlib import Path
from typing import Any, Tuple

import numpy as np
from PIL import Image
from shapely.ops import unary_union

from oc_core_02.core.bitmap_pipeline import BitmapParams
from .sdf_io import save_svg, rasterize_geometry
from .sdf_types import SDFParams
from .sdf_utils import (
    geom_is_empty,
    filter_small_polys,
    prepare_polygon_mask,
    mask_to_rings,
    rings_to_polys,
    build_clip_poly,
)



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def generate_slot_layer_polygon(
    z: int,
    slot_name: str,
    layer_mask: np.ndarray,
    grid_scale: int,
    match_h_px: int,
    match_w_px: int,
    params: BitmapParams,
    sdf_params: SDFParams,
    layer_occupied: Any,
    out_dir: Path
) -> Tuple[Any, Any, str | None]:
    """为特定层和 slot 生成最终多边形和裁剪多边形
    
    Args:
        z: 层索引
        slot_name: 槽位名称
        layer_mask: 层掩码
        grid_scale: 网格缩放
        match_h_px: 匹配高度(像素)
        match_w_px: 匹配宽度(像素)
        params: 位图参数
        sdf_params: SDF参数
        layer_occupied: 已占用区域
        out_dir: 输出目录
        
    Returns:
        (最终多边形, 裁剪多边形, 使用的后端)
    """
    mask_dir = out_dir / "02_masks"
    vtracer_dir = out_dir / "03_vtracer"
    poly_dir = out_dir / "04_polys"
    
    prefix = f"L{z:02d}_{slot_name}"
    
    pad_px = max(2, int(round(grid_scale / 2)))
    blur_radius = 0.6 if grid_scale >= 2 else 0.0
    px_per_mm = float(grid_scale) / float(params.nozzle_width_mm)
    width_mm = float(match_w_px / grid_scale) * float(params.nozzle_width_mm)
    height_mm = float(match_h_px / grid_scale) * float(params.nozzle_width_mm)

    try:
        raw_mask = (layer_mask.astype(np.uint8) * 255)
        Image.fromarray(raw_mask, mode="L").save(mask_dir / f"{prefix}_mask_raw.png")
    except Exception as e:
        logger.error(f"mask_raw 保存失败(layer={z}, slot={slot_name}): {e}")

    contour_backend = getattr(sdf_params, "contour_backend", "auto")
    clip_poly = build_clip_poly(layer_mask, grid_scale, match_h_px, params.nozzle_width_mm, pad_px, True)
    
    layer_mask_hi, pad_hi = prepare_polygon_mask(
        layer_mask,
        grid_scale,
        pad_px,
        blur_radius,
        True,
        keep_float=False
    )
    
    rings, used_backend = mask_to_rings(
        layer_mask_hi,
        backend=contour_backend,
        smooth_sigma=float(sdf_params.smooth_sigma),
        simplify_eps=float(sdf_params.simplify_eps),
        min_area=int(sdf_params.min_area),
        min_hole_area=int(sdf_params.min_hole_area),
        open_radius=int(sdf_params.open_radius) * grid_scale,
        close_radius=int(sdf_params.close_radius) * grid_scale,
        vtracer_mode=getattr(sdf_params, "vtracer_mode", "polygon"),
        vtracer_filter_speckle=int(getattr(sdf_params, "vtracer_filter_speckle", 4)) * max(1, grid_scale*grid_scale//4),
        vtracer_segment_length=int(getattr(sdf_params, "vtracer_segment_length", 4)),
        vtracer_corner_threshold=int(getattr(sdf_params, "vtracer_corner_threshold", 60)),
        debug_dir=vtracer_dir,
        slot_name=prefix
    )
    
    if not rings:
        return None, clip_poly, used_backend
        
    temp_polys = rings_to_polys(rings, match_h_px, grid_scale, params.nozzle_width_mm, pad_hi)
    if not temp_polys:
        return None, clip_poly, used_backend

    temp_polys.sort(key=lambda p: p.area, reverse=True)
    outers = []
    holes = []
    
    for p in temp_polys:
        is_hole = False
        for out_p in outers:
            if out_p.contains(p):
                already_in_hole = False
                for hp in holes:
                    if hp.contains(p):
                        already_in_hole = True
                        break
                if not already_in_hole:
                    holes.append(p)
                    is_hole = True
                    break
        if not is_hole:
            outers.append(p)

    slot_layer_poly = unary_union(outers).difference(unary_union(holes))
    if slot_layer_poly.is_empty:
        slot_layer_poly = unary_union(temp_polys)

    if slot_layer_poly.is_empty:
        return None, clip_poly, used_backend

    # 平滑与裁剪
    smooth_mm = max(0.01, float(params.nozzle_width_mm) * 0.15)
    try:
        slot_layer_poly = slot_layer_poly.buffer(smooth_mm).buffer(-smooth_mm)
    except Exception as e:
        logger.error(f"多边形平滑失败(layer={z}, slot={slot_name}): {e}")

    if sdf_params.enable_clip_intersection and clip_poly is not None and not clip_poly.is_empty:
        # 保存 clip_geom.svg 以供调试
        try:
            from .sdf_io import save_svg as io_save_svg
            gap_dir = out_dir / "05_gap"
            gap_dir.mkdir(parents=True, exist_ok=True)
            io_save_svg(clip_poly, gap_dir / f"{prefix}_clip_geom.svg", width_mm, height_mm)
        except Exception as e:
            logger.error(f"clip_geom.svg 保存失败: {e}")

        try:
            slot_layer_poly = slot_layer_poly.intersection(clip_poly)
        except Exception:
            slot_layer_poly = slot_layer_poly.buffer(0).intersection(clip_poly.buffer(0))

    if slot_layer_poly.is_empty:
        return None, clip_poly, used_backend

    # 填充缝隙
    if sdf_params.enable_gap_filling and sdf_params.fill_gap_mm and sdf_params.fill_gap_mm > 0:
        try:
            slot_layer_poly = slot_layer_poly.buffer(float(sdf_params.fill_gap_mm))
            if clip_poly is not None and not clip_poly.is_empty:
                slot_layer_poly = slot_layer_poly.intersection(clip_poly)
        except Exception:
            pass

    # 互斥裁剪
    if sdf_params.enable_mutual_exclusion and not geom_is_empty(layer_occupied):
        try:
            slot_layer_poly = slot_layer_poly.difference(layer_occupied)
        except Exception:
            slot_layer_poly = slot_layer_poly.buffer(0).difference(layer_occupied.buffer(0))

    if slot_layer_poly.is_empty:
        return None, clip_poly, used_backend

    # 过滤过小碎片
    min_piece_area_mm2 = (params.nozzle_width_mm ** 2) * 0.25
    slot_layer_poly = filter_small_polys(slot_layer_poly, min_piece_area_mm2)
    
    if not geom_is_empty(slot_layer_poly):
        try:
            save_svg(slot_layer_poly, poly_dir / f"{prefix}_poly_final.svg", width_mm, height_mm)
            poly_mask = rasterize_geometry(slot_layer_poly, match_w_px, match_h_px, height_mm, px_per_mm)
            if poly_mask is not None:
                Image.fromarray(poly_mask.astype(np.uint8) * 255, mode="L").save(poly_dir / f"{prefix}_poly_raster.png")
        except Exception as e:
            logger.error(f"中间结果保存失败(layer={z}, slot={slot_name}): {e}")

    return slot_layer_poly, clip_poly, used_backend
