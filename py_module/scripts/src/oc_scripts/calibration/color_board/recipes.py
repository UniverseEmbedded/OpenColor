from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


def clamp(x: float, a: float, b: float) -> float:
    """将数值限制在指定范围内"""
    return max(a, min(b, x))


def rgb_hex(rgb: Tuple[int, int, int]) -> str:
    """将RGB元组转换为十六进制颜色字符串"""
    r, g, b = rgb
    r = int(clamp(r, 0, 255))
    g = int(clamp(g, 0, 255))
    b = int(clamp(b, 0, 255))
    return f"#{r:02X}{g:02X}{b:02X}"


def mix_srgb(ch_fracs: Dict[str, float]) -> Tuple[int, int, int]:
    """
    仅用于预览：在sRGB空间中进行简单的线性混合
    这不代表实际打印结果，仅用于在SVG中可视化色块
    通道假设为：R,G,B,W（W会等量增加所有通道）
    """
    fR = ch_fracs.get("R", 0.0)
    fG = ch_fracs.get("G", 0.0)
    fB = ch_fracs.get("B", 0.0)
    fW = ch_fracs.get("W", 0.0)

    s = fR + fG + fB + fW
    if s <= 1e-9:
        return (0, 0, 0)
    fR, fG, fB, fW = fR / s, fG / s, fB / s, fW / s

    r = 255.0 * (fR + fW)
    g = 255.0 * (fG + fW)
    b = 255.0 * (fB + fW)

    return (
        int(clamp(round(r), 0, 255)),
        int(clamp(round(g), 0, 255)),
        int(clamp(round(b), 0, 255)),
    )


@dataclass
class SwatchRecipe:
    """色块配方数据类，描述色块的打印配置"""

    channels: List[str]  # 使用的通道列表（如['R','G']）
    fractions: Dict[str, float]  # 各通道的比例
    total_layers: int  # 总层数
    layer_height_mm: float  # 每层高度（毫米）
    layer_sequence: List[str]  # 层序列表


def make_layer_sequence(fractions: Dict[str, float], total_layers: int) -> List[str]:
    """
    将连续比例转换为离散的每层序列

    策略：
    - 使用最大余数法将比例转换为目标计数
    - 交错排列以避免长连续段（简单贪心间距）
    """
    chans = [c for c in ["R", "G", "B", "W"] if fractions.get(c, 0.0) > 0]
    s = sum(fractions.get(c, 0.0) for c in chans)
    if s <= 1e-9:
        return ["W"] * total_layers

    frac_n = {c: fractions.get(c, 0.0) / s for c in chans}

    raw = {c: frac_n[c] * total_layers for c in chans}
    floor_counts = {c: int(math.floor(raw[c])) for c in chans}
    remainder = total_layers - sum(floor_counts.values())
    rema = sorted(((raw[c] - floor_counts[c], c) for c in chans), reverse=True)
    counts = dict(floor_counts)
    for i in range(remainder):
        counts[rema[i % len(rema)][1]] += 1

    seq: List[str] = []
    last = None
    while sum(counts.values()) > 0:
        candidates = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        pick = None
        for c, n in candidates:
            if n <= 0:
                continue
            if c != last:
                pick = c
                break
        if pick is None:
            pick = candidates[0][0]
        seq.append(pick)
        counts[pick] -= 1
        last = pick

    return seq


def generate_swatch_recipes(
    layer_height_mm: float,
    single_layers: List[int],
    mix_layers: int,
    mix_steps: List[float],
    include_white_mixes: bool = True,
) -> List[Tuple[str, str, SwatchRecipe, str]]:
    """
    生成色块配方列表

    返回元组列表：(类型, 配方键, 配方对象, 标签文本)
    配方键是用于标识的稳定字符串
    """
    out = []

    # 生成单色配方
    for c in ["R", "G", "B", "W"]:
        for L in single_layers:
            fr = {c: 1.0}
            seq = make_layer_sequence(fr, L)
            rcp = SwatchRecipe(
                channels=[c],
                fractions=fr,
                total_layers=L,
                layer_height_mm=layer_height_mm,
                layer_sequence=seq,
            )
            key = f"SINGLE_{c}_L{L}"
            label = f"{c}  L={L}"
            out.append(("single", key, rcp, label))

    # 定义混合色对
    pairs = [("R", "G"), ("R", "B"), ("G", "B")]
    if include_white_mixes:
        pairs += [("R", "W"), ("G", "W"), ("B", "W")]

    # 生成混合配方
    for a, b in pairs:
        for fa in mix_steps:
            fb = 1.0 - fa
            fr = {a: fa, b: fb}
            seq = make_layer_sequence(fr, mix_layers)
            rcp = SwatchRecipe(
                channels=[a, b],
                fractions=fr,
                total_layers=mix_layers,
                layer_height_mm=layer_height_mm,
                layer_sequence=seq,
            )
            key = f"PAIR_{a}{b}_A{int(round(fa * 100)):03d}_L{mix_layers}"
            label = f"{a}:{int(round(fa * 100))}% {b}:{int(round(fb * 100))}%"
            out.append(("pair_mix", key, rcp, label))

    return out
