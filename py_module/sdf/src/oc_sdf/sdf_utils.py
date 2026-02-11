from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Any, TYPE_CHECKING, Tuple

import numpy as np
import trimesh
from PIL import Image, ImageFilter
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union

from oc_core_02.core.mesh_export import VoxelGrid, voxel_grid_to_mesh
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


import vtracer

HAS_VTRACER = True

import cv2

HAS_CV2 = True


def geom_is_empty(g: Any) -> bool:
    try:
        return g is None or g.is_empty
    except Exception:
        return True


def filter_small_polys(geom: Any, min_area_mm2: float) -> Any:
    """移除过小的碎多边形，降低切片时出现“椒盐杂点/碎块”的概率。"""
    if geom_is_empty(geom):
        return geom
    polys: List[Polygon] = []

    def _collect(g: Any) -> None:
        if isinstance(g, Polygon):
            polys.append(g)
        elif isinstance(g, MultiPolygon):
            polys.extend(list(g.geoms))
        elif hasattr(g, "geoms"):
            for gg in g.geoms:
                _collect(gg)

    _collect(geom)
    kept: List[Polygon] = []
    for p in polys:
        pp = p
        if not pp.is_valid:
            try:
                pp = pp.buffer(0)
            except Exception:
                continue
        if pp.is_empty:
            continue
        if pp.area >= float(min_area_mm2):
            kept.append(pp)
    if not kept:
        return GeometryCollection()
    try:
        return unary_union(kept)
    except Exception:
        return unary_union([p.buffer(0) for p in kept])


def upscale_mask(m: np.ndarray, grid_scale: int) -> np.ndarray:
    if grid_scale <= 1:
        return m
    return np.kron(m, np.ones((grid_scale, grid_scale), dtype=bool))


def pad_mask(m: np.ndarray, pad_px: int) -> np.ndarray:
    if pad_px <= 0:
        return m
    return np.pad(
        m, ((pad_px, pad_px), (pad_px, pad_px)), mode="constant", constant_values=False
    )


def blur_mask(m: np.ndarray, radius: float, return_float: bool = False) -> np.ndarray:
    if radius <= 0:
        return m.astype(np.float32) if return_float else m
    im = Image.fromarray(m.astype(np.uint8) * 255, mode="L")
    im = im.filter(ImageFilter.GaussianBlur(radius=float(radius)))
    arr = np.array(im, dtype=np.float32) / 255.0
    if return_float:
        return arr
    return arr >= 0.5


def prepare_polygon_mask(
    layer_mask: np.ndarray,
    grid_scale: int,
    pad_px: int,
    blur_radius: float,
    already_scaled: bool = False,
    keep_float: bool = False,
) -> Tuple[np.ndarray, int]:
    if already_scaled:
        hi = layer_mask
    else:
        hi = upscale_mask(layer_mask, grid_scale)
    pad_hi = int(pad_px) * int(grid_scale)
    hi = pad_mask(hi, pad_hi)
    hi = blur_mask(hi, blur_radius, return_float=keep_float)
    return hi, pad_hi


def _rings_from_bitmap2svg(
    layer_mask_hi: np.ndarray,
    smooth_sigma: float,
    simplify_eps: float,
    min_area: int,
    min_hole_area: int,
    open_radius: int,
    close_radius: int,
) -> List[np.ndarray]:
    return []


