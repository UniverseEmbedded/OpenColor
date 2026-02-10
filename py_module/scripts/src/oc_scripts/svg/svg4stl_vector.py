#!/usr/bin/env python3

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# svg4stl_vector.py
# 纯矢量区域流程: SVG（纯色填充路径） -> 4个STL实体（R,G,B,W）
# 无栅格化。无堆叠。每个区域拉伸到thickness_mm厚度。

import argparse
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

# 依赖
from svgpathtools import svg2paths2, Path  # pip install svgpathtools
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import trimesh  # pip install trimesh
# trimesh拉伸的三角化引擎: pip install mapbox_earcut

# ---------------------------
# 颜色工具
# ---------------------------

def srgb_to_linear01(x: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)

def parse_color_to_rgb255(s: str) -> Optional[Tuple[int, int, int]]:
    """
    解析SVG颜色字符串 -> (r,g,b) 0..255
    支持：
      #RGB, #RRGGBB
      rgb(r,g,b)
      命名颜色: red, green, blue, white, black等（最小集合）
      none -> None
    """
    if not s:
        return None
    s = s.strip().lower()
    if s == "none":
        return None

    # 十六进制
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

    # rgb(r,g,b)
    m = re.match(r"rgb\s*\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)", s)
    if m:
        r, g, b = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return (r, g, b)

    # 最小命名颜色集合
    named = {
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
    }
    return named.get(s, None)

def parse_fill_from_attrs(attrs: Dict[str, str]) -> Optional[Tuple[int, int, int]]:
    """
    从属性中提取填充颜色。优先级：
      attrs['fill'] -> style 'fill: ...' -> None
    """
    fill = attrs.get("fill", "") or ""
    rgb = parse_color_to_rgb255(fill)
    if rgb is not None:
        return rgb

    style = attrs.get("style", "") or ""
    # style: "fill:#RRGGBB; stroke:none; ..."
    m = re.search(r"fill\s*:\s*([^;]+)", style, re.IGNORECASE)
    if m:
        return parse_color_to_rgb255(m.group(1).strip())
    return None

# ---------------------------
# 几何构建
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

def classify_rgb_to_rgbw(rgb255: Tuple[int, int, int]) -> str:
    """
    线性RGB中最近的调色板
    """
    rgb = np.array(rgb255, dtype=np.float32) / 255.0
    rgb_lin = srgb_to_linear01(rgb)

    keys = ["R", "G", "B", "W"]
    pal = np.array([DEFAULT_RGBW[k].rgb255 for k in keys], dtype=np.float32) / 255.0
    pal_lin = srgb_to_linear01(pal)

    d2 = np.sum((pal_lin - rgb_lin[None, :]) ** 2, axis=1)
    return keys[int(np.argmin(d2))]

def get_viewbox(svg_attrs: Dict[str, str]) -> Tuple[float, float, float, float]:
    """
    返回viewBox（minx, miny, width, height）以SVG用户单位
    如果没有viewBox，回退到width/height属性（尽力而为）
    """
    vb = svg_attrs.get("viewBox") or svg_attrs.get("viewbox")
    if vb:
        parts = [p for p in re.split(r"[,\s]+", vb.strip()) if p]
        if len(parts) == 4:
            return (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))

    # 回退width/height（可能包含单位如"px"）
    def parse_len(v: str) -> float:
        if not v:
            return 100.0
        m = re.match(r"([0-9]*\.?[0-9]+)", v.strip())
        return float(m.group(1)) if m else 100.0

    w = parse_len(svg_attrs.get("width", "100"))
    h = parse_len(svg_attrs.get("height", "100"))
    return (0.0, 0.0, w, h)

def ring_area_xy(coords: List[Tuple[float, float]]) -> float:
    # 有符号面积
    a = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        a += x1 * y2 - x2 * y1
    return 0.5 * a

