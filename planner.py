from __future__ import annotations

import itertools
import json
import math
import os
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import forward_mc

RGBA = Tuple[int, int, int, int]
Vec3 = Tuple[float, float, float]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def srgb_to_linear01(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear01_to_srgb(c: float) -> float:
    c = _clamp(c)
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1 / 2.4)) - 0.055


def rgba_to_linear_rgba(rgba: RGBA) -> Tuple[float, float, float, float]:
    r, g, b, a = rgba
    rf = srgb_to_linear01(_clamp(r / 255.0))
    gf = srgb_to_linear01(_clamp(g / 255.0))
    bf = srgb_to_linear01(_clamp(b / 255.0))
    af = _clamp(a / 255.0)
    return rf, gf, bf, af


def rgba_to_linear_target(rgba: RGBA, alpha_background: str = "white") -> Vec3:
    r_lin, g_lin, b_lin, a_lin = rgba_to_linear_rgba(rgba)
    bg = (0.0, 0.0, 0.0) if alpha_background == "black" else (1.0, 1.0, 1.0)
    return (
        r_lin * a_lin + bg[0] * (1.0 - a_lin),
        g_lin * a_lin + bg[1] * (1.0 - a_lin),
        b_lin * a_lin + bg[2] * (1.0 - a_lin),
    )



def rgba_targets(
    rgba: RGBA,
    alpha_background: str = "white",
) -> Tuple[Vec3, float]:
    """Return (rgb_target_lin, opacity_target).

    - rgb_target_lin: standard alpha compositing of the input RGBA over alpha_background.
    - opacity_target: alpha interpreted as desired *opacity* in [0,1].

    Notes
    -----
    This is intentionally a lightweight semantic for 'A' that can be used even before
    you have measured real material transmittance. When you later have a calibrated
    instrument, you can replace this mapping with a data-driven target.
    """
    r_lin, g_lin, b_lin, a_lin = rgba_to_linear_rgba(rgba)
    bg = (0.0, 0.0, 0.0) if alpha_background == "black" else (1.0, 1.0, 1.0)
    rgb = (
        r_lin * a_lin + bg[0] * (1.0 - a_lin),
        g_lin * a_lin + bg[1] * (1.0 - a_lin),
        b_lin * a_lin + bg[2] * (1.0 - a_lin),
    )
    return rgb, float(a_lin)


def loss_rgba_like(
    rgb_pred: Vec3,
    rgb_target: Vec3,
    opacity_pred: float,
    opacity_target: float,
    opacity_weight: float,
    w_luma: float = 0.35,
) -> float:
    """Combined loss for color + (optional) opacity.

    opacity_weight==0 disables the opacity term.
    """
    L = loss_rgb(rgb_pred, rgb_target, w_luma=w_luma)
    if opacity_weight > 0.0:
        do = float(opacity_pred) - float(opacity_target)
        L += float(opacity_weight) * (do * do)
    return float(L)


def predict_fast_rgb_and_opacity(
    mats: Mapping[str, FastMaterial],
    seq: Sequence[str],
    heights_mm: Sequence[float],
    view: str = "top",
    backing: str = "white",
) -> Tuple[Vec3, float]:
    """Fast forward model returning (rgb_lin, opacity).

    rgb_lin is the observed color over a backing (white/black) for the chosen view.
    opacity is a simple order-invariant aggregate opacity in [0,1], defined as:
        opacity = 1 - Π_i (1 - a_i)
    where a_i is the per-layer effective opacity from FastMaterial.weight(height).

    This opacity proxy is useful as a cheap constraint when matching RGBA targets.
    """
    if len(seq) != len(heights_mm):
        raise ValueError("len(seq) must match len(heights_mm)")

    view_key = str(view).strip().lower()
    if view_key not in ("top", "bottom"):
        raise ValueError("view must be 'top' or 'bottom'")

    backing_key = str(backing).strip().lower()
    if backing_key == "white":
        rgb = [1.0, 1.0, 1.0]
    elif backing_key == "black":
        rgb = [0.0, 0.0, 0.0]
    else:
        raise ValueError("backing must be 'white' or 'black'")

    if view_key == "top":
        seq_from_backing = list(seq)
        heights_from_backing = list(heights_mm)
    else:
        seq_from_backing = list(reversed(seq))
        heights_from_backing = list(reversed(heights_mm))

    trans = 1.0
    for t, h in zip(seq_from_backing, heights_from_backing):
        m = mats[str(t).upper()]
        a = _clamp(m.weight(float(h)))
        ia = 1.0 - a
        rgb[0] = m.color_lin[0] * a + rgb[0] * ia
        rgb[1] = m.color_lin[1] * a + rgb[1] * ia
        rgb[2] = m.color_lin[2] * a + rgb[2] * ia
        trans *= ia

    opacity = 1.0 - _clamp(trans)
    return (_clamp(rgb[0]), _clamp(rgb[1]), _clamp(rgb[2])), float(opacity)

