#!/usr/bin/env python3
# bmp_map4stl_nooverlap_plus.py
# Bitmap -> 4 STL solids (R,G,B,W) using vector-region extraction (no stacking, no overlap).
# Improvements vs your original:
# - Fix: mask_to_polygon no longer drops extra outer contours; returns MultiPolygon
# - Speed: per-region bbox crop before contour extraction
# - Debug: optional debug PNG of 4-color assignment

import argparse
import json
import os
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageFilter

from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import trimesh  # pip install trimesh
# triangulation engine for trimesh extrusion: pip install mapbox_earcut

# pip install scikit-image scikit-learn
from skimage.measure import find_contours  # type: ignore
from sklearn.cluster import MiniBatchKMeans  # type: ignore


# ---------------------------
# Helpers
# ---------------------------

def srgb_to_linear01(x: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)

def classify_rgba_to_rgbw_nearest(rgb255: Tuple[int, int, int]) -> str:
    # nearest in linear RGB
    pal = {
        "R": (255, 0, 0),
        "G": (0, 255, 0),
        "B": (0, 0, 255),
        "W": (255, 255, 255),
    }
    rgb = np.array(rgb255, dtype=np.float32) / 255.0
    rgb_lin = srgb_to_linear01(rgb)
    keys = ["R", "G", "B", "W"]
    pal_lin = srgb_to_linear01(np.array([pal[k] for k in keys], dtype=np.float32) / 255.0)
    d2 = np.sum((pal_lin - rgb_lin[None, :]) ** 2, axis=1)
    return keys[int(np.argmin(d2))]

def connected_components_4n(mask: np.ndarray) -> np.ndarray:
    # returns labels 0..K, 0 means background
    H, W = mask.shape
    lbl = np.zeros((H, W), dtype=np.int32)
    cur = 0
    stack: List[Tuple[int, int]] = []
    for y in range(H):
        for x in range(W):
            if not mask[y, x] or lbl[y, x] != 0:
                continue
            cur += 1
            lbl[y, x] = cur
            stack.append((y, x))
            while stack:
                yy, xx = stack.pop()
                for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ny, nx = yy+dy, xx+dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and lbl[ny, nx] == 0:
                        lbl[ny, nx] = cur
                        stack.append((ny, nx))
    return lbl

def build_region_adjacency(region_id: np.ndarray, n_regions: int) -> List[List[int]]:
    H, W = region_id.shape
    adj = [set() for _ in range(n_regions + 1)]
    # 4-neighbor boundary adjacency
    for y in range(H):
        for x in range(W):
            a = region_id[y, x]
            if a == 0:
                continue
            if x + 1 < W:
                b = region_id[y, x + 1]
                if b != 0 and b != a:
                    adj[a].add(b); adj[b].add(a)
            if y + 1 < H:
                b = region_id[y + 1, x]
                if b != 0 and b != a:
                    adj[a].add(b); adj[b].add(a)
    return [sorted(list(s)) for s in adj]

def dsatur_4color(adj: List[List[int]], n_regions: int) -> Dict[int, int]:
    # DSATUR graph coloring with 4 colors (0..3)
    colors = {i: -1 for i in range(1, n_regions + 1)}
    sat = {i: 0 for i in range(1, n_regions + 1)}
    deg = {i: len(adj[i]) for i in range(1, n_regions + 1)}

    def sat_deg(i: int) -> Tuple[int, int]:
        return (sat[i], deg[i])

    while True:
        uncolored = [i for i in range(1, n_regions + 1) if colors[i] < 0]
        if not uncolored:
            break
        v = max(uncolored, key=sat_deg)

        used = set()
        for u in adj[v]:
            c = colors[u]
            if c >= 0:
                used.add(c)

        # pick smallest available
        for c in range(4):
            if c not in used:
                colors[v] = c
                break
        if colors[v] < 0:
            # fallback (should be rare)
            colors[v] = 0

        # update saturation of neighbors
        for u in adj[v]:
            if colors[u] >= 0:
                continue
            neighbor_colors = set(colors[w] for w in adj[u] if colors[w] >= 0)
            sat[u] = len(neighbor_colors)

    return colors

