"""
证据级校验模块
对Green L02、Magenta L02、Yellow L01三个问题层进行证据级校验
通过STL截面重建和面积对比判定问题来源
"""

import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from shapely.geometry import Polygon


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 添加lumina到路径
sys.path.insert(0, str(Path(__file__).parents[5] / "LumenBoardTool" / "src"))
from oc_sdf.sdf_io import rasterize_geometry_soft


def load_svg_and_get_area(svg_path: Path) -> float:
    """从SVG解析多边形并计算面积"""
    try:
        from oc_sdf.sdf_io import load_svg_polygons

        polys = load_svg_polygons(svg_path)
        if not polys:
            return 0.0
        total_area = 0.0
        for p in polys:
            if p.is_valid:
                total_area += p.area
        return total_area
    except Exception as e:
        logger.error(f"  [错误] 解析SVG失败: {e}")
        return 0.0


def loops_to_evenodd_polygon(loops_2d) -> Polygon:
    """将多个闭合环按照even-odd规则重建为带孔洞的多边形"""
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

    # 按面积排序（从大到小）
    rings.sort(key=lambda r: r.area, reverse=True)

    # XOR累积实现even-odd
    result = rings[0]
    for ring in rings[1:]:
        result = result.symmetric_difference(ring)

    return result


def rebuild_stl_to_2d(
    stl_path: Path, layer_z_mm: float, board_mm: float, pixel_size: int
) -> tuple:
    """
    STL截面 → loops → even-odd重建 → 2D raster

    Returns:
        (rebuild_poly, rebuild_img, area_mm2)
    """
    if not stl_path.exists():
        return None, None, 0.0

    # 加载STL
    mesh = trimesh.load_mesh(stl_path)

    # 截面
    slice_result = mesh.section(plane_origin=[0, 0, layer_z_mm], plane_normal=[0, 0, 1])
    if slice_result is None:
        return None, None, 0.0

    slice_2d, transform_matrix = slice_result.to_planar()
    if slice_2d is None:
        return None, None, 0.0

    # 使用discrete获取闭合loops
    loops_world = []
    for loop_local in slice_2d.discrete:
        if loop_local is None or len(loop_local) < 3:
            continue
        ones = np.ones((loop_local.shape[0], 1))
        coords_h = np.hstack([loop_local, np.zeros((loop_local.shape[0], 1)), ones])
        coords_3d_h = (transform_matrix @ coords_h.T).T
        xy = coords_3d_h[:, :2] / coords_3d_h[:, 3:4]
        loops_world.append(xy)

    # even-odd重建
    rebuild_poly = loops_to_evenodd_polygon(loops_world)
    if rebuild_poly.is_empty:
        return None, None, 0.0

    # 栅格化
    try:
        rebuild_img = rasterize_geometry_soft(
            rebuild_poly,
            board_mm=board_mm,
            pixel_size=pixel_size,
            blur_radius=0.0,
            closing_radius=0.0,
        )
    except Exception as e:
        logger.error(f"  [错误] 栅格化失败: {e}")
        rebuild_img = None

    area_mm2 = rebuild_poly.area if rebuild_poly.is_valid else 0.0

    return rebuild_poly, rebuild_img, area_mm2


