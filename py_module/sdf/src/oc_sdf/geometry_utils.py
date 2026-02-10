"""几何工具模块 - 提供几何处理、量化和简化功能

包含多边形处理、坐标量化、几何简化等功能，用于矢量图形处理。
"""

import traceback

import numpy as np
from shapely.geometry import GeometryCollection, Polygon
from shapely.ops import unary_union



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _iter_polygons(geom):
    """迭代几何体中的所有多边形
    
    递归遍历几何体，提取所有多边形（包括多边形集合中的多边形）。
    
    参数:
        geom: shapely几何体对象
        
    返回:
        多边形列表
    """
    if geom is None:
        return []
    gt = getattr(geom, "geom_type", None)
    if gt == "Polygon":
        return [geom]
    if gt == "MultiPolygon":
        return list(getattr(geom, "geoms", []) or [])
    if gt == "GeometryCollection":
        out = []
        for g in list(getattr(geom, "geoms", []) or []):
            out.extend(_iter_polygons(g))
        return out
    return []


def _to_polygonal(geom):
    """将几何体转换为多边形或多边形集合
    
    从几何集合中提取所有多边形，并合并为一个多边形或多边形集合。
    
    参数:
        geom: shapely几何体对象
        
    返回:
        多边形、多边形集合或空几何集合
    """
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
            if getattr(g, "geom_type", "") in ("Polygon", "MultiPolygon") and (not g.is_empty):
                polys.append(g)
        if not polys:
            return GeometryCollection()
        return unary_union(polys)
    return GeometryCollection()


def _round_to_grid(v: float, step: float) -> float:
    """将值量化到网格
    
    将浮点数值四舍五入到最近的网格点。
    
    参数:
        v: 原始值
        step: 网格步长
        
    返回:
        量化后的值
    """
    return float(np.floor((float(v) / float(step)) + 0.5) * float(step))


def _ring_point_collinear(a, b, c) -> bool:
    """检查三个点是否共线
    
    通过叉积判断三点是否在同一直线上，且b点位于a和c之间。
    
    参数:
        a: 第一个点坐标(x,y)
        b: 第二个点坐标(x,y)
        c: 第三个点坐标(x,y)
        
    返回:
        如果共线则返回True
    """
    ax, ay = a
    bx, by = b
    cx, cy = c
    # 计算叉积
    cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
    if cross != 0:
        return False
    # 检查b是否在a和c之间
    if (min(ax, cx) <= bx <= max(ax, cx)) and (min(ay, cy) <= by <= max(ay, cy)):
        return True
    return False


def _drop_collinear_open_ring(points):
    """移除共线点
    
    从点序列中移除中间共线的点，简化多边形边界。
    
    参数:
        points: 点坐标列表
        
    返回:
        移除共线点后的点列表
    """
    pts = list(points)
    if len(pts) <= 3:
        return pts
    for _ in range(len(pts)):
        if len(pts) <= 3:
            break
        changed = False
        n = len(pts)
        for i in range(n):
            a = pts[(i - 1) % n]
            b = pts[i]
            c = pts[(i + 1) % n]
            if _ring_point_collinear(a, b, c):
                del pts[i]
                changed = True
                break
        if not changed:
            break
    return pts


def _quantize_ring_coords(coords, *, step_mm: float):
    """量化环坐标到网格
    
    将多边形环的坐标点量化到指定网格，并移除重复点和共线点。
    
    参数:
        coords: 坐标序列
        step_mm: 网格步长（毫米）
        
    返回:
        量化后的坐标列表
    """
    pts = list(coords)
    # 移除首尾重复点（如果是闭合环）
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    out = []
    last = None
    for x, y in pts:
        qx = _round_to_grid(float(x), float(step_mm))
        qy = _round_to_grid(float(y), float(step_mm))
        cur = (qx, qy)
        # 跳过重复点
        if last is None or cur != last:
            out.append(cur)
            last = cur
    # 再次移除首尾重复点
    if len(out) >= 2 and out[0] == out[-1]:
        out = out[:-1]
    out = _drop_collinear_open_ring(out)
    # 闭合环
    if len(out) >= 3:
        out.append(out[0])
    return out


