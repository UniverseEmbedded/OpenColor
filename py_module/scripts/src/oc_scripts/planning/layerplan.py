#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""RGBA -> 层叠规划器（初始灰盒模型）

- 作为库使用:  from layerplan import solve_layers
- 作为命令行:  python layerplan.py --rgba 255,200,0,255 --mode rgbwkc

前向模型故意设计得简单（不使用Kubelka-Munk，无查找数据库）：
  - 每种材料m具有基础线性RGB颜色c_m和强度s_m
  - 每层厚度h的贡献权重为 w_m = 1 - exp(-s_m * h)
  - 具有层数n_m的堆叠预测值为：
        rgb = (sum n_m * w_m * c_m) / (sum n_m * w_m)

给定目标RGBA，我们在`layers`层中暴力枚举所有整数组合（层数通常较小，如5~12）
以最小化线性RGB中的误差。
然后输出有序序列，如 R-G-W-W-R。

参数调优
------
你可以在下方调整MATERIAL_PRESETS（颜色/强度）。获得单材料测量值后，
用拟合值替换预设。
"""

from __future__ import annotations

import argparse
import itertools
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
Vec3 = Tuple[float, float, float]
RGBA = Tuple[int, int, int, int]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def srgb_to_linear(c: float) -> float:
    """将sRGB（0..1）转换为线性RGB（0..1）"""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    """将线性RGB（0..1）转换为sRGB（0..1）"""
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
    color_lin: Vec3  # 线性RGB中的基础颜色
    strength: float  # 越高表示每层影响力越大

    def weight(self, layer_height_mm: float) -> float:
        # 小型指数模型提供平滑的有界权重（0..1）
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
    # 材料颜色的加权平均
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
    # 简单的加权平方误差，略微强调亮度
    dr = rgb_pred[0] - rgb_target[0]
    dg = rgb_pred[1] - rgb_target[1]
    db = rgb_pred[2] - rgb_target[2]
    # 线性空间中的近似亮度
    dl = 0.2126 * dr + 0.7152 * dg + 0.0722 * db
    return (dr * dr + dg * dg + db * db) + w_luma * (dl * dl)


def _compositions(total: int, parts: int) -> Iterable[List[int]]:
    """将总数分解为'parts'个部分的非负整数组合"""
    # 通过切割位置组合实现星条法
    # 复杂度: C(total+parts-1, parts-1)
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
    """从计数创建有序层序列"""
    seq: List[str] = []
    if pattern == "grouped":
        for t, n in sorted(zip(tokens, counts), key=lambda x: (-x[1], x[0])):
            seq.extend([t] * n)
        return seq

    # balanced: 轮询分布层以获得更平滑的堆叠
    remaining = {t: n for t, n in zip(tokens, counts) if n > 0}
    # 从出现最频繁的token开始以减少早期偏差
    last = None
    while remaining:
        # 按剩余计数排序，尽可能不重复上一个
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
        raise ValueError("--rgba 必须是 'r,g,b,a' 格式")
    vals = [int(x) for x in parts]
    for v in vals:
        if v < 0 or v > 255:
            raise ValueError("RGBA值必须在0..255范围内")
    return (vals[0], vals[1], vals[2], vals[3])


def _parse_hex_rgba(s: str) -> RGBA:
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) not in (6, 8):
        raise ValueError("--hex 必须是 RRGGBB 或 RRGGBBAA 格式")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    a = int(s[6:8], 16) if len(s) == 8 else 255
    return (r, g, b, a)


# -------- 材料预设（初始值，后续可调优） --------
# 标记：
#   R,G,B,W,K = 红、绿、蓝、白、黑
#   T = 透明（清澈）
#   C,M,Y = 青、品红、黄

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
    # 9色: CYM + RGB + W K T
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
    """求解 RGBA -> 离散层序列

    参数
    ----------
    rgba:
        (r,g,b,a) 范围0..255
    mode:
        'rgbw', 'rgbwkc', 'cymrgbwkc'
    layers:
        总微层数
    layer_height:
        每微层毫米数
    pattern:
        'balanced'（默认）或 'grouped'
    alpha_background:
        如何解释alpha：合成到'white'或'black'上
    forbid:
        要禁用的标记可迭代对象（如 forbid=('K',)）

    返回
    -------
    LayerPlan
    """
    mode_key = mode.strip().lower()
    if mode_key not in MATERIAL_PRESETS:
        raise ValueError(f"未知模式: {mode}。支持的: {list(MATERIAL_PRESETS)}")
    if layers <= 0:
        raise ValueError("层数必须 > 0")
    if layer_height <= 0:
        raise ValueError("层高度必须 > 0")

    mats_dict = MATERIAL_PRESETS[mode_key]
    mats = [m for t, m in mats_dict.items() if t not in set(forbid)]
    mats.sort(key=lambda m: m.token)
    tokens = [m.token for m in mats]

    # 线性空间中的目标颜色
    r_lin, g_lin, b_lin, a_lin = rgba_to_linear_rgba(rgba)

    # 将alpha视为在背景上合成的"覆盖率"
    if alpha_background == "black":
        bg = (0.0, 0.0, 0.0)
    else:
        bg = (1.0, 1.0, 1.0)

    rgb_target = (
        r_lin * a_lin + bg[0] * (1.0 - a_lin),
        g_lin * a_lin + bg[1] * (1.0 - a_lin),
        b_lin * a_lin + bg[2] * (1.0 - a_lin),
    )

    # 可选：根据alpha预留一些透明层
    # 当模式包含'T'时这会改善行为
    reserve_T = 0
    has_T = any(m.token == "T" for m in mats)
    if has_T:
        reserve_T = int(round((1.0 - a_lin) * layers))
        reserve_T = max(0, min(layers, reserve_T))

    remaining_layers = layers - reserve_T
    if remaining_layers <= 0:
        # 全部透明
        counts = {t: 0 for t in tokens}
        if "T" in counts:
            counts["T"] = layers
        seq = _sequence_from_counts(tokens, [counts[t] for t in tokens], pattern)
        rgb_pred = _predict_rgb_from_counts(
            mats, [counts[t] for t in tokens], layer_height
        )
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

    # 如果预留T，则在不包含T的情况下求解剩余组合，然后加回T
    mats_solve: List[Material] = []
    tokens_solve: List[str] = []
    for m in mats:
        if m.token == "T":
            continue
        mats_solve.append(m)
        tokens_solve.append(m.token)

    # 如果T是唯一材料（如用户禁用了其他所有材料），则回退
    if not mats_solve:
        mats_solve = mats
        tokens_solve = tokens

    best_counts = None
    best_loss = float("inf")
    best_pred = (0.0, 0.0, 0.0)

    # 枚举剩余层的整数组合
    for comp in _compositions(remaining_layers, len(mats_solve)):
        rgb_pred = _predict_rgb_from_counts(mats_solve, comp, layer_height)
        L = _loss(rgb_pred, rgb_target)
        if L < best_loss:
            best_loss = L
            best_counts = comp
            best_pred = rgb_pred

    assert best_counts is not None

    # 构建完整计数字典
    counts: Dict[str, int] = {t: 0 for t in tokens}
    for t, n in zip(tokens_solve, best_counts):
        counts[t] = int(n)
    if has_T:
        counts["T"] = reserve_T

    # 创建最终序列
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
    logger.info("交互模式。输入RGBA格式为 r,g,b,a 或十六进制如 #RRGGBB 或 #RRGGBBAA")
    logger.info("输入 'quit' 退出\n")
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
            if (
                s.startswith("#")
                or all(c in "0123456789abcdefABCDEF" for c in s)
                and len(s) in (6, 8)
            ):
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
            logger.info(
                f"  模式={plan.mode} 层数={plan.layers} 高度={plan.layer_height}mm"
            )
            logger.info(
                f"  输入={plan.rgba_in}  预测RGB={plan.rgb_pred_srgb}  损失={plan.loss:.6f}"
            )
            logger.info(f"  计数={ {k: v for k, v in plan.counts.items() if v > 0} }")
            logger.info(f"  序列={logic}\n")
        except Exception as e:
            logger.error(f"  错误: {e}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RGBA -> 层叠逻辑规划器")
    p.add_argument(
        "--mode", default="rgbw", choices=list(MATERIAL_PRESETS.keys()), help="材料集合"
    )
    p.add_argument("--layers", type=int, default=5, help="微层数量")
    p.add_argument("--layer-height", type=float, default=0.08, help="每微层毫米数")
    p.add_argument(
        "--pattern",
        default="balanced",
        choices=["balanced", "grouped"],
        help="序列排序方式",
    )
    p.add_argument(
        "--alpha-background",
        default="white",
        choices=["white", "black"],
        help="alpha合成背景",
    )
    p.add_argument("--forbid", nargs="*", default=[], help="禁用的标记，如 K T")

    g = p.add_mutually_exclusive_group()
    g.add_argument("--rgba", help="r,g,b,a 范围0..255")
    g.add_argument("--hex", help="#RRGGBB 或 #RRGGBBAA")
    g.add_argument("--interactive", action="store_true", help="交互式提示")

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
    logger.info(logic)
    logger.info(f"预测RGB={plan.rgb_pred_srgb} 损失={plan.loss:.6f}")
    logger.info(f"计数={ {k: v for k, v in plan.counts.items() if v > 0} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
