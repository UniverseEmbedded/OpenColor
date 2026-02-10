#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
生成多色校准板（SVG）+ 按色块配方元数据（JSON/CSV）。

设计目标（反"数据库查询"方法）：
- 校准板定义了一组已知"配方"的色块（层堆叠/通道分数/厚度）。
- 打印和拍照后，系统拟合光学/经验参数或小模型。
- 后续配方生成使用拟合模型的连续推理/优化（运行时无需数据库查询）。

输出：
- calibration_board.svg
- calibration_board_recipes.json
- （可选）calibration_board_recipes.csv

使用示例：
  python make_calibration_board.py --outdir out_board --page A4 --rows 8 --cols 6 --layer_h 0.2

说明：
- SVG单位为毫米。
- 每个色块包含：
  - swatch_id
  - x_mm, y_mm, w_mm, h_mm
  - recipe: (channels, fractions, total_layers, layer_sequence)
  - display_color (sRGB) 仅用于人类预览
"""

from __future__ import annotations
import argparse
import csv
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# -----------------------------
# 基础辅助函数
# -----------------------------
def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def mm(n: float) -> str:
    # 格式化毫米，最小噪声
    if abs(n - round(n)) < 1e-6:
        return str(int(round(n)))
    return f"{n:.3f}".rstrip("0").rstrip(".")


def rgb_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    r = int(clamp(r, 0, 255))
    g = int(clamp(g, 0, 255))
    b = int(clamp(b, 0, 255))
    return f"#{r:02X}{g:02X}{b:02X}"


def mix_srgb(ch_fracs: Dict[str, float]) -> Tuple[int, int, int]:
    """
    仅用于预览：在sRGB中进行简单线性混合。
    这不代表打印结果；仅用于在SVG中可视化色块。
    假设通道为：R,G,B,W（W等量增加所有通道）。
    """
    fR = ch_fracs.get("R", 0.0)
    fG = ch_fracs.get("G", 0.0)
    fB = ch_fracs.get("B", 0.0)
    fW = ch_fracs.get("W", 0.0)

    # 归一化（避免奇怪的总和）
    s = fR + fG + fB + fW
    if s <= 1e-9:
        return (0, 0, 0)
    fR, fG, fB, fW = fR / s, fG / s, fB / s, fW / s

    # "W"等量贡献
    r = 255.0 * (fR + fW)
    g = 255.0 * (fG + fW)
    b = 255.0 * (fB + fW)

    # 钳制
    return (int(clamp(round(r), 0, 255)),
            int(clamp(round(g), 0, 255)),
            int(clamp(round(b), 0, 255)))


# -----------------------------
# 配方定义
# -----------------------------
@dataclass
class SwatchRecipe:
    channels: List[str]                 # 例如 ["R","G"]
    fractions: Dict[str, float]         # 例如 {"R":0.75,"G":0.25}
    total_layers: int                   # 例如 4
    layer_height_mm: float              # 例如 0.2
    layer_sequence: List[str]           # 例如 ["R","G","R","R"]


@dataclass
class Swatch:
    swatch_id: str
    kind: str                           # 例如 "single", "pair_mix"
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    recipe: SwatchRecipe
    display_rgb: Tuple[int, int, int]   # 仅预览
    label: str                          # SVG中绘制的短文本


def make_layer_sequence(fractions: Dict[str, float], total_layers: int) -> List[str]:
    """
    将连续分数转换为离散每层序列。

    策略：
    - 将分数 -> 目标计数，使用最大余数舍入
    - 交错以避免长连续（简单贪婪间隔）
    """
    # 归一化
    chans = [c for c in ["R", "G", "B", "W"] if fractions.get(c, 0.0) > 0]
    s = sum(fractions.get(c, 0.0) for c in chans)
    if s <= 1e-9:
        return ["W"] * total_layers  # 回退

    frac_n = {c: fractions.get(c, 0.0) / s for c in chans}

    # 最大余数舍入
    raw = {c: frac_n[c] * total_layers for c in chans}
    floor_counts = {c: int(math.floor(raw[c])) for c in chans}
    remainder = total_layers - sum(floor_counts.values())
    rema = sorted(((raw[c] - floor_counts[c], c) for c in chans), reverse=True)
    counts = dict(floor_counts)
    for i in range(remainder):
        counts[rema[i % len(rema)][1]] += 1

    # 贪婪交错：总是选择剩余计数最高的，尽可能避免重复
    seq: List[str] = []
    last = None
    while sum(counts.values()) > 0:
        # 候选按剩余计数降序排序；尽可能避免重复上一个
        candidates = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        pick = None
        for c, n in candidates:
            if n <= 0:
                continue
            if c != last:
                pick = c
                break
        if pick is None:
            # 必须重复
            pick = candidates[0][0]
        seq.append(pick)
        counts[pick] -= 1
        last = pick

    return seq


# -----------------------------
# DOE：选择色块
# -----------------------------
def generate_swatch_recipes(
        layer_height_mm: float,
        single_layers: List[int],
        mix_layers: int,
        mix_steps: List[float],
        include_white_mixes: bool = True,
) -> List[Tuple[str, str, SwatchRecipe, str]]:
    """
    返回元组列表：
      (kind, recipe_key, recipe, label_text)

    recipe_key是用于标识的稳定字符串。
    """
    out = []

    # 单色：R/G/B/W多种厚度
    for c in ["R", "G", "B", "W"]:
        for L in single_layers:
            fr = {c: 1.0}
            seq = make_layer_sequence(fr, L)
            rcp = SwatchRecipe(channels=[c], fractions=fr, total_layers=L,
                               layer_height_mm=layer_height_mm, layer_sequence=seq)
            key = f"SINGLE_{c}_L{L}"
            label = f"{c}  L={L}"
            out.append(("single", key, rcp, label))

    # 双色混合
    pairs = [("R", "G"), ("R", "B"), ("G", "B")]
    if include_white_mixes:
        pairs += [("R", "W"), ("G", "W"), ("B", "W")]

    for a, b in pairs:
        for fa in mix_steps:
            fb = 1.0 - fa
            fr = {a: fa, b: fb}
            # 如果需要更少可以跳过退化0/1端点；默认保留
            seq = make_layer_sequence(fr, mix_layers)
            rcp = SwatchRecipe(channels=[a, b], fractions=fr, total_layers=mix_layers,
                               layer_height_mm=layer_height_mm, layer_sequence=seq)
            key = f"PAIR_{a}{b}_A{int(round(fa*100)):03d}_L{mix_layers}"
            label = f"{a}:{int(round(fa*100))}% {b}:{int(round(fb*100))}%"
            out.append(("pair_mix", key, rcp, label))

    return out


# -----------------------------
# SVG布局
# -----------------------------
PAGE_SIZES_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "LETTER": (215.9, 279.4),
}


def svg_header(w_mm: float, h_mm: float) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{mm(w_mm)}mm" height="{mm(h_mm)}mm" '
        f'viewBox="0 0 {mm(w_mm)} {mm(h_mm)}">\n'
        f'<rect x="0" y="0" width="{mm(w_mm)}" height="{mm(h_mm)}" fill="#FFFFFF"/>\n'
    )


def svg_footer() -> str:
    return "</svg>\n"


def svg_text(x: float, y: float, s: str, size: float = 3.2, fill: str = "#111",
             anchor: str = "start", weight: str = "normal") -> str:
    # y是SVG中的基线；小标签没问题
    s_esc = (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (f'<text x="{mm(x)}" y="{mm(y)}" font-size="{mm(size)}" '
            f'font-family="monospace" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{s_esc}</text>\n')


def svg_rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "#000",
             stroke_w: float = 0.35, rx: float = 0.0) -> str:
    rxs = f' rx="{mm(rx)}" ry="{mm(rx)}"' if rx > 0 else ""
    return (f'<rect x="{mm(x)}" y="{mm(y)}" width="{mm(w)}" height="{mm(h)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{mm(stroke_w)}"{rxs}/>\n')


def svg_fiducial(x: float, y: float, size: float) -> str:
    """
    简单高对比度基准标记（黑色方块 + 白色内嵌 + 黑色圆点）。
    用于照片后的透视校正。
    """
    s = ""
    s += svg_rect(x, y, size, size, fill="#000000", stroke="#000000", stroke_w=0.0)
    inset = size * 0.20
    s += svg_rect(x + inset, y + inset, size - 2 * inset, size - 2 * inset,
                  fill="#FFFFFF", stroke="#FFFFFF", stroke_w=0.0)
    dot = size * 0.10
    s += svg_rect(x + size/2 - dot/2, y + size/2 - dot/2, dot, dot,
                  fill="#000000", stroke="#000000", stroke_w=0.0)
    return s


def layout_board(
        page_w: float,
        page_h: float,
        margin: float,
        cols: int,
        rows: int,
        swatch_w: float,
        swatch_h: float,
        gap_x: float,
        gap_y: float,
        recipes: List[Tuple[str, str, SwatchRecipe, str]],
) -> List[Swatch]:
    """
    将色块放置在网格中，从左到右，从上到下。
    """
    swatches: List[Swatch] = []
    max_slots = cols * rows
    if len(recipes) > max_slots:
        recipes = recipes[:max_slots]

    start_x = margin
    start_y = margin + 18.0  # 预留标题区域

    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(recipes):
                break
            kind, key, recipe, label = recipes[idx]
            x = start_x + c * (swatch_w + gap_x)
            y = start_y + r * (swatch_h + gap_y)

            sid = f"P{idx:03d}"
            rgb = mix_srgb(recipe.fractions)
            # 标签中包含简短配方摘要
            lab = f"{sid}  {label}"
            swatches.append(Swatch(
                swatch_id=sid,
                kind=kind,
                x_mm=x, y_mm=y, w_mm=swatch_w, h_mm=swatch_h,
                recipe=recipe,
                display_rgb=rgb,
                label=lab,
            ))
            idx += 1

    return swatches


def write_outputs(
        outdir: Path,
        page_w: float,
        page_h: float,
        layer_height_mm: float,
        swatches: List[Swatch],
        title: str,
        notes: List[str],
        svg_name: str = "calibration_board.svg",
        json_name: str = "calibration_board_recipes.json",
        csv_name: str = "calibration_board_recipes.csv",
):
    outdir.mkdir(parents=True, exist_ok=True)

    # ---- SVG
    svg = []
    svg.append(svg_header(page_w, page_h))

    # 标题
    svg.append(svg_text(12, 10, title, size=6.0, weight="bold"))
    svg.append(svg_text(12, 15, f"层高度: {layer_height_mm} mm   （打印设置必须固定！）",
                        size=3.4, fill="#222"))
    y0 = 19.0
    for i, line in enumerate(notes[:4]):
        svg.append(svg_text(12, y0 + i * 4.0, f"- {line}", size=3.2, fill="#333"))

    # 基准标记（角点）
    fid = 10.0
    svg.append(svg_fiducial(6, 6, fid))
    svg.append(svg_fiducial(page_w - 6 - fid, 6, fid))
    svg.append(svg_fiducial(6, page_h - 6 - fid, fid))
    svg.append(svg_fiducial(page_w - 6 - fid, page_h - 6 - fid, fid))

    # 色块
    for s in swatches:
        fill = rgb_hex(s.display_rgb)
        svg.append(svg_rect(s.x_mm, s.y_mm, s.w_mm, s.h_mm, fill=fill, stroke="#000", stroke_w=0.35, rx=1.2))

        # ID + 短标签
        # 将标签放在色块顶部边缘内部（小）
        svg.append(svg_text(s.x_mm + 1.8, s.y_mm + 4.2, s.label, size=2.8, fill="#111"))

        # 在底部绘制小"代码"行：通道 + 层数
        chs = "".join(s.recipe.channels)
        L = s.recipe.total_layers
        frac_txt = " ".join([f"{k}{int(round(v*100)):02d}" for k, v in sorted(s.recipe.fractions.items())])
        code = f"{chs} L{L} {frac_txt}"
        svg.append(svg_text(s.x_mm + 1.8, s.y_mm + s.h_mm - 1.6, code, size=2.5, fill="#111"))

    svg.append(svg_footer())
    (outdir / svg_name).write_text("".join(svg), encoding="utf-8")

    # ---- JSON元数据
    meta = {
        "title": title,
        "page_mm": {"w": page_w, "h": page_h},
        "layer_height_mm": layer_height_mm,
        "swatch_count": len(swatches),
        "swatches": [
            {
                "swatch_id": s.swatch_id,
                "kind": s.kind,
                "rect_mm": {"x": s.x_mm, "y": s.y_mm, "w": s.w_mm, "h": s.h_mm},
                "recipe": {
                    "channels": s.recipe.channels,
                    "fractions": s.recipe.fractions,
                    "total_layers": s.recipe.total_layers,
                    "layer_height_mm": s.recipe.layer_height_mm,
                    "layer_sequence": s.recipe.layer_sequence,
                },
            }
            for s in swatches
        ],
        "notes": notes,
    }
    (outdir / json_name).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- CSV（可选方便）
    with (outdir / csv_name).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["swatch_id", "kind", "x_mm", "y_mm", "w_mm", "h_mm",
                    "channels", "fractions_json", "total_layers", "layer_height_mm", "layer_sequence"])
        for s in swatches:
            w.writerow([
                s.swatch_id, s.kind, s.x_mm, s.y_mm, s.w_mm, s.h_mm,
                "".join(s.recipe.channels),
                json.dumps(s.recipe.fractions, ensure_ascii=False),
                s.recipe.total_layers,
                s.recipe.layer_height_mm,
                "".join(s.recipe.layer_sequence),
            ])


# -----------------------------
# 主程序
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="out_calibration_board")
    ap.add_argument("--page", choices=list(PAGE_SIZES_MM.keys()), default="A4")
    ap.add_argument("--margin", type=float, default=12.0)
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--rows", type=int, default=8)
    ap.add_argument("--swatch_w", type=float, default=28.0)
    ap.add_argument("--swatch_h", type=float, default=18.0)
    ap.add_argument("--gap_x", type=float, default=3.0)
    ap.add_argument("--gap_y", type=float, default=3.0)

    ap.add_argument("--layer_h", type=float, default=0.20, help="层高度（毫米）")
    ap.add_argument("--single_layers", default="1,2,3,4,5",
                    help="单色色块的层数列表，逗号分隔")
    ap.add_argument("--mix_layers", type=int, default=4,
                    help="双色混合色块的总层数")
    ap.add_argument("--mix_steps", default="0,0.25,0.5,0.75,1.0",
                    help="双色混合中A的分数列表，逗号分隔（B=1-A）")
    ap.add_argument("--no_white_mixes", action="store_true",
                    help="如果设置，只生成RG/RB/GB对（不含R/W等）")
    args = ap.parse_args()

    page_w, page_h = PAGE_SIZES_MM[args.page]
    outdir = Path(args.outdir)

    single_layers = [int(x.strip()) for x in args.single_layers.split(",") if x.strip()]
    mix_steps = [float(x.strip()) for x in args.mix_steps.split(",") if x.strip()]

    recipes = generate_swatch_recipes(
        layer_height_mm=args.layer_h,
        single_layers=single_layers,
        mix_layers=args.mix_layers,
        mix_steps=mix_steps,
        include_white_mixes=(not args.no_white_mixes),
    )

    # 布局
    swatches = layout_board(
        page_w=page_w,
        page_h=page_h,
        margin=args.margin,
        cols=args.cols,
        rows=args.rows,
        swatch_w=args.swatch_w,
        swatch_h=args.swatch_h,
        gap_x=args.gap_x,
        gap_y=args.gap_y,
        recipes=recipes,
    )

    title = "OpenColor多色校准板（打印与拍照）"
    notes = [
        "打印设置必须在各次拍摄间固定（相同喷嘴、温度、风扇、速度、层高度）。",
        "尽可能拍摄RAW；锁定曝光和白平衡；避免HDR/色调映射。",
        "使用生成的JSON作为模型拟合的'真实配方规范'（不用于查找）。",
        "用于反射校准时：如果可用使用偏振光；避免镜面热点。",
    ]

    write_outputs(
        outdir=outdir,
        page_w=page_w,
        page_h=page_h,
        layer_height_mm=args.layer_h,
        swatches=swatches,
        title=title,
        notes=notes,
    )

    logger.info("完成。")
    logger.info("已写入:", outdir / "calibration_board.svg")
    logger.info("已写入:", outdir / "calibration_board_recipes.json")
    logger.info("已写入:", outdir / "calibration_board_recipes.csv")
    logger.info("色块数:", len(swatches))


if __name__ == "__main__":
    main()
