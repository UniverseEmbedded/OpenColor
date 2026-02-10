"""可视化模块 - 提供图层轮廓、调色板等可视化功能"""

from typing import Tuple, List, Dict

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _save_layer_total_contour_viz(
    image_key: str,
    layer_idx: int,
    layer_mask_u8: np.ndarray,
    output_path: str,
    *,
    contour_color: Tuple[int, int, int] = (255, 0, 0),
    thickness: int = 2,
) -> None:
    """
    保存图层总轮廓可视化
    """
    # 创建白色背景
    h, w = layer_mask_u8.shape
    viz = np.ones((h, w, 3), dtype=np.uint8) * 255

    # 找到轮廓
    contours, _ = cv2.findContours(layer_mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 绘制轮廓
    cv2.drawContours(viz, contours, -1, contour_color, thickness)

    # 保存
    Image.fromarray(viz).save(output_path)


def _save_layer_solved_palette_viz(
    image_key: str,
    layer_idx: int,
    solved_palette: List[Tuple[int, int, int]],
    layer_mask_u8: np.ndarray,
    output_path: str,
    *,
    swatch_size: int = 50,
    swatches_per_row: int = 8,
) -> None:
    """
    保存图层求解后的调色板可视化
    """
    n_colors = len(solved_palette)
    if n_colors == 0:
        return

    # 计算画布大小
    rows = (n_colors + swatches_per_row - 1) // swatches_per_row
    canvas_w = swatches_per_row * swatch_size + (swatches_per_row + 1) * 10
    canvas_h = rows * swatch_size + (rows + 1) * 10 + 40  # 额外空间给标题

    # 创建画布
    canvas = Image.new("RGB", (canvas_w, canvas_h), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)

    # 绘制标题
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()

    title = f"图层 {layer_idx} 求解调色板 ({n_colors} 色)"
    draw.text((10, 10), title, fill=(0, 0, 0), font=font)

    # 绘制色块
    for i, rgb in enumerate(solved_palette):
        row = i // swatches_per_row
        col = i % swatches_per_row

        x = 10 + col * (swatch_size + 10)
        y = 40 + row * (swatch_size + 10)

        # 绘制色块
        draw.rectangle([x, y, x + swatch_size, y + swatch_size], fill=rgb, outline=(0, 0, 0), width=1)

        # 绘制颜色值
        color_text = f"{rgb[0]},{rgb[1]},{rgb[2]}"
        draw.text((x, y + swatch_size + 2), color_text, fill=(0, 0, 0), font=font)

    canvas.save(output_path)


def _analyze_solved_palette_vs_solver_input(
    image_key: str,
    layer_idx: int,
    input_palette: List[Tuple[int, int, int]],
    solved_palette: List[Tuple[int, int, int]],
    output_path: str,
) -> Dict:
    """
    分析求解后的调色板与输入的差异
    """
    from scipy.spatial.distance import cdist

    # 转换为numpy数组
    input_arr = np.array(input_palette, dtype=np.float32)
    solved_arr = np.array(solved_palette, dtype=np.float32)

    # 计算距离矩阵
    dist_matrix = cdist(input_arr, solved_arr, metric="euclidean")

    # 找到每个输入颜色最近的求解颜色
    closest_indices = np.argmin(dist_matrix, axis=1)
    min_distances = np.min(dist_matrix, axis=1)

    # 统计信息
    stats = {
        "n_input_colors": len(input_palette),
        "n_solved_colors": len(solved_palette),
        "mean_distance": float(np.mean(min_distances)),
        "max_distance": float(np.max(min_distances)),
        "min_distance": float(np.min(min_distances)),
        "mappings": [],
    }

    for i, (input_rgb, closest_idx, dist) in enumerate(zip(input_palette, closest_indices, min_distances)):
        solved_rgb = solved_palette[closest_idx]
        stats["mappings"].append({
            "input": input_rgb,
            "solved": solved_rgb,
            "distance": float(dist),
        })

    # 生成可视化
    n_input = len(input_palette)
    n_solved = len(solved_palette)
    max_colors = max(n_input, n_solved)

    swatch_size = 40
    canvas_w = 400
    canvas_h = max(200, max_colors * (swatch_size + 10) + 60)

    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 10)
    except:
        font = ImageFont.load_default()
        font_small = font

    # 标题
    draw.text((10, 10), f"图层 {layer_idx} 调色板分析", fill=(0, 0, 0), font=font)
    draw.text((10, 35), f"输入颜色数: {n_input}, 求解颜色数: {n_solved}", fill=(0, 0, 0), font=font_small)

    # 绘制输入和求解调色板对比
    y_offset = 60
    for i in range(max_colors):
        # 输入颜色
        if i < n_input:
            input_rgb = input_palette[i]
            draw.rectangle([10, y_offset, 50, y_offset + swatch_size], fill=input_rgb, outline=(0, 0, 0))
            draw.text((55, y_offset + 10), f"输入: {input_rgb}", fill=(0, 0, 0), font=font_small)

        # 求解颜色
        if i < n_solved:
            solved_rgb = solved_palette[i]
            draw.rectangle([200, y_offset, 240, y_offset + swatch_size], fill=solved_rgb, outline=(0, 0, 0))
            draw.text((245, y_offset + 10), f"求解: {solved_rgb}", fill=(0, 0, 0), font=font_small)

        y_offset += swatch_size + 10

    canvas.save(output_path)

    return stats


def create_layer_composite_visualization(
    layers_rgba: List[np.ndarray],
    output_path: str,
    *,
    show_boundaries: bool = True,
    boundary_color: Tuple[int, int, int] = (255, 0, 0),
) -> None:
    """
    创建图层合成可视化
    """
    if not layers_rgba:
        return

    h, w = layers_rgba[0].shape[:2]

    # 合成所有图层
    composited = np.zeros((h, w, 3), dtype=np.float32)
    alpha_accum = np.zeros((h, w), dtype=np.float32)

    for layer in layers_rgba:
        rgb = layer[:, :, :3].astype(np.float32) / 255.0
        alpha = layer[:, :, 3].astype(np.float32) / 255.0

        contrib = alpha * (1 - alpha_accum)
        composited += rgb * contrib[:, :, np.newaxis]
        alpha_accum += contrib

    composited = (np.clip(composited, 0, 1) * 255).astype(np.uint8)

    # 如果需要显示边界
    if show_boundaries:
        for layer in layers_rgba:
            alpha = layer[:, :, 3]
            edges = cv2.Canny(alpha, 50, 150)
            composited[edges > 0] = boundary_color

    Image.fromarray(composited).save(output_path)


def create_difference_visualization(
    original: np.ndarray,
    reconstructed: np.ndarray,
    output_path: str,
    *,
    amplify: float = 5.0,
) -> None:
    """
    创建差异可视化图
    """
    # 计算差异
    diff = np.abs(original.astype(np.float32) - reconstructed.astype(np.float32))

    # 放大差异以便可视化
    diff_amplified = np.clip(diff * amplify, 0, 255).astype(np.uint8)

    # 转换为灰度图
    diff_gray = np.mean(diff_amplified, axis=2).astype(np.uint8)

    # 应用颜色映射
    diff_colored = cv2.applyColorMap(diff_gray, cv2.COLORMAP_JET)
    diff_colored = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)

    Image.fromarray(diff_colored).save(output_path)
