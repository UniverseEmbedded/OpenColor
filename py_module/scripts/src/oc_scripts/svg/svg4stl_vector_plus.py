#!/usr/bin/env python3

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# svg4stl_vector_plus.py
# 纯矢量区域流程：SVG -> 4个STL实体（R,G,B,W）。
# 相比原版的改进：
# - 支持常见SVG变换属性：translate/scale/rotate/matrix
# - 严格调色板模式（默认）：只接受精确的RGBW填充颜色
# - 可选的最近调色板分类（默认关闭）
# - 对不支持的功能有更明确的警告

import argparse
import json
import os
import re
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import trimesh  # pip install trimesh
# trimesh挤压的三角剖分引擎：pip install mapbox_earcut

# 依赖
# pip install svgpathtools
from svgpathtools import Path, parse_path  # type: ignore


# ---------------------------
# 颜色工具
# ---------------------------


def srgb_to_linear01(x: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)


def parse_color_to_rgb255(s: str) -> Optional[Tuple[int, int, int]]:
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
    fill = attrs.get("fill", "") or ""
    rgb = parse_color_to_rgb255(fill)
    if rgb is not None:
        return rgb
    style = attrs.get("style", "") or ""
    m = re.search(r"fill\s*:\s*([^;]+)", style, re.IGNORECASE)
    if m:
        return parse_color_to_rgb255(m.group(1).strip())
    return None


def _has_fill_spec(attrs: Dict[str, str]) -> bool:
    if "fill" in attrs:
        return True
    style = attrs.get("style", "") or ""
    return re.search(r"fill\s*:\s*", style, re.IGNORECASE) is not None


def _local_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _iter_svg_paths_with_group_transform(
    svg_path: str,
) -> Tuple[
    Dict[str, str],
    List[Tuple[Path, Dict[str, str], np.ndarray, bool, Optional[Tuple[int, int, int]]]],
]:
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
        M_here = _mat_mul(M_parent, M_local)

        fill_set2 = fill_set
        fill_value2 = fill_value
        if _has_fill_spec(attrs):
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


# ---------------------------
# 调色板
# ---------------------------


@dataclass(frozen=True)
class Material:
    key: str
    rgb255: Tuple[int, int, int]


DEFAULT_RGBW = {
    "R": Material("R", (255, 0, 0)),
    "G": Material("G", (0, 255, 0)),
    "B": Material("B", (0, 0, 255)),
    "W": Material("W", (255, 255, 255)),
}


def classify_rgb_to_rgbw_nearest(rgb255: Tuple[int, int, int]) -> str:
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
    # tol=0表示精确匹配；tol>0允许小差异（例如导出器有扰动时）
    for k, mat in DEFAULT_RGBW.items():
        r0, g0, b0 = mat.rgb255
        r, g, b = rgb255
        if abs(r - r0) <= tol and abs(g - g0) <= tol and abs(b - b0) <= tol:
            return k
    return None


# ---------------------------
# SVG viewBox + 变换
# ---------------------------


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


def _mat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a @ b


def _mat_translate(tx: float, ty: float) -> np.ndarray:
    return np.array([[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]], dtype=np.float64)


def _mat_scale(sx: float, sy: float) -> np.ndarray:
    return np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def _mat_rotate(deg: float) -> np.ndarray:
    th = math.radians(deg)
    c = math.cos(th)
    s = math.sin(th)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def parse_transform_attr(s: str) -> np.ndarray:
    """
    将SVG变换列表的最小子集解析为3x3仿射矩阵。
    支持：matrix(a,b,c,d,e,f), translate(tx,ty), scale(sx,sy), rotate(angle[,cx,cy])
    SVG中的顺序是左到右应用；对于列向量我们相应地进行右乘。
    我们构建矩阵M使得 p' = M * p。
    """
    if not s:
        return np.eye(3, dtype=np.float64)

    s = s.strip()
    M = np.eye(3, dtype=np.float64)

    # 标记化变换函数
    # 例如 "translate(10,20) rotate(30) scale(2)"
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
            # 忽略未知变换
            pass

    return M


