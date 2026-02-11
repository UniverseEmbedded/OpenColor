"""
重采样器模块
对同一层内的多个色块多边形进行共享边界重采样和拓扑重构
确保色块之间无重叠、无空隙
"""

from time import perf_counter

import numpy as np
from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry import Polygon, GeometryCollection, LineString
from shapely.ops import unary_union, snap
from shapely.validation import make_valid

from oc_core_02.utils.io_utils import print_ts
from oc_core_02.utils.bin_loader import import_cpp_extension
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from tqdm import tqdm
except Exception:
    tqdm = None


def _tqdm(it, *, total: int | None = None, desc: str = "", enabled: bool = True):
    if (not enabled) or (tqdm is None):
        return it
    return tqdm(it, total=total, desc=desc, dynamic_ncols=True)


_CPP_EXCLUSIVE_AVG_SEC_PER_SLOT: float | None = None


cpp_geometry = None
try:
    cpp_geometry = import_cpp_extension("opencolor_geometry")
except Exception as e:
    logger.error("导入 C++几何模块失败: {}", e)


def _to_polygonal(geom):
    if geom is None:
        return GeometryCollection()
    if getattr(geom, "is_empty", True):
        return geom

    gt = getattr(geom, "geom_type", "")
    if gt in ("Polygon", "MultiPolygon"):
        return geom
    if gt == "GeometryCollection":
        polys = []
        for g in geom.geoms:
            if getattr(g, "geom_type", "") in ("Polygon", "MultiPolygon") and (
                not g.is_empty
            ):
                polys.append(g)
        if not polys:
            return GeometryCollection()
        return unary_union(polys)
    return GeometryCollection()


def _geom_to_loops(geom):
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


def resample_line(line, interval=0.1):
    """对 LineString 进行等间距重采样"""
    if line.length <= 1e-7:
        return line

    if line.length <= interval:
        return LineString([line.coords[0], line.coords[-1]])

    distances = np.arange(0, line.length, interval)
    if distances[-1] < line.length - 1e-7:
        distances = np.append(distances, line.length)

    points = [line.interpolate(d) for d in distances]

    # 强制网格对齐 (0.001mm)，减少浮点误差导致的拓扑破碎
    unique_points = []
    for p in points:
        pt = (round(p.x, 4), round(p.y, 4))
        if not unique_points or pt != unique_points[-1]:
            unique_points.append(pt)

    if len(unique_points) < 2:
        return line

    return LineString(unique_points)