def loss_rgb(rgb_pred: Vec3, rgb_target: Vec3, w_luma: float = 0.35) -> float:
    dr = rgb_pred[0] - rgb_target[0]
    dg = rgb_pred[1] - rgb_target[1]
    db = rgb_pred[2] - rgb_target[2]
    dl = (0.2126 * dr + 0.7152 * dg + 0.0722 * db)
    return (dr * dr + dg * dg + db * db) + w_luma * (dl * dl)


def _rgb_lin_to_int_srgb(rgb_lin: Vec3) -> Tuple[int, int, int]:
    r = int(round(_clamp(linear01_to_srgb(rgb_lin[0])) * 255))
    g = int(round(_clamp(linear01_to_srgb(rgb_lin[1])) * 255))
    b = int(round(_clamp(linear01_to_srgb(rgb_lin[2])) * 255))
    return (r, g, b)


def _default_materials_path() -> str:
    return os.path.join(os.path.dirname(__file__), "materials.json")


@dataclass(frozen=True)
class FastMaterial:
    token: str
    color_lin: Vec3
    strength: float

    def weight(self, layer_height_mm: float) -> float:
        return 1.0 - math.exp(-self.strength * max(layer_height_mm, 0.0))


@dataclass(frozen=True)
class MaterialLibrary:
    modes: Dict[str, List[str]]
    fast: Dict[str, FastMaterial]
    phys: Dict[str, forward_mc.OpticalProps]
    names: Dict[str, str]


def load_materials(materials_json: Optional[str] = None) -> MaterialLibrary:
    path = materials_json or _default_materials_path()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modes = {str(k).lower(): [str(x).upper() for x in v] for k, v in data["modes"].items()}
    mats = data["materials"]

    fast: Dict[str, FastMaterial] = {}
    phys: Dict[str, forward_mc.OpticalProps] = {}
    names: Dict[str, str] = {}

    for token_raw, v in mats.items():
        token = str(token_raw).upper()
        names[token] = str(v.get("name", token))

        rgb255 = v.get("color_srgb")
        if rgb255 is None or len(rgb255) != 3:
            raise ValueError(f"materials.json: materials.{token}.color_srgb must be [r,g,b]")
        r_lin = srgb_to_linear01(float(rgb255[0]) / 255.0)
        g_lin = srgb_to_linear01(float(rgb255[1]) / 255.0)
        b_lin = srgb_to_linear01(float(rgb255[2]) / 255.0)
        strength = float(v.get("strength", 8.0))
        fast[token] = FastMaterial(token=token, color_lin=(r_lin, g_lin, b_lin), strength=strength)

        phys[token] = forward_mc.OpticalProps(
            mu_a=tuple(map(float, v["mu_a"])),
            mu_s=tuple(map(float, v["mu_s"])),
            g=float(v.get("g", 0.85)),
            n=float(v.get("n", 1.50)),
        )

    return MaterialLibrary(modes=modes, fast=fast, phys=phys, names=names)


def mode_tokens(lib: MaterialLibrary, mode: str, forbid: Sequence[str] = ()) -> List[str]:
    mode_key = mode.strip().lower()
    if mode_key not in lib.modes:
        raise ValueError(f"Unknown mode: {mode}. Supported: {sorted(lib.modes.keys())}")
    bad = {str(x).upper() for x in forbid}
    toks = [t for t in lib.modes[mode_key] if t not in bad]
    if not toks:
        raise ValueError("No materials left after forbid")
    return toks


def _compositions(total: int, parts: int) -> Iterable[List[int]]:
    for cuts in itertools.combinations(range(total + parts - 1), parts - 1):
        prev = -1
        comp: List[int] = []
        for c in cuts:
            comp.append(c - prev - 1)
            prev = c
        comp.append((total + parts - 1) - prev - 1)
        yield comp


def _sequence_from_counts(tokens: List[str], counts: List[int], pattern: str) -> List[str]:
    if pattern == "grouped":
        seq: List[str] = []
        for t, n in sorted(zip(tokens, counts), key=lambda x: (-x[1], x[0])):
            seq.extend([t] * n)
        return seq

    remaining = {t: n for t, n in zip(tokens, counts) if n > 0}
    last: Optional[str] = None
    seq = []
    while remaining:
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




