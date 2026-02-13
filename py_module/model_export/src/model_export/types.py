from __future__ import annotations

"""
类型定义和共享工具。
包含用于模型导出的数据类（如 MeshData, SlotColor）和辅助函数。
"""

# 导入数据类装饰器
from dataclasses import dataclass

# 导入类型提示模块
from typing import Dict, Tuple

# 导入数值计算模块
import numpy as np


@dataclass(frozen=True)
class MeshData:
    """
    简单的三角形网格数据类。

    属性:
        vertices: 顶点坐标数组，形状为 (N, 3)，float 类型
        faces: 三角面索引数组，形状为 (M, 3)，int 类型
    """

    vertices: np.ndarray
    faces: np.ndarray


@dataclass(frozen=True)
class SlotColor:
    """
    槽位颜色数据类。

    属性:
        name: 槽位名称（例如 "Red", "Slot 1"）
        rgba255: RGBA 颜色值，每个分量范围 0-255
    """

    name: str
    rgba255: Tuple[int, int, int, int]


# 默认槽位颜色字典
DEFAULT_SLOT_COLORS: Dict[str, Tuple[int, int, int, int]] = {
    # 简短的 RGBWY 风格键（遗留脚本 / SVG 工作流）
    "R": (255, 0, 0, 255),  # 红色
    "G": (0, 255, 0, 255),  # 绿色
    "Y": (255, 255, 0, 255),  # 黄色
    "B": (0, 0, 255, 255),  # 蓝色
    "W": (255, 255, 255, 255),  # 白色
    # `oc_core.core.color_systems` 使用的语义名称
    "Red": (255, 0, 0, 255),  # 红色
    "Green": (0, 255, 0, 255),  # 绿色
    "Blue": (0, 0, 255, 255),  # 蓝色
    "Yellow": (255, 255, 0, 255),  # 黄色
    "Cyan": (0, 190, 200, 255),  # 青色
    "Magenta": (200, 0, 170, 255),  # 洋红色
    "White": (255, 255, 255, 255),  # 白色
}


def apply_alpha_to_brightness(rgba: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    """
    将 Alpha 通道编码到 RGB 亮度中，返回新的 RGBA 元组。
    半透明颜色会显得更暗，但不改变 Alpha 值本身。

    用途：解决3MF文件中半透明颜色与纯色在视觉上重复的问题。
    例如：White(255,255,255,255) 和 Transparent(255,255,255,128)
    在3MF中如果只显示RGB部分会看起来完全一样，通过降低亮度可以区分。

    重要：此函数需要在所有导出路径中使用，包括：
    - XML导出路径（通过 rgba_to_hex）
    - lib3mf导出路径（standard_3mf.py 中直接调用）

    参数:
        rgba: RGBA 颜色元组，每个分量范围 0-255

    返回:
        调整后的 RGBA 元组，RGB 已根据 Alpha 值调整亮度
    """
    r, g, b, a = rgba
    # 将 Alpha 编码到亮度：Alpha 越低，颜色越暗
    # 使用 Alpha/255 作为亮度系数，但保持最小亮度避免完全变黑
    alpha_factor = max(0.3, a / 255.0)
    r_adj = int(r * alpha_factor)
    g_adj = int(g * alpha_factor)
    b_adj = int(b * alpha_factor)
    return (r_adj, g_adj, b_adj, a)


def rgba_to_hex(rgba: Tuple[int, int, int, int]) -> str:
    """
    将 RGBA 元组（0-255）转换为十六进制字符串，如 #RRGGBB。
    Alpha 通道会编码到 RGB 亮度中：半透明颜色会显得更暗。

    参数:
        rgba: RGBA 颜色元组，每个分量范围 0-255

    返回:
        十六进制颜色字符串，格式为 #RRGGBB
    """
    r_adj, g_adj, b_adj, _a = apply_alpha_to_brightness(rgba)
    return f"#{int(r_adj):02X}{int(g_adj):02X}{int(b_adj):02X}"


def _fmt(x: float) -> str:
    """
    通过四舍五入小数并去除尾随零来保持 XML 紧凑和稳定。
    用于减少 3MF 文件的大小并提高可读性。

    参数:
        x: 要格式化的浮点数

    返回:
        格式化后的字符串。如果是整数，则不带小数点；
        如果是小数，最多保留6位，并去除末尾的0。
    """
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.6f}".rstrip("0").rstrip(".")
