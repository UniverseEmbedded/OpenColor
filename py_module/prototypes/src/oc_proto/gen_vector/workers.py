"""工作进程模块 - 提供并行处理工作函数"""

from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image
from shapely import wkb as shapely_wkb
from shapely.ops import unary_union

from oc_core_02.utils.vtracer_bridge import vectorize_mask_to_mm_polys


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _vectorize_slot_worker(
    *,
    mask_path: str,
    prefix: str,
    slot_name: str,
    vector_backend: str,
    vtracer_params: dict,
    cv2_simplify_mm: float,
    cv2_min_area_px: int,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
    vtracer_dir: str | None,
    use_cpp: bool,
    union_jobs: int,
):
    """矢量化槽位工作进程

    将掩码图像转换为矢量多边形

    Args:
        mask_path: 掩码图像路径
        prefix: 输出前缀
        slot_name: 槽位名称
        vector_backend: 矢量化后端（'vtracer' 或 'cv2'）
        vtracer_params: vtracer参数
        cv2_simplify_mm: OpenCV简化容差（毫米）
        cv2_min_area_px: 最小区域面积（像素）
        board_mm: 板尺寸（毫米）
        pixel_w: 图像宽度（像素）
        pixel_h: 图像高度（像素）
        vtracer_dir: vtracer调试输出目录
        use_cpp: 是否使用C++加速
        union_jobs: 并集操作并行作业数

    Returns:
        (槽位名称, WKB字节, 处理时间)
    """
    t0 = perf_counter()
    mask = np.array(Image.open(mask_path).convert("L"))
    # 掩码像素过少时跳过
    if int(np.count_nonzero(mask)) < 2:
        return slot_name, None, perf_counter() - t0

    debug_dir = Path(vtracer_dir) if vtracer_dir else None
    polys = vectorize_mask_to_mm_polys(
        mask,
        backend=str(vector_backend),
        vtracer_params=vtracer_params,
        cv2_simplify_mm=float(cv2_simplify_mm),
        cv2_min_area_px=int(cv2_min_area_px),
        board_mm=board_mm,
        pixel_w=pixel_w,
        pixel_h=pixel_h,
        debug_dir=debug_dir,
        slot_name=prefix,
        use_cpp=use_cpp,
        progress=False,
        union_jobs=union_jobs,
    )

    if not polys:
        return slot_name, None, perf_counter() - t0

    # 合并所有多边形
    final_poly = unary_union(polys)
    if getattr(final_poly, "is_empty", True):
        return slot_name, None, perf_counter() - t0

    return slot_name, shapely_wkb.dumps(final_poly), perf_counter() - t0


def _rasterize_slot_worker(
    *,
    wkb_bytes: bytes,
    out_dir: str,
    prefix: str,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
):
    """栅格化槽位工作进程

    将WKB多边形栅格化为图像

    Args:
        wkb_bytes: WKB格式的多边形数据
        out_dir: 输出目录
        prefix: 输出前缀
        board_mm: 板尺寸（毫米）
        pixel_w: 输出图像宽度（像素）
        pixel_h: 输出图像高度（像素）

    Returns:
        (前缀, 处理时间)
    """
    t0 = perf_counter()
    try:
        from pathlib import Path
        import numpy as np
        from PIL import Image
        from shapely import wkb as _wkb
        from oc_sdf.sdf_io import save_svg, rasterize_geometry, rasterize_geometry_soft

        poly_dir = Path(out_dir)
        final_poly = _wkb.loads(wkb_bytes)

        # 保存SVG
        save_svg(final_poly, poly_dir / f"{prefix}_poly_final.svg", board_mm, board_mm)
        px_per_mm = float(pixel_w) / float(board_mm)

        # 标准分辨率栅格化
        raster = rasterize_geometry(final_poly, pixel_w, pixel_h, board_mm, px_per_mm)
        if raster is not None:
            Image.fromarray((raster * 255).astype(np.uint8)).save(
                poly_dir / f"{prefix}_poly_raster.png"
            )

        # 4倍超采样栅格化
        raster_4x = rasterize_geometry_soft(
            final_poly,
            pixel_w * 4,
            pixel_h * 4,
            board_mm,
            px_per_mm * 4,
            supersample=1,
        )
        if raster_4x is not None:
            Image.fromarray((raster_4x * 255).astype(np.uint8)).save(
                poly_dir / f"{prefix}_poly_raster_4x.png"
            )

        return prefix, perf_counter() - t0
    except Exception as e:
        logger.error(f"[错误] 栅格化任务失败: {prefix}, 原因={e}")
        import traceback

        traceback.print_exc()
        raise
