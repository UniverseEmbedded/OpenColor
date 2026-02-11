"""规划器模块 - 提供层序列求解功能

包含快速求解和物理模型求解两种方法，用于找到最优的打印层序列。
"""

from __future__ import annotations

from typing import Optional, Sequence

from .planner_models import (
    RGBA,
    Vec3,
    _clamp,
    _rgb_lin_to_int_srgb,
    loss_rgba_like,
    rgba_targets,
    PlanResult,
)
from .planner_io import forward_rgb
from .planner_search import _fast_candidates


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
    """使用快速前向模型搜索最优层序列

    基于简化的光学模型快速评估候选序列，返回最优结果。
    适合需要快速响应的场景。

    参数:
        rgba: 目标RGBA颜色
        mode: 颜色模式，如"rgbw"、"cmyk"等
        layers: 层数
        first_layer_height: 第一层高度（毫米）
        layer_height: 层高度（毫米）
        pattern: 层厚模式，如"balanced"、"thick_first"等
        alpha_background: Alpha通道背景处理方式
        forbid: 禁止使用的材料列表
        view: 观察方向，"bottom"或"top"
        backing: 背板颜色
        candidates: 候选序列数量
        brute_force_threshold: 暴力搜索阈值
        opacity_weight: 不透明度权重
        materials_json: 材料定义JSON文件路径

    返回:
        规划结果对象
    """
    # 获取候选序列
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
    # 返回最佳候选
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
    """使用蒙特卡洛物理前向模型优化层序列

    首先使用快速模型筛选候选序列，然后使用物理精确模型进行精细评估，
    返回最优结果。适合需要高精度预测的场景。

    参数:
        rgba: 目标RGBA颜色
        mode: 颜色模式
        layers: 层数
        first_layer_height: 第一层高度（毫米）
        layer_height: 层高度（毫米）
        pattern: 层厚模式
        alpha_background: Alpha通道背景处理方式
        forbid: 禁止使用的材料列表
        view: 观察方向
        backing: 背板颜色
        samples: 蒙特卡洛采样数
        seed: 随机种子
        candidates: 快速模型候选数
        brute_force_threshold: 暴力搜索阈值
        opacity_weight: 不透明度权重
        materials_json: 材料定义JSON文件路径

    返回:
        规划结果对象
    """
    # 计算目标RGB和不透明度
    rgb_target, opacity_target = rgba_targets(rgba, alpha_background=alpha_background)
    # 自动设置不透明度权重
    if opacity_weight is None:
        opacity_weight = 0.20 if opacity_target < 0.999 else 0.0

    # 使用快速模型获取候选序列
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

    # 使用物理模型评估每个候选
    best: Optional[PlanResult] = None
    for seq, heights, _pred_fast, _L_fast in cands:
        # 物理前向计算
        pred_lin, res = forward_rgb(
            seq=seq,
            heights_mm=heights,
            view=view,
            backing=backing,
            samples=samples,
            seed=seed,
            materials_json=materials_json,
        )

        # 计算透射率和不透明度
        T = res.T
        t_luma = _clamp(0.2126 * T[0] + 0.7152 * T[1] + 0.0722 * T[2])
        opacity_pred = _clamp(1.0 - t_luma)

        # 计算损失
        Lp = loss_rgba_like(
            pred_lin, rgb_target, opacity_pred, opacity_target, float(opacity_weight)
        )

        # 构建结果对象
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
        # 保留最优结果
        if best is None or pr.loss < best.loss:
            best = pr

    assert best is not None
    return best
