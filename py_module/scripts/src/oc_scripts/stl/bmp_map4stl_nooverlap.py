#!/usr/bin/env python3

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# bmp_map4stl_nooverlap.py
# 位图 -> 平面区域 -> 4色映射 -> 4个STL（A,B,C,D）
# 要求：相同位置，无体积重叠
# 修复：保留孔洞的区域多边形 + 4个输出间的布尔差集

import argparse
import os
from typing import Dict, List, Set, Optional

import numpy as np
from PIL import Image, ImageFilter
from skimage.measure import label as cc_label
from skimage import measure

from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import trimesh


def ensure_earcut():
    try:
        import mapbox_earcut  # noqa: F401
        return True
    except Exception:
        return False


def resample_to_width(img: Image.Image, width_mm: float, pixel_mm: float):
    w_px = max(1, int(round(width_mm / pixel_mm)))
    aspect = img.height / img.width if img.width else 1.0
    h_px = max(1, int(round(w_px * aspect)))
    img2 = img.resize((w_px, h_px), resample=Image.Resampling.LANCZOS)
    height_mm = h_px * pixel_mm
    return img2, pixel_mm, height_mm


def quantize_image(img_rgba: Image.Image, k: int) -> Image.Image:
    rgb = img_rgba.convert("RGB")
    pal = rgb.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    rgbq = pal.convert("RGB")
    a = img_rgba.getchannel("A")
    return Image.merge("RGBA", (*rgbq.split(), a))


def build_region_ids(rgba: np.ndarray, alpha_threshold: int):
    H, W, _ = rgba.shape
    a = rgba[..., 3].astype(np.uint8)
    printable = a >= alpha_threshold

    r = rgba[..., 0].astype(np.uint32)
    g = rgba[..., 1].astype(np.uint32)
    b = rgba[..., 2].astype(np.uint32)
    key = (r << 16) | (g << 8) | b

    reg = np.zeros((H, W), dtype=np.int32)
    next_id = 1

    keys = np.unique(key[printable]) if np.any(printable) else np.array([], dtype=np.uint32)
    for kv in keys:
        mask = printable & (key == kv)
        if not np.any(mask):
            continue
        cc = cc_label(mask, connectivity=1)
        ids = np.unique(cc)
        ids = ids[ids != 0]
        for cid in ids:
            reg[cc == cid] = next_id
            next_id += 1

    return reg, next_id - 1


def build_adjacency(reg: np.ndarray) -> Dict[int, Set[int]]:
    adj: Dict[int, Set[int]] = {}
    ids = np.unique(reg)
    ids = ids[ids != 0]
    for rid in ids:
        adj[int(rid)] = set()

    left = reg[:, :-1]
    right = reg[:, 1:]
    diff = (left != right) & (left != 0) & (right != 0)
    if np.any(diff):
        a = left[diff].ravel()
        b = right[diff].ravel()
        for u, v in zip(a, b):
            u = int(u); v = int(v)
            if u != v:
                adj[u].add(v); adj[v].add(u)

    up = reg[:-1, :]
    down = reg[1:, :]
    diff = (up != down) & (up != 0) & (down != 0)
    if np.any(diff):
        a = up[diff].ravel()
        b = down[diff].ravel()
        for u, v in zip(a, b):
            u = int(u); v = int(v)
            if u != v:
                adj[u].add(v); adj[v].add(u)

    return adj


def dsatur_4color(adj: Dict[int, Set[int]]) -> Dict[int, int]:
    nodes = list(adj.keys())
    degree = {u: len(adj[u]) for u in nodes}
    colored: Dict[int, int] = {}
    sat: Dict[int, Set[int]] = {u: set() for u in nodes}

    if not nodes:
        return colored

    u0 = max(nodes, key=lambda u: degree[u])
    colored[u0] = 0
    for v in adj[u0]:
        sat[v].add(0)

    while len(colored) < len(nodes):
        candidates = [u for u in nodes if u not in colored]
        u = max(candidates, key=lambda x: (len(sat[x]), degree[x]))

        used = {colored[v] for v in adj[u] if v in colored}
        c = None
        for k in range(4):
            if k not in used:
                c = k
                break
        if c is None:
            c = min(range(4), key=lambda k: sum((colored.get(v) == k) for v in adj[u]))

        colored[u] = c
        for v in adj[u]:
            if v not in colored:
                sat[v].add(c)

    return colored


def signed_area_xy(pts):
    a = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def mask_to_polygon_with_holes(mask: np.ndarray) -> Optional[Polygon]:
    contours = measure.find_contours(mask.astype(np.uint8), level=0.5)
    if not contours:
        return None

    rings = []
    for c in contours:
        if len(c) < 3:
            continue
        ring = [(float(p[1]), float(p[0])) for p in c]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        area = abs(signed_area_xy(ring))
        if area > 1e-6:
            rings.append((area, ring))

    if not rings:
        return None

    rings.sort(key=lambda x: x[0], reverse=True)
    outer = rings[0][1]
    outer_poly = Polygon(outer).buffer(0)
    if outer_poly.is_empty:
        return None

    holes = []
    for _, ring in rings[1:]:
        p = Polygon(ring).buffer(0)
        if p.is_empty:
            continue
        if outer_poly.contains(p.representative_point()):
            holes.append(ring)

    poly = Polygon(outer, holes).buffer(0)
    if poly.is_empty or poly.area <= 1e-6:
        return None
    return poly


def px_poly_to_mm(poly: Polygon, pixel_mm: float, height_px: int) -> Polygon:
    def conv(pt):
        x, y = pt
        return (x * pixel_mm, (height_px - y) * pixel_mm)

    ext = [conv(p) for p in poly.exterior.coords]
    holes = []
    for ring in poly.interiors:
        holes.append([conv(p) for p in ring.coords])

    out = Polygon(ext, holes).buffer(0)
    return out


