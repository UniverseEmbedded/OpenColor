#!/usr/bin/env python3

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# color_square_stack.py
# 将单个 RGBA 颜色转换为堆叠方块，导出为按材料分模式的 STL（如 R、G、B、W）
#
# 注意
# ----
# 旧版 OpenColor 在此脚本中包含一个"传统"的顺序无关前向模型。
# 在 v3 中，该代码已被移除以防止意外误用。所有规划都通过 planner.py 进行。
#
# 示例：
#   python color_square_stack.py --hex "#DDF4C4" --size-mm 30 --layers 5 --layer-height 0.08 --first-layer-height 0.12

import argparse
import os
from typing import Dict, List, Tuple

import trimesh
from shapely.geometry import Polygon

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "planning"))
import planner

RGBA = Tuple[int, int, int, int]


def parse_hex_rgba(s: str) -> RGBA:
    """解析十六进制颜色字符串为 RGBA 元组"""
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) not in (6, 8):
        raise ValueError("hex 必须是 #RRGGBB 或 #RRGGBBAA 格式")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    a = int(s[6:8], 16) if len(s) == 8 else 255
    return (r, g, b, a)


def extrude_poly_at_z(poly: Polygon, height: float, z0: float) -> trimesh.Trimesh:
    """在指定 Z 高度拉伸多边形"""
    mesh = trimesh.creation.extrude_polygon(poly, height)
    mesh.apply_translation((0.0, 0.0, z0))
    return mesh


def main() -> None:
    """主函数：生成彩色方块堆叠的 STL 文件"""
    lib = planner.load_materials(None)

    ap = argparse.ArgumentParser(description="单个 RGBA -> 堆叠方块，按材料导出 STL")
    ap.add_argument(
        "--hex", default="#DDF4C4", help="颜色十六进制 #RRGGBB 或 #RRGGBBAA"
    )
    ap.add_argument("--mode", default="rgbw", choices=sorted(lib.modes.keys()))
    ap.add_argument("--size-mm", type=float, default=30.0, help="方块边长（毫米）")
    ap.add_argument("--layers", type=int, default=5, help="层数")
    ap.add_argument(
        "--layer-height", type=float, default=0.08, help="每层高度（毫米，首层除外）"
    )
    ap.add_argument(
        "--first-layer-height", type=float, default=0.12, help="首层高度（毫米）"
    )
    ap.add_argument(
        "--view",
        default="bottom",
        choices=["top", "bottom"],
        help="观察面（顶面或底面）",
    )
    ap.add_argument(
        "--backing",
        default="white",
        choices=["white", "black"],
        help="前向模型使用的背板颜色",
    )
    ap.add_argument(
        "--phys", action="store_true", help="使用蒙特卡洛物理前向模型进行选择"
    )
    ap.add_argument("--samples", type=int, default=80000)
    ap.add_argument("--candidates", type=int, default=64)
    ap.add_argument(
        "--brute-force-threshold",
        type=int,
        default=60000,
        help="当 K^L <= 阈值时枚举所有序列",
    )
    ap.add_argument(
        "--opacity-weight", type=float, default=-1.0, help="不透明度项权重；<0 表示自动"
    )
    ap.add_argument(
        "--alpha-background",
        default="white",
        choices=["white", "black"],
        help="解释 RGBA 时使用的背景",
    )
    ap.add_argument(
        "--pattern",
        default="balanced",
        choices=["balanced", "grouped"],
        help="非暴力搜索时使用的模式",
    )
    ap.add_argument("--outdir", default="out_color_square", help="输出文件夹")
    ap.add_argument("--name", default="color_square", help="输出文件基本名称")
    ap.add_argument("--materials-json", default=None, help="materials.json 路径")
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
    logger.info(f"in={rgba}  seq={logic}")
    logger.info(
        f"pred={p.pred_rgb_srgb}  loss={p.loss:.6f}  total_thickness_mm={total_h:.3f}  view={p.view} backing={p.backing}"
    )

    s = float(args.size_mm)
    square = Polygon([(0, 0), (s, 0), (s, s), (0, s)])

    meshes: Dict[str, List[trimesh.Trimesh]] = {
        t: [] for t in planner.mode_tokens(lib, args.mode)
    }
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
        logger.info(f"wrote {out}")


if __name__ == "__main__":
    main()
