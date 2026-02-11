"""
掩码重叠检测模块
检测各层掩码之间的重叠和空缺情况，生成热力图可视化报告
"""

from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from oc_core_02.utils.io_utils import print_ts


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
try:
    import cv2

    _HAS_CV2 = True
except Exception as e:
    logger.warning(f"警告: 无法导入 cv2，部分边界容差功能不可用。原因: {e}")
    cv2 = None
    _HAS_CV2 = False


def check_mask_overlaps(
    mask_dir: str,
    full_mask: np.ndarray = None,
    pattern: str = "*_mask.png",
    output_suffix: str = "",
    *,
    binarize: bool = False,
    threshold_u8: int = 128,
    boundary_tolerance_px: int = 0,
    soft_edge_sigma_px: float = 0.0,
) -> dict:
    mask_path = Path(mask_dir)
    if not mask_path.exists():
        raise FileNotFoundError(f"未找到 mask 目录: {mask_path}")

    masks = list(mask_path.glob(pattern))
    if not masks:
        logger.warning(f"警告: 在 {mask_path} 下未找到符合模式 {pattern} 的文件")
        return {}

    layers: dict[str, list[Path]] = {}
    for m in masks:
        name = m.stem
        if "heatmap" in name:
            continue
        parts = name.split("_")
        if len(parts) < 3:
            continue
        layer_str = parts[0]
        layers.setdefault(layer_str, []).append(m)

    if not layers:
        logger.warning("警告: 未找到任何有效的层数据用于检测重叠")
        return {}

    report = {"layers": {}, "total_overlap_area": 0.0, "total_gap_area": 0.0}

    def _to_u8_mask(arr: np.ndarray) -> np.ndarray:
        if arr is None:
            return None
        if arr.dtype == bool:
            return arr.astype(np.uint8) * 255
        if np.issubdtype(arr.dtype, np.floating):
            mx = float(np.max(arr)) if arr.size > 0 else 0.0
            if mx <= 1.0:
                return np.clip(arr * 255.0, 0.0, 255.0).astype(np.uint8)
            return np.clip(arr, 0.0, 255.0).astype(np.uint8)
        if arr.dtype == np.uint8:
            return arr
        return np.clip(arr, 0, 255).astype(np.uint8)

    def _maybe_binarize_u8(arr_u8: np.ndarray) -> np.ndarray:
        if arr_u8 is None:
            return None
        if not binarize:
            return arr_u8
        thr = int(threshold_u8)
        thr = max(0, min(thr, 255))
        return (arr_u8 > thr).astype(np.uint8) * 255

    def _to01(arr_u8: np.ndarray) -> np.ndarray:
        if arr_u8 is None:
            return None
        return arr_u8.astype(np.float32) / 255.0

    def _soft_blur_01(arr_u8: np.ndarray) -> np.ndarray:
        if arr_u8 is None:
            return None
        sigma = float(soft_edge_sigma_px)
        if not (sigma > 0):
            return _to01(arr_u8)

        if _HAS_CV2:
            try:
                f01 = _to01(arr_u8)
                f2 = cv2.GaussianBlur(
                    f01,
                    ksize=(0, 0),
                    sigmaX=sigma,
                    sigmaY=sigma,
                    borderType=cv2.BORDER_REPLICATE,
                )
                return np.clip(f2, 0.0, 1.0).astype(np.float32)
            except Exception as e:
                logger.error(f"警告: cv2 高斯模糊失败，将回退到 PIL 模糊。原因: {e}")

        try:
            from PIL import ImageFilter

            im = Image.fromarray(arr_u8, mode="L")
            im2 = im.filter(ImageFilter.GaussianBlur(radius=float(sigma)))
            return _to01(np.array(im2, dtype=np.uint8))
        except Exception as e:
            logger.error(
                f"警告: PIL 高斯模糊失败，将跳过 soft_edge_sigma_px。原因: {e}"
            )
            return _to01(arr_u8)

    t_all0 = perf_counter()
    for layer_str, files in sorted(layers.items()):
        t0 = perf_counter()
        print_ts(
            f"[信息] 检查层质量(精细重叠与空缺分析): {layer_str}, 文件数={len(files)}"
        )

        first = None
        for p in files:
            try:
                first = np.array(Image.open(p).convert("L"), dtype=np.uint8)
                break
            except Exception as e:
                logger.error(f"读取 mask 失败: {p.name}, 错误: {e}")
                raise

        if first is None:
            continue

        h, w = first.shape
        masks_u8: list[np.ndarray] = []

        for p in files:
            name = p.stem
            parts = name.split("_")
            slot_name = parts[1] if len(parts) >= 2 else "?"
            try:
                m_u8 = np.array(Image.open(p).convert("L"), dtype=np.uint8)
            except Exception as e:
                logger.error(f"读取 mask 失败: {p.name}, 错误: {e}")
                raise

            if m_u8.shape != (h, w):
                logger.warning(
                    f"  警告: mask {slot_name} 尺寸不匹配 {m_u8.shape} != {(h, w)}，正在自动 resize..."
                )
                m_u8 = np.array(
                    Image.fromarray(m_u8).resize((w, h), Image.BILINEAR), dtype=np.uint8
                )

            if binarize:
                masks_u8.append(_maybe_binarize_u8(m_u8))
            else:
                masks_u8.append(m_u8)

        tol = int(boundary_tolerance_px)
        if tol < 0:
            tol = 0

        masks_for_overlap = masks_u8
        masks_for_gap = masks_u8

        if tol > 0:
            if not _HAS_CV2:
                logger.warning(
                    "  [警告] boundary_tolerance_px 已设置，但 cv2 不可用，将忽略边界容差"
                )
            else:
                k = 2 * tol + 1
                kernel = np.ones((k, k), dtype=np.uint8)
                masks_for_overlap = [
                    cv2.erode(m, kernel, iterations=1) for m in masks_u8
                ]
                masks_for_gap = [cv2.dilate(m, kernel, iterations=1) for m in masks_u8]

        masks_for_overlap_01 = [_soft_blur_01(m) for m in masks_for_overlap]
        masks_for_gap_01 = [_soft_blur_01(m) for m in masks_for_gap]

        sum_overlap_01 = np.zeros((h, w), dtype=np.float32)
        sum_gap_01 = np.zeros((h, w), dtype=np.float32)
        for m01 in masks_for_overlap_01:
            sum_overlap_01 += m01
        for m01 in masks_for_gap_01:
            sum_gap_01 += m01

        overlap_int_01 = np.maximum(0.0, sum_overlap_01 - 1.0)
        overlap_area = float(np.sum(overlap_int_01, dtype=np.float64))

        gap_area = 0.0
        gap_int_01 = np.zeros((h, w), dtype=np.float32)

        # 获取全局参考掩码的浮点值
        f_mask_u8 = None
        if full_mask is not None:
            f_mask_u8 = _to_u8_mask(full_mask)
            if f_mask_u8 is not None and f_mask_u8.shape != (h, w):
                f_mask_u8 = np.array(
                    Image.fromarray(f_mask_u8).resize((w, h), Image.BILINEAR),
                    dtype=np.uint8,
                )

            f_mask_u8 = _maybe_binarize_u8(f_mask_u8)

            if f_mask_u8 is not None:
                f_mask_01 = _soft_blur_01(f_mask_u8)
                gap_int_01 = np.maximum(0.0, f_mask_01 - sum_gap_01)
                gap_area = float(np.sum(gap_int_01, dtype=np.float64))

        # 3. 绘制重叠热力图 (Overlap Heatmap)
        # 背景灰度 64, 正常覆盖区域 128, 重叠区域 红色梯度
        overlap_vis = np.zeros((h, w, 3), dtype=np.uint8)
        # 背景：默认深灰
        overlap_vis[:] = [32, 32, 32]

        # 正常覆盖区域 (0.1 < sum_mask <= 1.0): 浅灰
        mask_normal = (sum_overlap_01 > 0.1) & (sum_overlap_01 <= 1.0)
        overlap_vis[mask_normal] = [128, 128, 128]

        # 重叠区域 (sum > 255): 红色梯度
        mask_ov = sum_overlap_01 > 1.0
        if np.any(mask_ov):
            ov_val = overlap_int_01[mask_ov].astype(np.float32)
            r = np.full_like(ov_val, 255)
            g = np.clip(100 - ov_val * 100, 0, 100)
            b = np.clip(100 - ov_val * 100, 0, 100)
            overlap_vis[mask_ov] = np.stack([r, g, b], axis=-1).astype(np.uint8)

        overlap_heatmap_path = (
            mask_path / f"{layer_str}{output_suffix}_overlap_heatmap.png"
        )
        Image.fromarray(overlap_vis).save(overlap_heatmap_path)

        # 4. 绘制空缺热力图 (Gap Heatmap)
        gap_vis = np.zeros((h, w, 3), dtype=np.uint8)
        gap_vis[:] = [32, 32, 32]  # 背景

        if full_mask is not None:
            # 有颜色覆盖的地方设为灰色
            mask_has_color = sum_gap_01 > 0.1
            gap_vis[mask_has_color] = [128, 128, 128]

            # 空缺的地方设为黄色梯度 (255, 255, 0)
            mask_gap = gap_int_01 > 0.05
            if np.any(mask_gap):
                g_val = gap_int_01[mask_gap].astype(np.float32)
                r = np.full_like(g_val, 255)
                g = np.full_like(g_val, 255)
                b = np.clip(100 - g_val * 100, 0, 100)  # 黄色变亮
                gap_vis[mask_gap] = np.stack([r, g, b], axis=-1).astype(np.uint8)

            gap_heatmap_path = mask_path / f"{layer_str}{output_suffix}_gap_heatmap.png"
            Image.fromarray(gap_vis).save(gap_heatmap_path)
            gap_path_str = gap_heatmap_path.name
        else:
            gap_path_str = "N/A (no full_mask)"

        logger.info(
            f"  层 {layer_str}: 重叠面积 = {overlap_area:.2f} px, 空缺面积 = {gap_area:.2f} px"
        )
        logger.info(f"    -> 重叠热力图: {overlap_heatmap_path.name}")
        if full_mask is not None:
            logger.info(f"    -> 空缺热力图: {gap_path_str}")

        report["layers"][layer_str] = {
            "overlap_area": overlap_area,
            "gap_area": gap_area,
            "overlap_heatmap_path": str(overlap_heatmap_path),
            "gap_heatmap_path": str(gap_heatmap_path)
            if full_mask is not None
            else None,
        }
        report["total_overlap_area"] += overlap_area
        report["total_gap_area"] += gap_area

        dt = perf_counter() - t0
        print_ts(f"[信息] {layer_str} 检测完成，用时 {dt:.3f}s")

    logger.info(
        f"检测完成: 总重叠面积 = {report['total_overlap_area']:.2f}, 总空缺面积 = {report['total_gap_area']:.2f}"
    )
    print_ts(f"[信息] 全部层检测完成，用时 {perf_counter() - t_all0:.3f}s")
    return report


if __name__ == "__main__":
    # 更新为 oc_proto 的路径
    check_mask_overlaps(
        r"D:\pama1234\pfp\p-2026-01\OpenColor-02\py_module\prototypes\src\oc_proto\gen_vector\out\02_masks"
    )
