from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

import cv2
import numpy as np


@dataclass
class WarpParams:
    """透视变换参数"""

    dst_size: int = 1000
    total_rows: int = 34
    total_cols: int = 34
    zoom: float = 1.0
    barrel: float = 0.0  # 径向畸变系数（较小值）
    offset_x: float = 0.0  # 畸变空间中的像素偏移 X
    offset_y: float = 0.0  # 畸变空间中的像素偏移 Y
    auto_wb: bool = False  # 自动白平衡
    vignette_fix: bool = False  # 暗角补偿


def estimate_coarse_homography(
    image_gray: np.ndarray, board_spec: Any, params: WarpParams
) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
    """估计粗略的单应性矩阵 H_coarse，并返回调试信息"""
    debug_info = {
        "detections": [],
        "tag_used": None,
        "tag_type": None,
        "rms_error": None,
    }

    # AprilTag 功能已移除
    return None, debug_info


def get_board_corners_from_h(
    H: np.ndarray, board_spec: Any
) -> List[Tuple[float, float]]:
    """通过 H 矩阵将板子四个角点投影到图像空间"""
    total_w = board_spec.cols * board_spec.cell_size_mm
    total_h = board_spec.rows * board_spec.cell_size_mm

    # 板子坐标系下的四个角 (TL, TR, BR, BL)
    board_corners = np.array(
        [[0, 0], [total_w, 0], [total_w, total_h], [0, total_h]], dtype=np.float32
    ).reshape(-1, 1, 2)

    img_corners = cv2.perspectiveTransform(board_corners, H)
    return [tuple(p) for p in img_corners.reshape(-1, 2)]


def _order_points_tl_tr_br_bl(pts: List[Tuple[float, float]]) -> np.ndarray:
    """根据和/差值将点排序为左上、右上、右下、左下"""
    if len(pts) != 4:
        raise ValueError("需要 4 个点")
    p = np.array(pts, dtype=np.float32)
    s = p.sum(axis=1)
    d = p[:, 0] - p[:, 1]
    # 修正排序逻辑：
    # tl: sum 最小
    # br: sum 最大
    # tr: x-y 最大
    # bl: x-y 最小
    tl = p[np.argmin(s)]
    br = p[np.argmax(s)]
    tr = p[np.argmax(d)]
    bl = p[np.argmin(d)]
    return np.stack([tl, tr, br, bl], axis=0)


def perspective_warp_bgr(
    img_bgr: np.ndarray, corner_points_xy: List[Tuple[float, float]], params: WarpParams
) -> np.ndarray:
    """将校准板照片透视变换为正方形"""
    pts_src = _order_points_tl_tr_br_bl(corner_points_xy)

    dst = params.dst_size
    pts_dst = np.array(
        [
            [0, 0],
            [dst, 0],
            [dst, dst],
            [0, dst],
        ],
        dtype=np.float32,
    )

    M = cv2.getPerspectiveTransform(pts_src, pts_dst)
    warped = cv2.warpPerspective(
        img_bgr, M, (dst, dst), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )

    return apply_adjustments_bgr(warped, params)