def predict_rgb_fast_from_sequence(
    mats: Mapping[str, FastMaterial],
    seq: Sequence[str],
    heights_mm: Sequence[float],
    view: str = "top",
    backing: str = "white",
) -> Vec3:
    rgb, _op = predict_fast_rgb_and_opacity(mats, seq, heights_mm, view=view, backing=backing)
    return rgb


def forward_rgb(
    seq: Sequence[str],
    heights_mm: Sequence[float],
    view: str = "top",
    backing: str = "white",
    samples: int = 200000,
    seed: int = 0,
    materials_json: Optional[str] = None,
) -> Tuple[Vec3, forward_mc.MCResult]:
    lib = load_materials(materials_json)

    backing_reflectance = (1.0, 1.0, 1.0) if backing == "white" else (0.0, 0.0, 0.0)

    seq_top_to_bottom = list(reversed([str(x).upper() for x in seq]))
    heights_top_to_bottom = list(reversed([float(h) for h in heights_mm]))

    res = forward_mc.forward_reflect_transmit(
        seq=seq_top_to_bottom,
        heights=heights_top_to_bottom,
        materials=lib.phys,
        view=view,
        samples=int(samples),
        seed=int(seed),
    )

    rgb = forward_mc.observed_rgb_under_backing(res.R, res.T, backing_reflectance=backing_reflectance)
    return rgb, res



def opacity_from_transmittance(T: Vec3) -> float:
    """Approximate opacity from spectral transmittance.

    We map opacity = 1 - luma(T). This is a simple proxy; after you have
    measurement data you can replace it with a calibrated mapping.
    """
    t = _clamp(0.2126 * T[0] + 0.7152 * T[1] + 0.0722 * T[2])
    return float(_clamp(1.0 - t))

@dataclass(frozen=True)
class PlanResult:
    method: str
    rgba: RGBA
    mode: str
    sequence: List[str]
    heights_mm: List[float]
    view: str
    backing: str
    pred_rgb_srgb: Tuple[int, int, int]
    pred_rgb_lin: Vec3
    loss: float
    phys_R: Optional[Vec3]
    phys_T: Optional[Vec3]
    samples: Optional[int]
    seed: Optional[int]

    def as_dict(self) -> Dict[str, object]:
        return {
            "method": self.method,
            "rgba": list(self.rgba),
            "mode": self.mode,
            "sequence": list(self.sequence),
            "heights_mm": list(self.heights_mm),
            "view": self.view,
            "backing": self.backing,
            "pred_rgb_srgb": list(self.pred_rgb_srgb),
            "pred_rgb_lin": list(self.pred_rgb_lin),
            "loss": float(self.loss),
            "phys_R": list(self.phys_R) if self.phys_R is not None else None,
            "phys_T": list(self.phys_T) if self.phys_T is not None else None,
            "samples": self.samples,
            "seed": self.seed,
        }


def _build_heights(layers: int, first_layer_height: float, layer_height: float) -> List[float]:
    if layers <= 0:
        raise ValueError("layers must be > 0")
    if first_layer_height <= 0 or layer_height <= 0:
        raise ValueError("layer heights must be > 0")
    if layers == 1:
        return [float(first_layer_height)]
    return [float(first_layer_height)] + [float(layer_height)] * (layers - 1)