def _rings_from_mask(mask: np.ndarray, simplify_tol: float) -> List[np.ndarray]:
    # contours at 0.5, return list of Nx2 arrays in (x,y) pixel coords
    rings = []
    for c in find_contours(mask.astype(np.uint8), 0.5):
        if c.shape[0] < 6:
            continue
        # find_contours returns (row, col) floats; convert to (x,y)
        pts = np.stack([c[:, 1], c[:, 0]], axis=1)
        # close
        if np.linalg.norm(pts[0] - pts[-1]) > 1e-6:
            pts = np.vstack([pts, pts[0]])
        # basic simplification by skipping points (cheap) before shapely simplify
        if simplify_tol > 0 and pts.shape[0] > 2000:
            step = max(1, int(simplify_tol))
            pts = pts[::step]
            if np.linalg.norm(pts[0] - pts[-1]) > 1e-6:
                pts = np.vstack([pts, pts[0]])
        rings.append(pts)
    return rings

def mask_to_multipolygon(mask: np.ndarray, min_area: float) -> MultiPolygon:
    """
    Convert a binary mask to (Multi)Polygon without silently dropping extra components.
    Strategy:
      - extract all contour rings
      - build polygons for rings
      - assign holes by containment
      - return MultiPolygon
    """
    rings = _rings_from_mask(mask, simplify_tol=0.0)
    polys = []
    ring_infos = []

    for pts in rings:
        p = Polygon(pts)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or p.area < min_area:
            continue
        ring_infos.append((p, pts))

    if not ring_infos:
        return MultiPolygon([])

    # sort by area desc
    ring_infos.sort(key=lambda t: t[0].area, reverse=True)

    outers: List[Tuple[Polygon, np.ndarray]] = []
    holes_map: Dict[int, List[np.ndarray]] = {}

    for p, pts in ring_infos:
        container_idx = None
        container_area = None
        for i, (op, _) in enumerate(outers):
            if op.contains(p):
                if container_area is None or op.area < container_area:
                    container_idx = i
                    container_area = op.area
        if container_idx is None:
            outers.append((p, pts))
        else:
            holes_map.setdefault(container_idx, []).append(pts)

    out_polys = []
    for i, (op, opts) in enumerate(outers):
        holes = []
        for hpts in holes_map.get(i, []):
            holes.append([(float(x), float(y)) for x, y in hpts])
        pp = Polygon([(float(x), float(y)) for x, y in opts], holes)
        if not pp.is_valid:
            pp = pp.buffer(0)
        if pp.is_empty or pp.area < min_area:
            continue
        out_polys.append(pp)

    if not out_polys:
        return MultiPolygon([])
    g = unary_union(out_polys)
    if g.is_empty:
        return MultiPolygon([])
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    return g

def extrude_geom_to_mesh(geom, height_mm: float, pixel_mm: float):
    if geom is None or geom.is_empty:
        return None
    # convert pixel coords to mm
    # shapely scale manually by multiplying coords
    def scale_poly(p: Polygon) -> Polygon:
        ext = [(x * pixel_mm, y * pixel_mm) for x, y in p.exterior.coords]
        holes = [[(x * pixel_mm, y * pixel_mm) for x, y in r.coords] for r in p.interiors]
        q = Polygon(ext, holes)
        if not q.is_valid:
            q = q.buffer(0)
        return q

    if isinstance(geom, Polygon):
        geom_mm = scale_poly(geom)
    else:
        parts = []
        for p in geom.geoms:
            parts.append(scale_poly(p))
        geom_mm = unary_union(parts).buffer(0)

    try:
        return trimesh.creation.extrude_polygon(geom_mm, height_mm)
    except Exception:
        return None

def save_debug_png(color_map: np.ndarray, out_path: str):
    # color_map is HxW with values 0..3
    # 0:R 1:G 2:B 3:W (just for visualization)
    palette = np.array([
        [255, 0, 0],
        [0, 255, 0],
        [0, 0, 255],
        [255, 255, 255],
    ], dtype=np.uint8)
    img = palette[color_map]
    Image.fromarray(img, mode="RGB").save(out_path)


# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="Bitmap -> 4 STL (R,G,B,W) by vector regions (no stacking, no overlap).")
    ap.add_argument("image", help="input bitmap (png/jpg)")
    ap.add_argument("--outdir", default="out_bmp4stl", help="output directory")
    ap.add_argument("--name", default=None, help="base name")
    ap.add_argument("--width-mm", type=float, default=80.0, help="target physical width in mm")
    ap.add_argument("--pixel-mm", type=float, default=0.5, help="sampling size in mm per pixel")
    ap.add_argument("--thickness-mm", type=float, default=0.8, help="extrude thickness for all regions")
    ap.add_argument("--alpha-threshold", type=int, default=1, help="alpha <= threshold treated as empty")
    ap.add_argument("--blur", type=float, default=0.0, help="gaussian blur radius (pixels) before quantize")
    ap.add_argument("--k", type=int, default=16, help="kmeans palette size before region extraction")
    ap.add_argument("--min-area-mm2", type=float, default=0.2, help="drop islands below area in mm^2")
    ap.add_argument("--debug-png", action="store_true", help="write debug PNG of 4-color assignment")
    ap.add_argument("--export-metadata", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    base = args.name or os.path.splitext(os.path.basename(args.image))[0]

    im = Image.open(args.image).convert("RGBA")

    if args.blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(radius=args.blur))

    # resize to target width in pixels by pixel-mm
    target_w_px = max(1, int(round(args.width_mm / args.pixel_mm)))
    w0, h0 = im.size
    target_h_px = max(1, int(round(target_w_px * (h0 / w0))))
    im = im.resize((target_w_px, target_h_px), resample=Image.Resampling.LANCZOS)

    arr = np.asarray(im, dtype=np.uint8)  # H W 4
    H, W = arr.shape[0], arr.shape[1]

    alpha = arr[:, :, 3]
    valid = alpha > args.alpha_threshold

    rgb = arr[:, :, :3].reshape(-1, 3).astype(np.float32)
    valid_flat = valid.reshape(-1)
    rgb_valid = rgb[valid_flat]

    if rgb_valid.shape[0] == 0:
        print("All pixels are transparent; nothing to do.")
        return

    # kmeans quantization
    k = max(2, int(args.k))
    km = MiniBatchKMeans(n_clusters=min(k, rgb_valid.shape[0]), random_state=0, n_init="auto")
    km.fit(rgb_valid)
    centers = km.cluster_centers_.astype(np.float32)  # K x 3
    labels = np.full((H * W,), -1, dtype=np.int32)
    labels[valid_flat] = km.predict(rgb_valid)

    # map kmeans centers to RGBW (nearest)
    center_to_rgbw = [classify_rgba_to_rgbw_nearest(tuple(map(int, c))) for c in centers]

    # build region masks per (kmeans label) then split CC to regions
    region_id = np.zeros((H, W), dtype=np.int32)
    rid = 0
    rid_to_rgbw: Dict[int, str] = {}
    rid_to_center_rgb255: Dict[int, Tuple[int, int, int]] = {}

    for li in range(centers.shape[0]):
        m = (labels.reshape(H, W) == li)
        if not m.any():
            continue
        cc = connected_components_4n(m)
        ncc = int(cc.max())
        for cci in range(1, ncc + 1):
            rid += 1
            region_id[cc == cci] = rid
            rid_to_rgbw[rid] = center_to_rgbw[li]
            c = centers[li]
            rid_to_center_rgb255[rid] = (int(round(float(c[0]))), int(round(float(c[1]))), int(round(float(c[2]))))

    n_regions = rid
    if n_regions == 0:
        print("No regions found.")
        return

    # adjacency and 4-color graph coloring to ensure no overlaps when exported
    adj = build_region_adjacency(region_id, n_regions)
    colors = dsatur_4color(adj, n_regions)  # rid -> 0..3

    # build 4 masks (color classes), then vectorize each with bbox crop per region
    # We'll accumulate polygons in each of 4 output channels
    out_polys: List[List[Polygon]] = [[], [], [], []]

    min_area_px2 = args.min_area_mm2 / (args.pixel_mm ** 2)

    # For speed: precompute bbox for each rid
    ys, xs = np.where(region_id > 0)
    # fallback: compute per rid directly (simple and robust)
    regions_meta = []
    for r in range(1, n_regions + 1):
        yy, xx = np.where(region_id == r)
        if yy.size == 0:
            continue
        y0, y1 = int(yy.min()), int(yy.max()) + 1
        x0, x1 = int(xx.min()), int(xx.max()) + 1
        # pad 2 pixels for contour stability
        pad = 2
        y0p = max(0, y0 - pad); y1p = min(H, y1 + pad)
        x0p = max(0, x0 - pad); x1p = min(W, x1 + pad)

        sub = (region_id[y0p:y1p, x0p:x1p] == r)
        if sub.sum() < 4:
            continue

        geom = mask_to_multipolygon(sub, min_area=min_area_px2)
        if geom.is_empty:
            continue

        # shift geometry back to full-image coordinates
        shifted_parts = []
        for p in geom.geoms:
            ext = [(x + x0p, y + y0p) for x, y in p.exterior.coords]
            holes = [[(x + x0p, y + y0p) for x, y in ring.coords] for ring in p.interiors]
            q = Polygon(ext, holes)
            if not q.is_valid:
                q = q.buffer(0)
            if q.is_empty or q.area < min_area_px2:
                continue
            shifted_parts.append(q)

        if not shifted_parts:
            continue

        g = unary_union(shifted_parts).buffer(0)
        cidx = int(colors[r])

        regions_meta.append(
            {
                "region_id": int(r),
                "center_rgb255": [int(rid_to_center_rgb255[r][0]), int(rid_to_center_rgb255[r][1]), int(rid_to_center_rgb255[r][2])],
                "class_rgbw": str(rid_to_rgbw[r]),
                "channel": int(cidx),
                "bbox_px": [int(x0), int(y0), int(x1), int(y1)],
            }
        )

        if isinstance(g, Polygon):
            out_polys[cidx].append(g)
        else:
            out_polys[cidx].extend(list(g.geoms))

    # Union per output channel, then forcibly remove overlaps (hard guarantee)
    unions = []
    for i in range(4):
        if out_polys[i]:
            unions.append(unary_union(out_polys[i]).buffer(0))
        else:
            unions.append(None)

    for i in range(4):
        if unions[i] is None or unions[i].is_empty:
            continue
        others = [unions[j] for j in range(4) if j != i and unions[j] is not None and not unions[j].is_empty]
        if others:
            unions[i] = unions[i].difference(unary_union(others)).buffer(0)

    # debug PNG of 4-color assignment
    if args.debug_png:
        cmap = np.zeros((H, W), dtype=np.uint8)
        for r in range(1, n_regions + 1):
            cmap[region_id == r] = np.uint8(colors[r])
        dbg = os.path.join(args.outdir, f"{base}_debug4color.png")
        save_debug_png(cmap, dbg)
        print(f"Wrote {dbg}")

    # Export 4 STLs; map 0..3 to R/G/B/W by label for convenience
    # These STL channels are only "non-overlap partitions" — you can assign them to any 4 AMS slots for testing.
    ch_names = ["A", "B", "C", "D"]  # neutral naming; avoids implying true RGBW at this stage
    exported: Dict[str, str] = {}
    for i in range(4):
        g = unions[i]
        if g is None or g.is_empty:
            print(f"{ch_names[i]}: empty")
            continue
        mesh = extrude_geom_to_mesh(g, height_mm=args.thickness_mm, pixel_mm=args.pixel_mm)
        if mesh is None:
            print(f"{ch_names[i]}: extrusion failed (earcut install? invalid geom?)")
            continue
        out = os.path.join(args.outdir, f"{base}_{ch_names[i]}.stl")
        mesh.export(out)
        exported[ch_names[i]] = os.path.abspath(out)
        print(f"{ch_names[i]}: wrote {out}")

    if args.export_metadata:
        meta = {
            "schema_version": 1,
            "script": os.path.basename(__file__),
            "input": {"image": os.path.abspath(args.image)},
            "params": {
                "outdir": os.path.abspath(args.outdir),
                "name": args.name,
                "width_mm": float(args.width_mm),
                "pixel_mm": float(args.pixel_mm),
                "thickness_mm": float(args.thickness_mm),
                "alpha_threshold": int(args.alpha_threshold),
                "blur": float(args.blur),
                "k": int(args.k),
                "min_area_mm2": float(args.min_area_mm2),
                "debug_png": bool(args.debug_png),
            },
            "regions": regions_meta,
            "outputs": exported,
        }
        meta_path = os.path.join(args.outdir, f"{base}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"metadata: wrote {meta_path}")

    print("Note: This script partitions regions into 4 non-overlapping STL channels for testing flow and geometry.")
    print("      It does NOT yet implement RGBW per-layer stacking; it's intended as a geometry pipeline validator.")

if __name__ == "__main__":
    main()
