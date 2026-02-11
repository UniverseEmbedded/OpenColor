"""
vtracer桥接模块
提供统一的vtracer调用接口，将位图掩码转换为SVG矢量多边形
包含解析、烘焙transform、像素到毫米坐标转换等功能
"""

import concurrent.futures
import json
import os
import re
import shutil
import tempfile
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from time import perf_counter
from typing import List, Tuple, Optional

import cv2
import numpy as np
from PIL import Image
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.ops import unary_union

from oc_core_02.utils.io_utils import print_ts
from oc_core_02.utils.bin_loader import import_cpp_extension
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import vtracer

    HAS_VTRACER = True
except ImportError:
    HAS_VTRACER = False


_CPP_GEOM = None
_CPP_GEOM_TRIED = False
_CPP_UNION_AVG_SEC_PER_RING: float | None = None


try:
    from tqdm import tqdm
except Exception:
    tqdm = None


def _tqdm(it, *, total: int | None = None, desc: str = "", enabled: bool = True):
    if (not enabled) or (tqdm is None):
        return it
    return tqdm(it, total=total, desc=desc, dynamic_ncols=True)


def _loops_to_evenodd_polygon(loops):
    rings = []
    for pts in loops or []:
        if pts is None:
            continue
        arr = np.asarray(pts, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[0] < 3 or arr.shape[1] != 2:
            continue
        p = Polygon(arr)
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

    result = rings[0]
    for r in rings[1:]:
        result = result.symmetric_difference(r)
    return result


def _cpp_union_all_loops(loops, scale: float):
    out_loops = _CPP_GEOM.clipper_union_all_nogil(loops, scale=scale)
    return out_loops


def _cpp_union_all_polygons(loops, scale: float):
    out_polys = _CPP_GEOM.clipper_union_all_to_polygons_nogil(loops, scale=scale)
    return out_polys


def _try_cpp_union_all(loops, scale: float, union_jobs: int = 1):
    global _CPP_GEOM, _CPP_GEOM_TRIED
    if not _CPP_GEOM_TRIED:
        _CPP_GEOM_TRIED = True
        try:
            _CPP_GEOM = import_cpp_extension("opencolor_geometry")
        except Exception as e:
            logger.error("导入 C++几何模块失败: {}", e)
            _CPP_GEOM = None

    if _CPP_GEOM is None:
        raise RuntimeError("已启用 C++并集，但 opencolor_geometry 不可用")

    try:
        loops = list(loops or [])
        n = len(loops)
        jobs = int(union_jobs) if union_jobs is not None else 1
        if jobs < 1:
            jobs = 1

        has_poly_api = hasattr(_CPP_GEOM, "clipper_union_all_to_polygons_nogil")

        if has_poly_api:
            out_polys = None
            if jobs >= 2 and n >= 1500:
                jobs = min(jobs, n)
                chunk_size = (n + jobs - 1) // jobs
                chunks = [loops[i : i + chunk_size] for i in range(0, n, chunk_size)]
                partial_loops = []
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
                        futs = [
                            ex.submit(_cpp_union_all_loops, c, scale)
                            for c in chunks
                            if c
                        ]
                        for f in concurrent.futures.as_completed(futs):
                            partial_loops.extend(f.result() or [])
                    out_polys = _cpp_union_all_polygons(partial_loops, scale)
                except Exception as e:
                    logger.warning("C++并集分块并行失败，将回退到单次并集。原因={}", e)
                    traceback.print_exc()
                    out_polys = None

            if out_polys is None:
                out_polys = _cpp_union_all_polygons(loops, scale)

            polys = []
            for shell, holes in out_polys or []:
                shell_arr = np.asarray(shell, dtype=np.float64)
                if (
                    shell_arr.ndim != 2
                    or shell_arr.shape[0] < 3
                    or shell_arr.shape[1] != 2
                ):
                    continue
                holes_arr = []
                for h in holes or []:
                    h_arr = np.asarray(h, dtype=np.float64)
                    if h_arr.ndim != 2 or h_arr.shape[0] < 3 or h_arr.shape[1] != 2:
                        continue
                    holes_arr.append(h_arr)
                p = Polygon(shell_arr, holes_arr)
                if not p.is_valid:
                    p = p.buffer(0)
                if p.is_empty:
                    continue
                if p.geom_type == "Polygon":
                    polys.append(p)
                else:
                    polys.extend(
                        [
                            g
                            for g in p.geoms
                            if g.geom_type == "Polygon" and g.area > 1e-9
                        ]
                    )

            if not polys:
                return Polygon()
            if len(polys) == 1:
                g = polys[0]
            else:
                g = MultiPolygon(polys)
            if not g.is_valid:
                g = g.buffer(0)
            return g

        out_loops = None
        if jobs >= 2 and n >= 1500:
            jobs = min(jobs, n)
            chunk_size = (n + jobs - 1) // jobs
            chunks = [loops[i : i + chunk_size] for i in range(0, n, chunk_size)]
            partial_loops = []
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
                    futs = [
                        ex.submit(_cpp_union_all_loops, c, scale) for c in chunks if c
                    ]
                    for f in concurrent.futures.as_completed(futs):
                        partial_loops.extend(f.result() or [])

                out_loops = _cpp_union_all_loops(partial_loops, scale)
            except Exception as e:
                logger.error(f"警告: C++并集分块并行失败，将回退到单次并集。原因={e}")
                traceback.print_exc()
                out_loops = None

        if out_loops is None:
            out_loops = _cpp_union_all_loops(loops, scale)

        g = _loops_to_evenodd_polygon(out_loops)
        if not g.is_valid:
            g = g.buffer(0)
        return g
    except Exception as e:
        logger.error(f"[错误] C++并集失败: {e}")
        traceback.print_exc()
        raise


def parse_translate(transform_str: Optional[str]) -> Tuple[float, float]:
    """解析 SVG 中的 transform="translate(tx, ty)" 或 "translate(tx ty)"。"""
    if not transform_str:
        return 0.0, 0.0
    match = re.search(r"translate\(([-\d.]+)[,\s]*([-\d.]*)\)", transform_str)
    if match:
        tx = float(match.group(1))
        ty = float(match.group(2)) if match.group(2) else 0.0
        return tx, ty
    return 0.0, 0.0


def bake_vtracer_svg(svg_text: str) -> List[np.ndarray]:
    try:
        root = ET.fromstring(svg_text)
    except Exception as e:
        logger.error(f"SVG 解析失败: {e}")
        return []

    from oc_sdf.sdf_utils import _parse_path_d_simple, _parse_svg_points

    rings: List[np.ndarray] = []
    for elem in root.iter():
        tag = elem.tag
        if not isinstance(tag, str):
            continue

        fill = elem.get("fill") or ""
        fill_norm = fill.strip().lower()
        if fill_norm in {"#ffffff", "#fff", "white", "rgb(255,255,255)"}:
            continue

        path_rings = []
        tx, ty = 0.0, 0.0

        if tag.endswith("path"):
            d = elem.get("d")
            transform = elem.get("transform")
            tx, ty = parse_translate(transform)
            path_rings = _parse_path_d_simple(d or "")
        elif tag.endswith("polygon"):
            points = elem.get("points")
            transform = elem.get("transform")
            tx, ty = parse_translate(transform)
            path_rings = _parse_svg_points(points or "")

        for r in path_rings:
            if r.size > 0:
                r[:, 0] += tx
                r[:, 1] += ty
                rings.append(r)

    return rings


def get_rings_bbox(rings: List[np.ndarray]) -> List[float]:
    """获取像素域 rings 的 bbox [xmin, ymin, xmax, ymax]"""
    if not rings:
        return [0.0, 0.0, 0.0, 0.0]
    all_pts = np.vstack(rings)
    xmin, ymin = all_pts.min(axis=0)
    xmax, ymax = all_pts.max(axis=0)
    return [float(xmin), float(ymin), float(xmax), float(ymax)]


def vtracer_tool_svg_to_mm_polys(
    svg_path: Path,
    *,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
    use_cpp: bool = True,
    progress: bool = True,
    union_jobs: int = 1,
) -> List[Polygon]:
    if not svg_path.exists():
        raise FileNotFoundError(f"未找到 vtracer_tool.svg: {svg_path}")

    svg_text = svg_path.read_text(encoding="utf-8")
    rings = bake_vtracer_svg(svg_text)
    if not rings:
        return []

    mm_per_px_x = float(board_mm) / float(pixel_w)
    mm_per_px_y = float(board_mm) / float(pixel_h)

    polys: List[Polygon] = []
    loops_mm: List[np.ndarray] = []
    for r in _tqdm(
        rings, total=len(rings), desc=f"解析 {svg_path.name}", enabled=progress
    ):
        if len(r) < 3:
            continue

        phys_r = []
        for rx, ry in r:
            px_x = float(rx)
            px_y = float(ry)

            mx = px_x * mm_per_px_x
            my = (float(pixel_h) - px_y) * mm_per_px_y
            phys_r.append((mx, my))

        arr = np.asarray(phys_r, dtype=np.float64)
        loops_mm.append(arr)

        p = Polygon(arr)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)

    if not polys:
        return []

    global _CPP_UNION_AVG_SEC_PER_RING
    n = len(loops_mm)
    final_geom = None
    if use_cpp:
        if _CPP_UNION_AVG_SEC_PER_RING is not None:
            est = _CPP_UNION_AVG_SEC_PER_RING * float(max(n, 1))
            logger.info("vtracer并集(C++)：开始，ring数={}，预计 {:.3f}s", n, est)
        else:
            logger.info("vtracer并集(C++)：开始，ring数={}，暂无历史数据无法预估", n)

        t0 = perf_counter()
        final_geom = _try_cpp_union_all(loops_mm, scale=10000.0, union_jobs=union_jobs)
        dt = perf_counter() - t0
        if n > 0:
            per = dt / float(n)
            _CPP_UNION_AVG_SEC_PER_RING = (
                per
                if _CPP_UNION_AVG_SEC_PER_RING is None
                else (0.8 * _CPP_UNION_AVG_SEC_PER_RING + 0.2 * per)
            )
        logger.info("vtracer并集(C++)完成，用时 {:.3f}s", dt)

    if final_geom is None:
        t0 = perf_counter()
        final_geom = unary_union(polys)
        dt = perf_counter() - t0
        logger.info(f"[信息] vtracer并集(Python)完成，用时 {dt:.3f}s")

    EPS = 1e-6
    minx, miny, maxx, maxy = final_geom.bounds
    if (
        minx < -EPS
        or miny < -EPS
        or maxx > float(board_mm) + EPS
        or maxy > float(board_mm) + EPS
    ):
        logger.warning(
            f"警告: vtracer_tool.svg 解析结果越界，已自动裁剪回板子范围内。file={svg_path.name}"
        )
        board_rect = box(0.0, 0.0, float(board_mm), float(board_mm))
        clipped = final_geom.intersection(board_rect)
        if clipped.is_empty:
            raise ValueError(f"vtracer_tool.svg 解析结果越界且裁剪后为空: {svg_path}")
        final_geom = clipped

    return [final_geom]


