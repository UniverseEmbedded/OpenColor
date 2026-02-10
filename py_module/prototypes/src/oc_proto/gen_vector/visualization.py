"""可视化模块 - 提供调试可视化功能

用于生成矢量化和掩码处理过程中的调试图像，包括轮廓、距离场和着色预览。
"""

import traceback
from pathlib import Path

import numpy as np
from PIL import Image

from oc_sdf.sdf_io import save_svg, rasterize_geometry_soft



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _save_debug_total(*, out_dir: Path, z: int, tag: str, geom, board_mm: float, pixel_w: int, pixel_h: int) -> None:
    """保存总轮廓调试信息
    
    保存每层总轮廓的SVG矢量图、栅格化图像和距离场图像，用于调试矢量化过程。
    
    参数:
        out_dir: 输出根目录
        z: 层索引
        tag: 标签名称
        geom: shapely几何体对象
        board_mm: 板尺寸（毫米）
        pixel_w: 像素宽度
        pixel_h: 像素高度
    """
    debug_dir = out_dir / "01_debug_total"
    debug_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"L{z:02d}_{tag}"
    # 保存SVG矢量图
    try:
        save_svg(geom, debug_dir / f"{prefix}_total_contour.svg", float(board_mm), float(board_mm))
    except Exception as e:
        logger.error(f"[警告] 保存总轮廓SVG失败: layer=L{z:02d}, tag={tag}, 原因={e}")
        traceback.print_exc()

    # 4x超采样栅格化
    px_per_mm = float(pixel_w) / float(board_mm)
    try:
        r4 = rasterize_geometry_soft(
            geom,
            int(pixel_w) * 4,
            int(pixel_h) * 4,
            float(board_mm),
            float(px_per_mm) * 4,
            supersample=1,
        )
        if r4 is not None:
            Image.fromarray((r4 * 255).astype(np.uint8)).save(debug_dir / f"{prefix}_total_raster_4x.png")
    except Exception as e:
        logger.error(f"[警告] 保存总轮廓栅格图失败: layer=L{z:02d}, tag={tag}, 原因={e}")
        traceback.print_exc()
        r4 = None

    if r4 is None:
        return

    # 计算并保存有符号距离场(SDF)
    try:
        import cv2

        # 二值化
        bin_u8 = (r4 >= 0.5).astype(np.uint8) * 255
        inv_u8 = (bin_u8 == 0).astype(np.uint8) * 255
        # 计算内外距离变换
        inside = cv2.distanceTransform(bin_u8, cv2.DIST_L2, 3)
        outside = cv2.distanceTransform(inv_u8, cv2.DIST_L2, 3)
        sdf = inside - outside

        # 归一化到0-255范围
        clamp = float(np.percentile(np.abs(sdf), 99.5))
        if not np.isfinite(clamp) or clamp <= 1e-6:
            clamp = 1.0
        clamp = float(min(max(clamp, 8.0), 256.0))

        # 保存有符号距离场
        sdf_u8 = np.clip((sdf / clamp) * 127.0 + 128.0, 0.0, 255.0).astype(np.uint8)
        Image.fromarray(sdf_u8).save(debug_dir / f"{prefix}_total_sdf_signed.png")

        # 保存内部和外部距离场
        inside_u8 = np.clip((inside / clamp) * 255.0, 0.0, 255.0).astype(np.uint8)
        outside_u8 = np.clip((outside / clamp) * 255.0, 0.0, 255.0).astype(np.uint8)
        Image.fromarray(inside_u8).save(debug_dir / f"{prefix}_total_sdf_inside.png")
        Image.fromarray(outside_u8).save(debug_dir / f"{prefix}_total_sdf_outside.png")
    except Exception as e:
        logger.error(f"[警告] 计算或保存距离场失败: layer=L{z:02d}, tag={tag}, 原因={e}")
        traceback.print_exc()


