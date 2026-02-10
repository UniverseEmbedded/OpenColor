"""gen_masks - 工具函数模块

本模块提供输出尺寸选择、目录清理、引导滤波等工具函数
"""

import shutil
from pathlib import Path

import cv2
import numpy as np


def _choose_preview_output_size(src_w: int, src_h: int, max_dim: int = 1920) -> tuple[int, int]:
    """选择预览输出尺寸"""
    if src_w <= 0 or src_h <= 0:
        return 1, 1
    mx = max(src_w, src_h)
    if mx <= max_dim:
        return int(src_w), int(src_h)
    s = float(max_dim) / float(mx)
    out_w = max(1, int(round(src_w * s)))
    out_h = max(1, int(round(src_h * s)))
    return out_w, out_h


def _clear_dir_keep_root(d: Path) -> None:
    """清空目录但保留根目录"""
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        return
    for child in d.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _guided_filter_gray(guidance_gray01: np.ndarray, src01: np.ndarray, radius: int, eps: float) -> np.ndarray:
    """引导滤波实现"""
    if guidance_gray01.ndim != 2:
        raise ValueError("guidance_gray01 必须是单通道二维数组")
    if src01.shape[:2] != guidance_gray01.shape[:2]:
        raise ValueError("guidance_gray01 与 src01 尺寸不一致")
    if int(radius) <= 0:
        return np.asarray(src01, dtype=np.float32)

    I = np.asarray(guidance_gray01, dtype=np.float32)
    p = np.asarray(src01, dtype=np.float32)
    r = int(radius)
    ksize = (r * 2 + 1, r * 2 + 1)
    mean_I = cv2.boxFilter(I, ddepth=-1, ksize=ksize, normalize=True)
    mean_p = cv2.boxFilter(p, ddepth=-1, ksize=ksize, normalize=True)
    corr_I = cv2.boxFilter(I * I, ddepth=-1, ksize=ksize, normalize=True)
    corr_Ip = cv2.boxFilter(I * p, ddepth=-1, ksize=ksize, normalize=True)
    var_I = corr_I - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p
    a = cov_Ip / (var_I + float(eps))
    b = mean_p - a * mean_I
    mean_a = cv2.boxFilter(a, ddepth=-1, ksize=ksize, normalize=True)
    mean_b = cv2.boxFilter(b, ddepth=-1, ksize=ksize, normalize=True)
    q = mean_a * I + mean_b
    return np.clip(q, 0.0, 1.0)
