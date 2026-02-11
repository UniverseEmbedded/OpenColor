"""
STL与多边形对比模块
用于验证SVG转STL的准确性，通过切片比较和栅格化对比检测几何差异
"""

import os

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("[DEBUG] stl_poly_compare loaded from:", os.path.abspath(__file__))

import numpy as np
from pathlib import Path
from PIL import Image
import json

import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union
from oc_sdf.sdf_io import rasterize_geometry_soft


def _loops_to_evenodd_polygon(loops_2d) -> Polygon:
    """
    将多个闭合环（loops）按照 even-odd 规则重建为带孔洞的多边形

    Args:
        loops_2d: list[np.ndarray], 每个元素是 (N,2) 的闭合环顶点坐标

    Returns:
        shapely Polygon/MultiPolygon，正确处理了孔洞
    """
    rings = []
    for pts in loops_2d:
        if pts is None or len(pts) < 3:
            continue
        p = Polygon(pts)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty:
            continue
        if p.geom_type == "Polygon":
            rings.append(p)
        else:
            rings.extend(
                [g for g in p.geoms if g.geom_type == "Polygon" and g.area > 1e-9]
            )

    if not rings:
        return Polygon()

    # 计算每个环的包围盒、面积和代表点
    boxes = [r.bounds for r in rings]
    areas = [abs(r.area) for r in rings]
    reps = [r.representative_point() for r in rings]
    order = np.argsort(areas)[::-1]  # 按面积从大到小排序

    # 找到每个环的父环（包含它的最小环）
    parent = [None] * len(rings)
    depth = [0] * len(rings)

    for i in order:
        x0, y0, x1, y1 = boxes[i]
        best = None
        best_area = None
        for j in order:
            if j == i or areas[j] <= areas[i]:
                continue
            bx0, by0, bx1, by1 = boxes[j]
            # 快速包围盒检查
            if bx0 <= x0 and by0 <= y0 and bx1 >= x1 and by1 >= y1:
                if rings[j].contains(reps[i]):
                    if best_area is None or areas[j] < best_area:
                        best = j
                        best_area = areas[j]
        parent[i] = best

    # 计算每个环的嵌套深度
    for i in range(len(rings)):
        d = 0
        p = parent[i]
        while p is not None:
            d += 1
            p = parent[p]
        depth[i] = d

    # 偶数深度的是外壳（shells），奇数深度的是孔洞（holes）
    shells = [i for i, d in enumerate(depth) if d % 2 == 0]
    holes_map = {s: [] for s in shells}

    # 奇数深度且父环是偶数深度的，是孔洞
    for i in range(len(rings)):
        p = parent[i]
        if p is not None and (depth[i] % 2 == 1) and (depth[p] % 2 == 0):
            holes_map[p].append(i)

    # 构建带孔洞的多边形
    polys = []
    for s in shells:
        shell = rings[s]
        holes = [list(rings[h].exterior.coords) for h in holes_map[s]]
        poly = Polygon(shell.exterior.coords, holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        if poly.geom_type == "Polygon":
            polys.append(poly)
        else:
            polys.extend([g for g in poly.geoms if g.area > 1e-9])

    if not polys:
        return Polygon()
    return unary_union(polys)


def load_stl_and_project_to_2d(stl_path: Path, layer_z_mm: float) -> Polygon:
    """
    加载STL文件，在指定Z高度切片，并投影到2D平面

    【修复】使用 even-odd 规则正确处理孔洞，避免把孔洞填实
    """
    mesh = trimesh.load_mesh(stl_path)

    slice_result = mesh.section(plane_origin=[0, 0, layer_z_mm], plane_normal=[0, 0, 1])
    if slice_result is None:
        return Polygon()

    slice_2d, transform_matrix = slice_result.to_planar()
    if slice_2d is None:
        return Polygon()

    # 使用 discrete loops，然后转回世界坐标XY
    loops_world = []
    for loop_local in slice_2d.discrete:
        if loop_local is None or len(loop_local) < 3:
            continue
        ones = np.ones((loop_local.shape[0], 1))
        coords_h = np.hstack([loop_local, np.zeros((loop_local.shape[0], 1)), ones])
        coords_3d_h = (transform_matrix @ coords_h.T).T
        xy = coords_3d_h[:, :2] / coords_3d_h[:, 3:4]
        loops_world.append(xy)

    return _loops_to_evenodd_polygon(loops_world)


def stl_to_bitmap(
    stl_path: Path, layer_z_mm: float, pixel_w: int, pixel_h: int, board_mm: float
) -> np.ndarray:
    """
    将STL文件的指定层转换为位图
    """
    poly_2d = load_stl_and_project_to_2d(stl_path, layer_z_mm)

    if poly_2d.is_empty:
        return np.zeros((pixel_h, pixel_w), dtype=np.float32)

    px_per_mm = float(pixel_w) / board_mm
    bitmap = rasterize_geometry_soft(poly_2d, pixel_w, pixel_h, board_mm, px_per_mm)

    return bitmap


def extract_slot_mask_from_preview(
    preview_image: np.ndarray, slot_rgb: tuple, color_tolerance: int = 30
) -> np.ndarray:
    """
    从层预览图中提取指定色块的掩码
    """
    h, w = preview_image.shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)

    for i in range(3):
        mask += (
            np.abs(preview_image[:, :, i].astype(np.float32) - slot_rgb[i])
            < color_tolerance
        ).astype(np.float32)

    # 至少2个通道匹配
    return (mask >= 2).astype(np.float32)


