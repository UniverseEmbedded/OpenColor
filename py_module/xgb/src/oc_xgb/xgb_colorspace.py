"""
颜色空间辅助模块
提供sRGB(0-255)与CIE Lab颜色空间之间的转换
使用OpenCV进行转换
"""

from __future__ import annotations

import cv2
import numpy as np


def srgb255_to_lab(rgb255: np.ndarray) -> np.ndarray:
    """
    将sRGB(0-255)颜色空间转换为CIE Lab颜色空间

    参数:
        rgb255: 输入数组，形状为(...,3)，数据类型为uint8或float，表示sRGB颜色值(0-255)

    返回:
        Lab颜色数组，形状为(...,3)，数据类型为float32
        L通道范围[0, 100]，a/b通道范围[-128, 127]
    """
    arr = np.asarray(rgb255, dtype=np.float32)
    arr01 = np.clip(arr / 255.0, 0.0, 1.0)
    img = arr01.reshape((-1, 1, 3))
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).reshape((-1, 3))
    return lab.astype(np.float32)


def lab_to_srgb255(lab: np.ndarray) -> np.ndarray:
    """
    将CIE Lab颜色空间转换为sRGB(0-255)颜色空间

    参数:
        lab: 输入数组，形状为(...,3)，数据类型为float32，表示OpenCV格式的Lab颜色值

    返回:
        sRGB颜色数组，形状为(...,3)，数据类型为uint8，值范围[0, 255]
    """
    lab = np.asarray(lab, dtype=np.float32).reshape((-1, 1, 3))
    rgb01 = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).reshape((-1, 3))
    rgb01 = np.clip(rgb01, 0.0, 1.0)
    rgb255 = (rgb01 * 255.0 + 0.5).astype(np.uint8)
    return rgb255
