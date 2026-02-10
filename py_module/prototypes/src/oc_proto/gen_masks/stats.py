"""统计模块 - 提供周长、岛屿等统计功能"""

from typing import Dict

import cv2
import numpy as np

from .joint_refinement_boundary import _boundary_length_4, _perimeter_by_slot_4



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def compute_perimeter_stats(mask_u8: np.ndarray) -> Dict:
    """计算掩码的周长统计信息

    Args:
        mask_u8: 二值掩码图像 (H, W) uint8

    Returns:
        包含周长统计信息的字典
    """
    # 找到轮廓
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    total_perimeter = 0
    contour_count = len(contours)

    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        total_perimeter += perimeter

    # 计算面积
    total_area = np.sum(mask_u8 > 127)

    # 计算圆形度
    circularity = 0.0
    if total_perimeter > 0:
        circularity = 4 * np.pi * total_area / (total_perimeter ** 2)

    return {
        "total_perimeter": float(total_perimeter),
        "contour_count": contour_count,
        "total_area": int(total_area),
        "circularity": float(circularity),
        "avg_perimeter": float(total_perimeter / contour_count) if contour_count > 0 else 0.0,
    }


def compute_island_stats(mask_u8: np.ndarray, *, min_area: int = 10) -> Dict:
    """计算岛屿（连通区域）统计信息

    Args:
        mask_u8: 二值掩码图像 (H, W) uint8
        min_area: 最小岛屿面积

    Returns:
        包含岛屿统计信息的字典
    """
    # 连通区域标记
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)

    # 过滤掉背景（标签0）和小面积区域
    island_areas = []
    island_count = 0
    total_island_area = 0

    for i in range(1, num_labels):  # 从1开始跳过背景
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            island_areas.append(area)
            island_count += 1
            total_island_area += area

    return {
        "island_count": island_count,
        "total_island_area": int(total_island_area),
        "avg_island_area": float(total_island_area / island_count) if island_count > 0 else 0.0,
        "max_island_area": int(max(island_areas)) if island_areas else 0,
        "min_island_area": int(min(island_areas)) if island_areas else 0,
        "island_areas": island_areas,
    }


def suppress_small_islands(mask_u8: np.ndarray, min_area: int = 50) -> np.ndarray:
    """抑制小岛屿（移除面积小于阈值的连通区域）

    Args:
        mask_u8: 二值掩码图像 (H, W) uint8
        min_area: 最小岛屿面积

    Returns:
        处理后的掩码
    """
    # 连通区域标记
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)

    # 创建输出掩码
    result = np.zeros_like(mask_u8)

    # 保留大岛屿
    for i in range(1, num_labels):  # 从1开始跳过背景
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            result[labels == i] = 255

    return result


def compute_layer_statistics(mask_u8: np.ndarray) -> Dict:
    """计算图层的综合统计信息

    Args:
        mask_u8: 二值掩码图像

    Returns:
        包含所有统计信息的字典
    """
    perimeter_stats = compute_perimeter_stats(mask_u8)
    island_stats = compute_island_stats(mask_u8)

    # 合并统计信息
    stats = {
        "perimeter": perimeter_stats,
        "islands": island_stats,
        "coverage_ratio": float(island_stats["total_island_area"] / mask_u8.size),
    }

    return stats


def print_layer_stats(layer_idx: int, mask_u8: np.ndarray, prefix: str = "") -> None:
    """打印图层统计信息

    Args:
        layer_idx: 图层索引
        mask_u8: 图层掩码
        prefix: 输出前缀
    """
    stats = compute_layer_statistics(mask_u8)

    logger.info(f"{prefix}图层 {layer_idx} 统计信息:")
    logger.info(f"{prefix}  - 周长: {stats['perimeter']['total_perimeter']:.1f} 像素")
    logger.info(f"{prefix}  - 轮廓数: {stats['perimeter']['contour_count']}")
    logger.info(f"{prefix}  - 岛屿数: {stats['islands']['island_count']}")
    logger.info(f"{prefix}  - 总面积: {stats['islands']['total_island_area']} 像素")
    logger.info(f"{prefix}  - 覆盖率: {stats['coverage_ratio']*100:.2f}%")


def print_layer_perimeter_stats(
    labels_by_layer: list[np.ndarray],
    *,
    full_mask: np.ndarray,
    slot_names: list[str],
    title: str,
) -> None:
    """打印每层色块边线长度统计"""
    roi = np.asarray(full_mask, dtype=bool)
    n_slots = int(len(slot_names))
    logger.info(f"[信息] 每层色块边线长度统计({title})")
    for z, lab0 in enumerate(labels_by_layer):
        lab = np.asarray(lab0, dtype=np.int16)
        if lab.shape[:2] != roi.shape[:2]:
            logger.warning(f"[警告] L{z:02d} labels 尺寸不一致，跳过边线统计: {lab.shape} vs {roi.shape}")
            continue
        total = _boundary_length_4(lab, roi)
        per_slot = _perimeter_by_slot_4(lab, roi, n_slots=n_slots)
        topk = np.argsort(-per_slot)[: min(5, int(per_slot.shape[0]))]
        top_txt = ", ".join([f"{slot_names[int(i)]}={int(per_slot[int(i)])}" for i in topk if int(per_slot[int(i)]) > 0])
        if top_txt:
            logger.info(f"  L{z:02d}: total_perim4={total}, top={top_txt}")
        else:
            logger.info(f"  L{z:02d}: total_perim4={total}")
