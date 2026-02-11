"""模型导出主模块

读取矢量多边形，转换为3D网格模型并导出
使用 oc_core_02 提供的功能，默认使用 C++ 加速
"""

import argparse
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from typing import Optional, Dict, Any, List, Tuple

import trimesh
from shapely.ops import unary_union

from oc_core_02.core.color_systems import ColorSystem
from oc_sdf.sdf_export import finalize_slot_mesh
from oc_sdf.sdf_extrude import extrude_layer_mesh
from oc_sdf.sdf_io import load_svg_polygons
from oc_core_02.utils.io_utils import start_heartbeat, print_ts
from oc_core_02.utils.manifest import write_manifest
from oc_core_02.utils.paths import get_out_dir, select_latest_subdir
from oc_proto.gen_3mf.geometry_bridge import check_cpp_available
from oc_proto.gen_3mf.interrupt_handler import (
    _install_interrupt_handlers,
    _hard_abort_if_interrupted,
)
from model_export.mesh_utils import _export_3mf


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
VERSION = "gen_model_exporter"


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
                "警告: 删除目录失败(可能被占用)，将重试 {}/{}: {}，原因={}",
                i + 1,
                tries,
                p,
                e,
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
                "警告: 删除文件失败(可能被占用)，将重试 {}/{}: {}，原因={}",
                i + 1,
                tries,
                p,
                e,
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
    poly_input_dir: str = None,
    *,
    use_cpp: bool = True,
    progress: bool = True,
    jobs: int = 0,
    repair: bool = True,
    simplify: bool = True,
    voxel_repair: bool = False,
    export_stl: bool = True,
    export_3mf: bool = True,
    use_cpp_union: bool = True,
):
    """运行模型导出流程"""
    hb = start_heartbeat("gen_model_exporter", 30.0)
    t_run0 = perf_counter()
    print_ts("[信息] gen_model_exporter 开始")

    _install_interrupt_handlers()

    import atexit

    def _on_exit():
        try:
            hb.set()
        finally:
            dt = perf_counter() - t_run0
            print_ts(f"[报时] gen_model_exporter 进程退出，总耗时 {dt:.1f}s")

    atexit.register(_on_exit)

    prototype_dir = Path(__file__).resolve().parent

    if poly_input_dir is None:
        poly_input_path = (prototype_dir.parent / "gen_vector" / "out").resolve()
    else:
        poly_input_path = Path(poly_input_dir).resolve()

    if not poly_input_path.exists():
        print_ts(f"[错误] 找不到矢量输入目录 {poly_input_path}")
        print_ts("[提示] 请确保已先运行 gen_vector 模块，或者手动通过 --input 指定路径")
        raise RuntimeError(f"矢量输入目录不存在: {poly_input_path}")

    def _pick_manifest_file(d: Path) -> Path | None:
        p1 = d / "manifest.json"
        if p1.exists():
            return p1
        p2 = d / "vtracer_manifest.json"
        if p2.exists():
            return p2
        return None

    def _looks_like_vector_run_dir(d: Path) -> bool:
        if _pick_manifest_file(d) is None:
            return False
        pd = d / "04_polys"
        if (not pd.exists()) or (not pd.is_dir()):
            return False
        try:
            return any(pd.glob("*.svg"))
        except OSError:
            return False

    if _looks_like_vector_run_dir(poly_input_path):
        poly_run_dir = poly_input_path
    else:
        cand = select_latest_subdir(poly_input_path, required_relpaths=["04_polys"])
        poly_run_dir = (
            cand
            if (cand is not None and _pick_manifest_file(cand) is not None)
            else None
        )

    if poly_run_dir is None:
        print_ts(f"[错误] 未在输入目录中找到可用的矢量运行子目录: {poly_input_path}")
        print_ts(
            "[提示] 期望目录结构: <out>/<文件名>_<hash6>/(manifest.json 或 vtracer_manifest.json) 与 04_polys/"
        )
        raise RuntimeError("未找到可用的矢量运行子目录")

    manifest_path = _pick_manifest_file(poly_run_dir)
    if manifest_path is None:
        print_ts(f"[错误] 找不到 Manifest 文件: {poly_run_dir}")
        raise RuntimeError("找不到 Manifest 文件")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    out_dir_base = get_out_dir(prototype_dir)
    run_id = str(poly_run_dir.name)

    def _make_fallback_out_dir() -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        return out_dir_base / f"{run_id}_run_{ts}"

    def _prepare_dirs(root_out: Path) -> tuple[Path, Path]:
        poly_d = root_out / "04_polys"
        model_d = root_out / "05_models"
        for d in [poly_d, model_d]:
            d.mkdir(parents=True, exist_ok=True)
            _clear_dir_keep_root(d)
        return poly_d, model_d

    out_dir = (out_dir_base / run_id).resolve()
    try:
        poly_dir, model_dir = _prepare_dirs(out_dir)
    except PermissionError as e:
        out_dir = _make_fallback_out_dir()
        logger.warning(
            "警告: 输出目录被占用，无法清理旧文件，将改为写入新目录: {}，原因={}",
            out_dir,
            e,
        )
        poly_dir, model_dir = _prepare_dirs(out_dir)

    print_ts("[信息] 正在同步矢量文件...")
    poly_files = list((poly_run_dir / "04_polys").glob("*.svg"))
    for p_file in _tqdm(
        poly_files, total=len(poly_files), desc="同步 04_polys", enabled=progress
    ):
        shutil.copy2(p_file, poly_dir / p_file.name)

    print_ts(f"[信息] 矢量文件同步完成: 数量={len(poly_files)}")

    def _get_param(key: str, default=None):
        if isinstance(manifest, dict) and key in manifest:
            v = manifest.get(key)
            return default if v is None else v
        params = manifest.get("params") if isinstance(manifest, dict) else None
        if isinstance(params, dict) and key in params:
            v = params.get(key)
            return default if v is None else v
        return default

    board_mm = _get_param("board_mm")
    n_layers = _get_param("n_layers")
    slot_names = _get_param("slot_names")
    layer_height_mm = _get_param("layer_height_mm", 0.12)

    image_name = _get_param("image_name")
    if not image_name:
        inputs = manifest.get("inputs") if isinstance(manifest, dict) else None
        if isinstance(inputs, list) and inputs:
            image_name = str(inputs[0])
        else:
            image_name = "unknown"

    if board_mm is None or n_layers is None or slot_names is None:
        print_ts(f"[错误] Manifest 缺少关键参数，无法继续: {manifest_path}")
        print_ts(
            "[提示] 请确保 gen_vector 输出目录包含 board_mm/n_layers/slot_names 信息"
        )
        raise RuntimeError("Manifest 缺少关键参数")

    print_ts(
        f"[信息] 参数: board_mm={float(board_mm):.3f}, layers={int(n_layers)}, slots={len(slot_names)}"
    )

    # 检查 C++ 模块
    if use_cpp:
        if not check_cpp_available():
            raise RuntimeError("C++ 几何模块不可用，但已启用 use_cpp=True")
        print_ts("[信息] C++ 加速已启用")
    else:
        print_ts("[信息] C++ 加速已禁用，使用纯 Python 实现")

    jobs_req = int(jobs)
    if jobs_req <= 0:
        import os

        jobs_req = max(1, int((os.cpu_count() or 1) - 1))

    logger.info("并行参数: jobs={}", jobs_req)
    logger.info(
        "导出选项: STL={}, 3MF={}, C++并集={}", export_stl, export_3mf, use_cpp_union
    )

    # 创建颜色系统
    slot_preview_rgb = _get_param("slot_preview_rgb", {})
    cs = ColorSystem.from_material_keys(name="ExportSystem", keys=slot_names)
    # 更新预览颜色（如果有）
    if slot_preview_rgb:
        cs.slot_preview_rgb.update({k: tuple(v) for k, v in slot_preview_rgb.items()})

    # 存储所有合并后的网格
    slot_meshes: Dict[str, trimesh.Trimesh] = {}
    mesh_report: Dict[str, Any] = {}

    # 处理每个槽位
    for slot_name in _tqdm(
        slot_names, total=len(slot_names), desc="处理槽位", enabled=progress
    ):
        t_slot0 = perf_counter()
        _hard_abort_if_interrupted(f"槽位 {slot_name}")

        # 收集所有层的几何体 - 使用并行加载
        print_ts(f"[进度] 槽位 {slot_name}: 开始收集几何体...")
        t_load0 = perf_counter()

        def _load_layer(z: int) -> Tuple[int, Any, float, float] | None:
            """加载单层，返回 (z, geom, svg_time, union_time) 或 None"""
            poly_path = poly_dir / f"L{z:02d}_{slot_name}_poly_final.svg"
            if not poly_path.exists():
                return None

            try:
                t_svg0 = perf_counter()
                polys = load_svg_polygons(poly_path)
                t_svg1 = perf_counter()
                svg_time = t_svg1 - t_svg0

                if not polys:
                    return None

                t_union0 = perf_counter()
                geom = unary_union(polys)
                t_union1 = perf_counter()
                union_time = t_union1 - t_union0

                if getattr(geom, "is_empty", True):
                    return None
                return (z, geom, svg_time, union_time)
            except Exception as e:
                logger.error("[错误] 解析SVG失败: {}，原因={}", poly_path.name, e)
                raise

        # 并行加载所有层
        slot_polys = []
        total_svg_time = 0.0
        total_union_time = 0.0

        with ThreadPoolExecutor(max_workers=min(n_layers, 4)) as executor:
            futures = {executor.submit(_load_layer, z): z for z in range(n_layers)}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    z, geom, svg_time, union_time = result
                    slot_polys.append((z, geom))
                    total_svg_time += svg_time
                    total_union_time += union_time

        # 按层数排序
        slot_polys.sort(key=lambda x: x[0])

        t_load1 = perf_counter()
        print_ts(
            f"[进度] 槽位 {slot_name}: 几何体收集完成，共 {len(slot_polys)} 层，总用时 {t_load1 - t_load0:.3f}s (SVG加载={total_svg_time:.3f}s, 合并={total_union_time:.3f}s)"
        )

        if not slot_polys:
            logger.info("[提示] 槽位 {} 没有有效几何体，跳过", slot_name)
            continue

        # 挤出每层为3D网格
        print_ts(f"[进度] 槽位 {slot_name}: 开始挤出 {len(slot_polys)} 层...")
        layer_meshes: List[trimesh.Trimesh] = []
        t_extrude0 = perf_counter()
        for z, poly in slot_polys:
            t_layer0 = perf_counter()
            try:
                meshes = extrude_layer_mesh(
                    z=z,
                    slot_name=slot_name,
                    poly=poly,
                    layer_height_mm=layer_height_mm,
                    use_cpp=use_cpp,  # 使用 C++ 加速挤出
                )
                layer_meshes.extend(meshes)
                t_layer1 = perf_counter()
                print_ts(
                    f"[进度] 槽位 {slot_name} 层 {z:02d}: 挤出完成，生成 {len(meshes)} 个网格，用时 {t_layer1 - t_layer0:.3f}s"
                )
            except Exception as e:
                logger.error(
                    "[错误] 挤出层失败: slot={}, layer={}, 原因={}", slot_name, z, e
                )
                if use_cpp:
                    raise
                continue
        t_extrude1 = perf_counter()
        print_ts(
            f"[进度] 槽位 {slot_name}: 挤出完成，共 {len(layer_meshes)} 个网格，总用时 {t_extrude1 - t_extrude0:.3f}s"
        )

        if not layer_meshes:
            logger.warning("[警告] 槽位 {} 没有生成任何网格，跳过", slot_name)
            continue

        # 使用 finalize_slot_mesh 合并层并导出
        print_ts(f"[进度] 槽位 {slot_name}: 开始合并层并导出...")
        t_finalize0 = perf_counter()
        try:
            cleaned_mesh, stl_path = finalize_slot_mesh(
                slot_name=slot_name,
                layer_meshes=layer_meshes,
                cs=cs,
                out_dir=model_dir,
                mesh_report=mesh_report,
                use_cpp_union=use_cpp and use_cpp_union,  # 使用 C++ 布尔运算
            )
            slot_meshes[slot_name] = cleaned_mesh
            t_finalize1 = perf_counter()
            print_ts(
                f"[进度] 槽位 {slot_name}: 处理完成 -> {stl_path.name}，finalize用时 {t_finalize1 - t_finalize0:.3f}s"
            )
        except Exception as e:
            logger.error(
                "[错误] finalize_slot_mesh 失败: slot={}, 原因={}", slot_name, e
            )
            raise

        t_slot1 = perf_counter()
        print_ts(f"[进度] 槽位 {slot_name}: 总计用时 {t_slot1 - t_slot0:.3f}s")

    # 导出 3MF（合并所有颜色）
    if export_3mf and slot_meshes:
        print_ts("[信息] 开始导出 3MF...")
        t_3mf0 = perf_counter()
        try:
            out_3mf = model_dir / "model_combined.3mf"
            _export_3mf(out_3mf, slot_meshes, slot_preview_rgb)
            t_3mf1 = perf_counter()
            print_ts(f"[进度] 3MF 导出完成，用时={t_3mf1 - t_3mf0:.3f}s")
        except Exception as e:
            logger.error("[错误] 3MF 导出失败: {}", e)
            raise  # 出错直接退出

    # 写入 Manifest
    write_manifest(
        output_dir=out_dir,
        version=VERSION,
        inputs=[image_name],
        outputs=[
            str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()
        ],
        params={
            "board_mm": board_mm,
            "n_layers": n_layers,
            "slot_names": slot_names,
            "layer_height_mm": layer_height_mm,
            "use_cpp": use_cpp,
            "use_cpp_union": use_cpp_union,
            "repair_enabled": repair,
            "simplify_enabled": simplify,
            "voxel_repair_enabled": voxel_repair,
            "export_stl": export_stl,
            "export_3mf": export_3mf,
        },
    )

    logger.info("完成。模型导出产物已就绪。")
    logger.info("输出目录: {}", out_dir)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="OpenColor 模型导出器")
    parser.add_argument(
        "--input", type=str, default=None, help="gen_vector 的输出目录 (默认自动寻找)"
    )
    parser.add_argument(
        "--no-cpp", action="store_true", help="禁用 C++ 加速（默认启用）"
    )
    parser.add_argument(
        "--no-cpp-union", action="store_true", help="禁用 C++ 布尔运算合并层"
    )
    parser.add_argument("--jobs", type=int, default=0, help="并行任务数，0 表示自动")
    parser.add_argument("--no-repair", action="store_true", help="禁用网格修复")
    parser.add_argument("--no-simplify", action="store_true", help="禁用网格简化")
    parser.add_argument(
        "--voxel-repair", action="store_true", help="启用体素修复（默认禁用）"
    )
    parser.add_argument("--no-stl", action="store_true", help="禁用 STL 导出")
    parser.add_argument("--no-3mf", action="store_true", help="禁用 3MF 导出")
    parser.add_argument("--no-progress", action="store_true", help="关闭进度条")

    args = parser.parse_args(argv)

    try:
        run(
            poly_input_dir=args.input,
            use_cpp=(not args.no_cpp),  # 默认启用 C++
            progress=(not args.no_progress),
            jobs=args.jobs,
            repair=(not args.no_repair),
            simplify=(not args.no_simplify),
            voxel_repair=args.voxel_repair,  # 默认禁用
            export_stl=(not args.no_stl),
            export_3mf=(not args.no_3mf),
            use_cpp_union=(not args.no_cpp_union),  # 默认启用 C++ 布尔运算
        )
    except RuntimeError as e:
        print_ts(f"[错误] {e}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        print_ts("[报时] 用户手动中断(Ctrl-C)")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