def _rings_from_cv2(layer_mask_hi: np.ndarray) -> List[np.ndarray]:
    """Extract contour rings using OpenCV.

    Notes:
    - Supports both OpenCV 3 (returns 3 values) and OpenCV 4+ (returns 2 values).
    - Handles float masks by thresholding at 0.5 before conversion to uint8.
    """
    if not HAS_CV2:
        return []
    # Normalize to binary uint8 {0,255}
    if np.issubdtype(layer_mask_hi.dtype, np.floating):
        mask_u8 = (layer_mask_hi >= 0.5).astype(np.uint8) * 255
    else:
        mask_u8 = layer_mask_hi.astype(np.uint8)
        if mask_u8.max() <= 1:
            mask_u8 = mask_u8 * 255
    try:
        res = cv2.findContours(mask_u8, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if len(res) == 3:
            _img, contours, hierarchy = res
        else:
            contours, hierarchy = res
    except Exception as e:
        logger.warning("cv2 轮廓提取失败: {}", e)
        return []
    rings: List[np.ndarray] = []
    for c in contours:
        if c is None:
            continue
        arr = np.squeeze(c, axis=1).astype(np.float32)
        if arr.shape[0] < 3:
            continue
        rings.append(arr)
    return rings


def _parse_svg_points(points_str: str) -> List[np.ndarray]:
    nums = re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", points_str or "")
    if len(nums) < 6:
        return []
    pts = []
    for i in range(0, len(nums) - 1, 2):
        try:
            pts.append((float(nums[i]), float(nums[i + 1])))
        except Exception as e:
            logger.warning("SVG 点解析失败: {}", e)
            return []
    arr = np.array(pts, dtype=np.float32)
    if arr.ndim == 2 and arr.shape[1] == 2 and len(arr) >= 3:
        return [arr]
    return []


def _parse_path_d_simple(d: str) -> List[np.ndarray]:
    """简单的 SVG path d 解析，支持 M, L, Z, C, Q, H, V 命令。"""
    # 增加对更多命令的支持
    tokens = re.findall(r"[MLZCQHVmlzcqhv]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", d or "")
    rings: List[np.ndarray] = []
    current: List[Tuple[float, float]] = []
    cmd = None
    i = 0

    last_x, last_y = 0.0, 0.0

    while i < len(tokens):
        t = tokens[i]
        if re.fullmatch(r"[MLZCQHVmlzcqhv]", t):
            cmd = t
            i += 1
            if cmd.upper() == "Z":
                if len(current) >= 3:
                    rings.append(np.array(current, dtype=np.float32))
                current = []
                # Z 不更新 last_x, last_y，通常回到起点，但这里简单处理
            continue

        # 这是一个坐标数字
        if cmd is None:
            i += 1
            continue
        upper_cmd = cmd.upper()
        is_rel = cmd.islower()
        if upper_cmd == "M":
            if len(current) >= 3:
                rings.append(np.array(current, dtype=np.float32))
            current = []
            if i + 1 >= len(tokens):
                break
            x = float(tokens[i])
            y = float(tokens[i + 1])
            if is_rel:
                x += last_x
                y += last_y
            last_x = x
            last_y = y
            current.append((last_x, last_y))
            i += 2
            # M 之后如果还有数字，隐含为 L
            cmd = "L" if cmd == "M" else "l"
        elif upper_cmd == "L":
            if i + 1 >= len(tokens):
                break
            x = float(tokens[i])
            y = float(tokens[i + 1])
            if is_rel:
                x += last_x
                y += last_y
            last_x = x
            last_y = y
            current.append((last_x, last_y))
            i += 2
        elif upper_cmd == "H":
            x = float(tokens[i])
            if is_rel:
                x += last_x
            last_x = x
            current.append((last_x, last_y))
            i += 1
        elif upper_cmd == "V":
            y = float(tokens[i])
            if is_rel:
                y += last_y
            last_y = y
            current.append((last_x, last_y))
            i += 1
        elif upper_cmd == "C":
            # Cubic Bezier: x1 y1 x2 y2 x y
            if i + 5 >= len(tokens):
                break
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x, y = float(tokens[i + 4]), float(tokens[i + 5])
            if is_rel:
                x1 += last_x
                y1 += last_y
                x2 += last_x
                y2 += last_y
                x += last_x
                y += last_y

            # 简单线性化：采样 4 个点
            p0 = (last_x, last_y)
            p1 = (x1, y1)
            p2 = (x2, y2)
            p3 = (x, y)
            for t_val in [0.33, 0.66, 1.0]:
                inv_t = 1.0 - t_val
                bx = (
                    inv_t**3 * p0[0]
                    + 3 * inv_t**2 * t_val * p1[0]
                    + 3 * inv_t * t_val**2 * p2[0]
                    + t_val**3 * p3[0]
                )
                by = (
                    inv_t**3 * p0[1]
                    + 3 * inv_t**2 * t_val * p1[1]
                    + 3 * inv_t * t_val**2 * p2[1]
                    + t_val**3 * p3[1]
                )
                current.append((bx, by))

            last_x, last_y = x, y
            i += 6
        elif upper_cmd == "Q":
            # Quadratic Bezier: x1 y1 x y
            if i + 3 >= len(tokens):
                break
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x, y = float(tokens[i + 2]), float(tokens[i + 3])
            if is_rel:
                x1 += last_x
                y1 += last_y
                x += last_x
                y += last_y

            # 简单线性化：采样 3 个点
            p0 = (last_x, last_y)
            p1 = (x1, y1)
            p2 = (x, y)
            for t_val in [0.5, 1.0]:
                inv_t = 1.0 - t_val
                bx = inv_t**2 * p0[0] + 2 * inv_t * t_val * p1[0] + t_val**2 * p2[0]
                by = inv_t**2 * p0[1] + 2 * inv_t * t_val * p1[1] + t_val**2 * p2[1]
                current.append((bx, by))

            last_x, last_y = x, y
            i += 4
        else:
            # 未知命令，跳过一个 token 避免死循环
            i += 1

    if len(current) >= 3:
        rings.append(np.array(current, dtype=np.float32))
    return rings


def _rings_from_svg_text(svg_text: str) -> List[np.ndarray]:
    try:
        root = ET.fromstring(svg_text)
    except Exception as e:
        logger.warning("SVG 解析失败: {}", e)
        return []
    rings: List[np.ndarray] = []

    def parse_translate(transform_str: Optional[str]) -> Tuple[float, float]:
        if not transform_str:
            return 0.0, 0.0
        match = re.search(r"translate\(([-\d.]+)[,\s]*([-\d.]*)\)", transform_str)
        if match:
            tx = float(match.group(1))
            ty = float(match.group(2)) if match.group(2) else 0.0
            return tx, ty
        return 0.0, 0.0

    for elem in root.iter():
        tag = elem.tag
        if not isinstance(tag, str):
            continue

        elem_rings = []
        tx, ty = 0.0, 0.0

        if tag.endswith("path"):
            d = elem.get("d")
            transform = elem.get("transform")
            tx, ty = parse_translate(transform)
            elem_rings = _parse_path_d_simple(d or "")
        elif tag.endswith("polygon"):
            points = elem.get("points")
            transform = elem.get("transform")
            tx, ty = parse_translate(transform)
            elem_rings = _parse_svg_points(points or "")

        for r in elem_rings:
            if r.size > 0:
                r[:, 0] += tx
                r[:, 1] += ty
                rings.append(r)
    return rings


def _rings_from_vtracer(
    layer_mask_hi: np.ndarray,
    vtracer_mode: str,
    vtracer_filter_speckle: int,
    vtracer_segment_length: int,
    vtracer_corner_threshold: int,
    debug_dir: Optional[Path] = None,
    slot_name: str = "default",
) -> List[np.ndarray]:
    if not HAS_VTRACER:
        return []
    if vtracer is None:
        logger.warning("vtracer 模块不可用")
        return []
    convert_func = None
    if hasattr(vtracer, "convert_image_to_svg_py"):
        convert_func = vtracer.convert_image_to_svg_py
    elif hasattr(vtracer, "convert_image_to_svg"):
        convert_func = vtracer.convert_image_to_svg
    if convert_func is None:
        logger.warning("vtracer 接口不可用")
        return []
    with tempfile.TemporaryDirectory() as tmpdir:
        inp = os.path.join(tmpdir, "mask.png")
        out = os.path.join(tmpdir, "out.svg")
        if np.issubdtype(layer_mask_hi.dtype, np.floating):
            mask_u8 = (layer_mask_hi >= 0.5).astype(np.uint8) * 255
        else:
            mask_u8 = layer_mask_hi.astype(np.uint8)
            if mask_u8.max() <= 1:
                mask_u8 = mask_u8 * 255
        try:
            Image.fromarray(mask_u8, mode="L").save(inp)
            if debug_dir:
                import shutil

                shutil.copy2(inp, debug_dir / f"{slot_name}_vtracer_input.png")
        except Exception as e:
            logger.warning("vtracer 输入写入失败: {}", e)
            return []
        try:
            convert_func(
                inp,
                out,
                colormode="binary",
                mode=str(vtracer_mode),
                filter_speckle=int(vtracer_filter_speckle),
                corner_threshold=int(vtracer_corner_threshold),
                length_threshold=float(vtracer_segment_length),
            )
            if debug_dir:
                import shutil

                shutil.copy2(out, debug_dir / f"{slot_name}_vtracer_tool.svg")

                # 获取像素域 bbox 报告 (为了对齐 18.md 的要求)
                try:
                    import json
                    from oc_core_02.utils.vtracer_bridge import (
                        parse_translate,
                        bake_vtracer_svg,
                        get_rings_bbox,
                    )

                    svg_text_raw = Path(out).read_text(encoding="utf-8")

                    # 解析原始 rings (不含 transform)
                    root_elem = ET.fromstring(svg_text_raw)
                    raw_rings = []
                    tx, ty = 0.0, 0.0
                    for elem in root_elem.iter():
                        tag = elem.tag
                        if not isinstance(tag, str):
                            continue
                        if tag.endswith("path"):
                            raw_rings.extend(_parse_path_d_simple(elem.get("d") or ""))
                            tx, ty = parse_translate(elem.get("transform"))
                        elif tag.endswith("polygon"):
                            raw_rings.extend(
                                _parse_svg_points(elem.get("points") or "")
                            )
                            tx, ty = parse_translate(elem.get("transform"))

                    d_bbox_px = get_rings_bbox(raw_rings)
                    baked_rings = bake_vtracer_svg(svg_text_raw)
                    final_bbox_px = get_rings_bbox(baked_rings)

                    report = {
                        "input": {
                            "W": int(mask_u8.shape[1]),
                            "H": int(mask_u8.shape[0]),
                        },
                        "tool_svg": {
                            "d_bbox_px": d_bbox_px,
                            "transform_translate_px": [tx, ty],
                            "final_bbox_px": final_bbox_px,
                        },
                        "info": "generated by sdf_utils.mask_to_rings",
                    }
                    (debug_dir / f"{slot_name}_bbox_report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                except Exception as e:
                    logger.warning("BBox report 生成失败: {}", e)

        except Exception as e:
            logger.warning("vtracer 生成 SVG 失败: {}", e)
            return []
        if not os.path.exists(out):
            logger.warning("vtracer 输出 SVG 不存在")
            return []
        try:
            svg_text = Path(out).read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("vtracer 输出 SVG 读取失败: {}", e)
            return []
        rings = _rings_from_svg_text(svg_text)
        if not rings:
            logger.info("vtracer 输出 SVG 解析为空")
        return rings


def mask_to_rings(
    layer_mask_hi: np.ndarray,
    *,
    backend: str,
    smooth_sigma: float,
    simplify_eps: float,
    min_area: int,
    min_hole_area: int,
    open_radius: int,
    close_radius: int,
    vtracer_mode: str = "polygon",
    vtracer_filter_speckle: int = 4,
    vtracer_segment_length: int = 4,
    vtracer_corner_threshold: int = 60,
    debug_dir: Optional[Path] = None,
    slot_name: str = "default",
) -> Tuple[List[np.ndarray], str]:
    backend_norm = (backend or "auto").lower()
    if backend_norm not in {"auto", "bitmap2svg", "vtracer", "cv2"}:
        logger.warning("未知轮廓后端: {}，已回退到 auto", backend_norm)
        backend_norm = "auto"

    if backend_norm == "auto":
        order = ["bitmap2svg", "vtracer", "cv2"]
    elif backend_norm == "bitmap2svg":
        order = ["bitmap2svg", "cv2"]
    elif backend_norm == "vtracer":
        order = ["vtracer", "bitmap2svg", "cv2"]
    else:
        order = ["cv2", "bitmap2svg"]

    for b in order:
        if b == "bitmap2svg":
            logger.info("bitmap2svg 不可用，尝试回退")
        if b == "vtracer":
            rings = _rings_from_vtracer(
                layer_mask_hi,
                vtracer_mode=vtracer_mode,
                vtracer_filter_speckle=vtracer_filter_speckle,
                vtracer_segment_length=vtracer_segment_length,
                vtracer_corner_threshold=vtracer_corner_threshold,
                debug_dir=debug_dir,
                slot_name=slot_name,
            )
        else:
            rings = _rings_from_cv2(layer_mask_hi)
        if rings:
            return rings, b
    return [], "none"


def rings_to_polys(
    rings: List[np.ndarray],
    h: int,
    grid_scale: int,
    nozzle_width_mm: float,
    pad_hi: int,
) -> List[Polygon]:
    """将 bitmap2svg rings 转为物理坐标多边形（并自动处理方向/坐标系）。

    rings 的坐标系：x 向右，y 向下，单位为像素。
    物理坐标系：x 向右，y 向上（通过 (h-1-y) 翻转）。
    若使用了 grid_scale，则 ring 坐标需除以 grid_scale。
    """
    out: List[Polygon] = []
    if not rings:
        return out
    H_hi = h
    for r in rings:
        if len(r) < 3:
            continue
        phys_r = [
            (
                (float(rx) - float(pad_hi)) / grid_scale * nozzle_width_mm,
                (float(H_hi) - (float(ry) - float(pad_hi)))
                / grid_scale
                * nozzle_width_mm,
            )
            for rx, ry in r
        ]
        p = Polygon(phys_r)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            out.append(p)
    return out


def build_clip_poly(
    layer_mask: np.ndarray,
    grid_scale: int,
    h: int,
    nozzle_width_mm: float,
    pad_px: int,
    already_scaled: bool = False,
) -> Optional[Polygon]:
    """构建该层该颜色的“精确裁剪边界”。

    我们用不平滑、不简化的轮廓来做 clip，确保 SDF 平滑不会越界到别的颜色区域。
    """
    lm_hi, pad_hi = prepare_polygon_mask(
        layer_mask, grid_scale, pad_px, 0.0, already_scaled
    )
    base_rings, _ = mask_to_rings(
        lm_hi,
        backend="cv2",
        smooth_sigma=0.0,
        simplify_eps=0.0,
        min_area=1,
        min_hole_area=1,
        open_radius=0,
        close_radius=0,
    )
    base_polys = rings_to_polys(base_rings, h, grid_scale, nozzle_width_mm, pad_hi)
    if not base_polys:
        return None
    try:
        u = unary_union(base_polys)
    except Exception:
        u = unary_union([p.buffer(0) for p in base_polys])
    if u.is_empty:
        return None
    # 只返回 Polygon/MultiPolygon 的 union 结果（用于 intersection）
    return u


def fallback_extrude_from_pixels(
    layer_mask: np.ndarray, z: int, nozzle_width_mm: float, layer_height_mm: float
) -> Optional[trimesh.Trimesh]:
    """兜底：当 SDF 多边形化失败时，直接将该层像素 mask 挤出成薄片（可能丑，但绝不留洞）。"""
    if not np.any(layer_mask):
        return None
    # 将 2D mask 作为单层体素网格 (1, H, W)
    vol = layer_mask[None, :, :]
    grid = VoxelGrid(
        volume=vol, voxel_size=(nozzle_width_mm, nozzle_width_mm, layer_height_mm)
    )
    try:
        m = voxel_grid_to_mesh(grid)
    except Exception as e:
        logger.warning("Fallback voxel mesh failed (layer={}): {}", z, e)
        return None
    # voxel_grid_to_mesh 生成的 z 从 0 开始，平移到对应层
    m.apply_translation([0, 0, z * layer_height_mm])
    return m
