"""偏差计算模块 - 提供几何体与掩码偏差计算功能

用于计算矢量化后的几何体与原始参考掩码之间的面积偏差，评估矢量化质量。
"""

import traceback

import numpy as np

from oc_sdf.sdf_io import rasterize_geometry_soft


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _compute_geom_mask_deviation_mm2(
    *,
    geom,
    ref_mask_bin: np.ndarray,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
    tol_px: int,
) -> float:
    """计算几何体与参考掩码的偏差面积（平方毫米）

    将几何体栅格化后与参考掩码比较，计算差异区域的面积。
    支持带容差的比较，允许边缘有一定偏差。

    参数:
        geom: shapely几何体对象
        ref_mask_bin: 参考二值掩码
        board_mm: 板尺寸（毫米）
        pixel_w: 像素宽度
        pixel_h: 像素高度
        tol_px: 容差像素数，0表示严格比较

    返回:
        偏差面积（平方毫米）
    """
    # 处理空几何情况
    if geom is None or getattr(geom, "is_empty", True):
        ref_area_px = int(np.count_nonzero(ref_mask_bin))
        mm_per_px_x = float(board_mm) / float(pixel_w)
        mm_per_px_y = float(board_mm) / float(pixel_h)
        return float(ref_area_px) * float(mm_per_px_x) * float(mm_per_px_y)

    # 栅格化几何体
    px_per_mm = float(pixel_w) / float(board_mm)
    r = rasterize_geometry_soft(
        geom,
        int(pixel_w),
        int(pixel_h),
        float(board_mm),
        float(px_per_mm),
        supersample=1,
    )
    if r is None:
        ref_area_px = int(np.count_nonzero(ref_mask_bin))
        mm_per_px_x = float(board_mm) / float(pixel_w)
        mm_per_px_y = float(board_mm) / float(pixel_h)
        return float(ref_area_px) * float(mm_per_px_x) * float(mm_per_px_y)

    # 二值化预测结果
    pred_bin = np.asarray(r >= 0.5, dtype=bool)
    ref_bin = np.asarray(ref_mask_bin, dtype=bool)

    # 计算像素面积（平方毫米）
    mm_per_px_x = float(board_mm) / float(pixel_w)
    mm_per_px_y = float(board_mm) / float(pixel_h)
    px_area_mm2 = float(mm_per_px_x) * float(mm_per_px_y)

    t = int(tol_px)
    if t <= 0:
        # 严格比较：直接XOR
        bad = np.logical_xor(ref_bin, pred_bin)
        return float(np.count_nonzero(bad)) * float(px_area_mm2)

    # 带容差的比较
    try:
        import cv2

        # 创建膨胀/腐蚀核
        k = 2 * t + 1
        kernel = np.ones((k, k), dtype=np.uint8)

        # 转换为uint8格式
        ref_u8 = ref_bin.astype(np.uint8) * 255
        pred_u8 = pred_bin.astype(np.uint8) * 255

        # 对参考和预测分别进行膨胀和腐蚀
        ref_dil = cv2.dilate(ref_u8, kernel, iterations=1) > 0
        ref_ero = cv2.erode(ref_u8, kernel, iterations=1) > 0
        pred_dil = cv2.dilate(pred_u8, kernel, iterations=1) > 0
        pred_ero = cv2.erode(pred_u8, kernel, iterations=1) > 0

        # 假阳性：预测为前景但参考膨胀后为背景（预测太宽）
        fp = pred_ero & (~ref_dil)
        # 假阴性：参考为前景但预测膨胀后为背景（预测太窄）
        fn = ref_ero & (~pred_dil)
        return float(np.count_nonzero(fp) + np.count_nonzero(fn)) * float(px_area_mm2)
    except Exception as e:
        logger.error(f"[警告] 计算容差偏差失败，将回退到无容差 XOR。原因={e}")
        traceback.print_exc()
        bad = np.logical_xor(ref_bin, pred_bin)
        return float(np.count_nonzero(bad)) * float(px_area_mm2)