def compare_bitmaps(
    bitmap_stl: np.ndarray, bitmap_poly: np.ndarray, slot_name: str, layer: int
) -> dict:
    """
    对比两个位图，返回统计信息
    """
    if bitmap_stl.shape != bitmap_poly.shape:
        raise ValueError(f"位图形状不匹配: {bitmap_stl.shape} vs {bitmap_poly.shape}")

    diff = bitmap_stl - bitmap_poly
    abs_diff = np.abs(diff)

    total_pixels = bitmap_stl.size
    diff_pixels = np.count_nonzero(abs_diff > 0.01)
    diff_ratio = diff_pixels / total_pixels if total_pixels > 0 else 0

    max_diff = np.max(abs_diff) if total_pixels > 0 else 0
    mean_diff = np.mean(abs_diff) if total_pixels > 0 else 0

    # STL有但Poly没有的像素
    stl_extra = np.clip(bitmap_stl - bitmap_poly, 0, 1)
    stl_extra_pixels = np.count_nonzero(stl_extra > 0.01)

    # Poly有但STL没有的像素
    stl_missing = np.clip(bitmap_poly - bitmap_stl, 0, 1)
    stl_missing_pixels = np.count_nonzero(stl_missing > 0.01)

    return {
        "slot_name": slot_name,
        "layer": layer,
        "total_pixels": int(total_pixels),
        "diff_pixels": int(diff_pixels),
        "diff_ratio": float(diff_ratio),
        "max_diff": float(max_diff),
        "mean_diff": float(mean_diff),
        "stl_extra_pixels": int(stl_extra_pixels),
        "stl_missing_pixels": int(stl_missing_pixels),
    }


def create_diff_image(bitmap_stl: np.ndarray, bitmap_poly: np.ndarray) -> np.ndarray:
    """
    创建彩色差异图
    红色: STL有但Poly没有
    蓝色: Poly有但STL没有
    绿色: 两者都有
    """
    h, w = bitmap_stl.shape
    diff_image = np.zeros((h, w, 3), dtype=np.uint8)

    stl_mask = (bitmap_stl > 0.5).astype(np.uint8)
    poly_mask = (bitmap_poly > 0.5).astype(np.uint8)

    # 红色: STL有但Poly没有
    diff_image[:, :, 0] = ((stl_mask - poly_mask) > 0) * 255
    # 蓝色: Poly有但STL没有
    diff_image[:, :, 2] = ((poly_mask - stl_mask) > 0) * 255
    # 绿色: 两者都有
    both_mask = (stl_mask & poly_mask) * 128
    diff_image[:, :, 1] = both_mask

    return diff_image


