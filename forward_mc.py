#!/usr/bin/env python3
# forward_mc.py
# Physically-based forward model for layered FDM color stacking (order matters).
# Uses Monte Carlo radiative transfer with absorption + scattering + Fresnel interfaces.
#
# Outputs per-channel (R,G,B) reflectance and transmittance under white illumination.
# Then combines with optional backing reflectance to give observed color.
#
# Example (CLI):
#   python forward_mc.py --seq G-R-W-W-W --heights 0.12,0.08,0.08,0.08,0.08 --view bottom --samples 200000
#
# Library usage:
#   from forward_mc import forward_rgb
#   rgb = forward_rgb(seq="W-G-W-R-W", heights=[0.08]*5, view="top", samples=200000, backing=(1,1,1))

from __future__ import annotations

import argparse
import json
import math
import random
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# -----------------------------
# Color space helpers
# -----------------------------

def srgb_to_linear01(x: float) -> float:
    if x <= 0.04045:
        return x / 12.92
    return ((x + 0.055) / 1.055) ** 2.4

def linear01_to_srgb(x: float) -> float:
    x = max(0.0, min(1.0, x))
    if x <= 0.0031308:
        return 12.92 * x
    return 1.055 * (x ** (1.0 / 2.4)) - 0.055

def rgb_lin_to_srgb255(rgb: Tuple[float, float, float]) -> Tuple[int, int, int]:
    return tuple(int(round(linear01_to_srgb(c) * 255.0)) for c in rgb)

# -----------------------------
# Physics: Fresnel (unpolarized), HG scattering
# -----------------------------

def fresnel_R_unpolarized(n1: float, n2: float, cos_i: float) -> float:
    """
    Unpolarized Fresnel reflectance at interface for a ray going from medium n1 to n2.
    cos_i must be in [0,1]. Handles total internal reflection.
    """
    cos_i = max(0.0, min(1.0, cos_i))
    # Snell: n1 sin_i = n2 sin_t
    sin_i2 = max(0.0, 1.0 - cos_i * cos_i)
    # if n1>n2, possible TIR
    sin_t2 = (n1 / n2) ** 2 * sin_i2
    if sin_t2 >= 1.0:
        return 1.0
    cos_t = math.sqrt(max(0.0, 1.0 - sin_t2))
    rs = ((n1 * cos_i - n2 * cos_t) / (n1 * cos_i + n2 * cos_t)) ** 2
    rp = ((n1 * cos_t - n2 * cos_i) / (n1 * cos_t + n2 * cos_i)) ** 2
    return 0.5 * (rs + rp)

def sample_hg_cos_theta(g: float, u: float) -> float:
    """
    Sample cos(theta) from Henyey-Greenstein phase function.
    g in [-1,1], u uniform in [0,1).
    """
    g = max(-0.999, min(0.999, g))
    if abs(g) < 1e-6:
        return 2.0 * u - 1.0
    # Inverse CDF
    num = 1.0 - g * g
    denom = 1.0 - g + 2.0 * g * u
    return (1.0 + g * g - (num / denom) ** 2) / (2.0 * g)

# -----------------------------
# Layer model
# -----------------------------

@dataclass
class OpticalProps:
    # per-channel coefficients in 1/mm
    mu_a: Tuple[float, float, float]  # absorption
    mu_s: Tuple[float, float, float]  # scattering
    g: float                          # anisotropy
    n: float                          # refractive index