def _cv2_contours_to_mm_polys(
    mask_u8: np.ndarray,
    *,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
    debug_dir: Path | None,
    slot_name: str,
    simplify_mm: float = 0.0,
    min_area_px: int = 4,
) -> List[Polygon]:
    if mask_u8.ndim != 2:
        raise ValueError(f"mask_u8 必须是二维灰度图，但收到 shape={mask_u8.shape}")

    src_h, src_w = int(mask_u8.shape[0]), int(mask_u8.shape[1])
    if int(pixel_w) != src_w or int(pixel_h) != src_h:
        logger.warning(
            f"警告: cv2 输入尺寸与参数不一致，已按 mask 实际尺寸覆盖: {pixel_w}x{pixel_h} -> {src_w}x{src_h}"
        )
        pixel_w = src_w
        pixel_h = src_h

    bin_u8 = (mask_u8 > 128).astype(np.uint8) * 255
    if int(np.count_nonzero(bin_u8)) < 2:
        return []

    if int(min_area_px) > 0:
        try:
            t0_cc = perf_counter()
            rows = np.any(bin_u8 != 0, axis=1)
            cols = np.any(bin_u8 != 0, axis=0)
            if bool(rows.any()) and bool(cols.any()):
                y0 = int(np.argmax(rows))
                y1 = int(len(rows) - int(np.argmax(rows[::-1])))
                x0 = int(np.argmax(cols))
                x1 = int(len(cols) - int(np.argmax(cols[::-1])))
                roi = (bin_u8[y0:y1, x0:x1] > 0).astype(np.uint8)
            else:
                roi = (bin_u8 > 0).astype(np.uint8)
                y0 = 0
                y1 = int(bin_u8.shape[0])
                x0 = 0
                x1 = int(bin_u8.shape[1])

            num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
                roi, connectivity=8
            )
            if int(num_labels) > 1:
                areas = stats[:, cv2.CC_STAT_AREA]
                small = areas <= int(min_area_px)
                small[0] = False
                n_removed_cc = int(np.count_nonzero(small))
                if n_removed_cc > 0:
                    removed_mask = small[labels]
                    removed_pixels = int(np.count_nonzero(removed_mask))
                    sub = bin_u8[y0:y1, x0:x1]
                    sub[removed_mask] = 0
                    bin_u8[y0:y1, x0:x1] = sub
                    dt_cc = perf_counter() - t0_cc
                    print_ts(
                        f"[信息] cv2 剔除极小孤立前景块完成: 阈值<={int(min_area_px)}px, 连通域移除={n_removed_cc}, 像素移除={removed_pixels}, 用时 {dt_cc:.3f}s"
                    )
        except Exception as e:
            logger.warning("cv2 连通域去噪失败，将继续尝试轮廓提取。原因: {}", e)
            traceback.print_exc()

    if debug_dir is not None:
        try:
            Image.fromarray(bin_u8, mode="L").save(
                debug_dir / f"{slot_name}_cv2_input.png"
            )
        except Exception as e:
            logger.warning("保存 cv2_input.png 失败: {}", e)

    try:
        bin2 = cv2.resize(
            bin_u8, (int(pixel_w) * 2, int(pixel_h) * 2), interpolation=cv2.INTER_LINEAR
        )
        bin2 = cv2.copyMakeBorder(
            bin2, 1, 1, 1, 1, borderType=cv2.BORDER_CONSTANT, value=0
        )
        res = cv2.findContours(bin2, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if len(res) == 3:
            _img, contours, hierarchy = res
        else:
            contours, hierarchy = res
    except Exception as e:
        logger.error(f"cv2 轮廓提取失败: {e}")
        traceback.print_exc()
        return []

    if hierarchy is None or len(contours) == 0:
        return []

    hierarchy = hierarchy[0]
    mm_per_px_x = float(board_mm) / float(pixel_w)
    mm_per_px_y = float(board_mm) / float(pixel_h)

    min_area_px2 = float(max(int(min_area_px), 0)) * 4.0

    def _contour_to_mm_ring(c) -> list[tuple[float, float]]:
        arr = np.squeeze(c, axis=1)
        if arr.ndim != 2 or arr.shape[0] < 3 or arr.shape[1] != 2:
            return []
        pts = []
        for x, y in arr:
            ox = (float(x) - 1.0) * 0.5
            oy = (float(y) - 1.0) * 0.5
            mx = float(ox) * mm_per_px_x
            my = (float(pixel_h) - float(oy)) * mm_per_px_y
            pts.append((mx, my))
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        return pts

    polys: list[Polygon] = []
    used = np.zeros((len(contours),), dtype=bool)

    for i in range(len(contours)):
        if used[i]:
            continue
        parent = int(hierarchy[i][3])
        if parent != -1:
            continue

        used[i] = True
        outer = contours[i]
        if outer is None or int(len(outer)) < 3:
            continue

        area = float(abs(cv2.contourArea(outer)))
        if area <= float(min_area_px2):
            continue

        shell = _contour_to_mm_ring(outer)
        if len(shell) < 3:
            continue

        holes = []
        child = int(hierarchy[i][2])
        while child != -1:
            used[child] = True
            hc = contours[child]
            if hc is not None and int(len(hc)) >= 3:
                h_area = float(abs(cv2.contourArea(hc)))
                if h_area > float(min_area_px2):
                    ring = _contour_to_mm_ring(hc)
                    if len(ring) >= 3:
                        holes.append(ring)
            child = int(hierarchy[child][0])

        p = Polygon(shell, holes)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty:
            continue
        polys.append(p)

    if not polys:
        return []

    if float(simplify_mm) > 0:
        simplified = []
        for p in polys:
            try:
                sp = p.simplify(float(simplify_mm), preserve_topology=True)
            except Exception as e:
                logger.warning("多边形简化失败，将使用未简化版本。原因: {}", e)
                traceback.print_exc()
                sp = p
            if not sp.is_valid:
                sp = sp.buffer(0)
            if not sp.is_empty:
                simplified.append(sp)
        polys = simplified
        if not polys:
            return []

    try:
        g = unary_union(polys) if len(polys) >= 2 else polys[0]
    except Exception as e:
        logger.error(
            f"警告: cv2 轮廓 union 失败，将尝试 buffer(0) 修复后重试。原因: {e}"
        )
        traceback.print_exc()
        fixed = []
        for p in polys:
            try:
                fixed.append(p.buffer(0))
            except Exception as ee:
                logger.warning("polygon buffer(0) 修复失败: {}", ee)
                traceback.print_exc()
        if not fixed:
            return []
        g = unary_union(fixed) if len(fixed) >= 2 else fixed[0]

    if not getattr(g, "is_valid", True):
        g = g.buffer(0)

    EPS = 1e-6
    minx, miny, maxx, maxy = g.bounds
    if (
        minx < -EPS
        or miny < -EPS
        or maxx > float(board_mm) + EPS
        or maxy > float(board_mm) + EPS
    ):
        board_rect = box(0.0, 0.0, float(board_mm), float(board_mm))
        clipped = g.intersection(board_rect)
        if clipped.is_empty:
            logger.warning("cv2 轮廓解析结果越界且裁剪后为空: slot={}", slot_name)
            return []
        g = clipped

    return [g]


def vectorize_mask_to_mm_polys(
    mask_u8: np.ndarray,
    *,
    backend: str,
    vtracer_params: dict,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
    debug_dir: Path | None,
    slot_name: str = "default",
    use_cpp: bool = True,
    progress: bool = True,
    union_jobs: int = 1,
    cv2_simplify_mm: float = 0.0,
    cv2_min_area_px: int = 4,
) -> List[Polygon]:
    b = str(backend or "cv2").strip().lower()
    if b not in {"cv2", "vtracer"}:
        logger.warning(f"警告: 未知 backend={backend}，将回退到 cv2")
        b = "cv2"

    if b == "vtracer":
        return vtracer_to_mm_polys(
            mask_u8=mask_u8,
            vtracer_params=vtracer_params,
            board_mm=board_mm,
            pixel_w=pixel_w,
            pixel_h=pixel_h,
            debug_dir=debug_dir,
            slot_name=slot_name,
            use_cpp=use_cpp,
            progress=progress,
            union_jobs=union_jobs,
        )

    return _cv2_contours_to_mm_polys(
        mask_u8,
        board_mm=board_mm,
        pixel_w=pixel_w,
        pixel_h=pixel_h,
        debug_dir=debug_dir,
        slot_name=slot_name,
        simplify_mm=float(cv2_simplify_mm),
        min_area_px=int(cv2_min_area_px),
    )


def vtracer_to_mm_polys(
    mask_u8: np.ndarray,
    vtracer_params: dict,
    board_mm: float,
    pixel_w: int,
    pixel_h: int,
    debug_dir: Path,
    slot_name: str = "default",
    use_cpp: bool = True,
    progress: bool = True,
    union_jobs: int = 1,
) -> List[Polygon]:
    """
    统一的 vtracer 调用 + 解析 + 烘焙 + 缩放逻辑。

    Args:
        mask_u8: 输入的 mask (0 或 255)
        vtracer_params: vtracer 参数 (mode, filter_speckle, corner_threshold, length_threshold)
        board_mm: 面板物理尺寸 (例如 60.06)
        pixel_w, pixel_h: 输入图像的基准分辨率
        debug_dir: 产物落盘目录
        slot_name: slot 名称，用于文件名
    """
    if not HAS_VTRACER:
        raise ImportError("vtracer 模块未安装，无法进行矢量化。")

    if mask_u8.ndim != 2:
        raise ValueError(f"mask_u8 必须是二维灰度图，但收到 shape={mask_u8.shape}")

    src_h, src_w = int(mask_u8.shape[0]), int(mask_u8.shape[1])
    if int(pixel_w) != src_w or int(pixel_h) != src_h:
        logger.warning(
            "vtracer 输入尺寸与参数不一致，已按 mask 实际尺寸覆盖: {}x{} -> {}x{}",
            pixel_w,
            pixel_h,
            src_w,
            src_h,
        )
        pixel_w = src_w
        pixel_h = src_h

    input_scale = int(vtracer_params.get("input_scale", 1))
    if input_scale < 1:
        input_scale = 1

    if input_scale != 1:
        t0_up = perf_counter()
        m_bin = mask_u8 > 128
        m_up = np.kron(m_bin, np.ones((input_scale, input_scale), dtype=bool))
        mask_u8 = m_up.astype(np.uint8) * 255
        pixel_w = int(pixel_w) * input_scale
        pixel_h = int(pixel_h) * input_scale
        dt_up = perf_counter() - t0_up
        print_ts(
            f"[信息] vtracer输入上采样完成: scale={input_scale}, 用时 {dt_up:.3f}s"
        )

    bin_u8 = (mask_u8 > 128).astype(np.uint8)
    if int(np.count_nonzero(bin_u8)) > 0:
        t0_cc = perf_counter()
        rows = np.any(bin_u8 != 0, axis=1)
        cols = np.any(bin_u8 != 0, axis=0)
        if bool(rows.any()) and bool(cols.any()):
            y0 = int(np.argmax(rows))
            y1 = int(len(rows) - int(np.argmax(rows[::-1])))
            x0 = int(np.argmax(cols))
            x1 = int(len(cols) - int(np.argmax(cols[::-1])))
            roi = bin_u8[y0:y1, x0:x1]
        else:
            roi = bin_u8
            y0 = 0
            y1 = int(bin_u8.shape[0])
            x0 = 0
            x1 = int(bin_u8.shape[1])

        num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            roi, connectivity=8
        )
        if num_labels > 1:
            areas = stats[:, cv2.CC_STAT_AREA]
            small = areas <= 4
            small[0] = False
            n_removed_cc = int(np.count_nonzero(small))
            if n_removed_cc > 0:
                removed_mask = small[labels]
                removed_pixels = int(np.count_nonzero(removed_mask))
                bin_u8[y0:y1, x0:x1][removed_mask] = 0
                mask_u8 = (bin_u8 * 255).astype(np.uint8)
                dt_cc = perf_counter() - t0_cc
                roi_area = int((y1 - y0) * (x1 - x0))
                full_area = int(bin_u8.shape[0] * bin_u8.shape[1])
                print_ts(
                    f"剔除极小孤立前景块: 阈值<=4px, 连通域移除={n_removed_cc}, 像素移除={removed_pixels}, 用时 {dt_cc:.3f}s, ROI像素={roi_area}/{full_area}"
                )
            else:
                dt_cc = perf_counter() - t0_cc
                roi_area = int((y1 - y0) * (x1 - x0))
                full_area = int(bin_u8.shape[0] * bin_u8.shape[1])
                print_ts(
                    f"[信息] 连通域扫描完成: 未发现<=4px前景块, 用时 {dt_cc:.3f}s, ROI像素={roi_area}/{full_area}"
                )
        else:
            dt_cc = perf_counter() - t0_cc
            print_ts(f"[信息] 连通域扫描完成: 前景仅1个连通域, 用时 {dt_cc:.3f}s")

    # 1. 保存 vtracer_input.png
    input_mask = np.where(mask_u8 > 128, 0, 255).astype(np.uint8)

    # 如果 debug_dir 为 None，则使用临时目录保存输入图片
    temp_input_dir = None
    if debug_dir is None:
        temp_input_dir = tempfile.TemporaryDirectory()
        input_png = Path(temp_input_dir.name) / f"{slot_name}_vtracer_input.png"
    else:
        input_png = debug_dir / f"{slot_name}_vtracer_input.png"

    Image.fromarray(input_mask).save(input_png)

    # 2. 调用 vtracer
    with tempfile.TemporaryDirectory() as tmpdir:
        out_svg_path = os.path.join(tmpdir, "out.svg")

        convert_func = None
        if hasattr(vtracer, "convert_image_to_svg_py"):
            convert_func = vtracer.convert_image_to_svg_py
        elif hasattr(vtracer, "convert_image_to_svg"):
            convert_func = vtracer.convert_image_to_svg

        if not convert_func:
            raise AttributeError("vtracer 接口不可用")

        colormode = str(vtracer_params.get("colormode", "color"))
        mode = str(vtracer_params.get("mode", "polygon"))
        filter_speckle = int(vtracer_params.get("filter_speckle", 0))
        color_precision = int(vtracer_params.get("color_precision", 8))
        layer_difference = int(vtracer_params.get("layer_difference", 16))
        corner_threshold = int(vtracer_params.get("corner_threshold", 60))
        length_threshold = float(vtracer_params.get("length_threshold", 4.0))
        max_iterations = int(vtracer_params.get("max_iterations", 10))
        splice_threshold = int(vtracer_params.get("splice_threshold", 45))
        path_precision = int(vtracer_params.get("path_precision", 3))

        t0_vtr = perf_counter()
        convert_func(
            str(input_png),
            out_svg_path,
            colormode=colormode,
            mode=mode,
            filter_speckle=filter_speckle,
            color_precision=color_precision,
            layer_difference=layer_difference,
            corner_threshold=corner_threshold,
            length_threshold=length_threshold,
            max_iterations=max_iterations,
            splice_threshold=splice_threshold,
            path_precision=path_precision,
        )
        dt_vtr = perf_counter() - t0_vtr
        print_ts(f"[信息] vtracer调用完成: slot={slot_name}, 用时 {dt_vtr:.3f}s")

        if not os.path.exists(out_svg_path):
            raise FileNotFoundError("vtracer 未能生成 SVG 输出")

        # 3. 保存 vtracer_tool.svg (原生输出)
        if debug_dir is not None:
            tool_svg_path = debug_dir / f"{slot_name}_vtracer_tool.svg"
            shutil.copy2(out_svg_path, tool_svg_path)

        svg_text = Path(out_svg_path).read_text(encoding="utf-8")

    # 清理临时输入目录
    if temp_input_dir:
        temp_input_dir.cleanup()

    # 4. 解析并烘焙 transform
    # 获取原始 bbox (不含 transform)
    from oc_sdf.sdf_utils import _parse_path_d_simple, _parse_svg_points

    root = ET.fromstring(svg_text)
    raw_rings = []
    tx, ty = 0.0, 0.0
    for elem in root.iter():
        tag = elem.tag
        if not isinstance(tag, str):
            continue
        fill = elem.get("fill") or ""
        fill_norm = fill.strip().lower()
        if fill_norm in {"#ffffff", "#fff", "white", "rgb(255,255,255)"}:
            continue
        if tag.endswith("path"):
            raw_rings.extend(_parse_path_d_simple(elem.get("d") or ""))
            tx, ty = parse_translate(elem.get("transform"))
        elif tag.endswith("polygon"):
            raw_rings.extend(_parse_svg_points(elem.get("points") or ""))
            tx, ty = parse_translate(elem.get("transform"))

    d_bbox_px = get_rings_bbox(raw_rings)

    # 烘焙 transform
    rings = bake_vtracer_svg(svg_text)
    final_bbox_px = get_rings_bbox(rings)

    # 5. px -> mm 缩放并转换为 Polygon
    # 使用 board_mm / pixel_w 确保边界对齐
    mm_per_px_x = board_mm / pixel_w
    mm_per_px_y = board_mm / pixel_h

    polys = []
    loops_mm = []
    for r in _tqdm(
        rings, total=len(rings), desc=f"{slot_name} rings", enabled=progress
    ):
        if len(r) < 3:
            continue

        phys_r = []
        for rx, ry in r:
            px_x = float(rx)
            px_y = float(ry)

            # px -> mm 转换
            mx = px_x * mm_per_px_x
            # 注意：vtracer 坐标系 y 向下，物理坐标系 y 向上
            my = (float(pixel_h) - px_y) * mm_per_px_y
            phys_r.append((mx, my))

        arr = np.asarray(phys_r, dtype=np.float64)
        loops_mm.append(arr)

        p = Polygon(arr)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)

    # 6. 最终 BBox 检查与报告
    report = {
        "input": {"W": int(pixel_w), "H": int(pixel_h)},
        "tool_svg": {
            "d_bbox_px": d_bbox_px,
            "transform_translate_px": [tx, ty],
            "final_bbox_px": final_bbox_px,
        },
        "wrapped": {
            "mm_per_px": [mm_per_px_x, mm_per_px_y],
            "board_mm": board_mm,
            "bbox_mm": [0.0, 0.0, 0.0, 0.0],
            "viewBox": [0.0, 0.0, board_mm, board_mm],
        },
    }

    if polys:
        global _CPP_UNION_AVG_SEC_PER_RING
        n = len(loops_mm)
        final_geom = None
        if use_cpp:
            if _CPP_UNION_AVG_SEC_PER_RING is not None:
                est = _CPP_UNION_AVG_SEC_PER_RING * float(max(n, 1))
                logger.info(
                    f"[信息] {slot_name} 并集(C++)：开始，ring数={n}，预计 {est:.3f}s"
                )
            else:
                logger.info(
                    f"[信息] {slot_name} 并集(C++)：开始，ring数={n}，暂无历史数据无法预估"
                )

            t0 = perf_counter()
            final_geom = _try_cpp_union_all(
                loops_mm, scale=10000.0, union_jobs=union_jobs
            )
            if final_geom is not None:
                dt = perf_counter() - t0
                if n > 0:
                    per = dt / float(n)
                    _CPP_UNION_AVG_SEC_PER_RING = (
                        per
                        if _CPP_UNION_AVG_SEC_PER_RING is None
                        else (0.8 * _CPP_UNION_AVG_SEC_PER_RING + 0.2 * per)
                    )
                logger.info(f"[信息] {slot_name} 并集(C++)完成，用时 {dt:.3f}s")

        if final_geom is None:
            t0 = perf_counter()
            final_geom = unary_union(polys)
            dt = perf_counter() - t0
            logger.info(f"[信息] {slot_name} 并集(Python)完成，用时 {dt:.3f}s")
        minx, miny, maxx, maxy = final_geom.bounds
        report["wrapped"]["bbox_mm"] = [minx, miny, maxx, maxy]

        EPS = 1e-6
        if minx < -EPS or miny < -EPS or maxx > board_mm + EPS or maxy > board_mm + EPS:
            logger.warning(
                f"警告: 最终几何轻微越界，已自动裁剪回板子范围内。slot={slot_name}"
            )
            logger.info(f"  裁剪前 BBox: ({minx}, {miny}, {maxx}, {maxy})")
            logger.info(f"  Board Limit: 0 ~ {board_mm}")

            board_rect = box(0.0, 0.0, float(board_mm), float(board_mm))
            clipped = final_geom.intersection(board_rect)
            if clipped.is_empty:
                logger.error(f"严重错误: 裁剪后几何为空，无法继续。slot={slot_name}")
                if debug_dir is not None:
                    report_path = debug_dir / f"{slot_name}_bbox_report.json"
                    report_path.write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    raise ValueError(
                        f"Slot {slot_name} geometry out of bounds and clip-to-board became empty. Report saved to {report_path}"
                    )
                raise ValueError(
                    f"Slot {slot_name} geometry out of bounds and clip-to-board became empty."
                )

            final_geom = clipped
            polys = [final_geom]
            minx, miny, maxx, maxy = final_geom.bounds
            report["wrapped"]["bbox_mm"] = [minx, miny, maxx, maxy]

            if (
                minx < -EPS
                or miny < -EPS
                or maxx > board_mm + EPS
                or maxy > board_mm + EPS
            ):
                logger.error(f"严重错误: 裁剪后仍越界! slot={slot_name}")
                logger.info(f"  裁剪后 BBox: ({minx}, {miny}, {maxx}, {maxy})")
                if debug_dir is not None:
                    report_path = debug_dir / f"{slot_name}_bbox_report.json"
                    report_path.write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    raise ValueError(
                        f"Slot {slot_name} geometry out of bounds after clipping: {final_geom.bounds}. Report saved to {report_path}"
                    )
                raise ValueError(
                    f"Slot {slot_name} geometry out of bounds after clipping: {final_geom.bounds}."
                )

    # 7. 保存产物
    # 写入 bbox_report.json
    if debug_dir is not None:
        report_path = debug_dir / f"{slot_name}_bbox_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return polys
