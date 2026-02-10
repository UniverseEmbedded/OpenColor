#!/usr/bin/env python3

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# svg_stack_rgbw_testsvg.py
# SVG -> 堆叠RGBW平面内容，导出为4个STL。
#
# 此脚本用于"底面颜色"实验（图像出现在与热床接触的面），
# 因此默认视图为"bottom"。
#
# 示例：
#   python svg_stack_rgbw_testsvg.py --svg test.svg --outdir out_testsvg --name test --width-mm 80 \
#       --first-layer-height 0.12 --layer-height 0.08 --layers 5 --view bottom --backing white

import argparse
import math
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from svgpathtools import Path, parse_path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'planning'))
import planner

RGBA = Tuple[int, int, int, int]


# -------------------------
# 颜色解析
# -------------------------

def parse_color_rgb255(s: str) -> Optional[Tuple[int, int, int]]:
    if not s:
        return None
    s = s.strip().lower()
    if s == "none":
        return None
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return None
    m = re.match(r"rgb\s*\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)", s)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    named = {
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
    }
    return named.get(s, None)


def parse_style_value(style: str, key: str) -> Optional[str]:
    if not style:
        return None
    m = re.search(rf"(?:^|;)\s*{re.escape(key)}\s*:\s*([^;]+)", style, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_float_maybe(v: str, what: str) -> Optional[float]:
    try:
        return float(v)
    except ValueError as e:
        logger.error(f"解析{what}失败: {v!r}，错误: {e}")
        return None


def parse_fill_rgba(attrs: Dict[str, str]) -> Optional[RGBA]:
    # 填充
    fill = attrs.get("fill", "") or ""
    rgb = parse_color_rgb255(fill)
    if rgb is None:
        style = attrs.get("style", "") or ""
        v = parse_style_value(style, "fill")
        if v:
            rgb = parse_color_rgb255(v)
    if rgb is None:
        return None

    # 不透明度 / 填充不透明度
    style = attrs.get("style", "") or ""
    a = 1.0

    if "fill-opacity" in attrs:
        vv = _parse_float_maybe(str(attrs["fill-opacity"]), "fill-opacity")
        if vv is not None:
            a *= vv
    v = parse_style_value(style, "fill-opacity")
    if v:
        vv = _parse_float_maybe(v, "style:fill-opacity")
        if vv is not None:
            a *= vv

    if "opacity" in attrs:
        vv = _parse_float_maybe(str(attrs["opacity"]), "opacity")
        if vv is not None:
            a *= vv
    v = parse_style_value(style, "opacity")
    if v:
        vv = _parse_float_maybe(v, "style:opacity")
        if vv is not None:
            a *= vv

    a = max(0.0, min(1.0, a))
    return (rgb[0], rgb[1], rgb[2], int(round(a * 255)))


# -------------------------
# SVG变换处理
# -------------------------

def _mat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a @ b


def _mat_translate(tx: float, ty: float) -> np.ndarray:
    return np.array(
        [[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]], dtype=np.float64
    )


def _mat_scale(sx: float, sy: float) -> np.ndarray:
    return np.array(
        [[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )


def _mat_rotate(deg: float) -> np.ndarray:
    th = math.radians(deg)
    c = math.cos(th)
    s = math.sin(th)
    return np.array(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )


def parse_transform_attr(s: str) -> np.ndarray:
    """将SVG变换列表的最小子集解析为3x3仿射矩阵。

    支持：matrix(a,b,c,d,e,f), translate(tx,ty), scale(sx,sy), rotate(angle[,cx,cy])。
    顺序为左到右应用。
    """
    if not s:
        return np.eye(3, dtype=np.float64)

    s = s.strip()
    M = np.eye(3, dtype=np.float64)

    for fn, argstr in re.findall(r"([a-zA-Z]+)\s*\(\s*([^)]*)\)", s):
        fn = fn.lower()
        args = [a for a in re.split(r"[,\s]+", argstr.strip()) if a]
        vals = [float(x) for x in args] if args else []

        if fn == "matrix" and len(vals) == 6:
            a, b, c, d, e, f = vals
            T = np.array([[a, c, e], [b, d, f], [0.0, 0.0, 1.0]], dtype=np.float64)
            M = _mat_mul(M, T)
        elif fn == "translate" and len(vals) >= 1:
            tx = vals[0]
            ty = vals[1] if len(vals) >= 2 else 0.0
            M = _mat_mul(M, _mat_translate(tx, ty))
        elif fn == "scale" and len(vals) >= 1:
            sx = vals[0]
            sy = vals[1] if len(vals) >= 2 else sx
            M = _mat_mul(M, _mat_scale(sx, sy))
        elif fn == "rotate" and len(vals) >= 1:
            ang = vals[0]
            if len(vals) >= 3:
                cx, cy = vals[1], vals[2]
                M = _mat_mul(M, _mat_translate(cx, cy))
                M = _mat_mul(M, _mat_rotate(ang))
                M = _mat_mul(M, _mat_translate(-cx, -cy))
            else:
                M = _mat_mul(M, _mat_rotate(ang))
        else:
            pass

    return M


def apply_affine_xy(x: float, y: float, M: np.ndarray) -> Tuple[float, float]:
    v = M @ np.array([x, y, 1.0], dtype=np.float64)
    return float(v[0]), float(v[1])


# -------------------------
# SVG viewBox + 几何辅助函数
# -------------------------

def get_viewbox(svg_attrs: Dict[str, str]) -> Tuple[float, float, float, float]:
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


def ring_area_xy(coords: List[Tuple[float, float]]) -> float:
    a = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def approx_closed_rings_from_path(path: Path, tol_units: float, M: np.ndarray) -> List[List[Tuple[float, float]]]:
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
            x, y = float(z.real), float(z.imag)
            x, y = apply_affine_xy(x, y, M)
            pts.append((x, y))
        pts.append(pts[0])
        if len(pts) >= 4 and abs(ring_area_xy(pts)) > 1e-8:
            rings.append(pts)
    return rings


def build_polygons_from_rings(rings: List[List[Tuple[float, float]]]) -> List[Polygon]:
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
    poly: Polygon,
    vb_minx: float,
    vb_miny: float,
    vb_h: float,
    scale: float,
) -> Polygon:
    xys = np.asarray(poly.exterior.coords, dtype=np.float64)
    x = (xys[:, 0] - vb_minx) * scale
    y = (vb_h - (xys[:, 1] - vb_miny)) * scale
    shell = list(zip(x.tolist(), y.tolist()))

    holes = []
    for ring in poly.interiors:
        pts = np.asarray(ring.coords, dtype=np.float64)
        xh = (pts[:, 0] - vb_minx) * scale
        yh = (vb_h - (pts[:, 1] - vb_miny)) * scale
        holes.append(list(zip(xh.tolist(), yh.tolist())))

    p = Polygon(shell, holes)
    if not p.is_valid:
        p = p.buffer(0)
    return p


def extrude_poly_at_z(poly: Polygon, height: float, z0: float) -> trimesh.Trimesh:
    mesh = trimesh.creation.extrude_polygon(poly, height)
    mesh.apply_translation((0.0, 0.0, z0))
    return mesh


# -------------------------
# SVG遍历
# -------------------------

def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def iter_paths_with_cumulative_transform(svg_file: str) -> Tuple[List[Tuple[Path, Dict[str, str], np.ndarray]], Dict[str, str]]:
    tree = ET.parse(svg_file)
    root = tree.getroot()
    svg_attrs = dict(root.attrib)

    items: List[Tuple[Path, Dict[str, str], np.ndarray]] = []

    def walk(node: ET.Element, M_parent: np.ndarray) -> None:
        M_local = parse_transform_attr(node.attrib.get("transform", "") or "")
        M = _mat_mul(M_parent, M_local)

        tag = _strip_ns(node.tag).lower()
        if tag == "path":
            d = node.attrib.get("d", "")
            if d:
                try:
                    p = parse_path(d)
                    items.append((p, dict(node.attrib), M))
                except Exception as e:
                    sid = node.attrib.get("id", "")
                    hint = f" id={sid}" if sid else ""
                    logger.error(f"解析SVG path失败{hint}: {e}")

        for ch in list(node):
            walk(ch, M)

    walk(root, np.eye(3, dtype=np.float64))
    return items, svg_attrs


# -------------------------
# 主程序
# -------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="SVG -> 堆叠RGBW平面内容，导出为4个STL")
    ap.add_argument("--svg", default="test.svg", help="输入svg")
    ap.add_argument("--outdir", default="out_svg_stack", help="输出目录")
    ap.add_argument("--name", default="testsvg_stack", help="基础名称")
    ap.add_argument("--mode", default="rgbw")
    ap.add_argument("--width-mm", type=float, default=90.0, help="目标宽度（毫米）")
    ap.add_argument("--first-layer-height", type=float, default=0.12)
    ap.add_argument("--layer-height", type=float, default=0.08)
    ap.add_argument("--layers", type=int, default=5)
    ap.add_argument("--pattern", default="balanced", choices=["balanced", "grouped"], help="仅用于非暴力均匀搜索")

    # 默认为底面视图（与热床接触的面）
    ap.add_argument("--view", default="bottom", choices=["top", "bottom"])
    ap.add_argument("--backing", default="white", choices=["white", "black"])
    ap.add_argument("--phys", action="store_true")
    ap.add_argument("--samples", type=int, default=80000)
    ap.add_argument("--candidates", type=int, default=64)
    ap.add_argument("--brute-force-threshold", type=int, default=60000)
    ap.add_argument("--opacity-weight", type=float, default=-1.0, help="<0表示自动：仅当alpha != 255时启用")

    ap.add_argument("--tol-mm", type=float, default=0.2)
    ap.add_argument("--simplify-mm", type=float, default=0.15)
    ap.add_argument("--min-area-mm2", type=float, default=0.2)
    ap.add_argument("--alpha-background", default="white", choices=["white", "black"], help="用于RGBA alpha合成目标")
    ap.add_argument("--materials-json", default=None, help="materials.json路径")

    args = ap.parse_args()

    lib = planner.load_materials(args.materials_json)
    mode_key = args.mode.strip().lower()
    if mode_key not in lib.modes:
        raise SystemExit(f"未知模式：{args.mode}（可用：{sorted(lib.modes.keys())}）")

    os.makedirs(args.outdir, exist_ok=True)

    layer_heights = [float(args.first_layer_height)] + [float(args.layer_height)] * (int(args.layers) - 1)
    total_h = sum(layer_heights)
    logger.info(f"view={args.view} backing={args.backing} alpha_background={args.alpha_background}")
    logger.info(f"layers={args.layers} heights={layer_heights} total={total_h:.3f}mm")

    items, svg_attrs = iter_paths_with_cumulative_transform(args.svg)
    vb_minx, vb_miny, vb_w, vb_h = get_viewbox(svg_attrs)
    scale = args.width_mm / vb_w if vb_w != 0 else 1.0
    tol_units = args.tol_mm / scale

    # 按绘制顺序收集形状：每个形状 -> (poly_mm, rgba)
    shapes: List[Tuple[Polygon, RGBA]] = []
    for path, a, M in items:
        rgba = parse_fill_rgba(a)
        if rgba is None:
            continue
        rings = approx_closed_rings_from_path(path, tol_units=tol_units, M=M)
        polys_u = build_polygons_from_rings(rings)
        for p_u in polys_u:
            p_mm = transform_svg_units_to_mm(p_u, vb_minx, vb_miny, vb_h, scale)
            if p_mm.is_empty:
                continue
            p_mm = p_mm.buffer(0)
            if args.simplify_mm > 0:
                p_mm = p_mm.simplify(args.simplify_mm, preserve_topology=True).buffer(0)
            if p_mm.is_empty or p_mm.area < args.min_area_mm2:
                continue
            shapes.append((p_mm, rgba))

    if not shapes:
        raise SystemExit("SVG中未找到填充的闭合形状。")

    # 缓存每个RGBA的方案
    plan_cache: Dict[RGBA, planner.PlanResult] = {}

    # 每层维护已占用区域以防止重叠（画家算法顺序）
    occupied_by_layer: List[Optional[Polygon]] = [None for _ in range(int(args.layers))]

    # 桶：token -> (poly, layer_index)列表
    layer_polys: Dict[str, List[Tuple[Polygon, int]]] = {t: [] for t in ["R", "G", "B", "W"]}

    opacity_weight: Optional[float]
    if float(args.opacity_weight) < 0:
        opacity_weight = None
    else:
        opacity_weight = float(args.opacity_weight)

    for poly, rgba in reversed(shapes):
        if rgba not in plan_cache:
            if args.phys:
                plan_cache[rgba] = planner.solve_layers_phys(
                    rgba=rgba,
                    mode=mode_key,
                    layers=int(args.layers),
                    first_layer_height=float(args.first_layer_height),
                    layer_height=float(args.layer_height),
                    pattern=str(args.pattern),
                    alpha_background=str(args.alpha_background),
                    view=str(args.view),
                    backing=str(args.backing),
                    samples=int(args.samples),
                    candidates=int(args.candidates),
                    brute_force_threshold=int(args.brute_force_threshold),
                    opacity_weight=opacity_weight,
                    materials_json=args.materials_json,
                )
            else:
                plan_cache[rgba] = planner.solve_layers_fast(
                    rgba=rgba,
                    mode=mode_key,
                    layers=int(args.layers),
                    first_layer_height=float(args.first_layer_height),
                    layer_height=float(args.layer_height),
                    pattern=str(args.pattern),
                    alpha_background=str(args.alpha_background),
                    view=str(args.view),
                    backing=str(args.backing),
                    candidates=int(args.candidates),
                    brute_force_threshold=int(args.brute_force_threshold),
                    opacity_weight=opacity_weight,
                    materials_json=args.materials_json,
                )
            p0 = plan_cache[rgba]
            logger.info(f"rgba={rgba} seq={'-'.join(p0.sequence)} pred={p0.pred_rgb_srgb} loss={p0.loss:.6f}")

        seq = plan_cache[rgba].sequence

        # 每层画家算法：后面的形状覆盖前面的
        for li, token in enumerate(seq):
            if token not in layer_polys:
                continue
            occ = occupied_by_layer[li]
            piece = poly if occ is None else poly.difference(occ)
            if piece.is_empty:
                continue
            piece = piece.buffer(0)
            layer_polys[token].append((piece, li))
            occupied_by_layer[li] = piece if occ is None else unary_union([occ, piece]).buffer(0)

    # 通过每层并集然后挤压到正确Z位置来构建每个材料的网格
    z_offsets = []
    z = 0.0
    for h in layer_heights:
        z_offsets.append(z)
        z += float(h)

    for token in ["R", "G", "B", "W"]:
        per_layer: Dict[int, List[Polygon]] = {}
        for geom, li in layer_polys[token]:
            if isinstance(geom, Polygon):
                per_layer.setdefault(li, []).append(geom)
            elif isinstance(geom, MultiPolygon):
                for p in geom.geoms:
                    per_layer.setdefault(li, []).append(p)

        meshes: List[trimesh.Trimesh] = []
        for li, polys in per_layer.items():
            g = unary_union(polys).buffer(0)
            if args.simplify_mm > 0:
                g = g.simplify(args.simplify_mm, preserve_topology=True).buffer(0)
            if g.is_empty:
                continue

            parts = []
            if isinstance(g, Polygon):
                if g.area >= args.min_area_mm2:
                    parts = [g]
            else:
                parts = [p for p in g.geoms if p.area >= args.min_area_mm2]
            if not parts:
                continue
            g2 = unary_union(parts).buffer(0)

            if isinstance(g2, Polygon):
                meshes.append(extrude_poly_at_z(g2, layer_heights[li], z_offsets[li]))
            else:
                for p in g2.geoms:
                    meshes.append(extrude_poly_at_z(p, layer_heights[li], z_offsets[li]))

        if not meshes:
            logger.info(f"{token}: 空")
            continue
        mesh = trimesh.util.concatenate(meshes)
        out = os.path.join(args.outdir, f"{args.name}_{token}.stl")
        mesh.export(out)
        logger.info(f"{token}: 已写入 {out}")


if __name__ == "__main__":
    main()