def _save_debug_layer_colored(
    *,
    out_dir: Path,
    mask_dir: Path,
    z: int,
    slot_names: list[str],
    slot_preview_rgb: dict,
    pixel_w: int,
    pixel_h: int,
    layer_polys: dict | None = None,
    board_mm: float | None = None,
) -> None:
    """保存图层着色调试图
    
    将每层的不同槽位用不同颜色渲染，生成着色预览图，支持从掩码或矢量轮廓生成。
    
    参数:
        out_dir: 输出根目录
        mask_dir: 掩码文件目录
        z: 层索引
        slot_names: 槽位名称列表
        slot_preview_rgb: 槽位预览颜色字典
        pixel_w: 像素宽度
        pixel_h: 像素高度
        layer_polys: 可选，层多边形字典，用于4x高质量渲染
        board_mm: 可选，板尺寸，用于4x高质量渲染
    """
    debug_dir = out_dir / "01_debug_total"
    debug_dir.mkdir(parents=True, exist_ok=True)

    # 初始化标签和颜色数组
    best = np.full((int(pixel_h), int(pixel_w)), -1, dtype=np.int16)
    rgb = np.zeros((int(pixel_h), int(pixel_w), 3), dtype=np.uint8)

    # 从掩码文件读取并着色
    for idx, slot_name in enumerate(slot_names):
        mp = mask_dir / f"L{int(z):02d}_{slot_name}_mask.png"
        if not mp.exists():
            continue
        m_u8 = np.array(Image.open(mp).convert("L"), dtype=np.uint8)
        if m_u8.shape[0] != int(pixel_h) or m_u8.shape[1] != int(pixel_w):
            logger.warning(f"[警告] 着色预览mask尺寸不一致，已跳过: {mp.name}, shape={m_u8.shape}, expect={int(pixel_h)}x{int(pixel_w)}")
            continue

        # 只取第一个覆盖该像素的槽位
        take = (m_u8 > 128) & (best < 0)
        if not bool(np.any(take)):
            continue
        best[take] = np.int16(idx)
        c = slot_preview_rgb.get(slot_name)
        if c is None:
            c = [128, 128, 128]
        rgb[take] = np.array(c, dtype=np.uint8)

    # 保存1x预览图
    out_png = debug_dir / f"L{int(z):02d}_colored_masks.png"
    Image.fromarray(rgb).save(out_png)

    # 保存4x高质量预览图
    out_png_4x = debug_dir / f"L{int(z):02d}_colored_masks_4x.png"
    if layer_polys is not None and board_mm is not None:
        try:
            w4 = int(pixel_w) * 4
            h4 = int(pixel_h) * 4
            best4 = np.full((h4, w4), -1, dtype=np.int16)
            rgb4 = np.zeros((h4, w4, 3), dtype=np.uint8)

            px_per_mm_4x = float(w4) / float(board_mm)
            # 从矢量轮廓栅格化
            for idx, slot_name in enumerate(slot_names):
                poly = layer_polys.get(slot_name)
                if poly is None or getattr(poly, "is_empty", True):
                    continue
                m4 = rasterize_geometry_soft(poly, w4, h4, float(board_mm), float(px_per_mm_4x), supersample=1)
                if m4 is None:
                    continue

                take = (np.asarray(m4) >= 0.5) & (best4 < 0)
                if not bool(np.any(take)):
                    continue
                best4[take] = np.int16(idx)
                c = slot_preview_rgb.get(slot_name)
                if c is None:
                    c = [128, 128, 128]
                rgb4[take] = np.asarray(c, dtype=np.uint8)

            Image.fromarray(rgb4).save(out_png_4x)
        except Exception as e:
            logger.error(f"[警告] 保存每层着色位图4x(轮廓栅格化)失败: L{int(z):02d}，原因={e}")
            traceback.print_exc()
            # 回退到简单4x放大
            rgb_4x = np.repeat(np.repeat(rgb, 4, axis=0), 4, axis=1)
            Image.fromarray(rgb_4x).save(out_png_4x)
    else:
        # 简单4x放大
        rgb_4x = np.repeat(np.repeat(rgb, 4, axis=0), 4, axis=1)
        Image.fromarray(rgb_4x).save(out_png_4x)