def apply_affine_to_points(
    pts: List[Tuple[float, float]], M: np.ndarray
) -> List[Tuple[float, float]]:
    if M is None:
        return pts
    out: List[Tuple[float, float]] = []
    for x, y in pts:
        v = M @ np.array([x, y, 1.0], dtype=np.float64)
        out.append((float(v[0]), float(v[1])))
    return out


# ---------------------------
# 几何构建
# ---------------------------


def ring_area_xy(coords: List[Tuple[float, float]]) -> float:
    a = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def approx_closed_rings_from_path(
    path: Path, tol_units: float, M: np.ndarray
) -> List[List[Tuple[float, float]]]:
    rings: List[List[Tuple[float, float]]] = []
    for sub in path.continuous_subpaths():
        if len(sub) == 0:
            continue
        if abs(sub.start - sub.end) > 1e-9:
            # 填充区域只支持闭合形状
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

        # 应用变换
        pts = apply_affine_to_points(pts, M)

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
            # 相反方向 => 该外轮廓的孔洞，否则视为嵌套外轮廓
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
    # 将SVG坐标映射到毫米并翻转Y轴，使+Y在打印空间中为"向上"
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
    # trimesh.creation.extrude_polygon 支持Polygon；对于MultiPolygon请在外面做并集
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
    if not polys:
        return None
    g = unary_union(polys)
    if g.is_empty:
        return None
    # 清理
    g = g.buffer(0)
    if simplify_mm > 0:
        g = g.simplify(simplify_mm, preserve_topology=True)
        g = g.buffer(0)
    # 过滤微小部分
    if isinstance(g, MultiPolygon):
        parts = [p for p in g.geoms if p.area >= min_area_mm2]
        if not parts:
            return None
        g = unary_union(parts).buffer(0)
    else:
        if g.area < min_area_mm2:
            return None
    return g


# ---------------------------
# 主程序
# ---------------------------