def run_stl_poly_comparison(
    export_dir: Path,
    poly_dir: Path,
    manifest: dict,
    stl_files: list,
    slot_names: list,
    slot_preview_rgb: dict,
    compare_root_dir: Path = None,
) -> dict:
    """
    运行STL与多边形预览图的对比
    使用单色栅格图进行对比（而不是从8色预览图中提取）

    Args:
        export_dir: STL导出目录
        poly_dir: 多边形预览图目录
        manifest: 配置manifest
        stl_files: STL文件路径列表
        slot_names: 色块名称列表
        slot_preview_rgb: 色块颜色映射
        compare_root_dir: 可选的对比输出根目录

    Returns:
        对比结果报告
    """
    board_mm = manifest.get("board_mm", 60.0)
    n_layers = manifest.get("n_layers", 5)
    layer_height_mm = manifest.get("layer_height_mm", 0.12)

    # 创建对比输出目录（强制清理旧产物）
    compare_dir = (
        compare_root_dir if compare_root_dir else (export_dir / "07_stl_poly_compare")
    )
    if compare_dir.exists():
        import shutil

        shutil.rmtree(compare_dir)
    compare_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"\n正在执行STL与多边形预览图对比...")
    logger.info(f"输出目录: {compare_dir}")
    logger.info(f"[清理] 已删除旧对比目录，确保干净重建")

    all_stats = []
    total_diff_pixels = 0
    total_pixels = 0

    for stl_path in stl_files:
        slot_name = stl_path.stem.replace("model_ExportSystem_", "")
        if slot_name not in slot_names:
            continue

        for layer in range(n_layers):
            layer_z_mm = layer * layer_height_mm + layer_height_mm / 2

            # 加载该色块该层的单色栅格图（4x分辨率）
            prefix = f"L{layer:02d}_{slot_name}"
            raster_path = poly_dir / f"{prefix}_poly_raster_4x.png"

            if not raster_path.exists():
                logger.warning(f"  警告: 找不到栅格图 {raster_path}")
                continue

            # 读取单色栅格图并归一化到0-1
            poly_mask = (
                np.array(Image.open(raster_path).convert("L"), dtype=np.float32) / 255.0
            )

            target_h, target_w = poly_mask.shape

            # 将STL转换为位图
            try:
                stl_bitmap = stl_to_bitmap(
                    stl_path, layer_z_mm, target_w, target_h, board_mm
                )
            except Exception as e:
                logger.error(f"  错误: STL切片失败 {slot_name} L{layer}: {e}")
                continue

            # 对比（主truth：poly_raster_4x.png）
            stats = compare_bitmaps(stl_bitmap, poly_mask, slot_name, layer)
            all_stats.append(stats)

            total_diff_pixels += stats["diff_pixels"]
            total_pixels += stats["total_pixels"]

            # 【双truth对比】从SVG poly_final栅格化作为第二truth
            svg_path = poly_dir / f"{prefix}_poly_final.svg"
            poly_mask_from_svg = None
            if svg_path.exists():
                try:
                    from oc_sdf.sdf_io import load_svg_polygons, rasterize_geometry_soft

                    polys = load_svg_polygons(svg_path)
                    if polys:
                        # 合并所有多边形
                        from shapely.ops import unary_union

                        merged_poly = unary_union(polys)
                        if merged_poly.is_empty:
                            logger.warning(f"    [警告] SVG合并后多边形为空")
                        else:
                            # 计算参数
                            px_per_mm = target_w / board_mm
                            poly_mask_from_svg = rasterize_geometry_soft(
                                merged_poly,
                                width_px=target_w,
                                height_px=target_h,
                                height_mm=board_mm,
                                px_per_mm=px_per_mm,
                                supersample=1,  # 已经是4x了，不需要再supersample
                            )
                            if poly_mask_from_svg is None:
                                logger.warning(f"    [警告] SVG栅格化返回None")
                            else:
                                # 对比SVG truth
                                stats_svg = compare_bitmaps(
                                    stl_bitmap, poly_mask_from_svg, slot_name, layer
                                )
                                # 如果差异显著不同，打印警告
                                if (
                                    abs(stats_svg["diff_ratio"] - stats["diff_ratio"])
                                    > 0.01
                                ):
                                    logger.warning(
                                        f"    [双truth警告] raster差异={stats['diff_ratio'] * 100:.2f}%, "
                                        f"SVG差异={stats_svg['diff_ratio'] * 100:.2f}%"
                                    )
                except Exception as e:
                    import traceback

                    logger.error(f"    [警告] SVG栅格化失败: {e}")
                    traceback.print_exc()

            # 保存差异图
            diff_img = create_diff_image(stl_bitmap, poly_mask)
            diff_path = compare_dir / f"{slot_name}_L{layer:02d}_diff.png"
            Image.fromarray(diff_img).save(diff_path)

            # 保存单独的位图
            Image.fromarray((stl_bitmap * 255).astype(np.uint8)).save(
                compare_dir / f"{slot_name}_L{layer:02d}_stl.png"
            )
            Image.fromarray((poly_mask * 255).astype(np.uint8)).save(
                compare_dir / f"{slot_name}_L{layer:02d}_poly.png"
            )

            # 如果有SVG truth，也保存对比
            if poly_mask_from_svg is not None:
                diff_img_svg = create_diff_image(stl_bitmap, poly_mask_from_svg)
                Image.fromarray(diff_img_svg).save(
                    compare_dir / f"{slot_name}_L{layer:02d}_diff_from_svg.png"
                )
                Image.fromarray((poly_mask_from_svg * 255).astype(np.uint8)).save(
                    compare_dir / f"{slot_name}_L{layer:02d}_poly_from_svg.png"
                )

            # 打印所有层的对比结果（不管差异大小）
            logger.info(
                f"  {slot_name} L{layer}: 差异 {stats['diff_ratio'] * 100:.2f}% "
                f"(多{stats['stl_extra_pixels']}, 缺{stats['stl_missing_pixels']})"
            )

    # 生成汇总报告
    overall_diff_ratio = total_diff_pixels / total_pixels if total_pixels > 0 else 0

    report = {
        "summary": {
            "total_pixels": total_pixels,
            "diff_pixels": total_diff_pixels,
            "diff_ratio": overall_diff_ratio,
            "diff_percentage": overall_diff_ratio * 100,
        },
        "details": all_stats,
    }

    # 保存报告
    report_path = compare_dir / "comparison_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"\nSTL与多边形对比完成:")
    logger.info(
        f"  总体差异: {total_diff_pixels}/{total_pixels} 像素 ({overall_diff_ratio * 100:.2f}%)"
    )
    logger.info(f"  报告已保存: {report_path}")

    if overall_diff_ratio > 0.05:
        logger.warning(f"  [警告] 差异较大，建议检查SVG转STL过程")
    elif overall_diff_ratio > 0.01:
        logger.info(f"  [提示] 存在轻微差异，可能在可接受范围内")
    else:
        logger.info(f"  [通过] 差异很小，STL与多边形匹配良好")

    return report
