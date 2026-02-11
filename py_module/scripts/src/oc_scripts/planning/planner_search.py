"""打印配方搜索模块 - 使用快速前向模型搜索最优层叠序列

本模块提供基于快速前向模型的打印配方搜索算法，支持穷举搜索和
启发式搜索，用于找到最接近目标颜色的材料层叠序列。
"""

from __future__ import annotations

import itertools
import random
from typing import Iterable, List, Optional, Sequence, Tuple

from .planner_models import (
    RGBA,
    Vec3,
    loss_rgba_like,
    rgba_targets,
    FastMaterial,
    MaterialLibrary,
)
from .planner_io import load_materials, predict_fast_rgb_and_opacity


def mode_tokens(
    lib: MaterialLibrary, mode: str, forbid: Sequence[str] = ()
) -> List[str]:
    """获取指定模式下的可用材料标记列表

    Args:
        lib: 材料库对象
        mode: 模式名称（如 "rgbw"）
        forbid: 禁用的材料标记列表

    Returns:
        可用的材料标记列表

    Raises:
        ValueError: 当模式未知或禁用后无可用材料时抛出
    """
    mode_key = mode.strip().lower()
    if mode_key not in lib.modes:
        raise ValueError(f"Unknown mode: {mode}. Supported: {sorted(lib.modes.keys())}")
    bad = {str(x).upper() for x in forbid}
    toks = [t for t in lib.modes[mode_key] if t not in bad]
    if not toks:
        raise ValueError("No materials left after forbid")
    return toks


def _compositions(total: int, parts: int) -> Iterable[List[int]]:
    """生成整数划分组合

    将 total 划分为 parts 个非负整数的所有组合，用于确定每种材料的使用次数

    Args:
        total: 总和
        parts: 部分数

    Yields:
        每种材料的数量列表
    """
    for cuts in itertools.combinations(range(total + parts - 1), parts - 1):
        prev = -1
        comp: List[int] = []
        for c in cuts:
            comp.append(c - prev - 1)
            prev = c
        comp.append((total + parts - 1) - prev - 1)
        yield comp


def _sequence_from_counts(
    tokens: List[str], counts: List[int], pattern: str
) -> List[str]:
    """根据材料数量和模式生成序列

    Args:
        tokens: 材料标记列表
        counts: 每种材料的数量列表
        pattern: 排列模式（"grouped" 或其他）

    Returns:
        材料序列列表
    """
    if pattern == "grouped":
        # 分组模式：相同材料连续排列，按数量降序
        seq: List[str] = []
        for t, n in sorted(zip(tokens, counts), key=lambda x: (-x[1], x[0])):
            seq.extend([t] * n)
        return seq

    # 平衡模式：尽量交替排列不同材料
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