def _fast_candidates(
    rgba: RGBA,
    mode: str,
    layers: int,
    first_layer_height: float,
    layer_height: float,
    pattern: str,
    alpha_background: str,
    forbid: Sequence[str],
    view: str,
    backing: str,
    max_candidates: int,
    brute_force_threshold: int,
    opacity_weight: Optional[float],
    materials_json: Optional[str],
) -> List[Tuple[List[str], List[float], Vec3, float]]:
    """Generate candidate sequences using the fast forward model.

    Strategy
    --------
    - If the full sequence space is small enough (<= brute_force_threshold), enumerate
      all sequences and return the best max_candidates.
    - Otherwise, for uniform heights we enumerate *compositions* (layer-count allocations)
      to get good material ratios, then expand each with multiple orderings/shuffles.

    Important
    ---------
    This function scores candidates with a *sequence-order-aware* fast forward model,
    so it will not collapse different orders with the same counts.
    """

    lib = load_materials(materials_json)
    tokens = mode_tokens(lib, mode, forbid=forbid)
    mats_fast = lib.fast

    heights = _build_heights(layers, first_layer_height=first_layer_height, layer_height=layer_height)

    rgb_target, opacity_target = rgba_targets(rgba, alpha_background=alpha_background)
    if opacity_weight is None:
        # Auto-enable alpha matching only when alpha is not fully opaque.
        opacity_weight = 0.20 if opacity_target < 0.999 else 0.0

    toks_sorted = sorted(tokens)
    space = len(toks_sorted) ** layers

    # 1) Exact brute force for small spaces.
    if space <= int(brute_force_threshold):
        scored: List[Tuple[float, List[str], Vec3]] = []
        for seq0 in itertools.product(toks_sorted, repeat=layers):
            s0 = list(seq0)
            rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(
                mats_fast, s0, heights, view=view, backing=backing
            )
            L = loss_rgba_like(rgb_pred, rgb_target, opacity_pred, opacity_target, float(opacity_weight))
            scored.append((L, s0, rgb_pred))
        scored.sort(key=lambda x: x[0])
        out: List[Tuple[List[str], List[float], Vec3, float]] = []
        for L, s0, rgb_pred in scored[:max(1, int(max_candidates))]:
            out.append((s0, heights, rgb_pred, L))
        return out

    # 2) Larger spaces: heuristic candidate generation.
    uniform = all(abs(h - heights[0]) <= 1e-12 for h in heights)
    if not uniform:
        # Non-uniform is rare for your workflow; keep a conservative exact limit.
        if space > 200000:
            raise ValueError(f"Search space too large for non-uniform heights: {space}")
        scored: List[Tuple[float, List[str], Vec3]] = []
        for seq0 in itertools.product(toks_sorted, repeat=layers):
            s0 = list(seq0)
            rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(
                mats_fast, s0, heights, view=view, backing=backing
            )
            L = loss_rgba_like(rgb_pred, rgb_target, opacity_pred, opacity_target, float(opacity_weight))
            scored.append((L, s0, rgb_pred))
        scored.sort(key=lambda x: x[0])
        out: List[Tuple[List[str], List[float], Vec3, float]] = []
        for L, s0, rgb_pred in scored[:max(1, int(max_candidates))]:
            out.append((s0, heights, rgb_pred, L))
        return out

    # Uniform heights: composition -> ordering expansion.
    comps: List[Tuple[float, List[int]]] = []
    for comp in _compositions(layers, len(toks_sorted)):
        seq0 = _sequence_from_counts(toks_sorted, comp, pattern=pattern)
        rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(mats_fast, seq0, heights, view=view, backing=backing)
        L = loss_rgba_like(rgb_pred, rgb_target, opacity_pred, opacity_target, float(opacity_weight))
        comps.append((L, comp))
    comps.sort(key=lambda x: x[0])

    rng = random.Random(0)
    seen: set[Tuple[str, ...]] = set()
    scored2: List[Tuple[float, List[str], Vec3]] = []

    def _try_add(s0: List[str]) -> None:
        key = tuple(s0)
        if key in seen:
            return
        seen.add(key)
        rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(mats_fast, s0, heights, view=view, backing=backing)
        L = loss_rgba_like(rgb_pred, rgb_target, opacity_pred, opacity_target, float(opacity_weight))
        scored2.append((L, s0, rgb_pred))

    seed_comps = max(1, min(len(comps), max(12, int(max_candidates))))
    rand_per_comp = max(3, int(max_candidates) // seed_comps)

    for _Lcomp, counts in comps[:seed_comps]:
        expanded: List[str] = []
        for t, n in zip(toks_sorted, counts):
            expanded.extend([t] * int(n))

        base_seq = _sequence_from_counts(toks_sorted, counts, pattern=pattern)
        _try_add(list(base_seq))
        _try_add(list(reversed(base_seq)))
        _try_add(_sequence_from_counts(toks_sorted, counts, pattern="grouped"))

        for _ in range(rand_per_comp * 8):
            s1 = list(expanded)
            rng.shuffle(s1)
            _try_add(s1)
            if len(seen) >= int(max_candidates) * 20:
                break
        if len(seen) >= int(max_candidates) * 20:
            break

    # Add a few global random sequences for diversity.
    for _ in range(int(max_candidates) * 6):
        s2 = [rng.choice(toks_sorted) for _ in range(layers)]
        _try_add(s2)
        if len(seen) >= int(max_candidates) * 24:
            break

    scored2.sort(key=lambda x: x[0])
    out: List[Tuple[List[str], List[float], Vec3, float]] = []
    for L, s0, rgb_pred in scored2[:max(1, int(max_candidates))]:
        out.append((s0, heights, rgb_pred, L))
    return out




def solve_layers_fast(
    rgba: RGBA,
    mode: str = "rgbw",
    layers: int = 5,
    first_layer_height: float = 0.12,
    layer_height: float = 0.08,
    pattern: str = "balanced",
    alpha_background: str = "white",
    forbid: Sequence[str] = (),
    view: str = "bottom",
    backing: str = "white",
    candidates: int = 64,
    brute_force_threshold: int = 60000,
    opacity_weight: Optional[float] = None,
    materials_json: Optional[str] = None,
) -> PlanResult:
    """Search the best layer sequence using the fast forward model.

    Defaults are tuned for *bottom-view* (i.e. looking from the bed/contact face).
    """
    cands = _fast_candidates(
        rgba=rgba,
        mode=mode,
        layers=layers,
        first_layer_height=first_layer_height,
        layer_height=layer_height,
        pattern=pattern,
        alpha_background=alpha_background,
        forbid=forbid,
        view=view,
        backing=backing,
        max_candidates=max(1, int(candidates)),
        brute_force_threshold=int(brute_force_threshold),
        opacity_weight=opacity_weight,
        materials_json=materials_json,
    )
    seq, heights, pred, L = cands[0]
    return PlanResult(
        method="fast",
        rgba=rgba,
        mode=mode.strip().lower(),
        sequence=list(seq),
        heights_mm=list(heights),
        view=view,
        backing=backing,
        pred_rgb_srgb=_rgb_lin_to_int_srgb(pred),
        pred_rgb_lin=pred,
        loss=L,
        phys_R=None,
        phys_T=None,
        samples=None,
        seed=None,
    )


def solve_layers_phys(
    rgba: RGBA,
    mode: str = "rgbw",
    layers: int = 5,
    first_layer_height: float = 0.12,
    layer_height: float = 0.08,
    pattern: str = "balanced",
    alpha_background: str = "white",
    forbid: Sequence[str] = (),
    view: str = "bottom",
    backing: str = "white",
    samples: int = 80000,
    seed: int = 0,
    candidates: int = 48,
    brute_force_threshold: int = 60000,
    opacity_weight: Optional[float] = None,
    materials_json: Optional[str] = None,
) -> PlanResult:
    """Refine best sequences using Monte Carlo (physical) forward model."""
    rgb_target, opacity_target = rgba_targets(rgba, alpha_background=alpha_background)
    if opacity_weight is None:
        # Auto-enable alpha matching only when alpha is not fully opaque.
        opacity_weight = 0.20 if opacity_target < 0.999 else 0.0

    cands = _fast_candidates(
        rgba=rgba,
        mode=mode,
        layers=layers,
        first_layer_height=first_layer_height,
        layer_height=layer_height,
        pattern=pattern,
        alpha_background=alpha_background,
        forbid=forbid,
        view=view,
        backing=backing,
        max_candidates=max(1, int(candidates)),
        brute_force_threshold=int(brute_force_threshold),
        opacity_weight=opacity_weight,
        materials_json=materials_json,
    )

    # Physical evaluation: use observed RGB over the chosen backing.
    backing_reflectance = (1.0, 1.0, 1.0) if backing == "white" else (0.0, 0.0, 0.0)

    best: Optional[PlanResult] = None
    for seq, heights, _pred_fast, _L_fast in cands:
        pred_lin, res = forward_rgb(
            seq=seq,
            heights_mm=heights,
            view=view,
            backing=backing,
            samples=samples,
            seed=seed,
            materials_json=materials_json,
        )

        # Opacity proxy from transmittance (higher T -> more background shows through).
        T = res.T
        t_luma = _clamp(0.2126 * T[0] + 0.7152 * T[1] + 0.0722 * T[2])
        opacity_pred = _clamp(1.0 - t_luma)

        Lp = loss_rgba_like(pred_lin, rgb_target, opacity_pred, opacity_target, float(opacity_weight))

        pr = PlanResult(
            method="phys",
            rgba=rgba,
            mode=mode.strip().lower(),
            sequence=list(seq),
            heights_mm=list(heights),
            view=view,
            backing=backing,
            pred_rgb_srgb=_rgb_lin_to_int_srgb(pred_lin),
            pred_rgb_lin=pred_lin,
            loss=Lp,
            phys_R=res.R,
            phys_T=res.T,
            samples=int(samples),
            seed=int(seed),
        )
        if best is None or pr.loss < best.loss:
            best = pr

    assert best is not None
    return best