def _quantize_geom_to_grid(geom, *, step_mm: float):
    """将几何体量化到网格
    
    使用shapely的set_precision或手工量化将几何体对齐到网格。
    
    参数:
        geom: shapely几何体对象
        step_mm: 网格步长（毫米）
        
    返回:
        量化后的几何体
    """
    if geom is None or getattr(geom, "is_empty", True):
        return geom
    if float(step_mm) <= 0:
        return geom

    try:
        import shapely

        # 优先使用shapely的set_precision进行量化
        if hasattr(shapely, "set_precision"):
            g2 = shapely.set_precision(geom, float(step_mm))
            if g2 is not None and (not getattr(g2, "is_empty", True)):
                try:
                    if not getattr(g2, "is_valid", True):
                        g2 = g2.buffer(0)
                except Exception as e:
                    logger.error(f"[警告] 量化后修复几何失败，将继续使用未修复结果。原因={e}")
                    traceback.print_exc()
                return g2
    except Exception as e:
        logger.error(f"[警告] set_precision 量化失败，将回退到手工量化。原因={e}")
        traceback.print_exc()

    # 手工量化回退方案
    out_polys = []
    for p in _iter_polygons(geom):
        if p is None or getattr(p, "is_empty", True):
            continue
        try:
            shell = _quantize_ring_coords(p.exterior.coords, step_mm=float(step_mm))
            if len(shell) < 4:
                continue

            holes = []
            for ring in list(getattr(p, "interiors", []) or []):
                h = _quantize_ring_coords(ring.coords, step_mm=float(step_mm))
                if len(h) >= 4:
                    holes.append(h)

            pp = Polygon(shell, holes)
            if not pp.is_valid:
                pp = pp.buffer(0)
            if not pp.is_empty:
                if getattr(pp, "geom_type", "") == "Polygon":
                    out_polys.append(pp)
                else:
                    out_polys.extend([g for g in getattr(pp, "geoms", []) if getattr(g, "geom_type", "") == "Polygon" and (not g.is_empty)])
        except Exception as e:
            logger.error(f"[错误] 手工量化失败: {e}")
            traceback.print_exc()
            continue

    if not out_polys:
        return GeometryCollection()
    try:
        return unary_union(out_polys).buffer(0)
    except Exception as e:
        logger.error(f"[错误] 量化后合并失败: {e}")
        traceback.print_exc()
        try:
            return unary_union([p.buffer(0) for p in out_polys]).buffer(0)
        except Exception as e2:
            logger.error(f"[错误] 量化后合并二次尝试失败: {e2}")
            traceback.print_exc()
            return unary_union(out_polys)


def _drop_small_holes(poly: Polygon, *, hole_min_area_mm2: float):
    """移除小孔洞
    
    从多边形中移除面积小于阈值的内部孔洞。
    
    参数:
        poly: 多边形对象
        hole_min_area_mm2: 孔洞最小面积阈值（平方毫米）
        
    返回:
        处理后的多边形
    """
    if poly is None or getattr(poly, "is_empty", True):
        return poly
    if float(hole_min_area_mm2) <= 0:
        return poly
    holes = []
    for ring in list(getattr(poly, "interiors", []) or []):
        try:
            hp = Polygon(ring)
            if (not hp.is_empty) and float(hp.area) >= float(hole_min_area_mm2):
                holes.append(list(ring.coords))
        except Exception as e:
            logger.error(f"[警告] 小孔洞筛选失败，将保留该孔洞。原因={e}")
            traceback.print_exc()
            holes.append(list(ring.coords))
    try:
        out = Polygon(list(poly.exterior.coords), holes)
        if not out.is_valid:
            out = out.buffer(0)
        return out
    except Exception as e:
        logger.error(f"[错误] 重建去孔洞多边形失败: {e}")
        traceback.print_exc()
        return poly


