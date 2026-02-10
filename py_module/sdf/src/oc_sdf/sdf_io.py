from __future__ import annotations

from time import perf_counter
from typing import List, Any, Tuple

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, MultiPolygon
from shapely.strtree import STRtree

from oc_core_02.utils.logger import get_logger
from oc_core_02.utils.bin_loader import import_cpp_extension

logger = get_logger(__name__)

# 尝试导入 C++ SVG 加载器
_cpp_load_svg_polygons = None
_HAS_CPP_SVG_LOADER = False
try:
    _cpp_geometry = import_cpp_extension("opencolor_geometry")
    _cpp_load_svg_polygons = getattr(_cpp_geometry, "load_svg_polygons", None)
    _HAS_CPP_SVG_LOADER = _cpp_load_svg_polygons is not None
except Exception as _e:
    logger.debug("C++ SVG 加载器导入失败: {}", _e)

def collect_polygons(geom: Any) -> List[Polygon]:
    """从几何对象中提取所有多边形，支持 Polygon、MultiPolygon 和几何集合。"""
    polys: List[Polygon] = []
    if geom is None:
        return polys
    if isinstance(geom, Polygon):
        polys.append(geom)
        return polys
    if isinstance(geom, MultiPolygon):
        polys.extend(list(geom.geoms))
        return polys
    if hasattr(geom, "geoms"):
        for g in geom.geoms:
            polys.extend(collect_polygons(g))
    return polys

def polygon_to_svg_path(p: Polygon, height_mm: float) -> str:
    """将多边形转换为 SVG 路径字符串，Y 坐标翻转以适应 SVG 坐标系。"""
    def _ring_to_path(coords: Any) -> str:
        pts = [f"{float(x):.4f},{float(height_mm - y):.4f}" for x, y in coords]
        if not pts:
            return ""
        return "M " + " L ".join(pts) + " Z"
    paths: List[str] = []
    paths.append(_ring_to_path(p.exterior.coords))
    for ring in p.interiors:
        paths.append(_ring_to_path(ring.coords))
    return " ".join([s for s in paths if s])

def save_svg(geom: Any, svg_path: Path, width_mm: float, height_mm: float) -> bool:
    """将几何对象保存为 SVG 文件。"""
    polys = collect_polygons(geom)
    if not polys:
        return False
    paths: List[str] = []
    for p in polys:
        pp = p
        if not pp.is_valid:
            try:
                pp = pp.buffer(0)
            except Exception as e:
                logger.warning("SVG 多边形修复失败: {}", e)
                continue
        if pp.is_empty:
            continue
        path = polygon_to_svg_path(pp, height_mm)
        if path:
            paths.append(path)
    if not paths:
        return False
    try:
        svg = (
            f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width_mm:.4f}mm\" "
            f"height=\"{height_mm:.4f}mm\" viewBox=\"0 0 {width_mm:.4f} {height_mm:.4f}\">"
            f"<path d=\"{' '.join(paths)}\" fill=\"black\" fill-rule=\"evenodd\"/>"
            "</svg>"
        )
        svg_path.write_text(svg, encoding="utf-8")
        return True
    except Exception as e:
        logger.error("SVG 写入失败: {} {}", svg_path, e)
        return False

import re
import xml.etree.ElementTree as ET


