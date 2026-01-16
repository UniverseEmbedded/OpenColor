#!/usr/bin/env python3
# svg4stl_vector.py
# Pure vector-region pipeline: SVG (paths with solid fill) -> 4 STL solids (R,G,B,W).
# No rasterization. No stacking. Each region extruded to thickness_mm.

import argparse
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

# deps
from svgpathtools import svg2paths2, Path  # pip install svgpathtools
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import trimesh  # pip install trimesh
# triangulation engine for trimesh extrusion: pip install mapbox_earcut

# ---------------------------
# Color utils
# ---------------------------

def srgb_to_linear01(x: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)

def parse_color_to_rgb255(s: str) -> Optional[Tuple[int, int, int]]:
    """
    Parse SVG color string -> (r,g,b) 0..255
    Supports:
      #RGB, #RRGGBB
      rgb(r,g,b)
      named: red, green, blue, white, black, etc (minimal set)
      none -> None
    """
    if not s:
        return None
    s = s.strip().lower()
    if s == "none":
        return None

    # hex
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

    # minimal named colors
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
    Extract fill color from attributes. Priority:
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
# Geometry building
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
    Nearest palette in linear RGB.
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
    Return viewBox (minx, miny, width, height) in SVG user units.
    If no viewBox, fallback to width/height attributes (best-effort).
    """
    vb = svg_attrs.get("viewBox") or svg_attrs.get("viewbox")
    if vb:
        parts = [p for p in re.split(r"[,\s]+", vb.strip()) if p]
        if len(parts) == 4:
            return (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))

    # fallback width/height (may include units like "px")
    def parse_len(v: str) -> float:
        if not v:
            return 100.0
        m = re.match(r"([0-9]*\.?[0-9]+)", v.strip())
        return float(m.group(1)) if m else 100.0

    w = parse_len(svg_attrs.get("width", "100"))
    h = parse_len(svg_attrs.get("height", "100"))
    return (0.0, 0.0, w, h)

def ring_area_xy(coords: List[Tuple[float, float]]) -> float:
    # signed area
    a = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        a += x1 * y2 - x2 * y1
    return 0.5 * a

def approx_closed_rings_from_path(path: Path, tol_units: float) -> List[List[Tuple[float, float]]]:
    """
    Convert SVG path into list of closed rings (each ring is list of (x,y) points, closed).
    We use svgpathtools continuous_subpaths and sample points along each closed subpath.
    """
    rings: List[List[Tuple[float, float]]] = []
    for sub in path.continuous_subpaths():
        if len(sub) == 0:
            continue
        # ensure closed
        if abs(sub.start - sub.end) > 1e-9:
            continue

        length = max(0.0, float(sub.length(error=1e-4)))
        # sample count based on tol
        n = int(np.ceil(length / max(1e-9, tol_units)))
        n = max(24, min(n, 20000))  # guardrails
        pts = []
        for i in range(n):
            t = i / n
            z = sub.point(t)
            pts.append((float(z.real), float(z.imag)))
        pts.append(pts[0])
        # drop degenerate
        if len(pts) >= 4 and abs(ring_area_xy(pts)) > 1e-8:
            rings.append(pts)
    return rings

def build_polygons_from_rings(rings: List[List[Tuple[float, float]]]) -> List[Polygon]:
    """
    Build polygons with holes via containment + orientation heuristic.
    Works well for common SVG export where outer rings and hole rings are separate subpaths.
    """
    if not rings:
        return []

    # prepare ring infos
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

    # sort by size descending so outers come first
    ring_infos.sort(key=lambda r: r["abs_area"], reverse=True)

    outers: List[Dict] = []
    holes_map: Dict[int, List[List[Tuple[float, float]]]] = {}

    for idx, r in enumerate(ring_infos):
        # find smallest outer that contains it
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
            # treat as hole if opposite orientation to container, else treat as nested outer
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
    Map SVG user coords to mm:
      x_mm = (x - vb_minx) * scale
      y_mm = (vb_h - (y - vb_miny)) * scale   # flip Y to make upward positive
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

    # filter + simplify
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
            # try cleaning again
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
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="Pure vector SVG -> 4 STL (RGBW). No rasterization. No stacking.")
    ap.add_argument("--in", dest="inp", required=True, help="Input SVG path")
    ap.add_argument("--outdir", default="out_rgbw", help="Output directory")
    ap.add_argument("--name", default="svg", help="Base output name")
    ap.add_argument("--width-mm", type=float, default=80.0, help="Physical width in mm")
    ap.add_argument("--thickness-mm", type=float, default=0.4, help="Extrusion thickness in mm")
    ap.add_argument("--tol-mm", type=float, default=0.2, help="Curve approx tolerance in mm (smaller = smoother, more segments)")
    ap.add_argument("--simplify-mm", type=float, default=0.15, help="Polygon simplify tolerance in mm")
    ap.add_argument("--min-area-mm2", type=float, default=0.8, help="Drop tiny polygons smaller than this area (mm^2)")
    args = ap.parse_args()

    if not args.inp.lower().endswith(".svg"):
        raise SystemExit("This script is SVG-only and does not rasterize. Provide an .svg file.")

    os.makedirs(args.outdir, exist_ok=True)

    paths, attrs, svg_attrs = svg2paths2(args.inp)

    vb_minx, vb_miny, vb_w, vb_h = get_viewbox(svg_attrs)
    if vb_w <= 0 or vb_h <= 0:
        raise SystemExit("Invalid SVG viewBox/size.")

    scale = args.width_mm / vb_w
    height_mm = vb_h * scale
    tol_units = args.tol_mm / scale

    print(f"Loaded {args.inp}")
    print(f"viewBox {vb_minx:g} {vb_miny:g} {vb_w:g} {vb_h:g}")
    print(f"scale {scale:.6f} mm per unit, physical {args.width_mm:.2f} x {height_mm:.2f} mm")
    print(f"curve tol {args.tol_mm:.3f} mm -> {tol_units:.6f} units")

    # Collect polygons per material
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

    print(f"paths total {len(paths)}, used {used}, skipped {skipped}")
    print("Note: transforms/clip/gradient/text are not supported in this minimal parser.")

    # Extrude and export
    for k in ["R", "G", "B", "W"]:
        mesh = extrude_union_to_mesh(
            buckets[k],
            thickness_mm=args.thickness_mm,
            simplify_mm=args.simplify_mm,
            min_area_mm2=args.min_area_mm2,
        )
        if mesh is None:
            print(f"{k}: empty")
            continue
        out = os.path.join(args.outdir, f"{args.name}_{k}.stl")
        mesh.export(out)
        print(f"{k}: wrote {out}  tris={len(mesh.faces)}")

    print("Done.")


if __name__ == "__main__":
    main()