DEFAULT_MATERIALS: Dict[str, OpticalProps] = {
    # These are placeholders. Replace with fitted values later.
    # Intuition:
    # - W: low absorption, high scattering (milky)
    # - Clear T: very low absorption, low scattering (transparent)
    # - K: high absorption all channels
    # - R/G/B: higher absorption in the "other" channels + moderate scattering
    "W": OpticalProps(mu_a=(0.10, 0.10, 0.10), mu_s=(6.0, 6.0, 6.0), g=0.85, n=1.50),
    "T": OpticalProps(mu_a=(0.01, 0.01, 0.01), mu_s=(0.4, 0.4, 0.4), g=0.80, n=1.50),
    "K": OpticalProps(mu_a=(8.0, 8.0, 8.0),     mu_s=(2.0, 2.0, 2.0), g=0.80, n=1.50),

    "R": OpticalProps(mu_a=(0.35, 2.2, 2.6),    mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "G": OpticalProps(mu_a=(2.2, 0.35, 2.2),    mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "B": OpticalProps(mu_a=(2.6, 2.2, 0.35),    mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),

    # Optional extras if you later extend:
    "C": OpticalProps(mu_a=(2.4, 0.50, 0.50),   mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "Y": OpticalProps(mu_a=(0.45, 0.45, 2.4),   mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "M": OpticalProps(mu_a=(0.50, 2.4, 0.50),   mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
}


def _default_materials_path() -> str:
    return os.path.join(os.path.dirname(__file__), "materials.json")


def load_materials_json(path: str) -> Dict[str, OpticalProps]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mats = data.get("materials") or {}
    out: Dict[str, OpticalProps] = {}
    for k, v in mats.items():
        k2 = str(k).upper()
        out[k2] = OpticalProps(
            mu_a=tuple(map(float, v["mu_a"])),
            mu_s=tuple(map(float, v["mu_s"])),
            g=float(v.get("g", 0.85)),
            n=float(v.get("n", 1.50)),
        )
    return out

def cumulative_bounds(heights: Sequence[float]) -> List[float]:
    z = 0.0
    b = [0.0]
    for h in heights:
        z += float(h)
        b.append(z)
    return b  # length L+1

def layer_index_at_z(bounds: Sequence[float], z: float) -> int:
    # z in [0, total]
    # bounds is sorted
    # linear scan OK for small L; can bisect if you want
    for i in range(len(bounds) - 1):
        if bounds[i] <= z < bounds[i + 1]:
            return i
    return len(bounds) - 2  # if z==total

# -----------------------------
# Monte Carlo transport in layered slab (1D geometry, 3D directions)
# -----------------------------

@dataclass
class MCResult:
    R: Tuple[float, float, float]  # reflectance per channel (0..1)
    T: Tuple[float, float, float]  # transmittance per channel (0..1)

def _mc_one_channel(
        seq: Sequence[str],
        heights: Sequence[float],
        mats: Dict[str, OpticalProps],
        channel: int,
        view: str,
        samples: int,
        seed: int,
        air_n: float = 1.0,
        collimated_normal: bool = True,
        max_scatter_events: int = 2000,
) -> Tuple[float, float]:
    """
    Returns (R, T) for one wavelength channel.
    view="top" means illumination enters at z=0 going +z.
    view="bottom" means illumination enters at z=total going -z.
    """
    rng = random.Random(seed + 10007 * channel)

    # If viewing from bottom, reverse coordinate system by mirroring
    if view.lower() == "bottom":
        seq_eff = list(reversed(seq))
        heights_eff = list(reversed(heights))
    else:
        seq_eff = list(seq)
        heights_eff = list(heights)

    bounds = cumulative_bounds(heights_eff)
    total = bounds[-1]

    # For simplicity we assume all layers share same refractive index (PLA-like)
    # but keep it per-layer anyway.
    # Interface Fresnel is computed at air/plastic and plastic/air only here.
    # Internal interfaces between same n don't matter; if you later set different n per material,
    # you can add internal Fresnel checks when crossing layer boundaries.

    # pre-fetch coefficients per layer
    mu_a = [mats[t].mu_a[channel] for t in seq_eff]
    mu_s = [mats[t].mu_s[channel] for t in seq_eff]
    g = [mats[t].g for t in seq_eff]
    n_layer = [mats[t].n for t in seq_eff]
    # We'll assume constant n inside = n_layer[0] for outer Fresnel.
    # If you want n varying, you need Fresnel at each boundary; doable but longer.
    n_in = float(np.median(n_layer)) if n_layer else 1.5

    R_count = 0.0
    T_count = 0.0

    for _ in range(samples):
        # Start photon at entry surface
        z = 0.0
        # Direction cosine mu = cos(theta) with respect to +z (downwards into slab)
        mu = 1.0 if collimated_normal else math.sqrt(rng.random())  # cosine-weighted if diffuse
        # phi not needed in 1D boundary tests; only for updating mu after scattering

        # Fresnel at entry air->plastic
        Rf = fresnel_R_unpolarized(air_n, n_in, abs(mu))
        if rng.random() < Rf:
            # specular reflection back to air
            R_count += 1.0
            continue

        # Photon enters
        # After refraction, direction changes; for simplicity keep mu same.
        # If you want strict Snell for direction, implement:
        # sin_t = n1/n2 * sin_i, cos_t from it; update mu = cos_t.
        # In practice with small angles and collimated normal, it’s minor.

        # Transport until absorbed or exits
        scatter_events = 0
        alive = True

        while alive and scatter_events < max_scatter_events:
            li = layer_index_at_z(bounds, z)
            mua = mu_a[li]
            mus = mu_s[li]
            mut = mua + mus
            if mut <= 1e-12:
                # ballistic through this layer: jump to next boundary
                # Determine next boundary depending on direction mu
                if mu > 0:
                    next_z = bounds[li + 1]
                else:
                    next_z = bounds[li]
                z = next_z
            else:
                # sample free path
                s = -math.log(max(1e-12, rng.random())) / mut
                # step in z
                dz = s * mu
                z_new = z + dz

                # boundary crossing handling: we must not "teleport" across multiple boundaries
                # We'll clip to the nearest boundary and continue with remaining distance.
                # In layered printing L is small; loop clipping is fine.
                while True:
                    if mu > 0:
                        # moving to +z, next boundary is top of current layer
                        b = bounds[li + 1]
                        if z_new < b + 1e-12:
                            # no boundary crossed
                            z = z_new
                            break
                        # boundary crossed
                        # consume distance to boundary
                        # (ignore partial absorption because we use interaction-based absorption)
                        z = b
                        li += 1
                        if z >= total - 1e-12:
                            # exit bottom (plastic -> air)
                            # Fresnel at plastic->air
                            Rb = fresnel_R_unpolarized(n_in, air_n, abs(mu))
                            if rng.random() < Rb:
                                # reflect back into slab
                                mu = -mu
                                z = total - 1e-9
                                break
                            T_count += 1.0
                            alive = False
                            break
                        # recompute z_new by "carrying on" remaining distance in same mu
                        # We approximate remaining distance by continuing with same z_new; it already includes it.
                        # But we must update layer index and continue; this is acceptable for small L.
                        # In a stricter implementation you'd track leftover distance.
                        z_new = z + 1e-9  # tiny nudge into next layer
                        li = layer_index_at_z(bounds, z_new)
                        # continue loop to check further crossings (rare)
                        continue
                    else:
                        # moving to -z, next boundary is bottom of current layer
                        b = bounds[li]
                        if z_new > b - 1e-12:
                            z = z_new
                            break
                        z = b
                        li -= 1
                        if z <= 0.0 + 1e-12:
                            # exit top (plastic -> air)
                            Rt = fresnel_R_unpolarized(n_in, air_n, abs(mu))
                            if rng.random() < Rt:
                                mu = -mu
                                z = 1e-9
                                break
                            R_count += 1.0
                            alive = False
                            break
                        z_new = z - 1e-9
                        li = layer_index_at_z(bounds, z_new)
                        continue

            if not alive:
                break

            # If we reached here, we are at an interaction in current layer
            # Absorb or scatter:
            li = layer_index_at_z(bounds, min(max(z, 0.0), total - 1e-9))
            mua = mu_a[li]
            mus = mu_s[li]
            mut = mua + mus
            if mut <= 1e-12:
                continue

            # absorption probability
            if rng.random() < (mua / mut):
                alive = False
                break

            # scatter
            scatter_events += 1
            # Update direction using HG: sample cos(theta) relative to current direction.
            ct = sample_hg_cos_theta(g[li], rng.random())
            # We only care about new mu (cos w.r.t +z).
            # In 3D, mu' = mu*ct + sqrt(1-mu^2)*sqrt(1-ct^2)*cos(phi)
            phi = 2.0 * math.pi * rng.random()
            st = math.sqrt(max(0.0, 1.0 - ct * ct))
            smu = math.sqrt(max(0.0, 1.0 - mu * mu))
            mu = mu * ct + smu * st * math.cos(phi)
            # clamp numeric drift
            mu = max(-1.0, min(1.0, mu))

        # if max scatter events exceeded, treat as absorbed (rare)
        # no count increment

    R = R_count / samples
    T = T_count / samples
    # energy conservation: A = 1 - R - T
    return (R, T)

def forward_reflect_transmit(
        seq: Sequence[str],
        heights: Sequence[float],
        materials: Optional[Dict[str, OpticalProps]] = None,
        view: str = "top",
        samples: int = 200000,
        seed: int = 0,
) -> MCResult:
    mats = materials or DEFAULT_MATERIALS

    # validate tokens
    for t in seq:
        if t not in mats:
            raise ValueError(f"Unknown material token {t}. Known: {sorted(mats.keys())}")

    if len(seq) != len(heights):
        raise ValueError("seq and heights must have same length")

    # three channels R,G,B
    Rvals = []
    Tvals = []
    for ch in range(3):
        Rch, Tch = _mc_one_channel(
            seq=seq,
            heights=heights,
            mats=mats,
            channel=ch,
            view=view,
            samples=samples,
            seed=seed,
        )
        Rvals.append(Rch)
        Tvals.append(Tch)
    return MCResult(R=tuple(Rvals), T=tuple(Tvals))

def observed_rgb_under_backing(
        R: Tuple[float, float, float],
        T: Tuple[float, float, float],
        backing_reflectance: Tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> Tuple[float, float, float]:
    """
    Very standard compositing for a slab on a backing:
      Observed ≈ R + T * backing
    This assumes backing is Lambertian reflector illuminated from the same side,
    and ignores multiple bounce between slab/backing. You can extend if you want.
    """
    return (
        max(0.0, min(1.0, R[0] + T[0] * backing_reflectance[0])),
        max(0.0, min(1.0, R[1] + T[1] * backing_reflectance[1])),
        max(0.0, min(1.0, R[2] + T[2] * backing_reflectance[2])),
    )

# -----------------------------
# CLI
# -----------------------------

def parse_seq(s: str) -> List[str]:
    s = s.strip()
    if "-" in s:
        return [x.strip().upper() for x in s.split("-") if x.strip()]
    return [c.upper() for c in s if not c.isspace()]

def parse_heights(s: str) -> List[float]:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return [float(p) for p in parts]

def main():
    ap = argparse.ArgumentParser(description="Physically-based forward model (Monte Carlo) for layered stacks.")
    ap.add_argument("--seq", required=True, help="sequence like W-G-W-R-W or WGW RW")
    ap.add_argument("--heights", required=True, help="comma heights in mm, e.g. 0.12,0.08,0.08,0.08,0.08")
    ap.add_argument("--view", default="top", choices=["top", "bottom"], help="illumination+view side")
    ap.add_argument("--samples", type=int, default=200000, help="Monte Carlo photons per channel")
    ap.add_argument("--samples-preview", type=int, default=None, help="low-sample fast mode for realtime preview")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--backing", default="white", choices=["white", "black"], help="backing reflectance for observed color")
    ap.add_argument("--materials-json", default=None, help="materials.json path")
    args = ap.parse_args()

    seq = parse_seq(args.seq)
    heights = parse_heights(args.heights)

    mats_path = args.materials_json or _default_materials_path()
    if not os.path.exists(mats_path):
        raise SystemExit(f"materials.json not found: {mats_path}")
    mats = load_materials_json(mats_path)

    if args.samples_preview is not None:
        args.samples = int(args.samples_preview)

    res = forward_reflect_transmit(seq=seq, heights=heights, materials=mats, view=args.view, samples=args.samples, seed=args.seed)

    backing = (1.0, 1.0, 1.0) if args.backing == "white" else (0.0, 0.0, 0.0)
    obs = observed_rgb_under_backing(res.R, res.T, backing_reflectance=backing)

    print(f"seq={seq}")
    print(f"heights_mm={heights} total={sum(heights):.3f}")
    print(f"view={args.view} samples={args.samples} seed={args.seed}")
    print(f"Reflectance R={res.R}  Transmittance T={res.T}  Absorption A={(1-res.R[0]-res.T[0], 1-res.R[1]-res.T[1], 1-res.R[2]-res.T[2])}")
    print(f"Observed on {args.backing} backing (linear)={obs}")
    print(f"Observed sRGB={rgb_lin_to_srgb255(obs)}")

if __name__ == "__main__":
    main()