def main():
    ap = argparse.ArgumentParser(
        description="SVG -> 4个STL（R,G,B,W），按矢量区域（无堆叠）。"
    )
    ap.add_argument("svg", help="输入SVG")
    ap.add_argument("--outdir", default="out_svg4stl", help="输出目录")
    ap.add_argument("--name", default=None, help="基础名称")
    ap.add_argument("--width-mm", type=float, default=80.0, help="目标宽度（毫米）")
    ap.add_argument(
        "--thickness-mm", type=float, default=0.8, help="所有区域的挤压厚度"
    )
    ap.add_argument(
        "--tol-mm",
        type=float,
        default=0.2,
        help="采样容差（毫米等效，控制多边形复杂度）",
    )
    ap.add_argument(
        "--simplify-mm", type=float, default=0.15, help="shapely简化容差（毫米）"
    )
    ap.add_argument(
        "--min-area-mm2",
        type=float,
        default=0.2,
        help="丢弃小于此面积（平方毫米）的微小岛屿",
    )
    ap.add_argument(
        "--strict-palette",
        action="store_true",
        help="只接受精确的RGBW填充颜色（测试推荐）",
    )
    ap.add_argument(
        "--palette-tol", type=int, default=0, help="严格匹配的RGB容差（0-255每通道）"
    )
    ap.add_argument(
        "--nearest-palette",
        action="store_true",
        help="将任意填充分类到最近的RGBW（谨慎使用）",
    )
    ap.add_argument("--export-metadata", action="store_true")
    args = ap.parse_args()

    if args.nearest_palette and args.strict_palette:
        logger.error(
            "错误：请只选择 --strict-palette 或 --nearest-palette 之一，不要同时选择。"
        )
        raise SystemExit(2)

    os.makedirs(args.outdir, exist_ok=True)
    base = args.name or os.path.splitext(os.path.basename(args.svg))[0]

    svg_attrs, paths = _iter_svg_paths_with_group_transform(args.svg)
    vb_minx, vb_miny, vb_w, vb_h = get_viewbox(svg_attrs)
    scale = args.width_mm / vb_w if vb_w != 0 else 1.0

    # SVG单位中的采样容差
    tol_units = args.tol_mm / scale

    buckets: Dict[str, List[Polygon]] = {"R": [], "G": [], "B": [], "W": []}
    skipped = 0
    warned_unsupported = False
    regions_meta = []
    region_id = 0

    for path, a, M, fill_set, fill_value in paths:
        if _has_fill_spec(a):
            fill = parse_fill_from_attrs(a)
        else:
            fill = fill_value if fill_set else None
        if fill is None:
            skipped += 1
            continue

        # 分类
        key: Optional[str]
        if args.strict_palette:
            key = classify_rgb_to_rgbw_strict(fill, tol=args.palette_tol)
            if key is None:
                skipped += 1
                continue
        elif args.nearest_palette:
            key = classify_rgb_to_rgbw_nearest(fill)
        else:
            # 默认行为：严格，但有 helpful 警告
            key = classify_rgb_to_rgbw_strict(fill, tol=args.palette_tol)
            if key is None:
                if not warned_unsupported:
                    logger.warning(
                        "警告：发现非RGBW填充。使用 --nearest-palette 自动分类或 --strict-palette 跳过它们。"
                    )
                    warned_unsupported = True
                skipped += 1
                continue

        rings = approx_closed_rings_from_path(path, tol_units=tol_units, M=M)
        polys_u = build_polygons_from_rings(rings)

        for p_u in polys_u:
            p_mm = transform_svg_units_to_mm(p_u, vb_minx, vb_miny, vb_h, scale)
            if p_mm.is_empty or p_mm.area < args.min_area_mm2:
                continue
            buckets[key].append(p_mm)
            region_id += 1
            regions_meta.append(
                {
                    "region_id": int(region_id),
                    "fill_rgb255": [int(fill[0]), int(fill[1]), int(fill[2])],
                    "class": str(key),
                    "area_mm2": float(p_mm.area),
                }
            )

    for key in ["R", "G", "B", "W"]:
        g = union_clean(
            buckets[key], simplify_mm=args.simplify_mm, min_area_mm2=args.min_area_mm2
        )
        if g is None:
            logger.info(f"{key}: 空")
            continue
        mesh = extrude_polygon_to_mesh(g, args.thickness_mm)
        if mesh is None:
            logger.error(f"{key}: 挤压失败（检查shapely有效性/earcut安装）")
            continue
        out = os.path.join(args.outdir, f"{base}_{key}.stl")
        mesh.export(out)
        logger.info(f"{key}: 已写入 {out}")

    if args.export_metadata:
        meta = {
            "schema_version": 1,
            "script": os.path.basename(__file__),
            "input": {"svg": os.path.abspath(args.svg)},
            "params": {
                "outdir": os.path.abspath(args.outdir),
                "name": args.name,
                "width_mm": float(args.width_mm),
                "thickness_mm": float(args.thickness_mm),
                "tol_mm": float(args.tol_mm),
                "simplify_mm": float(args.simplify_mm),
                "min_area_mm2": float(args.min_area_mm2),
                "strict_palette": bool(args.strict_palette),
                "palette_tol": int(args.palette_tol),
                "nearest_palette": bool(args.nearest_palette),
            },
            "stats": {"skipped_paths": int(skipped)},
            "regions": regions_meta,
            "outputs": {
                "R": os.path.abspath(os.path.join(args.outdir, f"{base}_R.stl")),
                "G": os.path.abspath(os.path.join(args.outdir, f"{base}_G.stl")),
                "B": os.path.abspath(os.path.join(args.outdir, f"{base}_B.stl")),
                "W": os.path.abspath(os.path.join(args.outdir, f"{base}_W.stl")),
            },
        }
        meta_path = os.path.join(args.outdir, f"{base}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        logger.info(f"元数据：已写入 {meta_path}")

    if skipped:
        logger.info(f"跳过了 {skipped} 个路径（无填充/非调色板填充/未闭合）。")
    logger.info(
        "注意：clipPath、渐变、文本、描边不会被展开。导出为带纯色填充的路径以获得最佳效果。"
    )


if __name__ == "__main__":
    main()
