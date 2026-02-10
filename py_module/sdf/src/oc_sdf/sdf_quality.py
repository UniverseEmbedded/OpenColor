"""SDF 质量分析模块 - 生成层质量分析报告"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
from PIL import Image
from shapely.geometry import GeometryCollection
from shapely.ops import unary_union

from oc_core_02.core.bitmap_pipeline import BitmapParams
from oc_core_02.core.color_systems import ColorSystem
from .sdf_io import collect_polygons, save_svg, rasterize_geometry



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def generate_quality_report(
    params: BitmapParams,
    cs: ColorSystem,
    layer_clip_polys: List[Dict[str, Any]],
    layer_final_polys: List[Dict[str, Any]],
    volumes: Dict[str, np.ndarray],
    data: Dict[str, Any],
    debug_root: Path
):
    """生成层质量分析报告（间隙与重叠）"""
    match_h_px = data["match_h_px"]
    match_w_px = data["match_w_px"]
    px_per_mm = float(data["grid_scale"]) / float(params.nozzle_width_mm)
    height_mm = float(data["target_h_px"]) * float(params.nozzle_width_mm)
    width_mm = float(data["target_w_px"]) * float(params.nozzle_width_mm)

    for z in range(params.n_layers):
        clip_list = [layer_clip_polys[z][s] for s in cs.slot_names if s in layer_clip_polys[z]]
        final_list = [layer_final_polys[z][s] for s in cs.slot_names if s in layer_final_polys[z]]
        
        layer_dir = debug_root / f"layer_{z:04d}"
        layer_dir.mkdir(parents=True, exist_ok=True)
        
        clip_union = unary_union(clip_list) if clip_list else GeometryCollection()
        final_union = unary_union(final_list) if final_list else GeometryCollection()
        
        try:
            gap_geom = clip_union.difference(final_union)
        except Exception:
            gap_geom = clip_union.buffer(0).difference(final_union.buffer(0))

        clip_area = float(getattr(clip_union, "area", 0.0))
        final_area = float(getattr(final_union, "area", 0.0))
        gap_area = float(getattr(gap_geom, "area", 0.0))
        
        overlap_area = 0.0
        prev_union = GeometryCollection()
        overlap_geom = GeometryCollection()
        for g in final_list:
            for p in collect_polygons(g):
                if p.is_empty: continue
                try:
                    inter = p.intersection(prev_union)
                    overlap_area += float(inter.area)
                    try:
                        overlap_geom = overlap_geom.union(inter)
                    except Exception:
                        overlap_geom = overlap_geom.buffer(0).union(inter.buffer(0))
                    prev_union = prev_union.union(p)
                except Exception:
                    pp, pu = p.buffer(0), prev_union.buffer(0)
                    inter = pp.intersection(pu)
                    overlap_area += float(inter.area)
                    try:
                        overlap_geom = overlap_geom.union(inter)
                    except Exception:
                        overlap_geom = overlap_geom.buffer(0).union(inter.buffer(0))
                    prev_union = pu.union(pp)

        gap_ratio = gap_area / clip_area if clip_area > 0 else 0.0
        overlap_ratio = overlap_area / clip_area if clip_area > 0 else 0.0

        # 栅格化汇总（用于调试）
        ref_union_mask = np.zeros((match_h_px, match_w_px), dtype=bool)
        for slot_name in cs.slot_names:
            ref_union_mask |= volumes[slot_name][z]

        sum_mask = np.zeros((match_h_px, match_w_px), dtype=np.int32)
        for g in final_list:
            try:
                m = rasterize_geometry(g, match_w_px, match_h_px, height_mm, px_per_mm)
                if m is not None: sum_mask += m.astype(np.int32)
            except Exception: pass
        
        gap_pixels = int(np.count_nonzero(ref_union_mask & (sum_mask == 0)))
        overlap_pixels = int(np.count_nonzero(sum_mask > 1))

        report = {
            "layer_index": int(z),
            "clip_area": clip_area,
            "final_area": final_area,
            "gap_area": gap_area,
            "gap_ratio": gap_ratio,
            "overlap_area": float(overlap_area),
            "overlap_ratio": overlap_ratio,
            "gap_pixels": gap_pixels,
            "overlap_pixels": overlap_pixels,
        }
        try:
            (layer_dir / "layer_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"layer_report.json 写入失败(layer={z}): {e}")

        # 保存间隙/重叠可视化
        _save_quality_visuals(layer_dir, gap_geom, overlap_geom, gap_ratio, overlap_ratio, gap_pixels, overlap_pixels, ref_union_mask, sum_mask, width_mm, height_mm)


def _save_quality_visuals(layer_dir, gap_geom, overlap_geom, gap_ratio, overlap_ratio, gap_pixels, overlap_pixels, ref_union_mask, sum_mask, width_mm, height_mm):
    """保存质量分析的可视化文件"""
    gap_ratio_threshold = 0.001
    abs_area_threshold = 1e-6
    
    if gap_ratio > gap_ratio_threshold or gap_pixels > 0:
        try:
            if not gap_geom.is_empty:
                save_svg(gap_geom, layer_dir / "gap_geom.svg", width_mm, height_mm)
            gap_img = (ref_union_mask & (sum_mask == 0)).astype(np.uint8) * 255
            Image.fromarray(gap_img, mode="L").save(layer_dir / "gap_pixels.png")
        except Exception as e:
            logger.error(f"保存 gap 可视化失败: {e}")
            traceback.print_exc()

    if overlap_ratio > 0 or overlap_pixels > 0:
        try:
            if not overlap_geom.is_empty:
                save_svg(overlap_geom, layer_dir / "overlap_geom.svg", width_mm, height_mm)
            overlap_img = (sum_mask > 1).astype(np.uint8) * 255
            Image.fromarray(overlap_img, mode="L").save(layer_dir / "overlap_pixels.png")
        except Exception as e:
            logger.error(f"保存 overlap 可视化失败: {e}")
            traceback.print_exc()
