"""几何桥接模块 - 提供Shapely与C++几何之间的转换"""

import numpy as np
from shapely.geometry import Polygon, MultiPolygon

from oc_core_02.utils.bin_loader import import_cpp_extension
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

# 尝试导入C++模块
cpp_geometry = None
try:
    cpp_geometry = import_cpp_extension("opencolor_geometry")
except Exception as e:
    logger.error("导入 C++ 几何模块失败: {}", e)


def _geom_to_loops_evenodd(geom) -> list[np.ndarray]:
    """将几何体转换为环列表（用于C++处理）"""
    if geom is None:
        return []

    loops: list[np.ndarray] = []
    gt = getattr(geom, "geom_type", "")
    if gt == "Polygon":
        ext = np.asarray(geom.exterior.coords, dtype=np.float64)
        if ext.ndim == 2 and ext.shape[0] >= 3 and ext.shape[1] == 2:
            loops.append(ext)
        for interior in geom.interiors:
            arr = np.asarray(interior.coords, dtype=np.float64)
            if arr.ndim == 2 and arr.shape[0] >= 3 and arr.shape[1] == 2:
                loops.append(arr)
        return loops

    if gt == "MultiPolygon":
        for p in getattr(geom, "geoms", []):
            loops.extend(_geom_to_loops_evenodd(p))
        return loops

    if hasattr(geom, "geoms"):
        for g in getattr(geom, "geoms", []):
            loops.extend(_geom_to_loops_evenodd(g))
        return loops
    return loops


def _cpp_polygons_to_shapely(polys) -> object:
    """将C++多边形转换为Shapely几何体"""
    out_polys = []
    for shell, holes in polys or []:
        shell_arr = np.asarray(shell, dtype=np.float64)
        if shell_arr.ndim != 2 or shell_arr.shape[0] < 3 or shell_arr.shape[1] != 2:
            continue
        holes_arr = []
        for h in holes or []:
            h_arr = np.asarray(h, dtype=np.float64)
            if h_arr.ndim != 2 or h_arr.shape[0] < 3 or h_arr.shape[1] != 2:
                continue
            holes_arr.append(h_arr)
        p = Polygon(shell_arr, holes_arr)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty:
            continue
        if p.geom_type == "Polygon":
            out_polys.append(p)
        else:
            out_polys.extend(
                [g for g in p.geoms if g.geom_type == "Polygon" and g.area > 1e-9]
            )

    if not out_polys:
        return Polygon()

    if len(out_polys) == 1:
        return out_polys[0]

    g = MultiPolygon(out_polys)
    if not g.is_valid:
        g = g.buffer(0)
    return g


def _make_exclusive_by_layer_cpp(
    slot_geoms_in_order: list[object | None], *, scale: float = 10000.0
) -> list[object | None]:
    """使用C++进行层内互斥裁剪"""
    if cpp_geometry is None:
        raise RuntimeError("未加载 C++ 几何模块(opencolor_geometry)，无法进行互斥裁剪")

    make_exclusive = getattr(cpp_geometry, "clipper_make_exclusive_nogil", None)
    to_polys = getattr(cpp_geometry, "clipper_union_all_to_polygons_nogil", None)
    if make_exclusive is None or to_polys is None:
        raise RuntimeError(
            "C++ 几何模块缺少 clipper_make_exclusive_nogil/clipper_union_all_to_polygons_nogil"
        )

    slots_loops = []
    for g in slot_geoms_in_order:
        slots_loops.append(_geom_to_loops_evenodd(g) if g is not None else [])

    out_loops_list = make_exclusive(slots_loops, scale=float(scale))
    out_geoms: list[object | None] = []
    for loops in out_loops_list or []:
        if not loops:
            out_geoms.append(None)
            continue
        polys = to_polys(loops, scale=float(scale))
        g = _cpp_polygons_to_shapely(polys)
        if getattr(g, "is_empty", True):
            out_geoms.append(None)
        else:
            out_geoms.append(g)

    if len(out_geoms) != len(slot_geoms_in_order):
        return slot_geoms_in_order
    return out_geoms


def _union_polys_cpp(polys: list, *, scale: float = 10000.0) -> object:
    """使用C++合并多个多边形

    Args:
        polys: 多边形列表 (Polygon 或 MultiPolygon)
        scale: Clipper 缩放因子

    Returns:
        合并后的几何体 (Polygon 或 MultiPolygon)
    """
    if cpp_geometry is None:
        raise RuntimeError(
            "未加载 C++ 几何模块(opencolor_geometry)，无法进行多边形合并"
        )

    union_fn = getattr(cpp_geometry, "clipper_union_all_to_polygons_nogil", None)
    if union_fn is None:
        raise RuntimeError("C++ 几何模块缺少 clipper_union_all_to_polygons_nogil")

    # 收集所有环
    all_loops = []
    for poly in polys:
        loops = _geom_to_loops_evenodd(poly)
        all_loops.extend(loops)

    if not all_loops:
        return Polygon()

    # 调用C++合并
    result_polys = union_fn(all_loops, scale=float(scale))
    return _cpp_polygons_to_shapely(result_polys)


def check_cpp_available() -> bool:
    """检查C++几何模块是否可用"""
    return cpp_geometry is not None


def get_cpp_geometry():
    """获取C++几何模块"""
    return cpp_geometry
