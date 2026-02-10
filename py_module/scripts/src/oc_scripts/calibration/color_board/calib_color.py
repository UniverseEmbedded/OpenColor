from __future__ import annotations

import cv2
import numpy as np


def srgb_to_linear01(srgb01: np.ndarray) -> np.ndarray:
    """
    将 sRGB 颜色从伽马空间转换到线性空间
    
    使用标准 sRGB 转换公式：
    - 对于值 <= 0.04045：linear = srgb / 12.92
    - 对于值 > 0.04045：linear = ((srgb + 0.055) / 1.055) ^ 2.4
    
    @param srgb01: sRGB 颜色值（0-1 范围）
    @return: 线性颜色值（0-1 范围）
    """
    a = 0.055
    srgb01 = np.clip(srgb01, 0.0, 1.0)
    return np.where(
        srgb01 <= 0.04045,
        srgb01 / 12.92,
        ((srgb01 + a) / (1 + a)) ** 2.4,
        )


def linear01_to_srgb(linear01: np.ndarray) -> np.ndarray:
    """
    将线性颜色从线性空间转换到 sRGB 伽马空间
    
    使用标准 sRGB 转换公式：
    - 对于值 <= 0.0031308：srgb = linear * 12.92
    - 对于值 > 0.0031308：srgb = 1.055 * (linear ^ (1/2.4)) - 0.055
    
    @param linear01: 线性颜色值（0-1 范围）
    @return: sRGB 颜色值（0-1 范围）
    """
    a = 0.055
    linear01 = np.clip(linear01, 0.0, 1.0)
    return np.where(
        linear01 <= 0.0031308,
        linear01 * 12.92,
        (1 + a) * (linear01 ** (1 / 2.4)) - a,
        )


def bgr_to_lab(img_bgr: np.ndarray) -> np.ndarray:
    """
    将 BGR 图像转换为 CIELAB 颜色空间
    
    OpenCV 默认使用 D65 白点和 2° 观察者。
    输出值范围：
    - L: 0-100
    - a: -128 到 127（灰度为 0）
    - b: -128 到 127（灰度为 0）
    
    @param img_bgr: BGR 格式图像（OpenCV 默认格式）
    @return: LAB 格式图像，形状与输入相同
    """
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0] * (100.0 / 255.0)  # L 通道：0-255 映射到 0-100
    a = lab[..., 1] - 128.0            # a 通道：0-255 映射到 -128-127
    b = lab[..., 2] - 128.0            # b 通道：0-255 映射到 -128-127
    return np.stack([L, a, b], axis=-1)


def deltaE76(lab1: np.ndarray, lab2: np.ndarray) -> float:
    """
    计算两个 CIELAB 颜色之间的 Delta E 1976 色差
    
    这是最简单的色差公式，直接计算欧几里得距离。
    
    @param lab1: 第一个 LAB 颜色
    @param lab2: 第二个 LAB 颜色
    @return: Delta E 色差值
    """
    d = lab1 - lab2
    return float(np.sqrt(np.sum(d * d)))
