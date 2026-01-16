#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mixplane.py - Planar discrete-layer stack-mix card (4 STL)

Two modes:
1) composition: all (a,b,c,d) nonnegative integers with a+b+c+d=layers
   Count = C(layers+3,3). For layers=5 -> 56 tiles.
   Stacking order inside tile is fixed: A(bottom)->B->C->D(top).

2) sequence: all sequences of length 'layers' over {A,B,C,D}
   Count = 4^layers. For layers=5 -> 1024 tiles.
   Stacking order inside tile follows the sequence bottom->top.

Tiles are contiguous (no gaps).

Outputs:
  outdir/<name>_A.stl ... <name>_D.stl

Dependencies: numpy, trimesh
"""

from __future__ import annotations

import argparse
import json
import math
import os
from typing import List, Tuple

import numpy as np
import trimesh


def add_mesh_accum(verts_acc: List[np.ndarray], faces_acc: List[np.ndarray], v: np.ndarray, f: np.ndarray) -> None:
    if len(v) == 0 or len(f) == 0:
        return
    offset = 0
    if verts_acc:
        offset = sum(len(x) for x in verts_acc)
    verts_acc.append(v)
    faces_acc.append(f + offset)


def prism(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Tuple[np.ndarray, np.ndarray]:
    v = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        dtype=float,
    )
    f = np.array(
        [
            [0, 1, 2], [0, 2, 3],  # bottom
            [4, 6, 5], [4, 7, 6],  # top
            [0, 4, 5], [0, 5, 1],  # y0
            [1, 5, 6], [1, 6, 2],  # x1
            [2, 6, 7], [2, 7, 3],  # y1
            [3, 7, 4], [3, 4, 0],  # x0
        ],
        dtype=np.int64,
    )
    return v, f


def compositions_4(n: int) -> List[Tuple[int, int, int, int]]:
    """All nonnegative integer tuples (a,b,c,d) with a+b+c+d=n."""
    n = int(n)
    out: List[Tuple[int, int, int, int]] = []
    for a in range(n, -1, -1):
        for b in range(n - a, -1, -1):
            for c in range(n - a - b, -1, -1):
                d = n - a - b - c
                out.append((a, b, c, d))
    return out


def sequence_index_to_digits(base: int, length: int, idx: int) -> List[int]:
    """
    idx in [0, base^length)
    returns digits (length) in lexicographic order (most significant first)
    digits are in [0..base-1]
    """
    digits = [0] * length
    x = idx
    for pos in range(length - 1, -1, -1):
        digits[pos] = x % base
        x //= base
    return digits


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate discrete-layer planar mix card (4 STLs).")
    ap.add_argument("--outdir", default="out_stl", help="Output directory.")
    ap.add_argument("--name", default="mixplane", help="Base name for STL files.")

    ap.add_argument("--mode", choices=["composition", "sequence"], default="composition", help="Mix enumeration mode.")
    ap.add_argument("--layers", type=int, default=5, help="Total discrete layers per tile (e.g. 5).")
    ap.add_argument("--layer-height", type=float, default=0.08, help="Height per discrete layer in mm (except first).")
    ap.add_argument("--first-layer-height", type=float, default=0.12, help="Height of first layer in mm (risk: can hide thin details).")
    ap.add_argument("--view", default="top", choices=["top", "bottom"])
    ap.add_argument("--backing", default="white", choices=["white", "black"])

    ap.add_argument("--tile", type=float, default=10.0, help="Tile size (mm). Tiles are contiguous with no gaps.")
    ap.add_argument("--nx", type=int, default=0, help="Tiles per row. 0 = auto (square-ish).")

    ap.add_argument("--material-names", default="A,B,C,D", help="Comma-separated 4 STL suffix names.")
    ap.add_argument("--validate", action="store_true", help="Run trimesh cleanup (slower).")
    ap.add_argument("--export-metadata", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    mat_names = [x.strip() for x in args.material_names.split(",")]
    if len(mat_names) != 4:
        raise ValueError("--material-names must be exactly 4 names, e.g. A,B,C,D")

    L = max(1, int(args.layers))
    h = float(args.layer_height)
    h0 = float(args.first_layer_height)
    if h <= 0 or h0 <= 0:
        raise ValueError("layer heights must be > 0")

    layer_heights = [h0] + [h] * (L - 1)

    tile = float(args.tile)
    if tile <= 0:
        raise ValueError("--tile must be > 0")

    if args.mode == "composition":
        combos = compositions_4(L)
        total = len(combos)  # C(L+3,3)
    else:
        total = 4 ** L

    # nx auto: aim for near-square grid
    if int(args.nx) <= 0:
        nx = int(math.ceil(math.sqrt(total)))
    else:
        nx = int(args.nx)
    nx = max(1, nx)
    ny = int(math.ceil(total / nx))

    total_thickness = sum(layer_heights)

    # Center the whole card at origin
    size_x = nx * tile
    size_y = ny * tile
    x0_card = -size_x / 2.0
    y0_card = -size_y / 2.0

    all_verts: List[List[np.ndarray]] = [[], [], [], []]
    all_faces: List[List[np.ndarray]] = [[], [], [], []]

    tiles_meta = []

    if args.mode == "composition":
        for idx, (a, b, c, d) in enumerate(combos):
            ix = idx % nx
            iy = idx // nx

            x0 = x0_card + ix * tile
            x1 = x0 + tile
            y0 = y0_card + iy * tile
            y1 = y0 + tile

            counts = [int(a), int(b), int(c), int(d)]
            seq_digits: List[int] = []
            for mi in range(4):
                seq_digits.extend([mi] * int(counts[mi]))
            if len(seq_digits) != L:
                raise RuntimeError("internal error: composition does not sum to layers")

            z = 0.0
            last_mi = None
            z0 = 0.0
            for layer_i, mi in enumerate(seq_digits):
                if last_mi is None:
                    last_mi = mi
                    z0 = 0.0

                z += float(layer_heights[layer_i])
                if layer_i == L - 1 or seq_digits[layer_i + 1] != mi:
                    v, f = prism(x0, x1, y0, y1, z0, z)
                    add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
                    z0 = z
                    last_mi = None

            tiles_meta.append(
                {
                    "tile_id": int(idx),
                    "ix": int(ix),
                    "iy": int(iy),
                    "counts": {mat_names[i]: int(counts[i]) for i in range(4)},
                    "seq": [mat_names[i] for i in seq_digits],
                    "heights_mm": [float(x) for x in layer_heights],
                    "view": str(args.view),
                    "backing": str(args.backing),
                }
            )
    else:
        # sequence mode: each of L layers picks a material; order matters
        for idx in range(total):
            ix = idx % nx
            iy = idx // nx

            x0 = x0_card + ix * tile
            x1 = x0 + tile
            y0 = y0_card + iy * tile
            y1 = y0 + tile

            seq_digits = sequence_index_to_digits(base=4, length=L, idx=idx)  # each in 0..3
            z = 0.0
            last_mi = None
            z0 = 0.0
            for layer_i, mi in enumerate(seq_digits):
                if last_mi is None:
                    last_mi = mi
                    z0 = z

                z += float(layer_heights[layer_i])
                if layer_i == L - 1 or seq_digits[layer_i + 1] != mi:
                    v, f = prism(x0, x1, y0, y1, z0, z)
                    add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
                    z0 = z
                    last_mi = None

            tiles_meta.append(
                {
                    "tile_id": int(idx),
                    "ix": int(ix),
                    "iy": int(iy),
                    "seq": [mat_names[i] for i in seq_digits],
                    "heights_mm": [float(x) for x in layer_heights],
                    "view": str(args.view),
                    "backing": str(args.backing),
                }
            )

    for mi in range(4):
        if not all_verts[mi]:
            print(f"[WARN] Material {mat_names[mi]} empty; skipping.")
            continue
        V = np.vstack(all_verts[mi])
        F = np.vstack(all_faces[mi])
        mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)
        if args.validate:
            mesh.remove_duplicate_faces()
            mesh.remove_degenerate_faces()
            mesh.merge_vertices()
            mesh.fix_normals()
        outpath = os.path.join(args.outdir, f"{args.name}_{mat_names[mi]}.stl")
        mesh.export(outpath)
        print(f"[OK] Wrote: {outpath} (verts={len(mesh.vertices)}, faces={len(mesh.faces)})")

    if args.export_metadata:
        meta = {
            "schema_version": 1,
            "script": os.path.basename(__file__),
            "params": {
                "mode": str(args.mode),
                "layers": int(L),
                "first_layer_height_mm": float(h0),
                "layer_height_mm": float(h),
                "tile_mm": float(tile),
                "grid_nx": int(nx),
                "grid_ny": int(ny),
                "view": str(args.view),
                "backing": str(args.backing),
                "material_names": list(mat_names),
            },
            "tiles": tiles_meta,
        }
        meta_path = os.path.join(args.outdir, f"{args.name}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"metadata: wrote {meta_path}")

    print("\nSummary:")
    print(f"  mode={args.mode}")
    print(f"  layers={L}, first_layer_height={h0} mm, layer_height={h} mm, tile_thickness={total_thickness} mm")
    if args.mode == "composition":
        print(f"  tiles = C(layers+3,3) = {total}")
        print("  stacking order per tile: A(bottom)->B->C->D(top)")
    else:
        print(f"  tiles = 4^layers = {total}")
        print("  stacking order per tile follows the sequence bottom->top")
    print(f"  grid = {nx} x {ny}, tile = {tile} mm, no gaps")


if __name__ == "__main__":
    main()
