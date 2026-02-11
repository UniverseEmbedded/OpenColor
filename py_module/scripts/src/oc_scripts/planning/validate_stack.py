#!/usr/bin/env python3
"""层堆叠验证工具 - 验证快速堆叠预测与物理前向模型的一致性

本脚本用于验证快速颜色预测模型与物理光线追踪模型之间的一致性，
通过对比两种模型的输出，评估快速模型的准确性。

使用示例:
    python validate_stack.py --mode rgbw --layers 5 --cases 16
    python validate_stack.py --seq "R-G-B-W" --heights "0.12,0.08,0.08,0.08"
"""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import sys

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(__file__))
import planner


RGBA = Tuple[int, int, int, int]


def _clamp_int(x: int, lo: int, hi: int) -> int:
    """将整数限制在指定范围内"""
    return lo if x < lo else hi if x > hi else x


def parse_rgba_list(s: str) -> RGBA:
    """解析RGBA列表字符串，格式为 r,g,b,a"""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) != 4:
        raise ValueError("--rgba must be r,g,b,a")
    vals = [int(p) for p in parts]
    return (
        _clamp_int(vals[0], 0, 255),
        _clamp_int(vals[1], 0, 255),
        _clamp_int(vals[2], 0, 255),
        _clamp_int(vals[3], 0, 255),
    )


def parse_hex_rgba(s: str) -> RGBA:
    """解析十六进制RGBA字符串，格式为 #RRGGBB 或 #RRGGBBAA"""
    h = s.strip()
    if h.startswith("#"):
        h = h[1:]
    if len(h) not in (6, 8):
        raise ValueError("--hex must be #RRGGBB or #RRGGBBAA")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (r, g, b, a)


def _iter_inputs(rgba_list: Sequence[str], hex_list: Sequence[str]) -> List[RGBA]:
    out: List[RGBA] = []
    for s in rgba_list:
        out.append(parse_rgba_list(s))
    for s in hex_list:
        out.append(parse_hex_rgba(s))
    return out


def _random_rgba(rng: random.Random, alpha: int) -> RGBA:
    return (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255), int(alpha))


def parse_seq(s: str) -> List[str]:
    s = s.strip()
    if "-" in s:
        return [x.strip().upper() for x in s.split("-") if x.strip()]
    return [c.upper() for c in s if not c.isspace()]


def parse_heights(s: str) -> List[float]:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return [float(p) for p in parts]


@dataclass(frozen=True)
class CaseResult:
    """测试结果数据类"""

    rgba: RGBA  # 输入RGBA颜色
    seq: List[str]  # 材料序列
    heights: List[float]  # 层高度列表
    fast_pred: Tuple[int, int, int]  # 快速模型预测颜色
    phys_pred: Tuple[int, int, int]  # 物理模型预测颜色
    loss_fast_to_target: float  # 快速模型到目标的损失
    loss_phys_to_target: float  # 物理模型到目标的损失
    loss_phys_to_fast: float  # 物理模型到快速模型的损失