def approx_closed_rings_from_path(path: Path, tol_units: float) -> List[List[Tuple[float, float]]]:
    """
    将SVG路径转换为闭合环列表（每个环是(x,y)点列表，闭合）
    我们使用svgpathtools的continuous_subpaths并沿每个闭合子路径采样点
    """
    rings: List[List[Tuple[float, float]]] = []
    for sub in path.continuous_subpaths():
        if len(sub) == 0:
            continue
        # 确保闭合
        if abs(sub.start - sub.end) > 1e-9:
            continue

        length = max(0.0, float(sub.length(error=1e-4)))
        # 基于容差的采样计数
        n = int(np.ceil(length / max(1e-9, tol_units)))
        n = max(24, min(n, 20000))  # 保护限制
        pts = []
        for i in range(n):
            t = i / n
            z = sub.point(t)
            pts.append((float(z.real), float(z.imag)))
        pts.append(pts[0])
        # 丢弃退化情况
        if len(pts) >= 4 and abs(ring_area_xy(pts)) > 1e-8:
            rings.append(pts)
    return rings

def build_polygons_from_rings(rings: List[List[Tuple[float, float]]]) -> List[Polygon]:
    """
    通过包含关系+方向启发式构建带孔的多边形
    适用于常见SVG导出，其中外环和孔环是独立的子路径
    """
    if not rings:
        return []

    # 准备环信息
    ring_infos = []
    for pts in rings:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.area <= 1e-10:
            continue
        area_signed = ring_area_xy(pts)
        ring_infos.append({
            "pts": pts,
            "poly": poly,
            "abs_area": abs(area_signed),
            "sign": 1 if area_signed >= 0 else -1,
        })

    if not ring_infos:
        return []

    # 按大小降序排序，使外环在前
    ring_infos.sort(key=lambda r: r["abs_area"], reverse=True)

    outers: List[Dict] = []
    holes_map: Dict[int, List[List[Tuple[float, float]]]] = {}

    for idx, r in enumerate(ring_infos):
        # 查找包含它的最小外环
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
            # 如果与容器方向相反则视为孔，否则视为嵌套外环
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
        scale_mm_per_unit: float,
) -> Polygon:
    """
    将SVG用户坐标映射到毫米：
      x_mm = (x - vb_minx) * scale
      y_mm = (vb_h - (y - vb_miny)) * scale   # 翻转Y使向上为正
    """
    def conv(pt):
        x, y = pt
        x_mm = (x - vb_minx) * scale_mm_per_unit
        y_mm = (vb_h - (y - vb_miny)) * scale_mm_per_unit
        return (x_mm, y_mm)

    ext = [conv(p) for p in poly.exterior.coords]
    holes = []
    for ring in poly.interiors:
        holes.append([conv(p) for p in ring.coords])

    out = Polygon(ext, holes)
    if not out.is_valid:
        out = out.buffer(0)
    return out

def extrude_union_to_mesh(polys_mm: List[Polygon], thickness_mm: float, simplify_mm: float, min_area_mm2: float) -> Optional[trimesh.Trimesh]:
    if not polys_mm:
        return None

    # 过滤+简化
    cleaned = []
    for p in polys_mm:
        if p.is_empty or p.area < min_area_mm2:
            continue
        pp = p.buffer(0)
        if simplify_mm > 0:
            pp = pp.simplify(simplify_mm, preserve_topology=True)
        pp = pp.buffer(0)
        if not pp.is_empty and pp.area >= min_area_mm2:
            cleaned.append(pp)

    if not cleaned:
        return None

    geom = unary_union(cleaned)
    if geom.is_empty:
        return None

    parts = []
    if isinstance(geom, Polygon):
        parts = [geom]
    elif isinstance(geom, MultiPolygon):
        parts = list(geom.geoms)
    else:
        parts = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]

    meshes = []
    for part in parts:
        if part.is_empty or part.area < min_area_mm2:
            continue
        try:
            m = trimesh.creation.extrude_polygon(part, height=thickness_mm, engine="earcut")
            meshes.append(m)
        except Exception:
            # 再次尝试清理
            pp = part.buffer(0)
            if pp.is_empty:
                continue
            try:
                m = trimesh.creation.extrude_polygon(pp, height=thickness_mm, engine="earcut")
                meshes.append(m)
            except Exception:
                continue

    if not meshes:
        return None

    merged = trimesh.util.concatenate(meshes)
    merged.process(validate=True)
    return merged