def _build_heights(
    layers: int, first_layer_height: float, layer_height: float
) -> List[float]:
    """构建层高度列表

    Args:
        layers: 层数
        first_layer_height: 首层高度（mm）
        layer_height: 后续层高度（mm）

    Returns:
        每层的厚度列表

    Raises:
        ValueError: 当参数无效时抛出
    """
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
    """使用快速前向模型生成候选序列

    根据搜索空间大小选择穷举搜索或启发式搜索策略，
    返回按损失排序的候选序列列表

    Args:
        rgba: 目标 RGBA 颜色
        mode: 材料模式
        layers: 层数
        first_layer_height: 首层高度
        layer_height: 层高度
        pattern: 排列模式
        alpha_background: 透明背景处理方式
        forbid: 禁用的材料列表
        view: 观察方向（"top" 或 "bottom"）
        backing: 背衬材料
        max_candidates: 返回的最大候选数
        brute_force_threshold: 穷举搜索阈值
        opacity_weight: 透明度损失权重
        materials_json: 材料定义 JSON 路径

    Returns:
        候选序列列表，每个元素为 (序列, 高度列表, 预测 RGB, 损失值)
    """
    lib = load_materials(materials_json)
    tokens = mode_tokens(lib, mode, forbid=forbid)
    mats_fast = lib.fast

    heights = _build_heights(
        layers, first_layer_height=first_layer_height, layer_height=layer_height
    )

    rgb_target, opacity_target = rgba_targets(rgba, alpha_background=alpha_background)
    if opacity_weight is None:
        opacity_weight = 0.20 if opacity_target < 0.999 else 0.0

    toks_sorted = sorted(tokens)
    space = len(toks_sorted) ** layers

    # 小搜索空间：穷举搜索
    if space <= int(brute_force_threshold):
        scored: List[Tuple[float, List[str], Vec3]] = []
        for seq0 in itertools.product(toks_sorted, repeat=layers):
            s0 = list(seq0)
            rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(
                mats_fast, s0, heights, view=view, backing=backing
            )
            L = loss_rgba_like(
                rgb_pred,
                rgb_target,
                opacity_pred,
                opacity_target,
                float(opacity_weight),
            )
            scored.append((L, s0, rgb_pred))
        scored.sort(key=lambda x: x[0])
        out: List[Tuple[List[str], List[float], Vec3, float]] = []
        for L, s0, rgb_pred in scored[: max(1, int(max_candidates))]:
            out.append((s0, heights, rgb_pred, L))
        return out

    # 检查层高度是否均匀
    uniform = all(abs(h - heights[0]) <= 1e-12 for h in heights)
    if not uniform:
        # 非均匀高度且搜索空间较大：限制搜索空间后穷举
        if space > 200000:
            raise ValueError(f"Search space too large for non-uniform heights: {space}")
        scored: List[Tuple[float, List[str], Vec3]] = []
        for seq0 in itertools.product(toks_sorted, repeat=layers):
            s0 = list(seq0)
            rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(
                mats_fast, s0, heights, view=view, backing=backing
            )
            L = loss_rgba_like(
                rgb_pred,
                rgb_target,
                opacity_pred,
                opacity_target,
                float(opacity_weight),
            )
            scored.append((L, s0, rgb_pred))
        scored.sort(key=lambda x: x[0])
        out: List[Tuple[List[str], List[float], Vec3, float]] = []
        for L, s0, rgb_pred in scored[: max(1, int(max_candidates))]:
            out.append((s0, heights, rgb_pred, L))
        return out

    # 大搜索空间：启发式搜索
    # 第一步：评估不同材料数量组合
    comps: List[Tuple[float, List[int]]] = []
    for comp in _compositions(layers, len(toks_sorted)):
        seq0 = _sequence_from_counts(toks_sorted, comp, pattern=pattern)
        rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(
            mats_fast, seq0, heights, view=view, backing=backing
        )
        L = loss_rgba_like(
            rgb_pred, rgb_target, opacity_pred, opacity_target, float(opacity_weight)
        )
        comps.append((L, comp))
    comps.sort(key=lambda x: x[0])

    # 第二步：基于最佳组合进行随机扰动搜索
    rng = random.Random(0)
    seen: set[Tuple[str, ...]] = set()
    scored2: List[Tuple[float, List[str], Vec3]] = []

    def _try_add(s0: List[str]) -> None:
        """尝试添加候选序列到结果集"""
        key = tuple(s0)
        if key in seen:
            return
        seen.add(key)
        rgb_pred, opacity_pred = predict_fast_rgb_and_opacity(
            mats_fast, s0, heights, view=view, backing=backing
        )
        L = loss_rgba_like(
            rgb_pred, rgb_target, opacity_pred, opacity_target, float(opacity_weight)
        )
        scored2.append((L, s0, rgb_pred))

    # 基于最佳组合生成变体
    seed_comps = max(1, min(len(comps), max(12, int(max_candidates))))
    rand_per_comp = max(3, int(max_candidates) // seed_comps)

    for _Lcomp, counts in comps[:seed_comps]:
        expanded: List[str] = []
        for t, n in zip(toks_sorted, counts):
            expanded.extend([t] * int(n))

        # 添加基础序列及其变体
        base_seq = _sequence_from_counts(toks_sorted, counts, pattern=pattern)
        _try_add(list(base_seq))
        _try_add(list(reversed(base_seq)))
        _try_add(_sequence_from_counts(toks_sorted, counts, pattern="grouped"))

        # 随机打乱生成更多变体
        for _ in range(rand_per_comp * 8):
            s1 = list(expanded)
            rng.shuffle(s1)
            _try_add(s1)
            if len(seen) >= int(max_candidates) * 20:
                break
        if len(seen) >= int(max_candidates) * 20:
            break

    # 添加完全随机序列
    for _ in range(int(max_candidates) * 6):
        s2 = [rng.choice(toks_sorted) for _ in range(layers)]
        _try_add(s2)
        if len(seen) >= int(max_candidates) * 24:
            break

    # 排序并返回最佳候选
    scored2.sort(key=lambda x: x[0])
    out: List[Tuple[List[str], List[float], Vec3, float]] = []
    for L, s0, rgb_pred in scored2[: max(1, int(max_candidates))]:
        out.append((s0, heights, rgb_pred, L))
    return out
