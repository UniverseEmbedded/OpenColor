"""
SVG 处理模块

提供 SVG 文件解析、颜色提取、几何变换和网格生成功能
用于将 SVG 图形转换为可打印的 3D 网格模型
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from svgpathtools import Path, parse_path


# --- 颜色工具 ---


def srgb_to_linear01(x: np.ndarray) -> np.ndarray:
    """将 sRGB 颜色值从非线性空间转换到线性空间（0-1范围）"""
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)


def parse_color_to_rgb255(s: str) -> Optional[Tuple[int, int, int]]:
    """解析颜色字符串为 RGB255 元组

    支持格式：
    - 十六进制：#RGB 或 #RRGGBB
    - RGB函数：rgb(r,g,b)
    - 命名颜色：red, green, blue, white, black
    """
    if not s:
        return None
    s = s.strip().lower()
    if s == "none":
        return None

    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            r = int(h[0] * 2, 16)
            g = int(h[1] * 2, 16)
            b = int(h[2] * 2, 16)
            return (r, g, b)
        if len(h) == 6:
            r = int(h[0:2], 16)
            g = int(h[2:4], 16)
            b = int(h[4:6], 16)
            return (r, g, b)
        return None

    m = re.match(r"rgb\s*\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)", s)
    if m:
        r, g, b = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return (r, g, b)

    named = {
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
    }
    return named.get(s, None)


def parse_fill_from_attrs(attrs: Dict[str, str]) -> Optional[Tuple[int, int, int]]:
    """从 SVG 属性字典中解析填充颜色"""
    fill = attrs.get("fill", "") or ""
    rgb = parse_color_to_rgb255(fill)
    if rgb is not None:
        return rgb
    style = attrs.get("style", "") or ""
    m = re.search(r"fill\s*:\s*([^;]+)", style, re.IGNORECASE)
    if m:
        return parse_color_to_rgb255(m.group(1).strip())
    return None


def has_fill_spec(attrs: Dict[str, str]) -> bool:
    """检查属性字典中是否包含填充颜色规范"""
    if "fill" in attrs:
        return True
    style = attrs.get("style", "") or ""
    return re.search(r"fill\s*:\s*", style, re.IGNORECASE) is not None


def _local_name(tag: str) -> str:
    """获取 XML 标签的本地名称（去掉命名空间前缀）"""
    return tag.split("}")[-1] if "}" in tag else tag


def iter_svg_paths_with_group_transform(
    svg_path: str,
) -> Tuple[
    Dict[str, str],
    List[Tuple[Path, Dict[str, str], np.ndarray, bool, Optional[Tuple[int, int, int]]]],
]:
    """遍历 SVG 文件中的所有路径，应用组变换矩阵

    Args:
        svg_path: SVG 文件路径

    Returns:
        (SVG属性字典, 路径列表)，其中路径列表每项包含：
        (路径对象, 属性字典, 变换矩阵, 是否设置填充, 填充颜色)
    """
    root = ET.parse(svg_path).getroot()
    svg_attrs: Dict[str, str] = {str(k): str(v) for k, v in root.attrib.items()}
    out: List[
        Tuple[Path, Dict[str, str], np.ndarray, bool, Optional[Tuple[int, int, int]]]
    ] = []

    def walk(
        node: ET.Element,
        M_parent: np.ndarray,
        fill_set: bool,
        fill_value: Optional[Tuple[int, int, int]],
    ) -> None:
        attrs: Dict[str, str] = {str(k): str(v) for k, v in node.attrib.items()}
        M_local = parse_transform_attr(attrs.get("transform", "") or "")
        M_here = M_parent @ M_local

        fill_set2 = fill_set
        fill_value2 = fill_value
        if has_fill_spec(attrs):
            fill_set2 = True
            fill_value2 = parse_fill_from_attrs(attrs)

        name = _local_name(str(node.tag))
        if name == "path":
            d = attrs.get("d", "")
            if d:
                out.append((parse_path(d), attrs, M_here, fill_set2, fill_value2))

        for child in list(node):
            walk(child, M_here, fill_set2, fill_value2)

    walk(root, np.eye(3, dtype=np.float64), False, None)
    return svg_attrs, out


# --- 调色板 ---


@dataclass(frozen=True)
class Material:
    """材料定义，包含键名和 RGB255 颜色值"""

    key: str
    rgb255: Tuple[int, int, int]


DEFAULT_RGBW = {
    "R": Material("R", (255, 0, 0)),
    "G": Material("G", (0, 255, 0)),
    "B": Material("B", (0, 0, 255)),
    "W": Material("W", (255, 255, 255)),
}


def classify_rgb_to_rgbw_nearest(rgb255: Tuple[int, int, int]) -> str:
    """将 RGB 颜色分类到最近的 RGBW 材料（基于线性颜色空间距离）"""
    rgb = np.array(rgb255, dtype=np.float32) / 255.0
    rgb_lin = srgb_to_linear01(rgb)

    keys = ["R", "G", "B", "W"]
    pal = np.array([DEFAULT_RGBW[k].rgb255 for k in keys], dtype=np.float32) / 255.0
    pal_lin = srgb_to_linear01(pal)

    d2 = np.sum((pal_lin - rgb_lin[None, :]) ** 2, axis=1)
    return keys[int(np.argmin(d2))]


def classify_rgb_to_rgbw_strict(
    rgb255: Tuple[int, int, int], tol: int = 0
) -> Optional[str]:
    """严格匹配 RGB 颜色到 RGBW 材料（在容差范围内）"""
    for k, mat in DEFAULT_RGBW.items():
        r0, g0, b0 = mat.rgb255
        r, g, b = rgb255
        if abs(r - r0) <= tol and abs(g - g0) <= tol and abs(b - b0) <= tol:
            return k
    return None


# --- SVG viewBox + 变换 ---


def get_viewbox(svg_attrs: Dict[str, str]) -> Tuple[float, float, float, float]:
    """从 SVG 属性中提取 viewBox 或从 width/height 计算

    Returns:
        (min_x, min_y, width, height)
    """
    vb = svg_attrs.get("viewBox") or svg_attrs.get("viewbox")
    if vb:
        parts = [p for p in re.split(r"[,\s]+", vb.strip()) if p]
        if len(parts) == 4:
            return (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))

    def parse_len(v: str) -> float:
        if not v:
            return 100.0
        m = re.match(r"([0-9]*\.?[0-9]+)", v.strip())
        return float(m.group(1)) if m else 100.0

    w = parse_len(svg_attrs.get("width", "100"))
    h = parse_len(svg_attrs.get("height", "100"))
    return (0.0, 0.0, w, h)


def _mat_translate(tx: float, ty: float) -> np.ndarray:
    """创建平移变换矩阵"""
    return np.array([[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]], dtype=np.float64)


def _mat_scale(sx: float, sy: float) -> np.ndarray:
    """创建缩放变换矩阵"""
    return np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def _mat_rotate(deg: float) -> np.ndarray:
    """创建旋转变换矩阵（角度制）"""
    th = math.radians(deg)
    c = math.cos(th)
    s = math.sin(th)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def parse_transform_attr(s: str) -> np.ndarray:
    """解析 SVG transform 属性字符串为 3x3 变换矩阵

    支持：matrix, translate, scale, rotate
    """
    if not s:
        return np.eye(3, dtype=np.float64)

    s = s.strip()
    M = np.eye(3, dtype=np.float64)

    for fn, argstr in re.findall(r"([a-zA-Z]+)\s*\(\s*([^\)]*)\)", s):
        fn = fn.lower()
        args = [a for a in re.split(r"[,\s]+", argstr.strip()) if a]
        vals = [float(x) for x in args] if args else []

        if fn == "matrix" and len(vals) == 6:
            a, b, c, d, e, f = vals
            T = np.array([[a, c, e], [b, d, f], [0.0, 0.0, 1.0]], dtype=np.float64)
            M = M @ T
        elif fn == "translate" and len(vals) >= 1:
            tx = vals[0]
            ty = vals[1] if len(vals) >= 2 else 0.0
            M = M @ _mat_translate(tx, ty)
        elif fn == "scale" and len(vals) >= 1:
            sx = vals[0]
            sy = vals[1] if len(vals) >= 2 else sx
            M = M @ _mat_scale(sx, sy)
        elif fn == "rotate" and len(vals) >= 1:
            ang = vals[0]
            if len(vals) >= 3:
                cx, cy = vals[1], vals[2]
                M = (
                    M
                    @ _mat_translate(cx, cy)
                    @ _mat_rotate(ang)
                    @ _mat_translate(-cx, -cy)
                )
            else:
                M = M @ _mat_rotate(ang)
    return M


def apply_affine_to_points(
    pts: List[Tuple[float, float]], M: np.ndarray
) -> List[Tuple[float, float]]:
    """将仿射变换矩阵应用到点集上"""
    if M is None:
        return pts
    out: List[Tuple[float, float]] = []
    for x, y in pts:
        v = M @ np.array([x, y, 1.0], dtype=np.float64)
        out.append((float(v[0]), float(v[1])))
    return out


# --- 几何构建 ---


def ring_area_xy(coords: List[Tuple[float, float]]) -> float:
    """计算多边形环的有向面积（使用鞋带公式）"""
    a = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def approx_closed_rings_from_path(
    path: Path, tol_units: float, M: np.ndarray
) -> List[List[Tuple[float, float]]]:
    """从 SVG 路径中提取闭合环（近似为多边形）

    Args:
        path: SVG 路径对象
        tol_units: 采样容差（单位长度）
        M: 变换矩阵

    Returns:
        闭合环的点列表列表
    """
    rings: List[List[Tuple[float, float]]] = []
    for sub in path.continuous_subpaths():
        if len(sub) == 0:
            continue
        if abs(sub.start - sub.end) > 1e-9:
            continue

        length = max(0.0, float(sub.length(error=1e-4)))
        n = int(np.ceil(length / max(1e-9, tol_units)))
        n = max(24, min(n, 20000))

        pts = []
        for i in range(n):
            t = i / n
            z = sub.point(t)
            pts.append((float(z.real), float(z.imag)))
        pts.append(pts[0])

        pts = apply_affine_to_points(pts, M)
        if len(pts) >= 4 and abs(ring_area_xy(pts)) > 1e-8:
            rings.append(pts)
    return rings


def build_polygons_from_rings(rings: List[List[Tuple[float, float]]]) -> List[Polygon]:
    """从环列表构建多边形（处理外环和孔洞关系）"""
    if not rings:
        return []

    ring_infos = []
    for pts in rings:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.area <= 1e-10:
            continue
        area_signed = ring_area_xy(pts)
        ring_infos.append(
            {
                "pts": pts,
                "poly": poly,
                "abs_area": abs(area_signed),
                "sign": 1 if area_signed >= 0 else -1,
            }
        )

    if not ring_infos:
        return []

    ring_infos.sort(key=lambda r: r["abs_area"], reverse=True)
    outers: List[Dict] = []
    holes_map: Dict[int, List[List[Tuple[float, float]]]] = {}

    for r in ring_infos:
        container_i = None
        container_area = None
        for oi, o in enumerate(outers):
            if o["poly"].contains(r["poly"]):
                if container_area is None or o["abs_area"] < container_area:
                    container_i = oi
                    container_area = o["abs_area"]

        if container_i is None:
            outers.append(r)
        else:
            if r["sign"] != outers[container_i]["sign"]:
                holes_map.setdefault(container_i, []).append(r["pts"])
            else:
                outers.append(r)

    polys: List[Polygon] = []
    for oi, outer in enumerate(outers):
        holes = holes_map.get(oi, [])
        p = Polygon(outer["pts"], holes)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or p.area <= 1e-10:
            continue
        polys.append(p)

    return polys


def transform_svg_units_to_mm(
    poly: Polygon, vb_minx: float, vb_miny: float, vb_h: float, scale_mm_per_unit: float
) -> Polygon:
    """将 SVG 单位坐标转换为毫米坐标（Y轴翻转）"""
    xys = np.asarray(poly.exterior.coords, dtype=np.float64)
    x = (xys[:, 0] - vb_minx) * scale_mm_per_unit
    y = (vb_h - (xys[:, 1] - vb_miny)) * scale_mm_per_unit
    shell = list(zip(x.tolist(), y.tolist()))

    holes = []
    for ring in poly.interiors:
        pts = np.asarray(ring.coords, dtype=np.float64)
        xh = (pts[:, 0] - vb_minx) * scale_mm_per_unit
        yh = (vb_h - (pts[:, 1] - vb_miny)) * scale_mm_per_unit
        holes.append(list(zip(xh.tolist(), yh.tolist())))

    p = Polygon(shell, holes)
    if not p.is_valid:
        p = p.buffer(0)
    return p


def extrude_polygon_to_mesh(geom, height_mm: float):
    """将多边形拉伸为 3D 网格"""
    if geom.is_empty:
        return None
    if isinstance(geom, MultiPolygon):
        geom = unary_union(geom)
        if geom.is_empty:
            return None
    try:
        mesh = trimesh.creation.extrude_polygon(geom, height_mm)
        return mesh
    except Exception:
        return None


def union_clean(polys: List[Polygon], simplify_mm: float, min_area_mm2: float):
    """合并多边形列表并清理（简化、过滤小面积）"""
    if not polys:
        return None
    g = unary_union(polys)
    if g.is_empty:
        return None
    g = g.buffer(0)
    if simplify_mm > 0:
        g = g.simplify(simplify_mm, preserve_topology=True)
        g = g.buffer(0)
    if isinstance(g, MultiPolygon):
        parts = [p for p in g.geoms if p.area >= min_area_mm2]
        if not parts:
            return None
        g = unary_union(parts).buffer(0)
    else:
        if g.area < min_area_mm2:
            return None
    return g
