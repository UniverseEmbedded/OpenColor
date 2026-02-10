"""标定板几何处理模块 - 提供四边形检测和透视变换功能"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from oc_scripts.calibration.calibrate_color_board_io import _write_png


def order_quad_points(pts: np.ndarray) -> np.ndarray:
    """
    将四边形点按左上、右上、右下、左下顺序排列

    使用坐标和与差值来确定角点位置
    """
    pts = np.array(pts, dtype=np.float32)
    if pts.shape != (4, 2):
        raise ValueError("Expected 4x2 points")
    s = pts.sum(axis=1)
    diff = (pts[:, 0] - pts[:, 1])
    tl = pts[np.argmin(s)]   # 左上：和最小
    br = pts[np.argmax(s)]   # 右下：和最大
    tr = pts[np.argmax(diff)]  # 右上：x-y差最大
    bl = pts[np.argmin(diff)]  # 左下：x-y差最小
    return np.stack([tl, tr, br, bl], axis=0).astype(np.float32)


def parse_corners(s: str) -> np.ndarray:
    """从字符串解析四个角点坐标

    格式：'x,y x,y x,y x,y' 或 'x,y; x,y; x,y; x,y'
    """
    parts = s.strip().replace(";", " ").split()
    if len(parts) != 4:
        raise ValueError("--corners must contain 4 points like 'x,y x,y x,y x,y'")
    pts = []
    for p in parts:
        xy = p.split(",")
        if len(xy) != 2:
            raise ValueError(f"Bad point: {p}")
        pts.append([float(xy[0]), float(xy[1])])
    return np.array(pts, dtype=np.float32)


def expand_quad(quad: np.ndarray, expand_frac: float, img_w: int, img_h: int) -> np.ndarray:
    """以质心为中心扩展四边形，并限制在图像边界内

    Args:
        quad: 四边形角点 (4,2)
        expand_frac: 扩展比例
        img_w: 图像宽度
        img_h: 图像高度
    """
    if expand_frac <= 0:
        return quad
    q = quad.astype(np.float32)
    c = q.mean(axis=0, keepdims=True)  # 质心
    q2 = c + (1.0 + float(expand_frac)) * (q - c)
    q2[:, 0] = np.clip(q2[:, 0], 0, img_w - 1)
    q2[:, 1] = np.clip(q2[:, 1], 0, img_h - 1)
    return q2.astype(np.float32)


def warp_perspective(img_bgr: np.ndarray, quad_tl_tr_br_bl: np.ndarray, out_w_px: int, out_h_px: int) -> Tuple[np.ndarray, np.ndarray]:
    """执行透视变换将四边形区域变换为矩形

    Returns:
        (变换后的图像, 单应性矩阵)
    """
    dst = np.array(
        [[0, 0], [out_w_px - 1, 0], [out_w_px - 1, out_h_px - 1], [0, out_h_px - 1]],
        dtype=np.float32,
    )
    H = cv2.getPerspectiveTransform(quad_tl_tr_br_bl, dst)
    warped = cv2.warpPerspective(img_bgr, H, (out_w_px, out_h_px))
    return warped, H


def detect_board_quad_by_chroma(img_bgr: np.ndarray, debug_dir: Optional[Path] = None) -> np.ndarray:
    """通过Lab色度通道检测标定板区域

    使用色度掩码对缝隙具有鲁棒性

    Args:
        img_bgr: BGR格式输入图像
        debug_dir: 调试输出目录（可选）

    Returns:
        按顺序排列的四边形角点 (4,2)
    """
    H, W = img_bgr.shape[:2]
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    a = lab[..., 1].astype(np.float32) - 128.0
    b = lab[..., 2].astype(np.float32) - 128.0
    chroma = np.sqrt(a * a + b * b)

    # 基于色度百分位数计算阈值
    thr = float(np.percentile(chroma, 65))
    thr = max(thr, 8.0)
    mask = (chroma >= thr).astype(np.uint8) * 255

    # 形态学操作清理掩码
    k = max(5, int(round(min(H, W) * 0.01)) | 1)
    kernel = np.ones((k, k), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # 查找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("No contours found from chroma mask")

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    c = contours[0]
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)

    # 获取四边形
    if len(approx) == 4:
        quad = order_quad_points(approx.reshape(4, 2).astype(np.float32))
    else:
        rect = cv2.minAreaRect(c)
        box = cv2.boxPoints(rect).astype(np.float32)
        quad = order_quad_points(box)

    # 保存调试图像
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        _write_png(debug_dir / "debug_mask.png", mask)
        edges = cv2.Canny(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY), 50, 150)
        _write_png(debug_dir / "debug_edges.png", edges)
        vis = img_bgr.copy()
        cv2.polylines(vis, [quad.astype(np.int32)], True, (0, 255, 0), 3)
        _write_png(debug_dir / "debug_quad.png", vis)

    return quad
