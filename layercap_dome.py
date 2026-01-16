#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
layercap_dome.py - 4-STL stack-mix dome with "layer-limited" Z compression

- Build a spherical-cap shell subdivided into patches (rings x segs).
- Within each patch, stack 4 materials radially: A innermost -> D outermost.
- Then apply a Z "slice & squash" transform:
    original Z range is divided into z_slices equal bins,
    each bin is scaled to slice_height (mm) and concatenated.
  Result: keeps curvature inside each bin, but total height becomes z_slices*slice_height,
  greatly reducing print layers and often reducing filament swaps.

Patterns are regular (not random) by default.

Dependencies: numpy, trimesh
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import trimesh

import planner


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def add_mesh_accum(verts_acc: List[np.ndarray], faces_acc: List[np.ndarray], v: np.ndarray, f: np.ndarray) -> None:
    if len(v) == 0 or len(f) == 0:
        return
    offset = 0
    if verts_acc:
        offset = sum(len(x) for x in verts_acc)
    verts_acc.append(v)
    faces_acc.append(f + offset)


def quad_faces(grid_w: int, grid_h: int, base: int = 0, flip: bool = False) -> np.ndarray:
    faces = []
    for r in range(grid_h - 1):
        for c in range(grid_w - 1):
            i0 = base + r * grid_w + c
            i1 = base + r * grid_w + (c + 1)
            i2 = base + (r + 1) * grid_w + c
            i3 = base + (r + 1) * grid_w + (c + 1)
            if not flip:
                faces.append([i0, i2, i1])
                faces.append([i1, i2, i3])
            else:
                faces.append([i0, i1, i2])
                faces.append([i1, i3, i2])
    return np.asarray(faces, dtype=np.int64)


def sph(r: float, theta: float, phi: float) -> np.ndarray:
    st = math.sin(theta)
    ct = math.cos(theta)
    cp = math.cos(phi)
    sp = math.sin(phi)
    return np.array([r * st * cp, r * st * sp, r * ct], dtype=float)


@dataclass
class Patch:
    ring: int
    seg: int
    theta0: float
    theta1: float
    phi0: float
    phi1: float


def build_patches(rings: int, segs: int, theta_max: float) -> List[Patch]:
    rings = max(1, int(rings))
    segs = max(3, int(segs))
    theta_edges = np.linspace(0.0, theta_max, rings + 1)
    patches: List[Patch] = []
    for r in range(rings):
        th0 = float(theta_edges[r])
        th1 = float(theta_edges[r + 1])
        for s in range(segs):
            ph0 = 2.0 * math.pi * (s / segs)
            ph1 = 2.0 * math.pi * ((s + 1) / segs)
            patches.append(Patch(r, s, th0, th1, ph0, ph1))
    return patches


