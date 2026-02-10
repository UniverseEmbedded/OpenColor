#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SVG -> 三角形SVG验证器。

使用示例：
  pixi run python svg_mesh_verify.py --in test.svg --out test_tri.svg --tol 0.5
  pixi run python svg_mesh_verify.py --in test.svg --out test_tri_raster.svg --color-mode raster --raster-scale 4

注意：
- 这不是完整的SVG2渲染器。它针对"几何保真度"检查。
- 最佳视觉匹配模式是：--color-mode paint（复制<defs>并重用绘制字符串）。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from lxml import etree
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import unary_union
import mapbox_earcut as earcut
from svgpathtools import parse_path


def _strip_ns(tag: str) -> str:
    """去除XML命名空间前缀"""
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_number_list(s: str) -> List[float]:
    """从字符串中解析数字列表"""
    if not s:
        return []
    nums = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", s)
    return [float(x) for x in nums]


def parse_length(val: Optional[str]) -> Optional[float]:
    """解析SVG长度。对于验证，我们将单位视为用户单位：
    - px: 1
    - 无单位: 1
    - mm/cm/in/pt/pc: 按96dpi转换。
    """
    if val is None:
        return None
    v = val.strip()
    if v == "":
        return None
    m = re.match(r"^([-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)([a-zA-Z%]*)$", v)
    if not m:
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in ("", "px"):
        return num
    if unit == "in":
        return num * 96.0
    if unit == "cm":
        return num * 96.0 / 2.54
    if unit == "mm":
        return num * 96.0 / 25.4
    if unit == "pt":
        return num * 96.0 / 72.0
    if unit == "pc":
        return num * 96.0 / 6.0
    return num


def parse_style_attr(style: Optional[str]) -> Dict[str, str]:
    """解析SVG样式属性字符串为字典"""
    out: Dict[str, str] = {}
    if not style:
        return out
    parts = [p.strip() for p in style.split(";") if p.strip()]
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def get_paint(el: etree._Element, key: str, style: Dict[str, str]) -> Optional[str]:
    """获取元素的绘制属性（fill/stroke等）"""
    v = el.get(key)
    if v is not None:
        return v.strip()
    if key in style:
        return style[key].strip()
    return None


def get_float(el: etree._Element, key: str, style: Dict[str, str], default: float) -> float:
    """获取元素的浮点数值属性"""
    v = el.get(key)
    if v is None and key in style:
        v = style[key]
    if v is None:
        return default
    try:
        return float(parse_number_list(v)[0])
    except Exception:
        return default