def main(argv: Optional[Sequence[str]] = None) -> int:
    """主函数 - 运行层堆叠验证"""
    ap = argparse.ArgumentParser(description="验证快速堆叠预测与物理前向模型的一致性")
    ap.add_argument("--mode", default="rgbw")
    ap.add_argument("--layers", type=int, default=5, help="micro-layer count")
    ap.add_argument(
        "--first-layer-height",
        type=float,
        default=0.12,
        help="mm for first layer (risk: can hide thin details)",
    )
    ap.add_argument(
        "--layer-height", type=float, default=0.08, help="mm per layer (except first)"
    )
    ap.add_argument("--pattern", default="balanced", choices=["balanced", "grouped"])
    ap.add_argument("--alpha-background", default="white", choices=["white", "black"])
    ap.add_argument("--view", default="top", choices=["top", "bottom"])
    ap.add_argument("--backing", default="white", choices=["white", "black"])
    ap.add_argument("--materials-json", default=None)

    ap.add_argument("--seq", default=None)
    ap.add_argument("--heights", default=None)

    ap.add_argument("--rgba", action="append", default=[])
    ap.add_argument("--hex", action="append", default=[])
    ap.add_argument("--cases", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--random-alpha", type=int, default=255)

    ap.add_argument("--samples", type=int, default=60000)
    ap.add_argument("--samples-preview", type=int, default=None)
    args = ap.parse_args(argv)

    samples = (
        int(args.samples_preview)
        if args.samples_preview is not None
        else int(args.samples)
    )
    inputs = _iter_inputs(args.rgba, args.hex)

    lib = planner.load_materials(args.materials_json)
    mode_key = str(args.mode).strip().lower()
    if mode_key not in lib.modes:
        raise SystemExit(
            f"Unknown mode: {args.mode} (available: {sorted(lib.modes.keys())})"
        )

    if args.seq is not None or args.heights is not None:
        if args.seq is None or args.heights is None:
            raise SystemExit("--seq and --heights must be provided together")

        seq = parse_seq(str(args.seq))
        heights = parse_heights(str(args.heights))
        if len(seq) != len(heights):
            raise SystemExit("len(seq) must match len(heights)")

        fast_lin = planner.predict_rgb_fast_from_sequence(
            lib.fast, seq, heights, view=str(args.view), backing=str(args.backing)
        )
        fast_srgb = planner._rgb_lin_to_int_srgb(fast_lin)
        phys_lin, _res = planner.forward_rgb(
            seq=seq,
            heights_mm=heights,
            view=str(args.view),
            backing=str(args.backing),
            samples=samples,
            seed=int(args.seed),
            materials_json=args.materials_json,
        )
        phys_srgb = planner._rgb_lin_to_int_srgb(phys_lin)
        loss_phys_to_fast = planner.loss_rgb(phys_lin, fast_lin)

        logger.info(
            f"samples={samples} mode={mode_key} view={args.view} backing={args.backing}"
        )
        logger.info(f"seq={'-'.join(seq)}")
        logger.info(
            f"fast_pred={fast_srgb} phys_pred={phys_srgb} loss_phys_to_fast={loss_phys_to_fast:.6f}"
        )

        if inputs:
            if len(inputs) != 1:
                raise SystemExit(
                    "Provide exactly one --rgba/--hex when validating a fixed seq"
                )
            target = planner.rgba_to_linear_target(
                inputs[0], alpha_background=str(args.alpha_background)
            )
            logger.info(
                "loss_fast_to_target=%.6f loss_phys_to_target=%.6f"
                % (
                    planner.loss_rgb(fast_lin, target),
                    planner.loss_rgb(phys_lin, target),
                )
            )
        return 0

    if not inputs:
        rng = random.Random(int(args.seed))
        alpha = _clamp_int(int(args.random_alpha), 0, 255)
        for _ in range(max(1, int(args.cases))):
            inputs.append(_random_rgba(rng, alpha=alpha))

    results: List[CaseResult] = []
    for i, rgba in enumerate(inputs):
        p = planner.solve_layers_fast(
            rgba=rgba,
            mode=mode_key,
            layers=int(args.layers),
            first_layer_height=float(args.first_layer_height),
            layer_height=float(args.layer_height),
            pattern=str(args.pattern),
            alpha_background=str(args.alpha_background),
            view=str(args.view),
            backing=str(args.backing),
            materials_json=args.materials_json,
        )
        pred_lin_phys, _res = planner.forward_rgb(
            seq=p.sequence,
            heights_mm=p.heights_mm,
            view=str(args.view),
            backing=str(args.backing),
            samples=samples,
            seed=int(args.seed) + 10007 * i,
            materials_json=args.materials_json,
        )
        target = planner.rgba_to_linear_target(
            rgba, alpha_background=str(args.alpha_background)
        )
        loss_fast_to_target = planner.loss_rgb(p.pred_rgb_lin, target)
        loss_phys_to_target = planner.loss_rgb(pred_lin_phys, target)
        loss_phys_to_fast = planner.loss_rgb(pred_lin_phys, p.pred_rgb_lin)
        results.append(
            CaseResult(
                rgba=rgba,
                seq=list(p.sequence),
                heights=list(p.heights_mm),
                fast_pred=tuple(map(int, p.pred_rgb_srgb)),
                phys_pred=planner._rgb_lin_to_int_srgb(pred_lin_phys),
                loss_fast_to_target=float(loss_fast_to_target),
                loss_phys_to_target=float(loss_phys_to_target),
                loss_phys_to_fast=float(loss_phys_to_fast),
            )
        )

    results.sort(key=lambda r: r.loss_phys_to_fast, reverse=True)
    worst = results[0]
    avg_df = sum(r.loss_phys_to_fast for r in results) / max(1, len(results))
    avg_dt = sum(r.loss_phys_to_target for r in results) / max(1, len(results))

    logger.info(
        f"cases={len(results)} samples={samples} mode={mode_key} view={args.view} backing={args.backing}"
    )
    logger.info(
        f"avg_loss_phys_to_fast={avg_df:.6f} avg_loss_phys_to_target={avg_dt:.6f}"
    )
    logger.info(
        "worst: rgba=%s seq=%s fast=%s phys=%s loss_phys_to_fast=%.6f loss_phys_to_target=%.6f"
        % (
            worst.rgba,
            "-".join(worst.seq),
            worst.fast_pred,
            worst.phys_pred,
            worst.loss_phys_to_fast,
            worst.loss_phys_to_target,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
