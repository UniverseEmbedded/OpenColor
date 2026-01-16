#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""RGBA -> layer stack planner (starter grey-box model).

- As library:  from layerplan import solve_layers
- As CLI:      python layerplan.py --rgba 255,200,0,255 --mode rgbwkc

The forward model is intentionally simple (NOT Kubelka-Munk, no lookup DB):
  - Each material m has base linear-RGB color c_m and strength s_m.
  - Each layer of thickness h contributes weight w_m = 1 - exp(-s_m * h).
  - A stack with counts n_m predicts:
        rgb = (sum n_m * w_m * c_m) / (sum n_m * w_m)

Given target RGBA, we brute-force all integer compositions of `layers` across
materials (layers is usually small, e.g. 5~12) to minimize error in linear-RGB.
Then we output an ordered sequence like R-G-W-W-R.

Tuning
------
You can tune MATERIAL_PRESETS below (colors/strength). Once you have single-
material measurements, replace presets with fitted values.
"""

from __future__ import annotations

import argparse
import itertools
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

Vec3 = Tuple[float, float, float]
RGBA = Tuple[int, int, int, int]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def srgb_to_linear(c: float) -> float:
    """Convert sRGB (0..1) to linear RGB (0..1)."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    """Convert linear RGB (0..1) to sRGB (0..1)."""
    c = _clamp(c)
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1 / 2.4)) - 0.055


def rgba_to_linear_rgba(rgba: RGBA) -> Tuple[float, float, float, float]:
    r, g, b, a = rgba
    rf = srgb_to_linear(_clamp(r / 255.0))
    gf = srgb_to_linear(_clamp(g / 255.0))
    bf = srgb_to_linear(_clamp(b / 255.0))
    af = _clamp(a / 255.0)
    return rf, gf, bf, af


@dataclass(frozen=True)
class Material:
    token: str
    color_lin: Vec3  # base color in linear RGB
    strength: float  # higher => more influence per layer

    def weight(self, layer_height_mm: float) -> float:
        # A small exp model gives a smooth, bounded weight in (0..1).
        return 1.0 - math.exp(-self.strength * max(layer_height_mm, 0.0))


@dataclass
class LayerPlan:
    mode: str
    rgba_in: RGBA
    layers: int
    layer_height: float
    counts: Dict[str, int]
    sequence: List[str]
    rgb_pred_srgb: Tuple[int, int, int]
    loss: float


def _predict_rgb_from_counts(
    mats: List[Material],
    counts: List[int],
    layer_height_mm: float,
) -> Vec3:
    # Weighted average of material colors.
    num = [0.0, 0.0, 0.0]
    denom = 0.0
    for m, n in zip(mats, counts):
        if n <= 0:
            continue
        w = m.weight(layer_height_mm)
        denom += n * w
        num[0] += n * w * m.color_lin[0]
        num[1] += n * w * m.color_lin[1]
        num[2] += n * w * m.color_lin[2]
    if denom <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (num[0] / denom, num[1] / denom, num[2] / denom)


def _loss(rgb_pred: Vec3, rgb_target: Vec3, w_luma: float = 0.35) -> float:
    # Simple weighted squared error, slightly emphasizing luminance.
    dr = rgb_pred[0] - rgb_target[0]
    dg = rgb_pred[1] - rgb_target[1]
    db = rgb_pred[2] - rgb_target[2]
    # approximate luminance in linear space
    dl = (0.2126 * dr + 0.7152 * dg + 0.0722 * db)
    return (dr * dr + dg * dg + db * db) + w_luma * (dl * dl)


def _compositions(total: int, parts: int) -> Iterable[List[int]]:
    """All nonnegative integer compositions of total into 'parts' bins."""
    # Stars and bars via combinations of cut positions.
    # Complexity: C(total+parts-1, parts-1)
    for cuts in itertools.combinations(range(total + parts - 1), parts - 1):
        prev = -1
        comp: List[int] = []
        for c in cuts:
            comp.append(c - prev - 1)
            prev = c
        comp.append((total + parts - 1) - prev - 1)
        yield comp


def _sequence_from_counts(
    tokens: List[str],
    counts: List[int],
    pattern: str = "balanced",
) -> List[str]:
    """Create an ordered layer sequence from counts."""
    seq: List[str] = []
    if pattern == "grouped":
        for t, n in sorted(zip(tokens, counts), key=lambda x: (-x[1], x[0])):
            seq.extend([t] * n)
        return seq

    # balanced: round-robin distribute layers for smoother stacking
    remaining = {t: n for t, n in zip(tokens, counts) if n > 0}
    # Start with most frequent token to reduce early bias
    last = None
    while remaining:
        # sort by remaining count, prefer not repeating last if possible
        choices = sorted(remaining.items(), key=lambda x: (-x[1], x[0]))
        pick = None
        for t, _n in choices:
            if t != last:
                pick = t
                break
        if pick is None:
            pick = choices[0][0]
        seq.append(pick)
        remaining[pick] -= 1
        if remaining[pick] <= 0:
            del remaining[pick]
        last = pick
    return seq


def _rgb_lin_to_int_srgb(rgb_lin: Vec3) -> Tuple[int, int, int]:
    r = int(round(_clamp(linear_to_srgb(rgb_lin[0])) * 255))
    g = int(round(_clamp(linear_to_srgb(rgb_lin[1])) * 255))
    b = int(round(_clamp(linear_to_srgb(rgb_lin[2])) * 255))
    return (r, g, b)


def _parse_rgba_list(s: str) -> RGBA:
    parts = [p.strip() for p in s.replace(" ", "").split(",") if p.strip()]
    if len(parts) != 4:
        raise ValueError("--rgba must be like 'r,g,b,a'")
    vals = [int(x) for x in parts]
    for v in vals:
        if v < 0 or v > 255:
            raise ValueError("RGBA values must be 0..255")
    return (vals[0], vals[1], vals[2], vals[3])


def _parse_hex_rgba(s: str) -> RGBA:
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) not in (6, 8):
        raise ValueError("--hex must be RRGGBB or RRGGBBAA")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    a = int(s[6:8], 16) if len(s) == 8 else 255
    return (r, g, b, a)


# -------- Material presets (starter values, tune later) --------
# Tokens:
#   R,G,B,W,K = red, green, blue, white, black
#   T = transparent (clear)
#   C,M,Y = cyan, magenta, yellow

MATERIAL_PRESETS: Dict[str, Dict[str, Material]] = {
    "rgbw": {
        "R": Material("R", (1.0, 0.08, 0.05), strength=10.0),
        "G": Material("G", (0.08, 1.0, 0.05), strength=10.0),
        "B": Material("B", (0.05, 0.10, 1.0), strength=10.0),
        "W": Material("W", (1.0, 1.0, 1.0), strength=6.0),
    },
    "rgbwkc": {
        "R": Material("R", (1.0, 0.08, 0.05), strength=10.0),
        "G": Material("G", (0.08, 1.0, 0.05), strength=10.0),
        "B": Material("B", (0.05, 0.10, 1.0), strength=10.0),
        "W": Material("W", (1.0, 1.0, 1.0), strength=6.0),
        "K": Material("K", (0.0, 0.0, 0.0), strength=14.0),
        "T": Material("T", (1.0, 1.0, 1.0), strength=1.5),
    },
    # 9-color: CYM + RGB + W K T
    "cymrgbwkc": {
        "C": Material("C", (0.05, 0.95, 0.95), strength=9.0),
        "M": Material("M", (0.95, 0.05, 0.95), strength=9.0),
        "Y": Material("Y", (0.95, 0.95, 0.05), strength=9.0),
        "R": Material("R", (1.0, 0.08, 0.05), strength=10.0),
        "G": Material("G", (0.08, 1.0, 0.05), strength=10.0),
        "B": Material("B", (0.05, 0.10, 1.0), strength=10.0),
        "W": Material("W", (1.0, 1.0, 1.0), strength=6.0),
        "K": Material("K", (0.0, 0.0, 0.0), strength=14.0),
        "T": Material("T", (1.0, 1.0, 1.0), strength=1.5),
    },
}


def solve_layers(
    rgba: RGBA,
    mode: str = "rgbw",
    layers: int = 5,
    layer_height: float = 0.08,
    pattern: str = "balanced",
    alpha_background: str = "white",
    forbid: Sequence[str] = (),
) -> LayerPlan:
    """Solve an RGBA -> discrete layer sequence.

    Parameters
    ----------
    rgba:
        (r,g,b,a) in 0..255.
    mode:
        'rgbw', 'rgbwkc', 'cymrgbwkc'.
    layers:
        total micro-layers.
    layer_height:
        mm per micro-layer.
    pattern:
        'balanced' (default) or 'grouped'.
    alpha_background:
        how to interpret alpha: composited onto 'white' or 'black'.
    forbid:
        iterable of tokens to disallow (e.g. forbid=('K',)).

    Returns
    -------
    LayerPlan
    """
    mode_key = mode.strip().lower()
    if mode_key not in MATERIAL_PRESETS:
        raise ValueError(f"Unknown mode: {mode}. Supported: {list(MATERIAL_PRESETS)}")
    if layers <= 0:
        raise ValueError("layers must be > 0")
    if layer_height <= 0:
        raise ValueError("layer_height must be > 0")

    mats_dict = MATERIAL_PRESETS[mode_key]
    mats = [m for t, m in mats_dict.items() if t not in set(forbid)]
    mats.sort(key=lambda m: m.token)
    tokens = [m.token for m in mats]

    r_lin, g_lin, b_lin, a_lin = rgba_to_linear_rgba(rgba)

    if alpha_background == "black":
        bg = (0.0, 0.0, 0.0)
    else:
        bg = (1.0, 1.0, 1.0)

    rgb_target = (
        r_lin * a_lin + bg[0] * (1.0 - a_lin),
        g_lin * a_lin + bg[1] * (1.0 - a_lin),
        b_lin * a_lin + bg[2] * (1.0 - a_lin),
    )

    reserve_T = 0
    has_T = any(m.token == "T" for m in mats)
    if has_T:
        reserve_T = int(round((1.0 - a_lin) * layers))
        reserve_T = max(0, min(layers, reserve_T))

    remaining_layers = layers - reserve_T
    if remaining_layers <= 0:
        counts = {t: 0 for t in tokens}
        if "T" in counts:
            counts["T"] = layers
        seq = _sequence_from_counts(tokens, [counts[t] for t in tokens], pattern)
        rgb_pred = _predict_rgb_from_counts(mats, [counts[t] for t in tokens], layer_height)
        return LayerPlan(
            mode=mode_key,
            rgba_in=rgba,
            layers=layers,
            layer_height=layer_height,
            counts=counts,
            sequence=seq,
            rgb_pred_srgb=_rgb_lin_to_int_srgb(rgb_pred),
            loss=_loss(rgb_pred, rgb_target),
        )

    mats_solve: List[Material] = []
    tokens_solve: List[str] = []
    for m in mats:
        if m.token == "T":
            continue
        mats_solve.append(m)
        tokens_solve.append(m.token)

    if not mats_solve:
        mats_solve = mats
        tokens_solve = tokens

    best_counts = None
    best_loss = float("inf")
    best_pred = (0.0, 0.0, 0.0)

    for comp in _compositions(remaining_layers, len(mats_solve)):
        rgb_pred = _predict_rgb_from_counts(mats_solve, comp, layer_height)
        L = _loss(rgb_pred, rgb_target)
        if L < best_loss:
            best_loss = L
            best_counts = comp
            best_pred = rgb_pred

    assert best_counts is not None

    counts: Dict[str, int] = {t: 0 for t in tokens}
    for t, n in zip(tokens_solve, best_counts):
        counts[t] = int(n)
    if has_T:
        counts["T"] = reserve_T

    seq = _sequence_from_counts(tokens, [counts[t] for t in tokens], pattern)

    return LayerPlan(
        mode=mode_key,
        rgba_in=rgba,
        layers=layers,
        layer_height=layer_height,
        counts=counts,
        sequence=seq,
        rgb_pred_srgb=_rgb_lin_to_int_srgb(best_pred),
        loss=best_loss,
    )


def _interactive_loop(args: argparse.Namespace) -> int:
    print("Interactive mode. Enter RGBA as r,g,b,a or hex like #RRGGBB or #RRGGBBAA.")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            s = input("RGBA/hex> ").strip()
        except EOFError:
            break
        if not s:
            continue
        if s.lower() in ("q", "quit", "exit"):
            break
        try:
            if s.startswith("#") or all(c in "0123456789abcdefABCDEF" for c in s) and len(s) in (6, 8):
                rgba = _parse_hex_rgba(s)
            else:
                rgba = _parse_rgba_list(s)
            plan = solve_layers(
                rgba,
                mode=args.mode,
                layers=args.layers,
                layer_height=args.layer_height,
                pattern=args.pattern,
                alpha_background=args.alpha_background,
                forbid=tuple(args.forbid or []),
            )
            logic = "-".join(plan.sequence)
            print(f"  mode={plan.mode} layers={plan.layers} h={plan.layer_height}mm")
            print(f"  in={plan.rgba_in}  pred_rgb={plan.rgb_pred_srgb}  loss={plan.loss:.6f}")
            print(f"  counts={ {k:v for k,v in plan.counts.items() if v>0} }")
            print(f"  seq={logic}\n")
        except Exception as e:
            print(f"  error: {e}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RGBA -> layer stack logic planner")
    p.add_argument("--mode", default="rgbw", choices=list(MATERIAL_PRESETS.keys()), help="material set")
    p.add_argument("--layers", type=int, default=5, help="micro-layer count")
    p.add_argument("--layer-height", type=float, default=0.08, help="mm per micro-layer")
    p.add_argument("--pattern", default="balanced", choices=["balanced", "grouped"], help="sequence ordering")
    p.add_argument("--alpha-background", default="white", choices=["white", "black"], help="alpha composite background")
    p.add_argument("--forbid", nargs="*", default=[], help="tokens to disallow, e.g. K T")

    g = p.add_mutually_exclusive_group()
    g.add_argument("--rgba", help="r,g,b,a in 0..255")
    g.add_argument("--hex", help="#RRGGBB or #RRGGBBAA")
    g.add_argument("--interactive", action="store_true", help="interactive prompt")

    args = p.parse_args(argv)

    if args.interactive or (args.rgba is None and args.hex is None):
        return _interactive_loop(args)

    if args.hex is not None:
        rgba = _parse_hex_rgba(args.hex)
    else:
        assert args.rgba is not None
        rgba = _parse_rgba_list(args.rgba)

    plan = solve_layers(
        rgba,
        mode=args.mode,
        layers=args.layers,
        layer_height=args.layer_height,
        pattern=args.pattern,
        alpha_background=args.alpha_background,
        forbid=tuple(args.forbid or []),
    )

    logic = "-".join(plan.sequence)
    print(logic)
    print(f"pred_rgb={plan.rgb_pred_srgb} loss={plan.loss:.6f}")
    print(f"counts={ {k:v for k,v in plan.counts.items() if v>0} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