def mat_identity() -> np.ndarray:
    """创建单位矩阵"""
    return np.array([[1.0, 0.0, 0.0],
                     [0.0, 1.0, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)


def mat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """矩阵乘法"""
    return a @ b


def mat_translate(tx: float, ty: float) -> np.ndarray:
    """创建平移矩阵"""
    m = mat_identity()
    m[0, 2] = tx
    m[1, 2] = ty
    return m


def mat_scale(sx: float, sy: float) -> np.ndarray:
    """创建缩放矩阵"""
    m = mat_identity()
    m[0, 0] = sx
    m[1, 1] = sy
    return m


def mat_rotate(deg: float) -> np.ndarray:
    """创建旋转矩阵"""
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return np.array([[c, -s, 0.0],
                     [s,  c, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)


def mat_skewx(deg: float) -> np.ndarray:
    """创建X轴倾斜矩阵"""
    t = math.tan(math.radians(deg))
    return np.array([[1.0, t, 0.0],
                     [0.0, 1.0, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)


def mat_skewy(deg: float) -> np.ndarray:
    """创建Y轴倾斜矩阵"""
    t = math.tan(math.radians(deg))
    return np.array([[1.0, 0.0, 0.0],
                     [t, 1.0, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)


def parse_transform(transform: Optional[str]) -> np.ndarray:
    """解析SVG变换属性为变换矩阵"""
    if not transform:
        return mat_identity()
    s = transform.strip()
    m = mat_identity()
    for fn, args in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", s):
        nums = parse_number_list(args)
        fn = fn.lower()
        if fn == "translate":
            tx = nums[0] if len(nums) > 0 else 0.0
            ty = nums[1] if len(nums) > 1 else 0.0
            m = mat_mul(m, mat_translate(tx, ty))
        elif fn == "scale":
            sx = nums[0] if len(nums) > 0 else 1.0
            sy = nums[1] if len(nums) > 1 else sx
            m = mat_mul(m, mat_scale(sx, sy))
        elif fn == "rotate":
            ang = nums[0] if len(nums) > 0 else 0.0
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                m = mat_mul(m, mat_translate(cx, cy))
                m = mat_mul(m, mat_rotate(ang))
                m = mat_mul(m, mat_translate(-cx, -cy))
            else:
                m = mat_mul(m, mat_rotate(ang))
        elif fn == "matrix":
            if len(nums) >= 6:
                a, b, c, d, e, f = nums[:6]
                mm = np.array([[a, c, e],
                               [b, d, f],
                               [0.0, 0.0, 1.0]], dtype=float)
                m = mat_mul(m, mm)
        elif fn == "skewx":
            ang = nums[0] if len(nums) > 0 else 0.0
            m = mat_mul(m, mat_skewx(ang))
        elif fn == "skewy":
            ang = nums[0] if len(nums) > 0 else 0.0
            m = mat_mul(m, mat_skewy(ang))
    return m


def apply_transform_pts(pts: Sequence[Tuple[float, float]], m: np.ndarray) -> List[Tuple[float, float]]:
    """将变换矩阵应用到点集"""
    out: List[Tuple[float, float]] = []
    for x, y in pts:
        v = m @ np.array([x, y, 1.0], dtype=float)
        out.append((float(v[0]), float(v[1])))
    return out


def dedup_consecutive(pts: List[Tuple[float, float]], eps: float = 1e-9) -> List[Tuple[float, float]]:
    """去除连续重复的点"""
    if not pts:
        return pts
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    return out


def close_ring(pts: List[Tuple[float, float]], eps: float = 1e-9) -> List[Tuple[float, float]]:
    """闭合点环（如果首尾点不相同则添加首点）"""
    if len(pts) < 2:
        return pts
    if abs(pts[0][0] - pts[-1][0]) > eps or abs(pts[0][1] - pts[-1][1]) > eps:
        pts.append(pts[0])
    return pts


def sample_svgpathtools_path(d: str, tol: float) -> List[List[Tuple[float, float]]]:
    """使用svgpathtools采样SVG路径"""
    p = parse_path(d)
    subpaths = p.continuous_subpaths()
    out: List[List[Tuple[float, float]]] = []
    for sp in subpaths:
        pts: List[Tuple[float, float]] = []
        for seg in sp:
            try:
                seg_len = float(seg.length(error=1e-4))
            except Exception:
                seg_len = 1.0
            n = max(2, int(math.ceil(seg_len / max(tol, 1e-6))))
            ts = np.linspace(0.0, 1.0, n, endpoint=True)
            for t in ts:
                z = seg.point(t)
                pts.append((float(z.real), float(z.imag)))
        pts = dedup_consecutive(pts)
        if len(pts) >= 2:
            out.append(pts)
    return out


def rect_to_ring(x: float, y: float, w: float, h: float) -> List[Tuple[float, float]]:
    """将矩形转换为点环"""
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


def circle_to_ring(cx: float, cy: float, r: float, tol: float) -> List[Tuple[float, float]]:
    """将圆形转换为点环（多边形逼近）"""
    n = max(16, int(math.ceil((2.0 * math.pi * r) / max(tol, 1e-6))))
    pts = []
    for i in range(n):
        a = 2.0 * math.pi * (i / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0])
    return pts


def ellipse_to_ring(cx: float, cy: float, rx: float, ry: float, tol: float) -> List[Tuple[float, float]]:
    """将椭圆转换为点环（多边形逼近）"""
    approx_c = 2.0 * math.pi * math.sqrt((rx * rx + ry * ry) / 2.0)
    n = max(16, int(math.ceil(approx_c / max(tol, 1e-6))))
    pts = []
    for i in range(n):
        a = 2.0 * math.pi * (i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    pts.append(pts[0])
    return pts


def points_attr_to_list(s: str) -> List[Tuple[float, float]]:
    """解析SVG points属性为点列表"""
    nums = parse_number_list(s)
    pts = []
    for i in range(0, len(nums) - 1, 2):
        pts.append((nums[i], nums[i + 1]))
    return pts


@dataclass
class ShapeGeom:
    """形状几何数据类"""
    fill_rings: List[List[Tuple[float, float]]]  # 填充环列表
    stroke_lines: List[List[Tuple[float, float]]]  # 描边线列表
    fill: Optional[str]  # 填充颜色
    stroke: Optional[str]  # 描边颜色
    stroke_width: float  # 描边宽度
    stroke_linecap: str  # 描边线帽样式
    stroke_linejoin: str  # 描边连接样式
    stroke_miterlimit: float  # 描边斜接限制
    fill_rule: str  # 填充规则
    opacity: Optional[str]  # 不透明度
    fill_opacity: Optional[str]  # 填充不透明度
    stroke_opacity: Optional[str]  # 描边不透明度


def extract_shapes(root: etree._Element, tol: float) -> List[Tuple[ShapeGeom, np.ndarray]]:
    """从SVG根元素提取所有形状几何数据"""
    shapes: List[Tuple[ShapeGeom, np.ndarray]] = []

    def walk(el: etree._Element, parent_m: np.ndarray):
        tag = _strip_ns(el.tag)
        style = parse_style_attr(el.get("style"))
        m = mat_mul(parent_m, parse_transform(el.get("transform")))

        fill = get_paint(el, "fill", style)
        stroke = get_paint(el, "stroke", style)
        opacity = get_paint(el, "opacity", style)
        fill_opacity = get_paint(el, "fill-opacity", style)
        stroke_opacity = get_paint(el, "stroke-opacity", style)
        fill_rule = (get_paint(el, "fill-rule", style) or "nonzero").strip()

        stroke_width = get_float(el, "stroke-width", style, 1.0)
        stroke_linecap = (get_paint(el, "stroke-linecap", style) or "butt").strip()
        stroke_linejoin = (get_paint(el, "stroke-linejoin", style) or "miter").strip()
        stroke_miterlimit = get_float(el, "stroke-miterlimit", style, 4.0)

        fill_rings: List[List[Tuple[float, float]]] = []
        stroke_lines: List[List[Tuple[float, float]]] = []

        if tag == "path":
            d = el.get("d") or ""
            subpolys = sample_svgpathtools_path(d, tol)
            for pts in subpolys:
                if len(pts) < 2:
                    continue
                stroke_lines.append(pts[:])
                if (fill is not None and fill.lower() != "none") or (pts[0] == pts[-1]):
                    ring = close_ring(pts[:])
                    fill_rings.append(ring)

        elif tag == "rect":
            x = parse_length(el.get("x")) or 0.0
            y = parse_length(el.get("y")) or 0.0
            w = parse_length(el.get("width")) or 0.0
            h = parse_length(el.get("height")) or 0.0
            ring = rect_to_ring(x, y, w, h)
            fill_rings.append(ring)
            stroke_lines.append(ring)

        elif tag == "circle":
            cx = parse_length(el.get("cx")) or 0.0
            cy = parse_length(el.get("cy")) or 0.0
            r = parse_length(el.get("r")) or 0.0
            ring = circle_to_ring(cx, cy, r, tol)
            fill_rings.append(ring)
            stroke_lines.append(ring)

        elif tag == "ellipse":
            cx = parse_length(el.get("cx")) or 0.0
            cy = parse_length(el.get("cy")) or 0.0
            rx = parse_length(el.get("rx")) or 0.0
            ry = parse_length(el.get("ry")) or 0.0
            ring = ellipse_to_ring(cx, cy, rx, ry, tol)
            fill_rings.append(ring)
            stroke_lines.append(ring)

        elif tag == "polygon":
            pts = points_attr_to_list(el.get("points") or "")
            if len(pts) >= 3:
                pts.append(pts[0])
                fill_rings.append(pts)
                stroke_lines.append(pts)

        elif tag == "polyline":
            pts = points_attr_to_list(el.get("points") or "")
            if len(pts) >= 2:
                stroke_lines.append(pts)

        elif tag == "line":
            x1 = parse_length(el.get("x1")) or 0.0
            y1 = parse_length(el.get("y1")) or 0.0
            x2 = parse_length(el.get("x2")) or 0.0
            y2 = parse_length(el.get("y2")) or 0.0
            stroke_lines.append([(x1, y1), (x2, y2)])

        if fill_rings or stroke_lines:
            fill_rings = [apply_transform_pts(r, m) for r in fill_rings]
            stroke_lines = [apply_transform_pts(l, m) for l in stroke_lines]

            geom = ShapeGeom(
                fill_rings=fill_rings,
                stroke_lines=stroke_lines,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                stroke_linecap=stroke_linecap,
                stroke_linejoin=stroke_linejoin,
                stroke_miterlimit=stroke_miterlimit,
                fill_rule=fill_rule,
                opacity=opacity,
                fill_opacity=fill_opacity,
                stroke_opacity=stroke_opacity,
            )
            shapes.append((geom, m))

        for ch in el:
            if isinstance(ch.tag, str):
                walk(ch, m)

    walk(root, mat_identity())
    return shapes


def _cap_style(s: str) -> int:
    """将SVG线帽样式转换为Shapely缓冲区线帽样式"""
    s = s.lower()
    if s == "round":
        return 1
    if s == "square":
        return 3
    return 2


def _join_style(s: str) -> int:
    """将SVG连接样式转换为Shapely缓冲区连接样式"""
    s = s.lower()
    if s == "round":
        return 1
    if s == "bevel":
        return 3
    return 2


def stroke_to_polygons(lines: List[List[Tuple[float, float]]],
                       stroke_width: float,
                       linecap: str,
                       linejoin: str,
                       miterlimit: float) -> Union[Polygon, MultiPolygon, None]:
    """将描边线转换为多边形"""
    if stroke_width <= 0.0:
        return None
    geoms = []
    for pts in lines:
        pts2 = dedup_consecutive(pts)
        if len(pts2) < 2:
            continue
        ls = LineString(pts2)
        buf = ls.buffer(
            stroke_width / 2.0,
            cap_style=_cap_style(linecap),
            join_style=_join_style(linejoin),
            mitre_limit=float(miterlimit),
            resolution=16,
            )
        if not buf.is_empty:
            geoms.append(buf)
    if not geoms:
        return None
    return unary_union(geoms)


def rings_to_area_geom(rings: List[List[Tuple[float, float]]], fill_rule: str) -> Union[Polygon, MultiPolygon, None]:
    """将环列表转换为面积几何体"""
    polys = []
    for r in rings:
        r2 = dedup_consecutive(r)
        r2 = close_ring(r2)
        if len(r2) < 4:
            continue
        try:
            p = Polygon(r2)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty:
                polys.append(p)
        except Exception:
            continue
    if not polys:
        return None

    rule = (fill_rule or "nonzero").lower()
    if rule == "evenodd":
        acc = polys[0]
        for p in polys[1:]:
            acc = acc.symmetric_difference(p)
        return acc
    else:
        return unary_union(polys)


def _earcut_one_polygon(poly: Polygon) -> Tuple[np.ndarray, np.ndarray]:
    """使用earcut对单个多边形进行三角化"""
    ext = np.asarray(poly.exterior.coords, dtype=float)
    if len(ext) >= 2 and np.allclose(ext[0], ext[-1]):
        ext = ext[:-1]
    rings = [ext]
    ring_end_indices = [len(ext)]

    for interior in poly.interiors:
        h = np.asarray(interior.coords, dtype=float)
        if len(h) >= 2 and np.allclose(h[0], h[-1]):
            h = h[:-1]
        if len(h) >= 3:
            rings.append(h)
            ring_end_indices.append(ring_end_indices[-1] + len(h))

    verts = np.vstack(rings).astype(np.float64)
    if verts.shape[0] < 3:
        return np.zeros((0, 2), float), np.zeros((0, 3), np.uint32)

    ring_ends = np.array(ring_end_indices, dtype=np.uint32)
    tri = earcut.triangulate_float64(verts, ring_ends)
    tri = np.asarray(tri, dtype=np.uint32).reshape(-1, 3)
    return verts, tri


def triangulate_geom(g: Union[Polygon, MultiPolygon]) -> Tuple[np.ndarray, np.ndarray]:
    """对几何体进行三角化"""
    verts_all = []
    tris_all = []
    vbase = 0
    polys = [g] if isinstance(g, Polygon) else list(g.geoms)
    for p in polys:
        v, t = _earcut_one_polygon(p)
        if v.size == 0 or t.size == 0:
            continue
        tris_all.append(t + vbase)
        verts_all.append(v)
        vbase += v.shape[0]
    if not verts_all:
        return np.zeros((0, 2), float), np.zeros((0, 3), np.uint32)
    return np.vstack(verts_all), np.vstack(tris_all)
