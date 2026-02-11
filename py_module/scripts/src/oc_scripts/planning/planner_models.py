"""规划器模型定义模块 - 定义颜色规划和材料模型相关的数据类

本模块提供规划器使用的数据模型，包括：
- 颜色空间转换函数
- 损失函数计算
- 快速材料和材料库定义
- 规划结果数据类
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

RGBA = Tuple[int, int, int, int]
Vec3 = Tuple[float, float, float]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """将值限制在指定范围内"""
    return lo if x < lo else hi if x > hi else x


def srgb_to_linear01(c: float) -> float:
    """sRGB转线性RGB"""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear01_to_srgb(c: float) -> float:
    """线性RGB转sRGB"""
    c = _clamp(c)
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1 / 2.4)) - 0.055


def rgba_to_linear_rgba(rgba: RGBA) -> Tuple[float, float, float, float]:
    """RGBA转线性RGBA"""
    r, g, b, a = rgba
    rf = srgb_to_linear01(_clamp(r / 255.0))
    gf = srgb_to_linear01(_clamp(g / 255.0))
    bf = srgb_to_linear01(_clamp(b / 255.0))
    af = _clamp(a / 255.0)
    return rf, gf, bf, af


def rgba_to_linear_target(rgba: RGBA, alpha_background: str = "white") -> Vec3:
    """RGBA转线性目标RGB（考虑背景）"""
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
    """返回 (rgb_target_lin, opacity_target)。"""
    r_lin, g_lin, b_lin, a_lin = rgba_to_linear_rgba(rgba)
    bg = (0.0, 0.0, 0.0) if alpha_background == "black" else (1.0, 1.0, 1.0)
    rgb = (
        r_lin * a_lin + bg[0] * (1.0 - a_lin),
        g_lin * a_lin + bg[1] * (1.0 - a_lin),
        b_lin * a_lin + bg[2] * (1.0 - a_lin),
    )
    return rgb, float(a_lin)


def loss_rgb(rgb_pred: Vec3, rgb_target: Vec3, w_luma: float = 0.35) -> float:
    dr = rgb_pred[0] - rgb_target[0]
    dg = rgb_pred[1] - rgb_target[1]
    db = rgb_pred[2] - rgb_target[2]
    dl = 0.2126 * dr + 0.7152 * dg + 0.0722 * db
    return (dr * dr + dg * dg + db * db) + w_luma * (dl * dl)


def loss_rgba_like(
    rgb_pred: Vec3,
    rgb_target: Vec3,
    opacity_pred: float,
    opacity_target: float,
    opacity_weight: float,
    w_luma: float = 0.35,
) -> float:
    """颜色 + （可选）不透明度的组合损失"""
    L = loss_rgb(rgb_pred, rgb_target, w_luma=w_luma)
    if opacity_weight > 0.0:
        do = float(opacity_pred) - float(opacity_target)
        L += float(opacity_weight) * (do * do)
    return float(L)


def _rgb_lin_to_int_srgb(rgb_lin: Vec3) -> Tuple[int, int, int]:
    r = int(round(_clamp(linear01_to_srgb(rgb_lin[0])) * 255))
    g = int(round(_clamp(linear01_to_srgb(rgb_lin[1])) * 255))
    b = int(round(_clamp(linear01_to_srgb(rgb_lin[2])) * 255))
    return (r, g, b)


def opacity_from_transmittance(T: Vec3) -> float:
    """Approximate opacity from spectral transmittance."""
    t = _clamp(0.2126 * T[0] + 0.7152 * T[1] + 0.0722 * T[2])
    return float(_clamp(1.0 - t))


@dataclass(frozen=True)
class FastMaterial:
    """快速材料模型

    用于快速颜色预测的简化材料模型

    Attributes:
        token: 材料标识符
        color_lin: 线性RGB颜色值
        strength: 材料强度系数
    """

    token: str
    color_lin: Vec3
    strength: float

    def weight(self, layer_height_mm: float) -> float:
        """根据层高度计算权重

        Args:
            layer_height_mm: 层高度（毫米）

        Returns:
            计算得到的权重值
        """
        return 1.0 - math.exp(-self.strength * max(layer_height_mm, 0.0))


@dataclass(frozen=True)
class MaterialLibrary:
    """材料库

    存储所有可用材料的数据库

    Attributes:
        modes: 模式到材料列表的映射
        fast: 快速材料模型字典
        phys: 物理材料模型字典
        names: 材料名称映射
    """

    modes: Dict[str, List[str]]
    fast: Dict[str, FastMaterial]
    phys: Dict[str, object]  # 避免循环引用，使用 object
    names: Dict[str, str]


@dataclass(frozen=True)
class PlanResult:
    """规划结果数据类

    存储颜色规划算法的输出结果

    Attributes:
        method: 使用的规划方法
        rgba: 目标RGBA颜色
        mode: 颜色模式
        sequence: 材料序列
        heights_mm: 层高度列表（毫米）
        view: 观察方向（top/bottom）
        backing: 背衬类型（white/black）
        pred_rgb_srgb: 预测的sRGB颜色值
        pred_rgb_lin: 预测的线性RGB值
        loss: 损失值
        phys_R: 物理反射率（可选）
        phys_T: 物理透射率（可选）
        samples: 采样数（可选）
        seed: 随机种子（可选）
    """

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