def _simplify_geom(
    geom,
    *,
    step_mm: float,
    tolerance_mm: float,
    closing_mm: float,
    min_area_mm2: float,
    hole_min_area_mm2: float,
):
    """简化几何体
    
    综合应用量化、拓扑简化、形态学闭运算和碎片过滤来简化几何体。
    
    参数:
        geom: shapely几何体对象
        step_mm: 量化步长（毫米）
        tolerance_mm: 拓扑简化容差（毫米）
        closing_mm: 形态学闭运算半径（毫米）
        min_area_mm2: 最小保留面积（平方毫米）
        hole_min_area_mm2: 最小孔洞面积（平方毫米）
        
    返回:
        简化后的几何体
    """
    if geom is None or getattr(geom, "is_empty", True):
        return geom

    g = geom
    # 修复无效几何
    try:
        if not getattr(g, "is_valid", True):
            g = g.buffer(0)
    except Exception as e:
        logger.error(f"[警告] 简化前修复失败: {e}")
        traceback.print_exc()

    # 量化到网格
    g = _quantize_geom_to_grid(g, step_mm=float(step_mm))

    # 拓扑简化
    try:
        tol = float(tolerance_mm)
        if tol > 0:
            g = g.simplify(tol, preserve_topology=True)
            if not getattr(g, "is_valid", True):
                g = g.buffer(0)
    except Exception as e:
        logger.error(f"[错误] 拓扑简化失败: {e}")
        traceback.print_exc()

    g = _quantize_geom_to_grid(g, step_mm=float(step_mm))

    # 形态学闭运算（开闭操作）
    try:
        r = float(closing_mm)
        if r > 0:
            try:
                g = g.buffer(r, quad_segs=1).buffer(-r, quad_segs=1)
            except TypeError:
                g = g.buffer(r, resolution=1).buffer(-r, resolution=1)
            if not getattr(g, "is_valid", True):
                g = g.buffer(0)
    except Exception as e:
        logger.error(f"[错误] 闭运算失败: {e}")
        traceback.print_exc()

    g = _quantize_geom_to_grid(g, step_mm=float(step_mm))

    # 过滤小面积碎片和孔洞
    try:
        kept = []
        for p in _iter_polygons(g):
            if p is None or getattr(p, "is_empty", True):
                continue
            pp = p
            if not getattr(pp, "is_valid", True):
                pp = pp.buffer(0)
            if pp.is_empty:
                continue
            pp = _drop_small_holes(pp, hole_min_area_mm2=float(hole_min_area_mm2))
            if pp.is_empty:
                continue
            if float(pp.area) >= float(min_area_mm2):
                kept.append(pp)
        if not kept:
            return GeometryCollection()
        g2 = unary_union(kept)
        if not getattr(g2, "is_valid", True):
            g2 = g2.buffer(0)
        return g2
    except Exception as e:
        logger.error(f"[错误] 碎片/孔洞治理失败: {e}")
        traceback.print_exc()
        return g


def _geom_vertex_stats(geom):
    """统计几何体顶点信息
    
    统计多边形数量、环数量、孔洞数量和顶点总数。
    
    参数:
        geom: shapely几何体对象
        
    返回:
        统计字典，包含polys、rings、holes、pts计数
    """
    polys = _iter_polygons(geom)
    n_polys = 0
    n_rings = 0
    n_holes = 0
    n_pts = 0
    for p in polys:
        if p is None or getattr(p, "is_empty", True):
            continue
        n_polys += 1
        try:
            ext = list(p.exterior.coords)
            # 减去重复的闭合点
            if len(ext) >= 2 and ext[0] == ext[-1]:
                n_pts += max(0, len(ext) - 1)
            else:
                n_pts += len(ext)
            n_rings += 1
        except Exception as e:
            logger.error(f"[警告] 统计外环顶点数失败，将跳过该外环。原因={e}")
            traceback.print_exc()
        for ring in list(getattr(p, "interiors", []) or []):
            try:
                pts = list(ring.coords)
                if len(pts) >= 2 and pts[0] == pts[-1]:
                    n_pts += max(0, len(pts) - 1)
                else:
                    n_pts += len(pts)
                n_rings += 1
                n_holes += 1
            except Exception as e:
                logger.error(f"[警告] 统计孔洞顶点数失败，将跳过该孔洞。原因={e}")
                traceback.print_exc()
    return {"polys": n_polys, "rings": n_rings, "holes": n_holes, "pts": n_pts}


def _geom_total_edge_len_mm(geom) -> float:
    """计算几何体总边长
    
    参数:
        geom: shapely几何体对象
        
    返回:
        总边长（毫米）
    """
    if geom is None or getattr(geom, "is_empty", True):
        return 0.0
    try:
        v = float(getattr(geom, "length", 0.0))
        if not np.isfinite(v):
            return 0.0
        return v
    except Exception as e:
        logger.error(f"[警告] 统计边线总长度失败，将按 0 处理。原因={e}")
        traceback.print_exc()
        return 0.0