def main():
    logger.info("=" * 60)
    logger.info("证据级校验：STL截面重建")
    logger.info("=" * 60)

    # 路径
    base_dir = Path(__file__).resolve().parent
    vtracer_out = base_dir.parent / "gen_vector" / "out"
    single_layer_dir = base_dir / "out" / "06_export" / "debug_single_layer"
    output_dir = base_dir / "out" / "06_export" / "07_stl_poly_compare_debug_final"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 参数
    board_mm = 60.06
    pixel_size = 572  # 4x supersample
    layer_height_mm = 0.12

    # 3个问题层
    problem_layers = [
        ("Green", 2),
        ("Magenta", 2),
        ("Yellow", 1),
    ]

    results = []

    for slot_name, layer in problem_layers:
        layer_str = f"L{layer:02d}"
        logger.info(f"\n--- {slot_name} {layer_str} ---")

        # 1. SVG面积
        svg_path = vtracer_out / "04_polys" / f"{layer_str}_{slot_name}_poly_final.svg"
        poly_area = load_svg_and_get_area(svg_path)
        logger.info(f"  SVG面积: {poly_area:.2f} mm²")

        # 2. STL重建
        stl_path = single_layer_dir / f"{layer_str}_{slot_name}.stl"
        z_mm = layer * layer_height_mm + layer_height_mm / 2

        rebuild_poly, rebuild_img, stl_rebuild_area = rebuild_stl_to_2d(
            stl_path, z_mm, board_mm, pixel_size
        )
        logger.info(f"  STL重建面积: {stl_rebuild_area:.2f} mm²")

        # 保存重建图
        if rebuild_img is not None:
            rebuild_img_path = output_dir / f"{slot_name}_{layer_str}_stl_rebuild.png"
            # 转换为uint8保存
            img_uint8 = (rebuild_img * 255).astype(np.uint8)
            Image.fromarray(img_uint8).save(rebuild_img_path)
            logger.info(f"  保存重建图: {rebuild_img_path.name}")

        # 3. 复制现有对比图
        compare_dir = base_dir / "out" / "06_export" / "07_stl_poly_compare"
        for suffix in ["poly.png", "stl.png", "diff.png"]:
            src = compare_dir / f"{slot_name}_{layer_str}_{suffix}"
            if src.exists():
                dst = output_dir / f"{slot_name}_{layer_str}_{suffix}"
                import shutil

                shutil.copy2(src, dst)

        # 4. 计算compare_stl面积（从现有stl.png）
        stl_png_path = compare_dir / f"{slot_name}_{layer_str}_stl.png"
        compare_stl_area = 0.0
        if stl_png_path.exists():
            try:
                img = np.array(Image.open(stl_png_path).convert("L"))
                # 阈值0.5，计算白色像素占比
                compare_stl_area = (img > 127).sum() / img.size * (board_mm**2)
            except Exception as e:
                logger.error(f"  [警告] 计算compare_stl面积失败: {e}")

        # 5. 从report读取diff统计
        report_path = compare_dir / "comparison_report.json"
        diff_pixels = 0
        stl_extra = 0
        stl_missing = 0
        if report_path.exists():
            try:
                with open(report_path) as f:
                    report = json.load(f)
                # 修复：按details列表匹配，不是layer_details字典
                for detail in report.get("details", []):
                    if (
                        detail.get("slot_name") == slot_name
                        and detail.get("layer") == layer
                    ):
                        diff_pixels = detail.get("diff_pixels", 0)
                        stl_extra = detail.get("stl_extra_pixels", 0)
                        stl_missing = detail.get("stl_missing_pixels", 0)
                        break
            except Exception as e:
                logger.error(f"  [警告] 读取report失败: {e}")

        # 保存证据json
        evidence = {
            "slot": slot_name,
            "layer": layer,
            "poly_area_mm2": round(poly_area, 4),
            "stl_rebuild_area_mm2": round(stl_rebuild_area, 4),
            "compare_stl_area_mm2": round(compare_stl_area, 4),
            "diff_pixels": diff_pixels,
            "stl_extra_pixels": stl_extra,
            "stl_missing_pixels": stl_missing,
            "area_diff_percent": round(
                abs(stl_rebuild_area - poly_area) / poly_area * 100, 4
            )
            if poly_area > 0
            else 0,
        }

        evidence_path = output_dir / f"{slot_name}_{layer_str}_evidence.json"
        with open(evidence_path, "w") as f:
            json.dump(evidence, f, indent=2)
        logger.info(f"  保存证据: {evidence_path.name}")

        results.append(evidence)

    # 输出结论
    logger.info("\n" + "=" * 60)
    logger.info("判定结果")
    logger.info("=" * 60)

    for r in results:
        slot = r["slot"]
        layer = r["layer"]
        poly_area = r["poly_area_mm2"]
        rebuild_area = r["stl_rebuild_area_mm2"]
        compare_area = r["compare_stl_area_mm2"]
        area_diff = r["area_diff_percent"]
        missing = r["stl_missing_pixels"]
        extra = r["stl_extra_pixels"]

        logger.info(f"\n{slot} L{layer}:")
        logger.info(f"  SVG面积: {poly_area:.2f} mm²")
        logger.info(f"  STL重建面积: {rebuild_area:.2f} mm² (差异 {area_diff:.2f}%)")
        logger.info(f"  Compare STL面积: {compare_area:.2f} mm²")
        logger.info(f"  差异像素: 多{extra}, 缺{missing}")

        # 判定逻辑
        if area_diff > 2.0:
            logger.info(f"  → [情况1] STL真缺几何 (面积差异 {area_diff:.1f}% > 2%)")
        elif abs(rebuild_area - compare_area) / poly_area > 0.01:
            logger.info(
                f"  → [情况2] 对比图生成有bug (重建面积≈SVG, 但compare面积不同)"
            )
        elif (
            missing > 0 and extra > 0 and abs(missing - extra) / (missing + extra) < 0.3
        ):
            logger.info(f"  → [情况3] 仅AA/采样误差 (对称差异)")
        else:
            logger.info(f"  → [待判定] 需要进一步分析")

    # 保存meta
    meta = {
        "run_time": datetime.now().isoformat(),
        "board_mm": board_mm,
        "pixel_size": pixel_size,
        "layer_height_mm": layer_height_mm,
        "stl_poly_compare_path": str(Path(__file__).resolve()),
        "results": results,
    }
    with open(output_dir / "run_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"\n证据包已保存到: {output_dir}")


if __name__ == "__main__":
    from datetime import datetime

    main()
