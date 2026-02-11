"""图像滤波模块 - 提供引导滤波、高斯模糊等图像处理功能"""

import numpy as np
from scipy.ndimage import gaussian_filter


def _guided_filter_gray(
    guidance_gray01: np.ndarray, src01: np.ndarray, radius: int, eps: float
) -> np.ndarray:
    """
    引导滤波实现
    """
    guidance_gray01 = guidance_gray01.astype(np.float64)
    src01 = src01.astype(np.float64)

    mean_I = box_filter(guidance_gray01, radius)
    mean_p = box_filter(src01, radius)
    mean_Ip = box_filter(guidance_gray01 * src01, radius)
    cov_Ip = mean_Ip - mean_I * mean_p

    mean_II = box_filter(guidance_gray01 * guidance_gray01, radius)
    var_I = mean_II - mean_I * mean_I

    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    mean_a = box_filter(a, radius)
    mean_b = box_filter(b, radius)

    q = mean_a * guidance_gray01 + mean_b
    return np.clip(q, 0, 1)


def box_filter(img: np.ndarray, r: int) -> np.ndarray:
    """
    快速盒式滤波（积分图优化版）
    """
    (rows, cols) = img.shape
    imDst = np.zeros_like(img)

    imCum = np.cumsum(img, 0)
    imDst[0 : r + 1, :] = imCum[r : 2 * r + 1, :]
    imDst[r + 1 : rows - r, :] = (
        imCum[2 * r + 1 : rows, :] - imCum[0 : rows - 2 * r - 1, :]
    )
    imDst[rows - r : rows, :] = (
        np.tile(imCum[rows - 1, :], [r, 1]) - imCum[rows - 2 * r - 1 : rows - r - 1, :]
    )

    imCum = np.cumsum(imDst, 1)
    imDst[:, 0 : r + 1] = imCum[:, r : 2 * r + 1]
    imDst[:, r + 1 : cols - r] = (
        imCum[:, 2 * r + 1 : cols] - imCum[:, 0 : cols - 2 * r - 1]
    )
    imDst[:, cols - r : cols] = (
        np.tile(imCum[:, cols - 1], [r, 1]).T
        - imCum[:, cols - 2 * r - 1 : cols - r - 1]
    )

    return imDst


def _gaussian_blur_masked_rgb_u8(
    image_u8: np.ndarray, mask_bool: np.ndarray, sigma: float
) -> np.ndarray:
    """
    带掩码的高斯模糊（仅对掩码内区域进行模糊，保持掩码外不变）
    """
    h, w = image_u8.shape[:2]
    result = image_u8.copy()

    # 分离掩码区域
    mask_coords = np.where(mask_bool)

    if len(mask_coords[0]) == 0:
        return result

    # 对每个通道分别处理
    for c in range(3):
        channel = image_u8[:, :, c].astype(np.float32)

        # 仅对掩码内区域进行高斯模糊
        blurred = gaussian_filter(channel, sigma=sigma, mode="nearest")

        # 将模糊结果应用到掩码区域
        result[mask_coords[0], mask_coords[1], c] = blurred[
            mask_coords[0], mask_coords[1]
        ].astype(np.uint8)

    return result


def apply_guided_filter_to_mask(
    mask_u8: np.ndarray, guidance_rgb: np.ndarray, radius: int = 4, eps: float = 0.01
) -> np.ndarray:
    """
    对掩码应用引导滤波
    """
    guidance_gray = np.mean(guidance_rgb, axis=2)
    guidance_gray01 = guidance_gray / 255.0
    mask01 = mask_u8.astype(np.float32) / 255.0

    filtered = _guided_filter_gray(guidance_gray01, mask01, radius, eps)
    return (filtered * 255).astype(np.uint8)


def apply_sharpening(image_u8: np.ndarray, strength: float = 1.5) -> np.ndarray:
    """
    应用锐化滤波
    """
    from scipy.ndimage import convolve

    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = np.zeros_like(image_u8, dtype=np.float32)

    for c in range(3):
        channel = image_u8[:, :, c].astype(np.float32)
        sharpened[:, :, c] = convolve(channel, kernel, mode="nearest")

    # 混合原图和锐化图
    result = image_u8.astype(np.float32) * (1 - strength) + sharpened * strength
    return np.clip(result, 0, 255).astype(np.uint8)


def apply_super_resolution_simple(image_u8: np.ndarray, scale: int = 2) -> np.ndarray:
    """
    简单的超分辨率（双三次插值）
    """
    from PIL import Image

    pil_img = Image.fromarray(image_u8)
    new_size = (pil_img.width * scale, pil_img.height * scale)
    upscaled = pil_img.resize(new_size, Image.Resampling.LANCZOS)
    return np.array(upscaled)
