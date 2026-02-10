"""
校准色板IO工具模块
提供图像读写功能，支持Unicode路径
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _read_image_unicode(path: str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    """
    读取图像文件（支持Unicode路径）
    
    使用numpy的fromfile方法读取文件数据，然后通过cv2.imdecode解码图像，
    以支持包含非ASCII字符的文件路径。
    
    参数:
        path: 图像文件路径
        flags: OpenCV读取标志，默认为cv2.IMREAD_COLOR（彩色读取）
        
    返回:
        解码后的图像数组
        
    异常:
        FileNotFoundError: 当图像读取失败时抛出
    """
    p = Path(path)
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, flags)
    if img is None:
        raise FileNotFoundError(f"Failed to read image: {path}")
    return img


def _write_png(path: Path, img: np.ndarray) -> None:
    """
    将图像保存为PNG格式（支持Unicode路径）
    
    使用cv2.imencode编码图像，然后通过numpy的tofile方法写入文件，
    以支持包含非ASCII字符的文件路径。
    
    参数:
        path: 输出PNG文件路径
        img: 要保存的图像数组
        
    异常:
        RuntimeError: 当PNG编码失败时抛出
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError(f"Failed to encode PNG: {path}")
    buf.tofile(str(path))