# ---------------------------
# 主程序
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="纯矢量SVG -> 4个STL（RGBW）。无栅格化。无堆叠。")
    ap.add_argument("--in", dest="inp", required=True, help="输入SVG路径")
    ap.add_argument("--outdir", default="out_rgbw", help="输出目录")
    ap.add_argument("--name", default="svg", help="基础输出名称")
    ap.add_argument("--width-mm", type=float, default=80.0, help="物理宽度（毫米）")
    ap.add_argument("--thickness-mm", type=float, default=0.4, help="拉伸厚度（毫米）")
    ap.add_argument("--tol-mm", type=float, default=0.2, help="曲线近似容差（毫米）（越小=越平滑，段数越多）")
    ap.add_argument("--simplify-mm", type=float, default=0.15, help="多边形简化容差（毫米）")
    ap.add_argument("--min-area-mm2", type=float, default=0.8, help="丢弃小于此面积的微小多边形（平方毫米）")
    args = ap.parse_args()

    if not args.inp.lower().endswith(".svg"):
        raise SystemExit("此脚本仅支持SVG且不进行栅格化。请提供.svg文件。")

    os.makedirs(args.outdir, exist_ok=True)

    paths, attrs, svg_attrs = svg2paths2(args.inp)

    vb_minx, vb_miny, vb_w, vb_h = get_viewbox(svg_attrs)
    if vb_w <= 0 or vb_h <= 0:
        raise SystemExit("无效的SVG viewBox/尺寸。")

    scale = args.width_mm / vb_w
    height_mm = vb_h * scale
    tol_units = args.tol_mm / scale

    logger.info(f"已加载 {args.inp}")
    logger.info(f"viewBox {vb_minx:g} {vb_miny:g} {vb_w:g} {vb_h:g}")
    logger.info(f"比例 {scale:.6f} 毫米/单位, 物理尺寸 {args.width_mm:.2f} x {height_mm:.2f} 毫米")
    logger.info(f"曲线容差 {args.tol_mm:.3f} 毫米 -> {tol_units:.6f} 单位")

    # 按材料收集多边形
    buckets: Dict[str, List[Polygon]] = {"R": [], "G": [], "B": [], "W": []}
    skipped = 0
    used = 0

    for p, a in zip(paths, attrs):
        rgb = parse_fill_from_attrs(a)
        if rgb is None:
            skipped += 1
            continue

        mat = classify_rgb_to_rgbw(rgb)

        rings = approx_closed_rings_from_path(p, tol_units=tol_units)
        if not rings:
            skipped += 1
            continue

        polys_units = build_polygons_from_rings(rings)
        if not polys_units:
            skipped += 1
            continue

        for poly_u in polys_units:
            poly_mm = transform_svg_units_to_mm(poly_u, vb_minx, vb_miny, vb_h, scale)
            if not poly_mm.is_empty:
                buckets[mat].append(poly_mm)
                used += 1

    logger.info(f"路径总数 {len(paths)}, 已使用 {used}, 已跳过 {skipped}")
    logger.info("注意：此最小化解析器不支持变换/裁剪/渐变/文本。")

    # 拉伸并导出
    for k in ["R", "G", "B", "W"]:
        mesh = extrude_union_to_mesh(
            buckets[k],
            thickness_mm=args.thickness_mm,
            simplify_mm=args.simplify_mm,
            min_area_mm2=args.min_area_mm2,
        )
        if mesh is None:
            logger.info(f"{k}: 空")
            continue
        out = os.path.join(args.outdir, f"{args.name}_{k}.stl")
        mesh.export(out)
        logger.info(f"{k}: 已写入 {out}  三角面={len(mesh.faces)}")

    logger.info("完成。")


if __name__ == "__main__":
    main()
