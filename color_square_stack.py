#!/usr/bin/env python3
# color_square_stack.py
# Single RGBA -> stacked square, exported as per-mode STL (e.g. R,G,B,W).
#
# Note
# ----
# Older versions of OpenColor had a "legacy" order-insensitive forward model in this script.
# In v3 that code is removed to prevent accidental misuse. All planning goes through planner.py.
#
# Example:
#   python color_square_stack.py --hex "#DDF4C4" --size-mm 30 --layers 5 --layer-height 0.08 --first-layer-height 0.12

import argparse
import os
from typing import Dict, List, Tuple

import trimesh
from shapely.geometry import Polygon

import planner

RGBA = Tuple[int, int, int, int]


def parse_hex_rgba(s: str) -> RGBA:
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) not in (6, 8):
        raise ValueError("hex must be #RRGGBB or #RRGGBBAA")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    a = int(s[6:8], 16) if len(s) == 8 else 255
    return (r, g, b, a)


def extrude_poly_at_z(poly: Polygon, height: float, z0: float) -> trimesh.Trimesh:
    mesh = trimesh.creation.extrude_polygon(poly, height)
    mesh.apply_translation((0.0, 0.0, z0))
    return mesh


def main() -> None:
    lib = planner.load_materials(None)

    ap = argparse.ArgumentParser(description="Single RGBA -> stacked square as per-material STL.")
    ap.add_argument("--hex", default="#DDF4C4", help="color hex #RRGGBB or #RRGGBBAA")
    ap.add_argument("--mode", default="rgbw", choices=sorted(lib.modes.keys()))
    ap.add_argument("--size-mm", type=float, default=30.0, help="square side length in mm")
    ap.add_argument("--layers", type=int, default=5, help="layer count")
    ap.add_argument("--layer-height", type=float, default=0.08, help="mm per layer (except first)")
    ap.add_argument("--first-layer-height", type=float, default=0.12, help="mm for first layer")
    ap.add_argument("--view", default="bottom", choices=["top", "bottom"], help="which side is the viewing side")
    ap.add_argument("--backing", default="white", choices=["white", "black"], help="backing color used by the forward model")
    ap.add_argument("--phys", action="store_true", help="use Monte-Carlo physical forward for selection")
    ap.add_argument("--samples", type=int, default=80000)
    ap.add_argument("--candidates", type=int, default=64)
    ap.add_argument("--brute-force-threshold", type=int, default=60000, help="enumerate all sequences when K^L <= threshold")
    ap.add_argument("--opacity-weight", type=float, default=-1.0, help="opacity term weight; <0 for auto")
    ap.add_argument("--alpha-background", default="white", choices=["white", "black"], help="background used when interpreting RGBA")
    ap.add_argument("--pattern", default="balanced", choices=["balanced", "grouped"], help="only used when not brute-forcing")
    ap.add_argument("--outdir", default="out_color_square", help="output folder")
    ap.add_argument("--name", default="color_square", help="base output name")
    ap.add_argument("--materials-json", default=None, help="materials.json path")
    args = ap.parse_args()

    rgba = parse_hex_rgba(args.hex)
    os.makedirs(args.outdir, exist_ok=True)

    opacity_w = None if args.opacity_weight < 0 else float(args.opacity_weight)

    if args.phys:
        p = planner.solve_layers_phys(
            rgba=rgba,
            mode=args.mode,
            layers=args.layers,
            first_layer_height=args.first_layer_height,
            layer_height=args.layer_height,
            pattern=args.pattern,
            alpha_background=args.alpha_background,
            view=args.view,
            backing=args.backing,
            samples=args.samples,
            candidates=args.candidates,
            brute_force_threshold=args.brute_force_threshold,
            opacity_weight=opacity_w,
            materials_json=args.materials_json,
        )
    else:
        p = planner.solve_layers_fast(
            rgba=rgba,
            mode=args.mode,
            layers=args.layers,
            first_layer_height=args.first_layer_height,
            layer_height=args.layer_height,
            pattern=args.pattern,
            alpha_background=args.alpha_background,
            view=args.view,
            backing=args.backing,
            candidates=args.candidates,
            brute_force_threshold=args.brute_force_threshold,
            opacity_weight=opacity_w,
            materials_json=args.materials_json,
        )

    logic = "-".join(p.sequence)
    total_h = sum(p.heights_mm)
    print(f"in={rgba}  seq={logic}")
    print(f"pred={p.pred_rgb_srgb}  loss={p.loss:.6f}  total_thickness_mm={total_h:.3f}  view={p.view} backing={p.backing}")

    s = float(args.size_mm)
    square = Polygon([(0, 0), (s, 0), (s, s), (0, s)])

    meshes: Dict[str, List[trimesh.Trimesh]] = {t: [] for t in planner.mode_tokens(lib, args.mode)}
    z = 0.0
    for t, h in zip(p.sequence, p.heights_mm):
        meshes[t].append(extrude_poly_at_z(square, float(h), float(z)))
        z += float(h)

    for t, parts in meshes.items():
        if not parts:
            continue
        m = trimesh.util.concatenate(parts)
        out = os.path.join(args.outdir, f"{args.name}_{t}.stl")
        m.export(out)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
