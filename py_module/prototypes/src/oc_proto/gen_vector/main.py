"""vtracer矢量化主模块

读取掩码图像，调用vtracer转换为SVG矢量多边形，执行重采样和质量检测
"""

import argparse
import concurrent.futures
import json
import os
import shutil
import time
import traceback
from pathlib import Path
from time import perf_counter
from typing import Optional, Dict, Any

import numpy as np
from PIL import Image
from shapely import wkb as shapely_wkb
from shapely.geometry import GeometryCollection
from shapely.ops import unary_union

from oc_sdf.sdf_io import save_svg, rasterize_geometry_soft
from oc_core_02.utils.io_utils import start_heartbeat, print_ts
from oc_core_02.utils.manifest import write_manifest
from oc_core_02.utils.paths import get_out_dir, select_latest_subdir
from oc_core_02.utils.vtracer_bridge import vectorize_mask_to_mm_polys
from oc_proto.gen_vector.mask_overlap_check import check_mask_overlaps
from oc_proto.gen_vector.resampler import resample_shared_boundaries
from .exclusive_clipper import _make_layer_exclusive
from .reconcile import _reconcile_layer_polys_by_raster
from .svg_utils import _mm_geom_to_vtracer_tool_svg_text
from .visualization import _save_debug_layer_colored
from .workers import _vectorize_slot_worker


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
VERSION = "gen_vector"


try:
    from tqdm import tqdm
except Exception:
    tqdm = None


def _tqdm(it, *, total: int | None = None, desc: str = "", enabled: bool = True):
    if (not enabled) or (tqdm is None):
        return it
    return tqdm(it, total=total, desc=desc, dynamic_ncols=True)


def _rmtree_retry(p: Path, *, tries: int = 8, wait_s: float = 0.2) -> None:
    for i in range(int(tries)):
        try:
            shutil.rmtree(p)
            return
        except PermissionError as e:
            if i >= int(tries) - 1:
                raise
            logger.error(
                f"警告: 删除目录失败(可能被占用)，将重试 {i + 1}/{tries}: {p}，原因={e}"
            )
            time.sleep(float(wait_s))


def _unlink_retry(p: Path, *, tries: int = 8, wait_s: float = 0.2) -> None:
    for i in range(int(tries)):
        try:
            p.unlink()
            return
        except PermissionError as e:
            if i >= int(tries) - 1:
                raise
            logger.error(
                f"警告: 删除文件失败(可能被占用)，将重试 {i + 1}/{tries}: {p}，原因={e}"
            )
            time.sleep(float(wait_s))


def _clear_dir_keep_root(d: Path) -> None:
    if not d.exists():
        return
    for child in d.iterdir():
        if child.is_dir():
            _rmtree_retry(child)
        else:
            _unlink_retry(child)