def geom_to_polygons(geom) -> List[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]


def extrude_geom(geom, thickness_mm: float, simplify_mm: float, min_area_mm2: float) -> Optional[trimesh.Trimesh]:
    if geom is None or geom.is_empty:
        return None

    # 在几何级别简化
    g = geom.buffer(0)
    if simplify_mm > 0:
        g = g.simplify(simplify_mm, preserve_topology=True).buffer(0)

    parts = geom_to_polygons(g)
    meshes = []
    for part in parts:
        if part.is_empty or part.area < min_area_mm2:
            continue
        try:
            m = trimesh.creation.extrude_polygon(part, height=thickness_mm, engine="earcut")
            meshes.append(m)
        except Exception:
            continue

    if not meshes:
        return None

    merged = trimesh.util.concatenate(meshes)
    merged.process(validate=True)
    return merged


def main():
    ap = argparse.ArgumentParser(description="位图 -> 4色平面映射 -> 4个STL（A,B,C,D），相同位置，无重叠。")
    ap.add_argument("--in", dest="inp", required=True, help="输入位图（png/jpg/...）")
    ap.add_argument("--outdir", default="out_map4", help="输出目录")
    ap.add_argument("--name", default="map", help="基础名称")
    ap.add_argument("--width-mm", type=float, default=80.0, help="物理宽度（毫米）")
    ap.add_argument("--pixel-mm", type=float, default=0.35, help="采样间距（毫米）")
    ap.add_argument("--thickness-mm", type=float, default=0.4, help="拉伸厚度")
    ap.add_argument("--quant", type=int, default=16, help="颜色量化级别")
    ap.add_argument("--blur-sigma-px", type=float, default=0.0, help="可选模糊半径（像素）")
    ap.add_argument("--alpha-threshold", type=int, default=16, help="低于此值的Alpha为背景")
    ap.add_argument("--gap-mm", type=float, default=0.0, help="区域内缩（可选）。0保持精确平铺。")
    ap.add_argument("--simplify-mm", type=float, default=0.15, help="多边形简化容差")
    ap.add_argument("--min-area-mm2", type=float, default=1.0, help="丢弃微小区域")
    args = ap.parse_args()

    if not ensure_earcut():
        raise SystemExit("缺少三角化引擎mapbox_earcut。请将其添加到pixi并重新安装。")

    os.makedirs(args.outdir, exist_ok=True)

    img0 = Image.open(args.inp).convert("RGBA")
    img1, pixel_mm, height_mm = resample_to_width(img0, args.width_mm, args.pixel_mm)
    if args.blur_sigma_px > 0:
        img1 = img1.filter(ImageFilter.GaussianBlur(radius=args.blur_sigma_px))

    imgq = quantize_image(img1, k=max(2, args.quant))
    rgba = np.array(imgq, dtype=np.uint8)
    H, W, _ = rgba.shape

    reg, nreg = build_region_ids(rgba, alpha_threshold=args.alpha_threshold)
    logger.info(f"已加载 {args.inp}")
    logger.info(f"栅格 {W} x {H} 像素, 像素 {pixel_mm:.4f} 毫米, 物理尺寸 {args.width_mm:.2f} x {height_mm:.2f} 毫米")
    logger.info(f"区域数: {nreg}")
    if nreg == 0:
        logger.info("无可打印区域。")
        return

    adj = build_adjacency(reg)
    rid_to_col = dsatur_4color(adj)

    # 构建每色多边形列表（每区域保留孔洞）
    buckets_mm: Dict[int, List[Polygon]] = {0: [], 1: [], 2: [], 3: []}
    for rid, col in rid_to_col.items():
        mask = (reg == rid)
        poly_px = mask_to_polygon_with_holes(mask)
        if poly_px is None:
            continue
        pmm = px_poly_to_mm(poly_px, pixel_mm=pixel_mm, height_px=H)
        if pmm.is_empty or pmm.area < args.min_area_mm2:
            continue

        if args.gap_mm > 0:
            p2 = pmm.buffer(-args.gap_mm).buffer(0)
            if p2.is_empty or p2.area < args.min_area_mm2:
                continue
            pmm = p2

        buckets_mm[col].append(pmm)

    # 合并为4个几何体
    geoms: Dict[int, Optional[object]] = {}
    for c in range(4):
        geoms[c] = unary_union(buckets_mm[c]).buffer(0) if buckets_mm[c] else None

    # 硬性保证：无重叠体积（差集其他颜色）
    for c in range(4):
        if geoms[c] is None or geoms[c].is_empty:
            continue
        others = [geoms[d] for d in range(4) if d != c and geoms.get(d) is not None and (not geoms[d].is_empty)]
        if others:
            other_u = unary_union(others).buffer(0)
            geoms[c] = geoms[c].difference(other_u).buffer(0)

    keys = {0: "A", 1: "B", 2: "C", 3: "D"}
    for c in range(4):
        mesh = extrude_geom(geoms[c], thickness_mm=args.thickness_mm, simplify_mm=args.simplify_mm, min_area_mm2=args.min_area_mm2)
        if mesh is None:
            logger.info(f"{keys[c]}: 空")
            continue
        out = os.path.join(args.outdir, f"{args.name}_{keys[c]}.stl")
        mesh.export(out)
        logger.info(f"{keys[c]}: 已写入 {out}  三角面={len(mesh.faces)}")

    logger.info("完成。")


if __name__ == "__main__":
    main()