def apply_adjustments_bgr(warped_bgr: np.ndarray, params: WarpParams) -> np.ndarray:
    """在畸变空间中应用缩放、偏移和简单的桶形畸变"""
    img = warped_bgr
    dst = params.dst_size

    # 1) 围绕中心缩放
    if abs(params.zoom - 1.0) > 1e-6:
        center = (dst / 2.0, dst / 2.0)
        Mz = cv2.getRotationMatrix2D(center, 0.0, params.zoom)
        img = cv2.warpAffine(
            img, Mz, (dst, dst), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        )

    # 2) 偏移
    if abs(params.offset_x) > 1e-6 or abs(params.offset_y) > 1e-6:
        Mo = np.array(
            [[1, 0, params.offset_x], [0, 1, params.offset_y]], dtype=np.float32
        )
        img = cv2.warpAffine(
            img, Mo, (dst, dst), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        )

    # 3) 桶形畸变（径向）
    if abs(params.barrel) > 1e-9:
        k = float(params.barrel)
        h, w = img.shape[:2]
        cx, cy = w / 2.0, h / 2.0
        # 归一化坐标在 [-1,1] 范围内
        xs = (np.arange(w, dtype=np.float32) - cx) / (w / 2.0)
        ys = (np.arange(h, dtype=np.float32) - cy) / (h / 2.0)
        xv, yv = np.meshgrid(xs, ys)
        r2 = xv * xv + yv * yv
        # 前向模型: x_d = x * (1 + k*r^2)
        factor = 1.0 + k * r2
        x_d = xv * factor
        y_d = yv * factor
        # 映射回像素坐标
        map_x = (x_d * (w / 2.0) + cx).astype(np.float32)
        map_y = (y_d * (h / 2.0) + cy).astype(np.float32)
        img = cv2.remap(
            img,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

    # 4) 自动白平衡
    if params.auto_wb:
        img = apply_auto_white_balance_bgr(img)

    # 5) 暗角补偿
    if params.vignette_fix:
        img = apply_brightness_correction_bgr(img)

    return img


def extract_lut_from_warped_bgr(
    warped_bgr: np.ndarray,
    total_rows: int = 34,
    total_cols: int = 34,
    window_px: int = 8,
) -> np.ndarray:
    """从标准化的畸变板图像中采样所有单元格的 RGB 值。
    注意：返回的是一个 (total_rows, total_cols, 3) 的数组，包含边框。
    """
    dst = warped_bgr.shape[0]
    if warped_bgr.shape[0] != warped_bgr.shape[1]:
        raise ValueError("畸变矫正后的图像必须为正方形")

    cell_w = dst / float(total_cols)
    cell_h = dst / float(total_rows)

    samples = np.zeros((total_rows, total_cols, 3), dtype=np.uint8)

    rad = max(1, int(window_px // 2))
    for r in range(total_rows):
        for c in range(total_cols):
            cx = int(round((c + 0.5) * cell_w))
            cy = int(round((r + 0.5) * cell_h))
            x0 = max(0, cx - rad)
            x1 = min(dst, cx + rad)
            y0 = max(0, cy - rad)
            y1 = min(dst, cy + rad)
            patch = warped_bgr[y0:y1, x0:x1]
            # 使用中值 (median) 替代均值 (mean)，对噪声更鲁棒
            bgr = np.median(patch.reshape(-1, 3), axis=0)
            rgb = bgr[::-1]
            samples[r, c] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)

    return samples


def render_grid_overlay_bgr(
    warped_bgr: np.ndarray,
    total_rows: int = 34,
    total_cols: int = 34,
    line_step: int = 1,
) -> np.ndarray:
    """渲染网格叠加层用于可视化"""
    img = warped_bgr.copy()
    h, w = img.shape[:2]
    cell_w = w / float(total_cols)
    cell_h = h / float(total_rows)

    # 绘制垂直线
    for i in range(0, total_cols + 1, line_step):
        x = int(round(i * cell_w))
        cv2.line(img, (x, 0), (x, h - 1), (0, 255, 0), 1)

    # 绘制水平线
    for i in range(0, total_rows + 1, line_step):
        y = int(round(i * cell_h))
        cv2.line(img, (0, y), (w - 1, y), (0, 255, 0), 1)

    return img


def apply_auto_white_balance_bgr(img_bgr: np.ndarray) -> np.ndarray:
    """
    自动白平衡：假设四个角（边框处）应该是中性色（白色）。
    """
    h, w = img_bgr.shape[:2]
    m = 50  # 采样边长

    # 采样四角
    tl = img_bgr[0:m, 0:m].mean(axis=(0, 1))
    tr = img_bgr[0:m, w - m : w].mean(axis=(0, 1))
    bl = img_bgr[h - m : h, 0:m].mean(axis=(0, 1))
    br = img_bgr[h - m : h, w - m : w].mean(axis=(0, 1))

    avg_white = (tl + tr + bl + br) / 4.0
    # 避免除以零
    avg_white = np.maximum(avg_white, 1e-5)

    # 计算增益，目标是使四个角平均值为 [240, 240, 240] (略低于纯白)
    target = np.array([240, 240, 240], dtype=np.float32)
    gain = target / avg_white

    res = img_bgr.astype(np.float32) * gain
    return np.clip(res, 0, 255).astype(np.uint8)


def apply_brightness_correction_bgr(img_bgr: np.ndarray) -> np.ndarray:
    """
    暗角补偿：通过分析四角亮度差异，生成渐变掩模来补偿光照不均。
    """
    h, w = img_bgr.shape[:2]
    # 使用 LAB 空间的 L 分量（亮度）进行处理
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l_float = l.astype(np.float32)

    m = 50
    tl = l_float[0:m, 0:m].mean()
    tr = l_float[0:m, w - m : w].mean()
    bl = l_float[h - m : h, 0:m].mean()
    br = l_float[h - m : h, w - m : w].mean()

    # 创建双线性插值的亮度掩模
    top = np.linspace(tl, tr, w)
    bottom = np.linspace(bl, br, w)
    mask = np.zeros((h, w), dtype=np.float32)
    for y in range(h):
        weight_bot = y / (h - 1)
        mask[y, :] = (1.0 - weight_bot) * top + weight_bot * bottom

    target = (tl + tr + bl + br) / 4.0
    # 补偿系数 = 目标亮度 / 当前位置亮度
    correction = target / np.maximum(mask, 1.0)

    l_corrected = np.clip(l_float * correction, 0, 255).astype(np.uint8)
    res_lab = cv2.merge([l_corrected, a, b])
    return cv2.cvtColor(res_lab, cv2.COLOR_LAB2BGR)
