"""
颜色空间转换模块

提供RGB与Lab颜色空间之间的转换函数
"""

from __future__ import annotations

import cv2
import numpy as np


def _as_img(rgb01: np.ndarray) -> np.ndarray:
    """确保形状 (...,3) -> (N,1,3) float32 以供 cv2 使用"""
    arr = np.asarray(rgb01, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    arr = arr.reshape((-1, 1, 3)).astype(np.float32)
    return arr


def rgb01_to_lab(rgb01: np.ndarray) -> np.ndarray:
    """sRGB (0..1) 转换为 CIE Lab (float32; L 范围 [0..100], a/b 约 [-128..127])"""
    img = _as_img(rgb01)
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    return lab.reshape((-1, 3)).astype(np.float32)


def lab_to_rgb01(lab: np.ndarray) -> np.ndarray:
    """将 (N, 3) 的 Lab 转换为 0-1 RGB"""
    img = _as_img(lab)
    rgb = cv2.cvtColor(img, cv2.COLOR_LAB2RGB)
    # OpenCV 对于 float32 的 Lab 输入，返回的 RGB 已经是 0-1 范围
    return rgb.reshape((-1, 3)).astype(np.float32)


def srgb_to_linear01(srgb01: np.ndarray) -> np.ndarray:
    """将 sRGB 从非线性空间转换到线性空间（0-1范围）"""
    a = 0.055
    x = np.clip(np.asarray(srgb01, dtype=np.float32), 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4).astype(np.float32)


def linear01_to_srgb01(lin01: np.ndarray) -> np.ndarray:
    """将线性 sRGB 从线性空间转换到非线性空间（0-1范围）"""
    a = 0.055
    x = np.clip(np.asarray(lin01, dtype=np.float32), 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, (1 + a) * (x ** (1 / 2.4)) - a).astype(np.float32)


def delta_e_cie76(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """计算 CIE76 Delta E 颜色差异
    
    Args:
        lab1: 第一个 Lab 颜色数组 (N, 3)
        lab2: 第二个 Lab 颜色数组 (N, 3)
        
    Returns:
        Delta E 差异值数组 (N,)
    """
    lab1 = np.asarray(lab1, dtype=np.float32)
    lab2 = np.asarray(lab2, dtype=np.float32)
    return np.sqrt(np.sum((lab1 - lab2) ** 2, axis=-1)).astype(np.float32)
