"""
颜色空间转换工具模块
提供sRGB与线性RGB、CIE Lab颜色空间之间的转换函数
"""

import cv2
import numpy as np


def srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    """将sRGB转换为线性RGB

    应用sRGB的Gamma校正逆过程，将sRGB值（0-255）转换为线性RGB值（0-1）

    Args:
        rgb: 输入RGB数组，范围0-255

    Returns:
        线性RGB数组，范围0-1
    """
    rgb = np.asarray(rgb, dtype=np.float32) / 255.0
    a = 0.055
    return np.where(rgb <= 0.04045, rgb/12.92, ((rgb + a) / (1 + a)) ** 2.4)

def linear_to_srgb(lin: np.ndarray) -> np.ndarray:
    """将线性RGB转换为sRGB

    应用sRGB的Gamma校正，将线性RGB值（0-1）转换为sRGB值（0-255）

    Args:
        lin: 输入线性RGB数组，范围0-1

    Returns:
        sRGB数组，范围0-255
    """
    lin = np.asarray(lin, dtype=np.float32)
    a = 0.055
    srgb = np.where(lin <= 0.0031308, lin * 12.92, (1 + a) * np.power(lin, 1/2.4) - a)
    return np.clip(srgb * 255.0, 0, 255)

def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """将RGB转换为CIE Lab颜色空间

    使用OpenCV将RGB颜色转换为CIE Lab颜色空间

    Args:
        rgb: 输入RGB数组，形状(...,3)，范围0-255或0-1

    Returns:
        Lab数组，形状(...,3)，L范围0-100，a,b范围-128到127
    """
    # rgb: (...,3) uint8 or float 0..255
    arr = np.asarray(rgb, dtype=np.float32)
    if arr.max() <= 1.0:
        arr = arr * 255.0
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    bgr = arr[..., ::-1]
    lab = cv2.cvtColor(bgr.reshape(-1,1,3), cv2.COLOR_BGR2LAB).reshape(-1,3).astype(np.float32)
    return lab

def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    """将CIE Lab转换为RGB颜色空间

    使用OpenCV将CIE Lab颜色转换为RGB颜色空间

    Args:
        lab: 输入Lab数组，形状(...,3)

    Returns:
        RGB数组，形状(...,3)，范围0-255
    """
    lab = np.asarray(lab, dtype=np.float32).reshape(-1,1,3)
    bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR).reshape(-1,3)
    rgb = bgr[..., ::-1]
    return np.clip(rgb, 0, 255)
