"""互斥裁剪模块 - 提供图层互斥裁剪功能"""

import traceback
from time import perf_counter

import numpy as np
from shapely.errors import GEOSException
from shapely.geometry import Polygon, MultiPolygon

from oc_core_02.utils.bin_loader import import_cpp_extension
from oc_core_02.utils.logger import get_logger
from oc_sdf.geometry_utils import _to_polygonal

logger = get_logger(__name__)

# 尝试导入C++模块
cpp_geometry = None
try:
    cpp_geometry = import_cpp_extension("opencolor_geometry")
except Exception as e:
    logger.error("导入 C++几何模块失败: {}", e)


def _geom_to_loops(geom):
    """将几何体转换为环列表"""
    if geom is None:
        return []
    if getattr(geom, "is_empty", True):
        return []

    out = []
    gt = getattr(geom, "geom_type", "")
    if gt == "Polygon":
        out.append(np.asarray(geom.exterior.coords, dtype=np.float64))
        for ring in geom.interiors:
            out.append(np.asarray(ring.coords, dtype=np.float64))
        return out
    if gt == "MultiPolygon":
        for p in geom.geoms:
            if p.is_empty:
                continue
            out.append(np.asarray(p.exterior.coords, dtype=np.float64))
            for ring in p.interiors:
                out.append(np.asarray(ring.coords, dtype=np.float64))
        return out
    if gt == "GeometryCollection":
        for g in geom.geoms:
            out.extend(_geom_to_loops(g))
        return out
    return []


def _loops_to_evenodd_polygon(loops):
    """将环列表转换为奇偶填充多边形"""
    rings = []
    for pts in loops or []:
        if pts is None:
            continue
        arr = np.asarray(pts, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[0] < 3 or arr.shape[1] != 2:
            continue
        p = Polygon(arr)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty:
            continue
        if p.geom_type == "Polygon":
            rings.append(p)
        else:
            rings.extend(
                [g for g in p.geoms if g.geom_type == "Polygon" and g.area > 1e-9]
            )

    if not rings:
        return Polygon()

    result = rings[0]
    for r in rings[1:]:
        result = result.symmetric_difference(r)
    return result


_CPP_EXCLUSIVE_AVG_SEC_PER_SLOT: float | None = None


def _make_layer_exclusive(
    layer_polys: dict,
    ordered_slots: list,
    grid_size: float,
    *,
    use_cpp: bool,
    progress: bool,
    tag: str,
) -> dict:
    """使图层多边形互斥（不重叠）"""

    def _python_impl() -> dict:
        layer_occupied = None
        out = {}
        t0 = perf_counter()

        try:
            from tqdm import tqdm
        except Exception:
            tqdm = None

        def _tqdm(it, *, total=None, desc="", enabled=True):
            if (not enabled) or (tqdm is None):
                return it
            return tqdm(it, total=total, desc=desc, dynamic_ncols=True)

        it = _tqdm(
            ordered_slots,
            total=len(ordered_slots),
            desc=f"{tag} 互斥裁剪(Python)",
            enabled=progress,
        )
        for slot_name in it:
            if slot_name not in layer_polys:
                continue
            p = _to_polygonal(layer_polys[slot_name])
            if layer_occupied is not None:
                occ = _to_polygonal(layer_occupied)
                try:
                    p = _to_polygonal(p.difference(occ, grid_size=grid_size))
                except GEOSException as e:
                    logger.error(
                        f"  [警告] 互斥裁剪(difference)启用grid_size失败，已回退到普通差集。slot={slot_name}，原因={e}"
                    )
                    p = _to_polygonal(p.difference(occ))
            if not p.is_empty:
                if not p.is_valid:
                    p = p.buffer(0)
                out[slot_name] = p
                if layer_occupied is None:
                    layer_occupied = p
                else:
                    occ = _to_polygonal(layer_occupied)
                    try:
                        layer_occupied = _to_polygonal(
                            occ.union(p, grid_size=grid_size)
                        )
                    except GEOSException as e:
                        logger.error(
                            f"  [警告] 更新占用区域(union)启用grid_size失败，已回退到普通并集。slot={slot_name}，原因={e}"
                        )
                        layer_occupied = _to_polygonal(occ.union(p))
        dt = perf_counter() - t0
        logger.info(f"{tag} 互斥裁剪(Python)完成，用时 {dt:.3f}s")
        return out

    if (not use_cpp) or (cpp_geometry is None):
        if use_cpp and (cpp_geometry is None):
            raise RuntimeError(
                f"{tag} 互斥裁剪：已选择 C++ 实现，但未能加载 opencolor_geometry"
            )
        return _python_impl()

    global _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT

    scale = max(1.0, 1.0 / max(float(grid_size), 1e-9))
    slots_loops = []
    for slot_name in ordered_slots:
        g = _to_polygonal(layer_polys.get(slot_name))
        slots_loops.append(_geom_to_loops(g))

    n = len(ordered_slots)
    if _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT is not None:
        est = _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT * float(max(n, 1))
        logger.info(f"{tag} 互斥裁剪(C++)：开始，色块数={n}，预计 {est:.3f}s")
    else:
        logger.info(f"{tag} 互斥裁剪(C++)：开始，色块数={n}，暂无历史数据无法预估")

    t0 = perf_counter()
    try:
        out_loops = cpp_geometry.clipper_make_exclusive_nogil(slots_loops, scale=scale)
    except Exception as e:
        logger.error(f"  [错误] C++互斥裁剪失败: {e}")
        traceback.print_exc()
        raise

    dt = perf_counter() - t0
    if n > 0:
        per = dt / float(n)
        _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT = (
            per
            if _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT is None
            else (0.8 * _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT + 0.2 * per)
        )
    logger.info(f"{tag} 互斥裁剪(C++)完成，用时 {dt:.3f}s")

    out = {}
    for slot_name, loops in zip(ordered_slots, out_loops):
        g = None
        try:
            polys = cpp_geometry.clipper_union_all_to_polygons_nogil(loops, scale=scale)
            built = []
            for shell, holes in polys:
                p = Polygon(shell, holes)
                if not p.is_valid:
                    p = p.buffer(0)
                if p.is_empty:
                    continue
                gt = getattr(p, "geom_type", "")
                if gt == "Polygon":
                    built.append(p)
                elif gt == "MultiPolygon":
                    built.extend(
                        [
                            g
                            for g in p.geoms
                            if (not getattr(g, "is_empty", True))
                            and getattr(g, "geom_type", "") == "Polygon"
                        ]
                    )
            if built:
                g = built[0] if len(built) == 1 else MultiPolygon(built)
                if not getattr(g, "is_valid", True):
                    try:
                        from shapely import make_valid

                        g = make_valid(g)
                    except Exception as e:
                        logger.error(
                            f"  [警告] C++互斥裁剪结果 make_valid 失败: slot={slot_name}，原因={e}"
                        )
                        traceback.print_exc()
                        g = g.buffer(0)
            else:
                g = Polygon()
        except Exception as e:
            logger.error(
                f"  [错误] C++互斥裁剪结果重建失败: slot={slot_name}，原因={e}"
            )
            traceback.print_exc()
            raise

        g = _to_polygonal(g)
        if g.is_empty:
            continue
        if not g.is_valid:
            g = g.buffer(0)
        if not g.is_empty:
            out[slot_name] = g
    return out
