"""
可视化辅助模块
提供色盘、掩码、热力图等可视化渲染功能
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import cv2
import numpy as np


def _grid_shape(cells) -> Tuple[int, int]:
    """计算网格的行列数

    根据单元格列表计算网格的形状（行数、列数）

    Args:
        cells: 单元格对象列表，每个对象需要有row和col属性

    Returns:
        (行数, 列数) 元组
    """
    rows = [c.row for c in cells]
    cols = [c.col for c in cells]
    return (max(rows) + 1 if rows else 0, max(cols) + 1 if cols else 0)


def render_board_rgb(
    cells,
    rgb_by_rc: Dict[Tuple[int, int], Optional[Tuple[int, int, int]]],
    default=(0, 0, 0),
    cell_px: int = 64,
    border_px: int = 2,
):
    """渲染RGB色盘图像

    将单元格的RGB颜色渲染为可视化图像，每个单元格显示其对应的颜色

    Args:
        cells: 单元格对象列表
        rgb_by_rc: 字典，键为(行,列)元组，值为RGB元组或None
        default: 默认颜色，当rgb_by_rc中没有对应值时使用
        cell_px: 每个单元格的像素大小
        border_px: 边框像素大小

    Returns:
        渲染好的RGB图像数组
    """
    h, w = _grid_shape(cells)
    H = h * cell_px + (h + 1) * border_px
    W = w * cell_px + (w + 1) * border_px
    img = np.full((H, W, 3), 40, dtype=np.uint8)  # 深色背景
    for r in range(h):
        for c in range(w):
            y0 = border_px + r * (cell_px + border_px)
            x0 = border_px + c * (cell_px + border_px)
            y1 = y0 + cell_px
            x1 = x0 + cell_px
            rgb = rgb_by_rc.get((r, c), None)
            if rgb is None:
                rgb = default
            img[y0:y1, x0:x1, :] = np.array(rgb, dtype=np.uint8)
    return img


def render_mask(
    cells,
    mask_by_rc: Dict[Tuple[int, int], bool],
    cell_px: int = 64,
    border_px: int = 2,
):
    """渲染掩码图像

    将单元格的布尔掩码渲染为可视化图像，True显示为白色，False显示为灰色

    Args:
        cells: 单元格对象列表
        mask_by_rc: 字典，键为(行,列)元组，值为布尔值
        cell_px: 每个单元格的像素大小
        border_px: 边框像素大小

    Returns:
        渲染好的灰度图像数组
    """
    h, w = _grid_shape(cells)
    H = h * cell_px + (h + 1) * border_px
    W = w * cell_px + (w + 1) * border_px
    img = np.full((H, W), 30, dtype=np.uint8)
    for r in range(h):
        for c in range(w):
            y0 = border_px + r * (cell_px + border_px)
            x0 = border_px + c * (cell_px + border_px)
            y1 = y0 + cell_px
            x1 = x0 + cell_px
            v = 255 if mask_by_rc.get((r, c), False) else 50
            img[y0:y1, x0:x1] = v
    return img


def render_error_heatmap(
    cells,
    err_by_rc: Dict[Tuple[int, int], float],
    vmax: float,
    cell_px: int = 64,
    border_px: int = 2,
):
    """渲染误差热力图

    将单元格的误差值渲染为热力图，使用JET色彩映射（蓝色表示低值，红色表示高值）

    Args:
        cells: 单元格对象列表
        err_by_rc: 字典，键为(行,列)元组，值为误差值
        vmax: 误差值的最大值，用于归一化
        cell_px: 每个单元格的像素大小
        border_px: 边框像素大小

    Returns:
        渲染好的BGR图像数组（带颜色条图例）
    """
    h, w = _grid_shape(cells)
    H = h * cell_px + (h + 1) * border_px
    W = w * cell_px + (w + 1) * border_px
    img = np.full((H, W), 40, dtype=np.uint8)
    for r in range(h):
        for c in range(w):
            y0 = border_px + r * (cell_px + border_px)
            x0 = border_px + c * (cell_px + border_px)
            y1 = y0 + cell_px
            x1 = x0 + cell_px
            e = float(err_by_rc.get((r, c), 0.0))
            v = 0.0 if vmax <= 0 else min(1.0, e / vmax)
            img[y0:y1, x0:x1] = int(round(v * 255))
    # 应用色彩映射（蓝色低值 -> 红色高值）
    heat = cv2.applyColorMap(img, cv2.COLORMAP_JET)
    # 在右侧添加颜色条图例
    bar_w = 48
    bar = np.linspace(255, 0, H, dtype=np.uint8).reshape(H, 1)
    bar = np.repeat(bar, bar_w, axis=1)
    bar_c = cv2.applyColorMap(bar, cv2.COLORMAP_JET)
    canvas = np.concatenate([heat, bar_c], axis=1)
    # 添加标注
    cv2.putText(
        canvas,
        f"{vmax:.1f}",
        (W + 4, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "0.0",
        (W + 4, H - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "err",
        (W + 8, H // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return canvas