def run(
    mask_input_dir: str = None,
    resample: bool = True,
    vtracer_override: Optional[Dict[str, Any]] = None,
    *,
    impl: str = "cpp",
    progress: bool = True,
    jobs: int = 0,
    union_jobs: int = 0,
    preview_4x: bool = False,
    vector_backend: str = "cv2",
    cv2_simplify_mm: float = 0.1,
    cv2_min_area_px: int = 4,
    reconcile: bool = False,
    reconcile_scale: int = 2,
    reconcile_cv2_simplify_mm: float = 0.05,
    svg_simplify_level: int = 3,
    svg_simplify_max_diff_ratio: float = 0.001,
    svg_simplify_min_diff_px: int = 64,
    svg_simplify_tol_px: int = 1,
    svg_simplify_perimeter_weight: float = 0.2,
    svg_simplify_max_attempts: int = 6,
):
    """运行矢量化流程"""
    hb = start_heartbeat("gen_vector", 30.0)
    t_run0 = perf_counter()
    print_ts("[信息] gen_vector 开始")

    # 处理简化级别参数
    try:
        svg_simplify_level = int(svg_simplify_level)
    except Exception as e:
        logger.error(f"[警告] svg_simplify_level 解析失败，将回退为 1。原因={e}")
        traceback.print_exc()
        svg_simplify_level = 1
    if svg_simplify_level < 1:
        svg_simplify_level = 1
    if svg_simplify_level > 3:
        svg_simplify_level = 3

    if svg_simplify_level == 2:
        svg_simplify_max_diff_ratio = float(svg_simplify_max_diff_ratio) * 2.5
        svg_simplify_min_diff_px = int(max(int(svg_simplify_min_diff_px), 0)) * 2
        svg_simplify_tol_px = int(max(int(svg_simplify_tol_px), 2))
        svg_simplify_perimeter_weight = float(svg_simplify_perimeter_weight) * 0.75
        svg_simplify_max_attempts = int(max(int(svg_simplify_max_attempts), 8))
    elif svg_simplify_level >= 3:
        svg_simplify_max_diff_ratio = float(svg_simplify_max_diff_ratio) * 4.0
        svg_simplify_min_diff_px = int(max(int(svg_simplify_min_diff_px), 0)) * 4
        svg_simplify_tol_px = int(max(int(svg_simplify_tol_px), 3))
        svg_simplify_perimeter_weight = float(svg_simplify_perimeter_weight) * 0.5
        svg_simplify_max_attempts = int(max(int(svg_simplify_max_attempts), 10))

    import atexit

    def _on_exit():
        try:
            hb.set()
        finally:
            dt = perf_counter() - t_run0
            print_ts(f"[报时] gen_vector 进程退出，总耗时 {dt:.1f}s")

    atexit.register(_on_exit)
    prototype_dir = Path(__file__).resolve().parent

    is_default_input = mask_input_dir is None
    if is_default_input:
        mask_input_path = (prototype_dir.parent / "gen_masks" / "out").resolve()
    else:
        mask_input_path = Path(mask_input_dir).resolve()

    if not mask_input_path.exists():
        print_ts(f"[错误] 找不到掩码输入目录 {mask_input_path}")
        print_ts("[提示] 请确保已先运行 gen_masks 模块，或者手动通过 --input 指定路径")
        return

    def _looks_like_mask_run_dir(d: Path) -> bool:
        mp = d / "mask_manifest.json"
        md = d / "02_masks"
        if (not mp.exists()) or (not md.exists()) or (not md.is_dir()):
            return False
        try:
            return any(md.glob("*.png"))
        except OSError:
            return False

    if is_default_input:
        mask_run_dir = select_latest_subdir(
            mask_input_path, required_relpaths=["mask_manifest.json", "02_masks"]
        )
        if mask_run_dir is None and _looks_like_mask_run_dir(mask_input_path):
            mask_run_dir = mask_input_path
    else:
        if _looks_like_mask_run_dir(mask_input_path):
            mask_run_dir = mask_input_path
        else:
            mask_run_dir = select_latest_subdir(
                mask_input_path, required_relpaths=["mask_manifest.json", "02_masks"]
            )

    if mask_run_dir is None:
        print_ts(f"[错误] 未在输入目录中找到可用的掩码运行子目录: {mask_input_path}")
        print_ts(
            "[提示] 期望目录结构: <out>/<文件名>_<hash6>/mask_manifest.json 与 02_masks/"
        )
        return

    manifest_path = mask_run_dir / "mask_manifest.json"
    if not manifest_path.exists():
        print_ts(f"[错误] 找不到 Manifest 文件 {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    out_dir_base = get_out_dir(prototype_dir)
    run_id = str(mask_run_dir.name)

    def _make_fallback_out_dir() -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        return out_dir_base / f"{run_id}_run_{ts}"

    def _prepare_dirs(root_out: Path) -> tuple[Path, Path, Path]:
        mask_d = root_out / "02_masks"
        vtracer_d = root_out / "03_vtracer"
        poly_d = root_out / "04_polys"
        for d in [mask_d, vtracer_d, poly_d]:
            d.mkdir(parents=True, exist_ok=True)
            _clear_dir_keep_root(d)
        return mask_d, vtracer_d, poly_d

    out_dir = (out_dir_base / run_id).resolve()
    try:
        mask_dir, vtracer_dir, poly_dir = _prepare_dirs(out_dir)
    except PermissionError as e:
        out_dir = _make_fallback_out_dir()
        logger.warning(
            f"警告: 输出目录被占用，无法清理旧文件，将改为写入新目录: {out_dir}，原因={e}"
        )
        mask_dir, vtracer_dir, poly_dir = _prepare_dirs(out_dir)

    print_ts("[信息] 正在同步掩码文件...")
    mask_files = list((mask_run_dir / "02_masks").glob("*.png"))
    for m_file in _tqdm(
        mask_files, total=len(mask_files), desc="同步 02_masks", enabled=progress
    ):
        shutil.copy2(m_file, mask_dir / m_file.name)

    print_ts(f"[信息] 掩码同步完成: 数量={len(mask_files)}")

    pixel_w = manifest["pixel_w"]
    pixel_h = manifest["pixel_h"]
    board_mm = manifest["board_mm"]
    n_layers = manifest["n_layers"]
    slot_names = manifest["slot_names"]
    layer_height_mm = manifest.get("layer_height_mm")
    print_ts(
        f"[信息] 参数: pixel={pixel_w}x{pixel_h}, board_mm={float(board_mm):.3f}, layers={int(n_layers)}, slots={len(slot_names)}"
    )

    slot_preview_rgb = manifest.get("slot_preview_rgb")

    # 加载 full_mask
    full_mask_bin_hi = None
    if bool(reconcile):
        try:
            fm_path = mask_dir / "full_mask.png"
            if fm_path.exists():
                fm_u8 = np.array(Image.open(fm_path).convert("L"), dtype=np.uint8)
                fm_bin = fm_u8 > 128
                s = int(reconcile_scale) if reconcile_scale is not None else 4
                if s < 1:
                    s = 1
                full_mask_bin_hi = np.repeat(np.repeat(fm_bin, s, axis=0), s, axis=1)
        except Exception as e:
            logger.error(
                f"[警告] reconcile 读取 full_mask.png 失败，将跳过 reconcile。原因={e}"
            )
            traceback.print_exc()
            full_mask_bin_hi = None

    background_slot = manifest.get("background_slot")
    if background_slot not in slot_names:
        background_slot = "BLACK" if (slot_names and "BLACK" in slot_names) else None
    slot_names_no_bg = [sn for sn in slot_names if sn != background_slot]

    # vtracer 参数
    vtracer_params = {
        "colormode": "binary",
        "mode": "spline",
        "filter_speckle": 4,
        "corner_threshold": 120,
        "length_threshold": 8,
        "input_scale": 1,
    }

    if vtracer_override:
        for k, v in vtracer_override.items():
            if v is not None:
                vtracer_params[k] = v

    if int(vtracer_params.get("input_scale", 1)) != 1:
        logger.warning(
            f"警告: 检测到 vtracer 输入mask超分 input_scale={vtracer_params.get('input_scale')}，为了避免像素轮廓问题，已强制关闭(设为 1)。"
        )
        vtracer_params["input_scale"] = 1

    logger.info(
        f"开始处理 [矢量化] 阶段: {manifest['image_name']} (重采样: {'启用' if resample else '禁用'})"
    )
    logger.info(f"本次矢量化后端: {str(vector_backend).strip().lower()}")
    logger.info(
        f"vtracer参数: colormode={vtracer_params.get('colormode')}, mode={vtracer_params.get('mode')}, filter_speckle={vtracer_params.get('filter_speckle')}, corner_threshold={vtracer_params.get('corner_threshold')}, length_threshold={vtracer_params.get('length_threshold')}, input_scale={vtracer_params.get('input_scale')}"
    )
    logger.info(
        f"cv2参数: simplify_mm={float(cv2_simplify_mm)}, min_area_px={int(cv2_min_area_px)}"
    )

    use_cpp = str(impl).strip().lower() == "cpp"
    logger.info(f"本次运行后端选择: {'C++' if use_cpp else 'Python'}")

    jobs_req = int(jobs)
    if jobs_req <= 0:
        jobs_req = max(1, int((os.cpu_count() or 1) - 1))
    jobs_req = max(1, min(jobs_req, int(len(slot_names) or 1)))

    union_jobs_req = int(union_jobs)
    if union_jobs_req <= 0:
        if jobs_req >= 2:
            union_jobs_req = max(1, int((os.cpu_count() or 1) // jobs_req))
        else:
            union_jobs_req = max(1, int((os.cpu_count() or 1) - 1))
    union_jobs_req = max(1, union_jobs_req)

    logger.info(f"并行参数: jobs={jobs_req}, union_jobs={union_jobs_req}")

    # 预先矢量化 full_mask
    full_mask_path = mask_dir / "full_mask.png"
    full_mask_poly = None
    full_mask_bitmap = None
    if full_mask_path.exists():
        fm_mask = np.array(Image.open(full_mask_path).convert("L"))
        full_mask_bitmap = fm_mask > 128
        if np.count_nonzero(fm_mask) > 10:
            fm_polys = vectorize_mask_to_mm_polys(
                fm_mask,
                backend=str(vector_backend),
                vtracer_params=vtracer_params,
                cv2_simplify_mm=float(cv2_simplify_mm),
                cv2_min_area_px=int(cv2_min_area_px),
                board_mm=board_mm,
                pixel_w=pixel_w,
                pixel_h=pixel_h,
                debug_dir=None,
                slot_name="full_mask_ref",
                use_cpp=use_cpp,
                progress=progress,
            )
            if fm_polys:
                full_mask_poly = unary_union(fm_polys)
                save_svg(
                    full_mask_poly,
                    poly_dir / "full_mask_ref_poly_final.svg",
                    board_mm,
                    board_mm,
                )
                logger.info(f"DEBUG: 全局参考边界 (full_mask) 矢量化完成。")

    # 逐层处理
    for z in _tqdm(range(n_layers), total=n_layers, desc="逐层处理", enabled=progress):
        layer_polys = {}
        layer_polys_vtraced = {}

        layer_sum = np.zeros((pixel_h, pixel_w), dtype=np.uint16)
        t_layer0 = perf_counter()
        it_slots = _tqdm(
            slot_names, total=len(slot_names), desc=f"L{z:02d} 矢量化", enabled=progress
        )
        for slot_name in it_slots:
            prefix = f"L{z:02d}_{slot_name}"
            mask_path = mask_dir / f"{prefix}_mask.png"
            if not mask_path.exists():
                continue
            mask_u8 = np.array(Image.open(mask_path).convert("L"))
            layer_sum += (mask_u8 > 128).astype(np.uint16)

        layer_covered = layer_sum > 0
        layer_overlap = layer_sum > 1
        ref = full_mask_bitmap if full_mask_bitmap is not None else layer_covered
        layer_hole = ref & (~layer_covered)

        layer_issue = np.zeros((pixel_h, pixel_w, 3), dtype=np.uint8)
        layer_issue[ref] = np.array([50, 50, 50], dtype=np.uint8)
        layer_issue[layer_covered & ref] = np.array([220, 220, 220], dtype=np.uint8)
        layer_issue[layer_hole] = np.array([255, 0, 0], dtype=np.uint8)
        layer_issue[layer_overlap] = np.array([0, 180, 255], dtype=np.uint8)
        Image.fromarray(layer_issue).save(mask_dir / f"L{z:02d}_layer_mask_issue.png")

        if slot_preview_rgb is not None:
            try:
                _save_debug_layer_colored(
                    out_dir=out_dir,
                    mask_dir=mask_dir,
                    z=int(z),
                    slot_names=list(slot_names),
                    slot_preview_rgb=dict(slot_preview_rgb),
                    pixel_w=int(pixel_w),
                    pixel_h=int(pixel_h),
                )
            except Exception as e:
                logger.error(f"[警告] 保存每层着色位图失败: L{z:02d}，原因={e}")
                traceback.print_exc()

        slot_inputs = []
        for slot_name in slot_names:
            prefix = f"L{z:02d}_{slot_name}"
            mask_path = mask_dir / f"{prefix}_mask.png"
            if not mask_path.exists():
                continue
            slot_inputs.append((slot_name, prefix, str(mask_path)))

        # 并行或串行矢量化
        if jobs_req >= 2 and len(slot_inputs) >= 2:
            logger.info(f"L{z:02d} 层：开始并行矢量化，任务数={len(slot_inputs)}")
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=min(jobs_req, len(slot_inputs))
            ) as ex:
                futs = []
                for slot_name, prefix, mp in slot_inputs:
                    futs.append(
                        ex.submit(
                            _vectorize_slot_worker,
                            mask_path=mp,
                            prefix=prefix,
                            slot_name=slot_name,
                            vector_backend=str(vector_backend),
                            vtracer_params=vtracer_params,
                            cv2_simplify_mm=float(cv2_simplify_mm),
                            cv2_min_area_px=int(cv2_min_area_px),
                            board_mm=board_mm,
                            pixel_w=pixel_w,
                            pixel_h=pixel_h,
                            vtracer_dir=str(vtracer_dir)
                            if vtracer_dir is not None
                            else None,
                            use_cpp=use_cpp,
                            union_jobs=union_jobs_req,
                        )
                    )

                it = concurrent.futures.as_completed(futs)
                it = _tqdm(
                    it, total=len(futs), desc=f"L{z:02d} 矢量化(并行)", enabled=progress
                )
                for f in it:
                    try:
                        slot_name, wkb_bytes, dt = f.result()
                    except Exception as e:
                        logger.error(f"[错误] L{z:02d} 并行矢量化任务失败: {e}")
                        traceback.print_exc()
                        continue

                    if dt >= 1.0:
                        logger.info(
                            f"[信息] L{z:02d}_{slot_name} 矢量化任务完成，用时 {dt:.3f}s"
                        )

                    if wkb_bytes is None:
                        continue
                    final_poly = shapely_wkb.loads(wkb_bytes)
                    if getattr(final_poly, "is_empty", True):
                        continue
                    layer_polys_vtraced[slot_name] = final_poly
                    if slot_name != background_slot:
                        layer_polys[slot_name] = final_poly
        else:
            for slot_name, prefix, mp in slot_inputs:
                mask = np.array(Image.open(mp).convert("L"))
                if np.count_nonzero(mask) < 2:
                    continue

                polys = vectorize_mask_to_mm_polys(
                    mask,
                    backend=str(vector_backend),
                    vtracer_params=vtracer_params,
                    cv2_simplify_mm=float(cv2_simplify_mm),
                    cv2_min_area_px=int(cv2_min_area_px),
                    board_mm=board_mm,
                    pixel_w=pixel_w,
                    pixel_h=pixel_h,
                    debug_dir=vtracer_dir,
                    slot_name=prefix,
                    use_cpp=use_cpp,
                    progress=progress,
                    union_jobs=union_jobs_req,
                )

                if not polys:
                    continue

                final_poly = unary_union(polys)
                if final_poly.is_empty:
                    continue

                layer_polys_vtraced[slot_name] = final_poly
                if slot_name != background_slot:
                    layer_polys[slot_name] = final_poly

        grid_size = max((float(board_mm) / float(pixel_w)) / 4.0, 1e-6)

        logger.info(f"L{z:02d} 层：矢量化完成，用时 {perf_counter() - t_layer0:.3f}s")

        # 互斥裁剪
        layer_polys = _make_layer_exclusive(
            layer_polys,
            slot_names_no_bg,
            grid_size,
            use_cpp=use_cpp,
            progress=progress,
            tag=f"L{z:02d}",
        )

        # 重采样
        if resample and layer_polys:
            try:
                layer_polys = resample_shared_boundaries(
                    layer_polys,
                    full_mask_poly=full_mask_poly,
                    use_cpp=use_cpp,
                    progress=progress,
                    tag=f"L{z:02d}",
                )
            except Exception as e:
                logger.error(
                    f"  [重采样器][错误] 重采样失败，回退到未重采样版本。原因={e}"
                )

        if layer_polys:
            layer_polys = _make_layer_exclusive(
                layer_polys,
                slot_names_no_bg,
                grid_size,
                use_cpp=use_cpp,
                progress=progress,
                tag=f"L{z:02d}",
            )

        # 处理背景
        if background_slot and full_mask_poly is not None:
            ordered_slots = slot_names_no_bg + [background_slot]
            if layer_polys:
                t_occ0 = perf_counter()
                occupied = unary_union(
                    [p.buffer(0) if not p.is_valid else p for p in layer_polys.values()]
                )
                print_ts(
                    f"[信息] L{z:02d} 背景计算: 已合并占用区域，用时 {perf_counter() - t_occ0:.3f}s"
                )
            else:
                occupied = GeometryCollection()

            t_diff0 = perf_counter()
            bg_poly = full_mask_poly.difference(occupied)
            print_ts(
                f"[信息] L{z:02d} 背景计算: full_mask - occupied 完成，用时 {perf_counter() - t_diff0:.3f}s"
            )
            if not bg_poly.is_empty:
                if not bg_poly.is_valid:
                    bg_poly = bg_poly.buffer(0)
                if not bg_poly.is_empty:
                    layer_polys[background_slot] = bg_poly

            layer_polys = _make_layer_exclusive(
                layer_polys,
                ordered_slots,
                grid_size,
                use_cpp=use_cpp,
                progress=progress,
                tag=f"L{z:02d}",
            )

        # SVG 简化
        if layer_polys:
            _simplify_layer_polys(
                layer_polys,
                mask_dir,
                z,
                slot_names_no_bg,
                background_slot,
                board_mm,
                pixel_w,
                pixel_h,
                grid_size,
                use_cpp,
                progress,
                svg_simplify_level,
                svg_simplify_max_diff_ratio,
                svg_simplify_min_diff_px,
                svg_simplify_tol_px,
                svg_simplify_perimeter_weight,
                svg_simplify_max_attempts,
            )

        # Reconcile
        if (
            layer_polys
            and bool(reconcile)
            and full_mask_bin_hi is not None
            and background_slot is not None
            and full_mask_poly is not None
        ):
            try:
                layer_polys = _reconcile_layer_polys_by_raster(
                    layer_polys=layer_polys,
                    full_mask_poly=full_mask_poly,
                    full_mask_bin_hi=full_mask_bin_hi,
                    slot_names_no_bg=list(slot_names_no_bg),
                    background_slot=str(background_slot),
                    board_mm=float(board_mm),
                    pixel_w=int(pixel_w),
                    pixel_h=int(pixel_h),
                    scale=int(reconcile_scale),
                    grid_size=float(grid_size),
                    use_cpp=use_cpp,
                    progress=progress,
                    tag=f"L{z:02d}",
                    cv2_simplify_mm=float(reconcile_cv2_simplify_mm),
                    cv2_min_area_px=int(cv2_min_area_px),
                )
            except Exception as e:
                logger.error(
                    f"[警告] L{z:02d} reconcile 失败，已回退到原矢量结果。原因={e}"
                )
                traceback.print_exc()

        # 保存结果
        if layer_polys:
            _save_layer_results(
                layer_polys,
                vtracer_dir,
                poly_dir,
                z,
                board_mm,
                pixel_w,
                pixel_h,
                jobs_req,
                mask_dir,
                slot_names,
                slot_preview_rgb,
                preview_4x,
            )

    # 质量检测
    _run_quality_checks(mask_dir, poly_dir, full_mask_bitmap)

    # 写入 Manifest
    write_manifest(
        output_dir=out_dir,
        version=VERSION,
        inputs=[manifest["image_name"]],
        outputs=[
            str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()
        ],
        params={
            "vector_backend": str(vector_backend).strip().lower(),
            "vtracer_params": vtracer_params,
            "cv2_params": {
                "simplify_mm": float(cv2_simplify_mm),
                "min_area_px": int(cv2_min_area_px),
            },
            "svg_simplify_params": {
                "level": int(svg_simplify_level),
                "max_diff_ratio": float(svg_simplify_max_diff_ratio),
                "min_diff_px": int(svg_simplify_min_diff_px),
                "tol_px": int(svg_simplify_tol_px),
                "perimeter_weight": float(svg_simplify_perimeter_weight),
                "max_attempts": int(svg_simplify_max_attempts),
            },
            "board_mm": board_mm,
            "n_layers": n_layers,
            "slot_names": slot_names,
            "layer_height_mm": layer_height_mm,
            "slot_preview_rgb": slot_preview_rgb,
            "resample_enabled": resample,
        },
    )
    logger.info(f"完成。矢量化产物已就绪。")
    logger.info(f"输出目录: {out_dir}")


def _simplify_layer_polys(
    layer_polys,
    mask_dir,
    z,
    slot_names_no_bg,
    background_slot,
    board_mm,
    pixel_w,
    pixel_h,
    grid_size,
    use_cpp,
    progress,
    svg_simplify_level,
    svg_simplify_max_diff_ratio,
    svg_simplify_min_diff_px,
    svg_simplify_tol_px,
    svg_simplify_perimeter_weight,
    svg_simplify_max_attempts,
):
    """简化图层多边形"""
    t_simp0 = perf_counter()
    mm_per_px_x = float(board_mm) / float(pixel_w)
    mm_per_px_y = float(board_mm) / float(pixel_h)
    mm_per_px = min(mm_per_px_x, mm_per_px_y)
    px_area_mm2 = float(mm_per_px_x) * float(mm_per_px_y)
    base_step_mm = max(mm_per_px / 2.0, 1e-6)
    post_step_mm = base_step_mm

    target_ratio = 0.25
    target_ratio_black = 0.08
    tol_factor = 3.0
    step_cap_mm = float(mm_per_px) * 4.0
    tol_growth = 2.0
    min_target_pts = 4000

    if svg_simplify_level == 2:
        target_ratio = 0.15
        target_ratio_black = 0.05
        tol_factor = 4.0
        step_cap_mm = float(mm_per_px) * 6.0
        tol_growth = 2.2
        min_target_pts = 2500
        post_step_mm = float(base_step_mm) * 1.5
    elif svg_simplify_level >= 3:
        target_ratio = 0.10
        target_ratio_black = 0.035
        tol_factor = 6.0
        step_cap_mm = float(mm_per_px) * 8.0
        tol_growth = 2.5
        min_target_pts = 1500
        post_step_mm = float(base_step_mm) * 2.0

    print_ts(
        f"[信息] L{z:02d} 开始SVG简化: level={int(svg_simplify_level)} mm_per_px={mm_per_px:.6f}"
    )

    simplified = {}
    total_before = 0
    total_after = 0

    ordered_simplify_slots = list(slot_names_no_bg)
    if background_slot:
        ordered_simplify_slots.append(background_slot)

    for slot_name in ordered_simplify_slots:
        p0 = layer_polys.get(slot_name)
        if p0 is None or getattr(p0, "is_empty", True):
            continue

        def _count_geom_points(g) -> int:
            if g is None or getattr(g, "is_empty", True):
                return 0
            gt = getattr(g, "geom_type", "")
            if gt == "Polygon":
                n = (
                    int(len(g.exterior.coords))
                    if getattr(g, "exterior", None) is not None
                    else 0
                )
                for ring in getattr(g, "interiors", []) or []:
                    n += int(len(ring.coords))
                return n
            if gt == "MultiPolygon":
                return sum(
                    _count_geom_points(gg) for gg in getattr(g, "geoms", []) or []
                )
            if gt == "GeometryCollection":
                return sum(
                    _count_geom_points(gg) for gg in getattr(g, "geoms", []) or []
                )
            return 0

        before_pts = _count_geom_points(p0)
        total_before += int(before_pts)

        if int(before_pts) < int(min_target_pts):
            simplified[slot_name] = p0
            total_after += int(before_pts)
            continue

        px_per_mm = float(pixel_w) / float(board_mm)
        base_tol_mm = float(base_step_mm) * float(tol_factor)
        per = float(getattr(p0, "length", 0.0))
        base_tol_mm = float(base_tol_mm) + float(svg_simplify_perimeter_weight) * float(
            per / float(max(int(before_pts), 1))
        )
        base_tol_mm = float(
            min(float(step_cap_mm), float(max(base_tol_mm, float(mm_per_px) * 0.25)))
        )

        try:
            orig_r = rasterize_geometry_soft(
                p0, pixel_w, pixel_h, board_mm, px_per_mm, supersample=1
            )
        except Exception as e:
            logger.error(
                f"[错误] L{z:02d} SVG简化：原始多边形栅格化失败，slot={slot_name}，原因={e}"
            )
            simplified[slot_name] = p0
            total_after += int(before_pts)
            continue

        if orig_r is None:
            logger.error(
                f"[错误] L{z:02d} SVG简化：原始多边形栅格化返回None，slot={slot_name}"
            )
            simplified[slot_name] = p0
            total_after += int(before_pts)
            continue

        orig_b = np.asarray(orig_r > 0.5, dtype=bool)
        orig_fg = int(np.count_nonzero(orig_b))
        if orig_fg <= 0:
            simplified[slot_name] = p0
            total_after += int(before_pts)
            continue

        slot_target_ratio = (
            float(target_ratio_black)
            if str(slot_name).upper() == "BLACK"
            else float(target_ratio)
        )
        best = None
        best_pts = int(before_pts)
        best_tol = None

        for i in range(int(svg_simplify_max_attempts)):
            tol_mm = float(base_tol_mm) * float(tol_growth ** float(i))
            tol_mm = float(min(float(step_cap_mm), tol_mm))
            if tol_mm <= 0.0:
                continue

            cand = p0.simplify(tol_mm, preserve_topology=True)
            if cand is None or getattr(cand, "is_empty", True):
                continue
            if not getattr(cand, "is_valid", True):
                cand = cand.buffer(0)
            if cand is None or getattr(cand, "is_empty", True):
                continue

            after_pts = _count_geom_points(cand)
            if int(after_pts) <= 0 or int(after_pts) >= int(best_pts):
                continue

            try:
                cand_r = rasterize_geometry_soft(
                    cand, pixel_w, pixel_h, board_mm, px_per_mm, supersample=1
                )
            except Exception as e:
                logger.error(
                    f"[错误] L{z:02d} SVG简化：候选多边形栅格化失败，slot={slot_name} tol={tol_mm:.6f}mm，原因={e}"
                )
                continue

            if cand_r is None:
                continue

            cand_b = np.asarray(cand_r > 0.5, dtype=bool)
            diff_px = int(np.count_nonzero(orig_b ^ cand_b))
            diff_ratio = float(diff_px) / float(max(orig_fg, 1))

            if (diff_px <= int(svg_simplify_min_diff_px)) or (
                diff_ratio <= float(svg_simplify_max_diff_ratio)
            ):
                best = cand
                best_pts = int(after_pts)
                best_tol = float(tol_mm)

                if float(best_pts) <= float(before_pts) * float(slot_target_ratio):
                    break

        if best is None:
            simplified[slot_name] = p0
            total_after += int(before_pts)
            continue

        if float(post_step_mm) > 0.0:
            post = best.simplify(float(post_step_mm), preserve_topology=True)
            if post is not None and (not getattr(post, "is_empty", True)):
                if not getattr(post, "is_valid", True):
                    post = post.buffer(0)
                if post is not None and (not getattr(post, "is_empty", True)):
                    best = post

        simplified[slot_name] = best
        total_after += int(_count_geom_points(best))
        logger.info(
            f"L{z:02d} SVG简化: slot={slot_name} pts {int(before_pts)} -> {int(best_pts)} tol={float(best_tol or 0.0):.6f}mm"
        )

    if simplified:
        for k, v in simplified.items():
            layer_polys[k] = v

    print_ts(f"[信息] L{z:02d} SVG简化完成，用时 {perf_counter() - t_simp0:.3f}s")


def _save_layer_results(
    layer_polys,
    vtracer_dir,
    poly_dir,
    z,
    board_mm,
    pixel_w,
    pixel_h,
    jobs_req,
    mask_dir,
    slot_names,
    slot_preview_rgb,
    preview_4x,
):
    """保存图层结果"""
    t_save0 = perf_counter()
    print_ts(f"[信息] L{z:02d} 开始落盘SVG与栅格化: 色块数={len(layer_polys)}")

    # 保存 vtracer_tool.svg
    for slot_name, final_poly in layer_polys.items():
        prefix = f"L{z:02d}_{slot_name}"
        tool_svg_path = vtracer_dir / f"{prefix}_vtracer_tool.svg"
        try:
            svg_text = _mm_geom_to_vtracer_tool_svg_text(
                final_poly,
                board_mm=float(board_mm),
                pixel_w=int(pixel_w),
                pixel_h=int(pixel_h),
            )
            tool_svg_path.write_text(svg_text, encoding="utf-8")
        except Exception as e:
            logger.error(
                f"[错误] 写回最终vtracer_tool.svg失败: layer=L{z:02d}, slot={slot_name}, 原因={e}"
            )
            traceback.print_exc()

    # 栅格化
    for slot_name, final_poly in layer_polys.items():
        prefix = f"L{z:02d}_{slot_name}"
        save_svg(final_poly, poly_dir / f"{prefix}_poly_final.svg", board_mm, board_mm)
        px_per_mm = float(pixel_w) / board_mm

        raster = rasterize_geometry_soft(
            final_poly, pixel_w, pixel_h, board_mm, px_per_mm, supersample=1
        )
        if raster is not None:
            Image.fromarray((raster * 255).astype(np.uint8)).save(
                poly_dir / f"{prefix}_poly_raster.png"
            )

        raster_4x = rasterize_geometry_soft(
            final_poly, pixel_w * 4, pixel_h * 4, board_mm, px_per_mm * 4, supersample=1
        )
        if raster_4x is not None:
            Image.fromarray((raster_4x * 255).astype(np.uint8)).save(
                poly_dir / f"{prefix}_poly_raster_4x.png"
            )

    print_ts(f"[信息] L{z:02d} 栅格化落盘完成，用时 {perf_counter() - t_save0:.3f}s")


def _run_quality_checks(mask_dir, poly_dir, full_mask):
    """运行质量检测"""
    logger.info("\n>>> 正在进行 02_masks (位图阶段) 质量检测...")
    try:
        t_chk0 = perf_counter()
        check_mask_overlaps(str(mask_dir), full_mask=full_mask, soft_edge_sigma_px=1.0)
        print_ts(f"[信息] 位图阶段质量检测完成，用时 {perf_counter() - t_chk0:.3f}s")
    except Exception as e:
        logger.error(f"位图重叠检测失败: {e}")

    logger.info("\n>>> 正在进行 04_polys (矢量阶段 4x) 质量检测...")
    try:
        t_chk1 = perf_counter()
        full_mask_bin_4x = None
        if full_mask is not None:
            fm = np.asarray(full_mask, dtype=bool)
            full_mask_bin_4x = np.repeat(np.repeat(fm, 4, axis=0), 4, axis=1)

        check_mask_overlaps(
            str(poly_dir),
            full_mask=full_mask_bin_4x,
            pattern="*_poly_raster_4x.png",
            output_suffix="_poly_4x_soft_tol1",
            binarize=False,
            boundary_tolerance_px=1,
            soft_edge_sigma_px=1.0,
        )
        print_ts(f"[信息] 矢量阶段4x质量检测完成，用时 {perf_counter() - t_chk1:.3f}s")
    except Exception as e:
        logger.error(f"矢量重叠检测失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenColor vtracer 矢量化器")
    parser.add_argument(
        "--input", type=str, default=None, help="gen_masks 的输出目录 (默认自动寻找)"
    )
    parser.add_argument(
        "--vector-backend",
        type=str,
        default="cv2",
        choices=["cv2", "vtracer"],
        help="矢量化后端",
    )
    parser.add_argument(
        "--cv2-simplify-mm", type=float, default=0.1, help="cv2 轮廓简化阈值(mm)"
    )
    parser.add_argument(
        "--cv2-min-area-px", type=int, default=4, help="cv2 轮廓最小面积阈值(px^2)"
    )
    parser.add_argument(
        "--impl",
        type=str,
        default="cpp",
        choices=["cpp", "python"],
        help="选择几何计算实现",
    )
    parser.add_argument(
        "--jobs", type=int, default=0, help="并行矢量化任务数，0 表示自动"
    )
    parser.add_argument(
        "--union-jobs", type=int, default=0, help="C++并集分块并行任务数，0 表示自动"
    )
    parser.add_argument(
        "--no-progress", action="store_true", help="关闭进度条与耗时预估输出"
    )
    parser.add_argument(
        "--preview-4x",
        action="store_true",
        default=False,
        help="生成每层彩色预览图(4x)",
    )
    parser.add_argument(
        "--reconcile",
        action="store_true",
        default=False,
        help="启用 reconcile(默认禁用，谨慎使用)",
    )
    parser.add_argument(
        "--no-reconcile", action="store_false", dest="reconcile", help="禁用 reconcile"
    )
    parser.add_argument(
        "--reconcile-scale", type=int, default=2, help="reconcile 栅格分辨率倍率"
    )
    parser.add_argument(
        "--reconcile-cv2-simplify-mm",
        type=float,
        default=0.05,
        help="reconcile 后 cv2 轮廓简化阈值(mm)",
    )
    parser.add_argument(
        "--resample",
        action="store_true",
        default=True,
        help="启用共享边界重采样 (默认)",
    )
    parser.add_argument(
        "--no-resample",
        action="store_false",
        dest="resample",
        help="禁用共享边界重采样",
    )
    parser.add_argument(
        "--svg-simplify-level",
        type=int,
        default=3,
        choices=[1, 2, 3],
        help="SVG简化强度等级",
    )

    args = parser.parse_args()

    try:
        run(
            mask_input_dir=args.input,
            resample=args.resample,
            impl=args.impl,
            progress=(not args.no_progress),
            jobs=args.jobs,
            union_jobs=args.union_jobs,
            preview_4x=args.preview_4x,
            vector_backend=args.vector_backend,
            cv2_simplify_mm=args.cv2_simplify_mm,
            cv2_min_area_px=args.cv2_min_area_px,
            reconcile=args.reconcile,
            reconcile_scale=args.reconcile_scale,
            reconcile_cv2_simplify_mm=args.reconcile_cv2_simplify_mm,
            svg_simplify_level=args.svg_simplify_level,
        )
    except KeyboardInterrupt:
        print_ts("[报时] 用户手动中断(Ctrl-C)")
        raise SystemExit(130)
