from __future__ import annotations

import json
import os
from typing import Dict, Mapping, Optional, Sequence, Tuple

import forward_mc
from .planner_models import (
    Vec3,
    _clamp,
    srgb_to_linear01,
    FastMaterial,
    MaterialLibrary,
)


def _default_materials_path() -> str:
    """获取默认材料配置文件的路径。

    优先返回校准后的材料文件 materials_calibrated.json，
    如果不存在则返回默认材料文件 materials.json。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 之前是 py_module/scripts/planning/
    # 现在是 py_module/scripts/src/oc_scripts/planning/
    # 目标是 repo 根目录下的 data 文件夹
    root = Path(__file__).resolve().parents[5]
    base_dir = str(root / "data")
    calibrated = os.path.join(base_dir, "materials_calibrated.json")
    if os.path.exists(calibrated):
        return calibrated
    return os.path.join(base_dir, "materials.json")


def load_materials(materials_json: Optional[str] = None) -> MaterialLibrary:
    """加载材料库配置文件并解析为 MaterialLibrary 对象。"""
    path = materials_json or _default_materials_path()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modes = {
        str(k).lower(): [str(x).upper() for x in v] for k, v in data["modes"].items()
    }
    mats = data["materials"]

    fast: Dict[str, FastMaterial] = {}
    phys: Dict[str, forward_mc.OpticalProps] = {}
    names: Dict[str, str] = {}

    for token_raw, v in mats.items():
        token = str(token_raw).upper()
        names[token] = str(v.get("name", token))

        rgb255 = v.get("color_srgb")
        if rgb255 is None or len(rgb255) != 3:
            raise ValueError(
                f"materials.json: materials.{token}.color_srgb must be [r,g,b]"
            )
        r_lin = srgb_to_linear01(float(rgb255[0]) / 255.0)
        g_lin = srgb_to_linear01(float(rgb255[1]) / 255.0)
        b_lin = srgb_to_linear01(float(rgb255[2]) / 255.0)
        strength = float(v.get("strength", 8.0))
        fast[token] = FastMaterial(
            token=token, color_lin=(r_lin, g_lin, b_lin), strength=strength
        )

        phys[token] = forward_mc.OpticalProps(
            mu_a=tuple(map(float, v["mu_a"])),
            mu_s=tuple(map(float, v["mu_s"])),
            g=float(v.get("g", 0.85)),
            n=float(v.get("n", 1.50)),
        )

    return MaterialLibrary(modes=modes, fast=fast, phys=phys, names=names)


def predict_fast_rgb_and_opacity(
    mats: Mapping[str, FastMaterial],
    seq: Sequence[str],
    heights_mm: Sequence[float],
    view: str = "top",
    backing: str = "white",
) -> Tuple[Vec3, float]:
    """使用快速前向模型预测 RGB 颜色和不透明度。

    返回: (线性 RGB 元组, 不透明度值)
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


def predict_rgb_fast_from_sequence(
    mats: Mapping[str, FastMaterial],
    seq: Sequence[str],
    heights_mm: Sequence[float],
    view: str = "top",
    backing: str = "white",
) -> Vec3:
    """使用快速前向模型从材料序列预测 RGB 颜色。"""
    rgb, _op = predict_fast_rgb_and_opacity(
        mats, seq, heights_mm, view=view, backing=backing
    )
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
    """使用蒙特卡洛前向模拟计算材料堆叠的反射颜色。

    返回: (RGB 颜色元组, 蒙特卡洛模拟结果对象)
    """
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

    rgb = forward_mc.observed_rgb_under_backing(
        res.R, res.T, backing_reflectance=backing_reflectance
    )
    return rgb, res