def fracs_regular(p: Patch, rings: int, segs: int, pattern: str, include_pures: bool) -> np.ndarray:
    # A/B/C/D fractions per patch, regular patterns
    if include_pures and p.ring == 0 and p.seg < 4:
        fr = np.zeros(4, dtype=float)
        fr[p.seg] = 1.0
        return fr

    if pattern == "cycle":
        # cycle pure material by patch index
        k = (p.ring * segs + p.seg) % 4
        fr = np.zeros(4, dtype=float)
        fr[k] = 1.0
        return fr

    if pattern == "checker":
        # alternating between two 70/30 mixes, rotated by quadrant
        a = (p.ring + p.seg) % 2
        pair = [(0, 1), (2, 3), (0, 2), (1, 3)][(p.seg // max(1, segs // 4)) % 4]
        fr = np.zeros(4, dtype=float)
        if a == 0:
            fr[pair[0]] = 0.7
            fr[pair[1]] = 0.3
        else:
            fr[pair[0]] = 0.3
            fr[pair[1]] = 0.7
        return fr / fr.sum()

    # gradient (default): A/B change with phi, C/D change with theta
    u = 0.0 if segs <= 1 else p.seg / (segs - 1)
    v = 0.0 if rings <= 1 else p.ring / (rings - 1)
    A = 1 - u
    B = u
    C = 1 - v
    D = v
    fr = np.array([A, B, C, D], dtype=float) + 1e-6
    fr = fr / fr.sum()
    return fr


def auto_steps_for_patch(r_ref: float, theta0: float, theta1: float, phi0: float, phi1: float, max_edge_len: float, t_mul: int, p_mul: int) -> Tuple[int, int]:
    t_mul = max(1, int(t_mul))
    p_mul = max(1, int(p_mul))
    if max_edge_len <= 0:
        return t_mul, p_mul
    dtheta = abs(theta1 - theta0)
    dphi = abs(phi1 - phi0)
    arc_theta = r_ref * dtheta
    th_mid = 0.5 * (theta0 + theta1)
    sin_ref = max(1e-6, abs(math.sin(th_mid)))
    arc_phi = r_ref * sin_ref * dphi
    t_steps = max(1, int(math.ceil(arc_theta / max_edge_len))) * t_mul
    p_steps = max(1, int(math.ceil(arc_phi / max_edge_len))) * p_mul
    return t_steps, p_steps


def build_shell_patch_segment(r_in: float, r_out: float, theta0: float, theta1: float, phi0: float, phi1: float, t_steps: int, p_steps: int) -> Tuple[np.ndarray, np.ndarray]:
    if r_out <= r_in:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)

    thetas = np.linspace(theta0, theta1, max(1, int(t_steps)) + 1)
    phis = np.linspace(phi0, phi1, max(1, int(p_steps)) + 1)

    outer = np.asarray([sph(r_out, th, ph) for th in thetas for ph in phis], dtype=float)
    inner = np.asarray([sph(r_in, th, ph) for th in thetas for ph in phis], dtype=float)

    v = np.vstack([outer, inner])
    outer_base = 0
    inner_base = len(outer)

    grid_h = len(thetas)
    grid_w = len(phis)

    faces = []
    faces.append(quad_faces(grid_w, grid_h, base=outer_base, flip=False))
    faces.append(quad_faces(grid_w, grid_h, base=inner_base, flip=True))

    def idx_outer(r: int, c: int) -> int:
        return outer_base + r * grid_w + c

    def idx_inner(r: int, c: int) -> int:
        return inner_base + r * grid_w + c

    def wall_between_loops(loop_o: List[int], loop_i: List[int], flip_wall: bool) -> np.ndarray:
        wall = []
        for i in range(len(loop_o) - 1):
            o0, o1 = loop_o[i], loop_o[i + 1]
            i0, i1 = loop_i[i], loop_i[i + 1]
            if not flip_wall:
                wall.append([o0, i0, o1]); wall.append([o1, i0, i1])
            else:
                wall.append([o0, o1, i0]); wall.append([o1, i1, i0])
        return np.asarray(wall, dtype=np.int64)

    # close 4 boundaries
    row0 = 0
    row1 = grid_h - 1
    col0 = 0
    col1 = grid_w - 1
    faces.append(wall_between_loops([idx_outer(row0, c) for c in range(grid_w)], [idx_inner(row0, c) for c in range(grid_w)], flip_wall=False))
    faces.append(wall_between_loops([idx_outer(row1, c) for c in range(grid_w)], [idx_inner(row1, c) for c in range(grid_w)], flip_wall=True))
    faces.append(wall_between_loops([idx_outer(r, col0) for r in range(grid_h)], [idx_inner(r, col0) for r in range(grid_h)], flip_wall=True))
    faces.append(wall_between_loops([idx_outer(r, col1) for r in range(grid_h)], [idx_inner(r, col1) for r in range(grid_h)], flip_wall=False))

    f = np.vstack(faces)
    return v, f


def z_slice_squash(vertices: np.ndarray, z_slices: int, slice_height: float) -> np.ndarray:
    """
    Divide original z-range into z_slices equal bins, scale each bin to slice_height,
    concatenate bins (no gaps). Keeps within-bin curvature but reduces total height.
    """
    z_slices = max(1, int(z_slices))
    if slice_height <= 0:
        return vertices

    v = vertices.copy()
    z = v[:, 2]
    zmin = float(z.min())
    zmax = float(z.max())
    if zmax <= zmin + 1e-9:
        return v

    dz = (zmax - zmin) / z_slices
    dz = max(dz, 1e-9)

    # bin index
    t = (z - zmin) / dz
    k = np.floor(t).astype(int)
    k = np.clip(k, 0, z_slices - 1)
    # local position within bin
    local = t - k
    z_new = k * slice_height + local * slice_height
    v[:, 2] = z_new
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description="Layer-limited (z-squashed) stack-mix dome generator.")
    ap.add_argument("--outdir", default="out_stl", help="Output directory.")
    ap.add_argument("--name", default="layercap_dome", help="Base name for STL files.")
    ap.add_argument("--radius", type=float, default=20.0, help="Outer radius (mm).")
    ap.add_argument("--thickness", type=float, default=1.6, help="Shell thickness (mm).")
    ap.add_argument("--theta-max-deg", type=float, default=80.0, help="Max theta in degrees (90=hemisphere).")
    ap.add_argument("--rings", type=int, default=5, help="Latitudinal rings.")
    ap.add_argument("--segs", type=int, default=8, help="Segments per ring.")
    ap.add_argument("--t-subdiv", type=int, default=1, help="Theta tessellation multiplier.")
    ap.add_argument("--p-subdiv", type=int, default=1, help="Phi tessellation multiplier.")
    ap.add_argument("--max-edge-len", type=float, default=1.2, help="Max edge length on outer sphere (mm). 0 disables auto-steps.")
    ap.add_argument("--pattern", choices=["gradient", "cycle", "checker"], default="gradient", help="Regular mixing pattern.")
    ap.add_argument("--include-pures", action="store_true", help="Make first 4 patches pure A/B/C/D.")
    ap.add_argument("--material-names", default="A,B,C,D", help="Comma-separated 4 STL suffix names.")
    ap.add_argument("--eps-skip", type=float, default=1e-4, help="Skip a material if fraction < eps.")

    ap.add_argument("--planner-mode", default=None)
    ap.add_argument("--layers", type=int, default=5, help="micro-layer count")
    ap.add_argument("--layer-height", type=float, default=0.08, help="mm per layer (except first)")
    ap.add_argument("--first-layer-height", type=float, default=0.12, help="mm for first layer (risk: can hide thin details)")
    ap.add_argument("--view", default="top", choices=["top", "bottom"])
    ap.add_argument("--backing", default="white", choices=["white", "black"])
    ap.add_argument("--materials-json", default=None)
    ap.add_argument("--phys", action="store_true")
    ap.add_argument("--export-metadata", action="store_true")

    # Layer-limit params
    ap.add_argument("--z-slices", type=int, default=10, help="Number of horizontal slices to squash into.")
    ap.add_argument("--slice-height", type=float, default=0.4, help="Compressed height per slice (mm). (Total height ~= z-slices*slice-height)")
    ap.add_argument("--validate", action="store_true", help="Run trimesh cleanup (slower).")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    mat_names = [x.strip() for x in args.material_names.split(",") if x.strip()]
    if len(mat_names) != 4:
        raise ValueError("--material-names must be exactly 4 names, e.g. A,B,C,D")

    radius = float(args.radius)
    thickness = float(args.thickness)
    if thickness <= 0 or thickness >= radius:
        raise ValueError("thickness must be > 0 and < radius")

    theta_max = math.radians(float(args.theta_max_deg))
    theta_max = clamp01(theta_max / (math.pi / 2)) * (math.pi / 2)
    if theta_max <= 0:
        raise ValueError("theta-max-deg must be > 0")

    inner_radius = radius - thickness
    patches = build_patches(args.rings, args.segs, theta_max)

    patch_meta = []

    use_planner = args.planner_mode is not None
    if use_planner:
        lib = planner.load_materials(args.materials_json)
        mode_key = str(args.planner_mode).strip().lower()
        if mode_key not in lib.modes:
            raise SystemExit(f"Unknown planner mode: {args.planner_mode} (available: {sorted(lib.modes.keys())})")

        tokens = [str(x).upper() for x in lib.modes[mode_key]]
        if len(tokens) != 4:
            raise SystemExit(f"planner mode must have exactly 4 materials, got: {tokens}")

        default_names = ["A", "B", "C", "D"]
        out_names = mat_names if mat_names != default_names else tokens

        all_verts_by_tok = {t: [] for t in tokens}
        all_faces_by_tok = {t: [] for t in tokens}
        heights_mm = [float(args.first_layer_height)] + [float(args.layer_height)] * (max(1, int(args.layers)) - 1)
        heights_sum = float(sum(heights_mm))
        if heights_sum <= 0:
            raise SystemExit("invalid heights")
    else:
        all_verts = [[], [], [], []]
        all_faces = [[], [], [], []]

    for p in patches:
        fr = fracs_regular(p, args.rings, args.segs, args.pattern, args.include_pures)
        fr = fr / fr.sum()

        if use_planner:
            rgb_lin = [0.0, 0.0, 0.0]
            for i, tok in enumerate(tokens):
                m = lib.fast[tok]
                w = float(fr[i])
                rgb_lin[0] += w * m.color_lin[0]
                rgb_lin[1] += w * m.color_lin[1]
                rgb_lin[2] += w * m.color_lin[2]
            target_srgb = planner._rgb_lin_to_int_srgb((rgb_lin[0], rgb_lin[1], rgb_lin[2]))
            rgba = (int(target_srgb[0]), int(target_srgb[1]), int(target_srgb[2]), 255)

            if args.phys:
                plan = planner.solve_layers_phys(
                    rgba=rgba,
                    mode=mode_key,
                    layers=int(args.layers),
                    first_layer_height=float(args.first_layer_height),
                    layer_height=float(args.layer_height),
                    pattern=str(args.pattern),
                    alpha_background="white",
                    view=str(args.view),
                    backing=str(args.backing),
                    materials_json=args.materials_json,
                    samples=60000,
                    seed=0,
                )
            else:
                plan = planner.solve_layers_fast(
                    rgba=rgba,
                    mode=mode_key,
                    layers=int(args.layers),
                    first_layer_height=float(args.first_layer_height),
                    layer_height=float(args.layer_height),
                    pattern=str(args.pattern),
                    alpha_background="white",
                    view=str(args.view),
                    backing=str(args.backing),
                    materials_json=args.materials_json,
                )

            seq = [str(x).upper() for x in plan.sequence]

            radial_thicknesses = [thickness * (h_i / heights_sum) for h_i in heights_mm]

            cum = inner_radius
            run_tok = None
            run_th = 0.0
            run_r_in = inner_radius
            for li, tok in enumerate(seq):
                if run_tok is None:
                    run_tok = tok
                    run_th = 0.0
                    run_r_in = cum

                cum += float(radial_thicknesses[li])
                run_th += float(radial_thicknesses[li])

                if li == len(seq) - 1 or seq[li + 1] != tok:
                    r_in = run_r_in
                    r_out = r_in + run_th

                    t_steps, p_steps = auto_steps_for_patch(
                        r_ref=r_out,
                        theta0=p.theta0,
                        theta1=p.theta1,
                        phi0=p.phi0,
                        phi1=p.phi1,
                        max_edge_len=float(args.max_edge_len),
                        t_mul=int(args.t_subdiv),
                        p_mul=int(args.p_subdiv),
                    )
                    v, f = build_shell_patch_segment(r_in, r_out, p.theta0, p.theta1, p.phi0, p.phi1, t_steps, p_steps)
                    v2 = z_slice_squash(v, int(args.z_slices), float(args.slice_height))
                    add_mesh_accum(all_verts_by_tok[run_tok], all_faces_by_tok[run_tok], v2, f)

                    run_tok = None

            patch_meta.append(
                {
                    "ring": int(p.ring),
                    "seg": int(p.seg),
                    "rgba": [int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3])],
                    "seq": seq,
                    "heights_mm": [float(x) for x in heights_mm],
                    "view": str(args.view),
                    "backing": str(args.backing),
                    "method": str(plan.method),
                    "pred_rgb_srgb": [int(plan.pred_rgb_srgb[0]), int(plan.pred_rgb_srgb[1]), int(plan.pred_rgb_srgb[2])],
                }
            )
        else:
            cum = inner_radius
            for mi in range(4):
                f_i = float(fr[mi])
                if f_i < float(args.eps_skip):
                    continue

                r_in = cum
                r_out = cum + thickness * f_i
                cum = r_out

                t_steps, p_steps = auto_steps_for_patch(
                    r_ref=r_out,
                    theta0=p.theta0,
                    theta1=p.theta1,
                    phi0=p.phi0,
                    phi1=p.phi1,
                    max_edge_len=float(args.max_edge_len),
                    t_mul=int(args.t_subdiv),
                    p_mul=int(args.p_subdiv),
                )

                v, f = build_shell_patch_segment(r_in, r_out, p.theta0, p.theta1, p.phi0, p.phi1, t_steps, p_steps)
                v2 = z_slice_squash(v, int(args.z_slices), float(args.slice_height))
                add_mesh_accum(all_verts[mi], all_faces[mi], v2, f)

    if use_planner:
        for tok, name in zip(tokens, out_names):
            if not all_verts_by_tok[tok]:
                print(f"[WARN] Material {name} empty; skipping.")
                continue
            V = np.vstack(all_verts_by_tok[tok])
            F = np.vstack(all_faces_by_tok[tok])
            mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)
            if args.validate:
                mesh.remove_duplicate_faces()
                mesh.remove_degenerate_faces()
                mesh.merge_vertices()
                mesh.fix_normals()
            outpath = os.path.join(args.outdir, f"{args.name}_{name}.stl")
            mesh.export(outpath)
            print(f"[OK] Wrote: {outpath} (verts={len(mesh.vertices)}, faces={len(mesh.faces)})")
    else:
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
                "planner_mode": args.planner_mode,
                "layers": int(args.layers),
                "first_layer_height_mm": float(args.first_layer_height),
                "layer_height_mm": float(args.layer_height),
                "view": str(args.view),
                "backing": str(args.backing),
                "materials_json": args.materials_json,
                "phys": bool(args.phys),
                "z_slices": int(args.z_slices),
                "slice_height": float(args.slice_height),
            },
            "patches": patch_meta,
        }
        meta_path = os.path.join(args.outdir, f"{args.name}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"metadata: wrote {meta_path}")

    print("\nNotes:")
    print("  Radial stacking order is A(innermost)->B->C->D(outermost).")
    print("  Layer-limit is applied by Z slicing and squashing; total height ~= z-slices*slice-height.")
    print("  Use smaller slice-height or fewer z-slices to reduce print layers and filament swaps (but geometry becomes more 'compressed').")


if __name__ == "__main__":
    main()