def _load_svg_polygons_python(svg_path: Path) -> List[Polygon]:
    """Python 实现的 SVG 加载（作为 C++ 失败时的备用，但当前策略是 C++ 失败直接报错）"""
    t_total0 = perf_counter()
    if not svg_path.exists():
        return []

    try:
        content = svg_path.read_text(encoding="utf-8")
        h_match = re.search(r'height="([\d.]+)mm"', content)
        if not h_match:
            return []
        height_mm = float(h_match.group(1))

        root = ET.fromstring(content)
        ns = {'svg': 'http://www.w3.org/2000/svg'}

        rings: List[List[Tuple[float, float]]] = []

        def _flush_ring(r: List[Tuple[float, float]]):
            """处理并存储一个环（轮廓或孔洞），去除重复点和显式闭合点。"""
            if len(r) < 3:
                return
            # 如果首尾点相同，移除显式闭合点
            if len(r) >= 2 and (abs(r[0][0] - r[-1][0]) < 1e-9 and abs(r[0][1] - r[-1][1]) < 1e-9):
                r = r[:-1]
            # 移除连续重复点
            cleaned = []
            for pt in r:
                if not cleaned or (abs(pt[0] - cleaned[-1][0]) > 1e-9 or abs(pt[1] - cleaned[-1][1]) > 1e-9):
                    cleaned.append(pt)
            if len(cleaned) >= 3:
                rings.append(cleaned)

        for path in root.findall('.//svg:path', ns):
            d = path.get('d')
            if not d:
                continue
            tokens = d.strip().split()
            cur: List[Tuple[float, float]] = []
            i = 0
            while i < len(tokens):
                t = tokens[i]
                if t in ("M", "L"):
                    if i + 1 >= len(tokens):
                        break
                    x_str, y_str = tokens[i + 1].split(",")
                    x = float(x_str)
                    y_svg = float(y_str)
                    # Y 坐标翻转：SVG 坐标系原点在左上角，转换为毫米坐标系（原点在左下角）
                    y = height_mm - y_svg
                    cur.append((x, y))
                    i += 2
                elif t == "Z":
                    _flush_ring(cur)
                    cur = []
                    i += 1
                else:
                    i += 1
            _flush_ring(cur)

        if not rings:
            return []

        # 构建环多边形
        ring_polys: List[Polygon] = []
        ring_coords: List[List[Tuple[float, float]]] = []
        for r in rings:
            try:
                p = Polygon(r)
                if not p.is_valid:
                    p_fix = p.buffer(0)
                    if isinstance(p_fix, Polygon) and not p_fix.is_empty:
                        p = p_fix
                if not p.is_empty and p.area > 1e-12:
                    ring_polys.append(p)
                    ring_coords.append(list(p.exterior.coords)[:-1])
            except Exception:
                continue

        if not ring_polys:
            return []

        # 构建包含关系树（奇偶填充规则）- 使用空间索引优化
        t_contain0 = perf_counter()
        n = len(ring_polys)
        areas = [rp.area for rp in ring_polys]
        rep_pts = [rp.representative_point() for rp in ring_polys]

        parent = [-1] * n
        children: List[List[int]] = [[] for _ in range(n)]

        # 按面积排序，从大到小处理
        sorted_indices = sorted(range(n), key=lambda i: areas[i], reverse=True)
        
        # 逐步构建空间索引，只包含已经处理过的（面积更大的）多边形
        tree_polys = []  # 已加入索引的多边形
        tree_indices = []  # 对应的原始索引
        
        for idx in sorted_indices:
            current_poly = ring_polys[idx]
            current_rep = rep_pts[idx]
            current_area = areas[idx]
            
            if tree_polys:
                # 查询可能包含当前点的多边形
                tree = STRtree(tree_polys)
                candidates = tree.query(current_rep)
                
                # 在候选中找到真正包含当前点的最小面积多边形
                best_parent = -1
                best_area = float('inf')
                for c_idx in candidates:
                    original_idx = tree_indices[c_idx]
                    if areas[original_idx] > current_area:
                        try:
                            if tree_polys[c_idx].contains(current_rep):
                                if areas[original_idx] < best_area:
                                    best_parent = original_idx
                                    best_area = areas[original_idx]
                        except Exception:
                            continue
                
                if best_parent != -1:
                    parent[idx] = best_parent
            
            # 将当前多边形加入索引
            tree_polys.append(current_poly)
            tree_indices.append(idx)

        for i in range(n):
            if parent[i] != -1:
                children[parent[i]].append(i)

        depth = [0] * n
        for i in range(n):
            d = 0
            k = i
            while parent[k] != -1:
                d += 1
                k = parent[k]
            depth[i] = d

        # 构建最终带孔洞的多边形
        out_polys: List[Polygon] = []
        for i in range(n):
            if depth[i] % 2 != 0:
                continue  # 奇数深度为孔洞，跳过
            exterior = ring_coords[i]
            holes = []
            for c in children[i]:
                if depth[c] == depth[i] + 1:
                    holes.append(ring_coords[c])
            try:
                poly = Polygon(exterior, holes)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if isinstance(poly, Polygon) and not poly.is_empty:
                    out_polys.append(poly)
            except Exception:
                continue

        final: List[Polygon] = []
        for p in out_polys:
            try:
                if p.is_empty:
                    continue
                if not p.is_valid:
                    p = p.buffer(0)
                if isinstance(p, Polygon) and not p.is_empty and p.area > 1e-12:
                    final.append(p)
            except Exception:
                continue

        t_contain1 = perf_counter()
        t_total1 = perf_counter()
        logger.info(
            "SVG加载完成(Python): {} | 环数={}, 输出多边形={}, 包含计算={:.3f}s, 总计={:.3f}s",
            svg_path.name, len(rings), len(final), t_contain1 - t_contain0, t_total1 - t_total0
        )
        return final

    except Exception as e:
        logger.error("Python SVG 加载失败: {}, 原因={}", svg_path.name, e)
        raise