def resample_shared_boundaries(
    layer_polys: dict,
    tolerance: float = 0.15,
    full_mask_poly: Polygon = None,
    *,
    use_cpp: bool = True,
    progress: bool = True,
    tag: str = "",
) -> dict:
    """
    对同一层内的多个色块多边形进行共享边界重采样。

    极致优化版：
    1. 提取所有边界并强制网格化。
    2. 使用较高的 snap 容差消除 vtracer 抖动。
    3. 拓扑重构碎片。
    4. 使用更严格的排他性分配逻辑。
    """
    if not layer_polys:
        return {}

    prefix = f"{tag} " if tag else ""
    print_ts(
        f"  [Resampler] {prefix}正在执行共享边界对齐 (针对 {len(layer_polys)} 个色块)..."
    )

    grid_size = max(float(tolerance) / 5.0, 1e-4)

    if use_cpp and (cpp_geometry is None):
        raise RuntimeError(
            f"  [Resampler] {prefix}已选择 C++ 实现，但未能加载 opencolor_geometry"
        )

    if use_cpp and (cpp_geometry is not None):
        try:
            scale = max(1.0, 1.0 / max(float(grid_size), 1e-9))
            slot_names = list(layer_polys.keys())
            slots_loops = []
            for name in slot_names:
                g = _to_polygonal(layer_polys.get(name))
                slots_loops.append(_geom_to_loops(g))

            global _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT
            n = len(slot_names)
            if _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT is not None:
                est = _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT * float(max(n, 1))
                print_ts(
                    f"  [Resampler] {prefix}共享边界对齐(C++)：开始，色块数={n}，预计 {est:.3f}s"
                )
            else:
                print_ts(
                    f"  [Resampler] {prefix}共享边界对齐(C++)：开始，色块数={n}，暂无历史数据无法预估"
                )

            t0 = perf_counter()
            out_loops = cpp_geometry.clipper_make_exclusive_nogil(
                slots_loops, scale=scale
            )
            dt = perf_counter() - t0

            if n > 0:
                per = dt / float(n)
                _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT = (
                    per
                    if _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT is None
                    else (0.8 * _CPP_EXCLUSIVE_AVG_SEC_PER_SLOT + 0.2 * per)
                )
            print_ts(f"  [Resampler] {prefix}共享边界对齐(C++)完成，用时 {dt:.3f}s")

            out = {}
            for name, loops in zip(slot_names, out_loops):
                try:
                    polys = cpp_geometry.clipper_union_all_to_polygons_nogil(
                        loops, scale=scale
                    )
                    built = []
                    for shell, holes in polys:
                        p = Polygon(shell, holes)
                        if not p.is_valid:
                            p = p.buffer(0)
                        if not p.is_empty:
                            built.append(p)
                    if built:
                        g = unary_union(built) if len(built) >= 2 else built[0]
                    else:
                        g = Polygon()
                except Exception as e:
                    print_ts(
                        f"  [Resampler][错误] C++输出重建失败: slot={name}，原因={e}"
                    )
                    traceback.print_exc()
                    raise

                g = _to_polygonal(g)
                if not g.is_valid:
                    g = g.buffer(0)
                out[name] = g if not g.is_empty else Polygon()
            print_ts(f"  [Resampler] {prefix}共享边界对齐完成")
            return out
        except Exception as e:
            print_ts(f"  [Resampler][错误] C++共享边界对齐失败: {e}")
            traceback.print_exc()
            raise

    slot_names = list(layer_polys.keys())
    fixed_polys = {}
    boundaries = []

    if full_mask_poly and (not full_mask_poly.is_empty):
        fm = wkt.loads(wkt.dumps(full_mask_poly, rounding_precision=4))
        if not fm.is_valid:
            fm = make_valid(fm)
        fm = _to_polygonal(fm)
        if not fm.is_empty:
            boundaries.append(fm.boundary)

    t0 = perf_counter()
    for name in _tqdm(
        slot_names, total=len(slot_names), desc=f"{prefix}预处理", enabled=progress
    ):
        p = layer_polys.get(name)
        if p is None or p.is_empty:
            continue
        p = wkt.loads(wkt.dumps(p, rounding_precision=4))
        if not p.is_valid:
            p = make_valid(p)
        p = _to_polygonal(p)
        if p.is_empty:
            continue
        fixed_polys[name] = p
        boundaries.append(p.boundary)

    if not fixed_polys:
        return {name: Polygon() for name in slot_names}

    ref_lines = unary_union(boundaries) if boundaries else None
    snapped_polys = {}
    for name in _tqdm(
        slot_names, total=len(slot_names), desc=f"{prefix}snap", enabled=progress
    ):
        p = fixed_polys.get(name)
        if p is None:
            snapped_polys[name] = Polygon()
            continue
        if ref_lines is None:
            snapped = p
        else:
            try:
                snapped = snap(p, ref_lines, tolerance=tolerance)
            except Exception as e:
                print_ts(f"  [Resampler][错误] snap 失败，slot={name}，原因={e}")
                snapped = p
        snapped = _to_polygonal(snapped)
        snapped = wkt.loads(wkt.dumps(snapped, rounding_precision=4))
        if not snapped.is_valid:
            snapped = make_valid(snapped)
        snapped = _to_polygonal(snapped)
        snapped_polys[name] = snapped if not snapped.is_empty else Polygon()

    final_polys = {}
    layer_occupied = Polygon()
    for name in _tqdm(
        slot_names, total=len(slot_names), desc=f"{prefix}排他分配", enabled=progress
    ):
        p = snapped_polys.get(name, Polygon())
        p = _to_polygonal(p)
        if p.is_empty:
            final_polys[name] = Polygon()
            continue
        if not layer_occupied.is_empty:
            layer_occupied = _to_polygonal(layer_occupied)
            try:
                p = p.difference(layer_occupied, grid_size=grid_size)
            except GEOSException as e:
                print_ts(
                    f"  [Resampler][警告] difference 启用grid_size失败，回退到普通差集。slot={name}，原因={e}"
                )
                p = p.difference(layer_occupied)
            except Exception as e:
                print_ts(f"  [Resampler][错误] difference 失败，slot={name}，原因={e}")
                try:
                    p = p.buffer(0).difference(layer_occupied.buffer(0))
                except Exception as e2:
                    print_ts(
                        f"  [Resampler][错误] difference 回退失败，slot={name}，原因={e2}"
                    )
        p = _to_polygonal(p)
        p = wkt.loads(wkt.dumps(p, rounding_precision=4))
        if not p.is_valid:
            p = make_valid(p)
        p = _to_polygonal(p)
        final_polys[name] = p if not p.is_empty else Polygon()
        if not final_polys[name].is_empty:
            try:
                layer_occupied = _to_polygonal(layer_occupied).union(
                    final_polys[name], grid_size=grid_size
                )
            except GEOSException as e:
                print_ts(
                    f"  [Resampler][警告] 更新占用区域(union)启用grid_size失败，回退到普通并集。原因={e}"
                )
                layer_occupied = _to_polygonal(layer_occupied).union(final_polys[name])
            except Exception as e:
                print_ts(f"  [Resampler][错误] 更新占用区域失败，原因={e}")
            layer_occupied = _to_polygonal(layer_occupied)

    dt = perf_counter() - t0
    print_ts(f"  [Resampler] {prefix}共享边界对齐(Python)完成，用时 {dt:.3f}s")
    return final_polys