def load_svg_polygons(svg_path: Path) -> List[Polygon]:
    """
    从 SVG 文件中加载多边形。
    
    默认使用 C++ 实现（高性能），如果 C++ 加载器不可用或失败则报错退出。
    
    返回：一组 Shapely Polygon，每个 Polygon 可能带孔洞
    """
    if not svg_path.exists():
        return []
    
    # 检查 C++ 加载器是否可用
    if not _HAS_CPP_SVG_LOADER or _cpp_load_svg_polygons is None:
        raise RuntimeError(
            f"C++ SVG 加载器不可用，无法加载 {svg_path.name}\n"
            f"请确保 opencolor_geometry 模块已正确编译和安装。"
        )
    
    # 使用 C++ 加载器
    try:
        # C++ 返回的是 [(外轮廓, [孔洞列表]), ...] 格式
        # 需要转换为 Shapely Polygon
        result = _cpp_load_svg_polygons(str(svg_path))
        
        # 转换为 Shapely Polygon
        polygons: List[Polygon] = []
        for exterior, holes in result:
            try:
                # exterior 和 holes 是 [(x,y), ...] 格式
                poly = Polygon(exterior, holes)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if isinstance(poly, Polygon) and not poly.is_empty and poly.area > 1e-12:
                    polygons.append(poly)
            except Exception as e:
                logger.warning("构建多边形失败: {}", e)
                continue
        
        return polygons
        
    except Exception as e:
        # C++ 失败时报错退出，不回退到 Python
        raise RuntimeError(
            f"C++ SVG 加载失败: {svg_path.name}\n"
            f"原因: {e}\n"
            f"请检查 SVG 文件格式或报告此问题。"
        ) from e


def rasterize_geometry(
    geom: Any,
    width_px: int,
    height_px: int,
    height_mm: float,
    px_per_mm: float,
) -> np.ndarray | None:
    """硬栅格化几何对象为二值图像（0 和 1）。"""
    polys = collect_polygons(geom)
    if not polys:
        return None
    img = Image.new("L", (int(width_px), int(height_px)), 0)
    draw = ImageDraw.Draw(img)
    for p in polys:
        pp = p
        if not pp.is_valid:
            try:
                pp = pp.buffer(0)
            except Exception as e:
                logger.warning("栅格化多边形修复失败: {}", e)
                continue
        if pp.is_empty:
            continue
        exterior = [
            (float(x) * px_per_mm, float(height_mm - y) * px_per_mm)
            for x, y in pp.exterior.coords
        ]
        if len(exterior) >= 3:
            draw.polygon(exterior, fill=1)
        for ring in pp.interiors:
            hole = [
                (float(x) * px_per_mm, float(height_mm - y) * px_per_mm)
                for x, y in ring.coords
            ]
            if len(hole) >= 3:
                draw.polygon(hole, fill=0)
    return np.array(img, dtype=np.uint8)

def rasterize_geometry_soft(
    geom: Any,
    width_px: int,
    height_px: int,
    height_mm: float,
    px_per_mm: float,
    supersample: int = 4
) -> np.ndarray | None:
    """软栅格化几何对象为抗锯齿图像，返回 float32 类型的 0.0-1.0 范围数值。"""
    polys = collect_polygons(geom)
    if not polys:
        return None
    
    # 在超采样分辨率下进行渲染
    sw = int(width_px * supersample)
    sh = int(height_px * supersample)
    spx = px_per_mm * supersample
    
    img = Image.new("L", (sw, sh), 0)
    draw = ImageDraw.Draw(img)
    
    for p in polys:
        pp = p
        if not pp.is_valid:
            try:
                pp = pp.buffer(0)
            except Exception as e:
                logger.warning("软栅格化多边形修复失败: {}", e)
                continue
        if pp.is_empty:
            continue
            
        exterior = [
            (float(x) * spx, float(height_mm - y) * spx)
            for x, y in pp.exterior.coords
        ]
        if len(exterior) >= 3:
            draw.polygon(exterior, fill=255)
            
        for ring in pp.interiors:
            hole = [
                (float(x) * spx, float(height_mm - y) * spx)
                for x, y in ring.coords
            ]
            if len(hole) >= 3:
                draw.polygon(hole, fill=0)
    
    # 缩回到原始尺寸实现抗锯齿
    if supersample > 1:
        img = img.resize((int(width_px), int(height_px)), Image.BOX)
        
    return np.array(img, dtype=np.float32) / 255.0
