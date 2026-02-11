from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Callable, List

from oc_core_02.core.bitmap_pipeline import BitmapParams, process_bitmap
from oc_core_02.core.three_mf import export_bambu_project_3mf, export_standard_3mf
from . import upsert_library_item
from ..jobs import Job


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _unique_path(p: Path) -> Path:
    """生成唯一的文件路径，避免文件名冲突

    如果目标路径已存在，则在文件名后添加数字后缀（_1, _2, ...）
    如果数字后缀达到1000，则使用时间戳作为后缀

    参数:
        p: 目标文件路径

    返回:
        唯一的文件路径
    """
    if not p.exists():
        return p
    for i in range(1, 1000):
        cand = p.with_name(f"{p.stem}_{i}{p.suffix}")
        if not cand.exists():
            return cand
    return p.with_name(f"{p.stem}_{int(time.time())}{p.suffix}")


def handle_bitmap_export(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
    """处理位图导出任务

    将图像根据 LUT（颜色查找表）转换为多材料3D打印模型，
    支持导出为 STL 文件和 3MF 格式

    参数:
        job: 任务对象，包含输出目录等信息
        params: 任务参数字典，包含图像路径、LUT路径、颜色系统等
        progress: 进度回调函数，接收进度值(0-1)、状态和描述

    返回:
        包含导出文件路径的元数据字典

    异常:
        ValueError: 缺少必需的参数时抛出
    """
    out_dir = Path(job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    image_path = params.get("image_path")
    lut_path = params.get("lut_path")
    if not image_path:
        raise ValueError("缺少 image_path")
    if not lut_path:
        raise ValueError("缺少 lut_path")

    progress(0.1, "prepare", "准备参数")
    bp = BitmapParams(
        color_system=params.get("color_system", "RYBW"),
        nozzle_width_mm=float(params.get("nozzle_width_mm", 0.42)),
        target_width_mm=float(params.get("target_width_mm", 60.0)),
        layer_height_mm=float(params.get("layer_height_mm", 0.2)),
        n_layers=int(params.get("n_layers", 5)),
        alpha_threshold=int(params.get("alpha_threshold", 10)),
        auto_bg_remove=bool(params.get("auto_bg_remove", False)),
        bg_tol=int(params.get("bg_tol", 15)),
    )

    src_hash = hashlib.md5(f"{image_path}|{lut_path}".encode("utf-8")).hexdigest()[:6]

    def _build_3mf_name(variant: str) -> str:
        w = int(round(bp.target_width_mm))
        noz = int(round(bp.nozzle_width_mm * 100))
        lh = int(round(bp.layer_height_mm * 100))
        return f"oc1_bm_{variant}_cs{bp.color_system}_n{bp.n_layers}_w{w}_noz{noz:03d}_lh{lh:03d}_i{src_hash}.3mf"

    progress(0.35, "match_lut", "匹配 LUT")
    outputs = process_bitmap(str(image_path), str(lut_path), bp, out_dir)

    # 从 ALL_SYSTEMS 获取显式的 slot_names 顺序
    from oc_core_02.core.color_systems import ALL_SYSTEMS

    cs = ALL_SYSTEMS[bp.color_system]

    # 按 slot_names 显式排序收集 STL 路径
    stl_paths: List[Path] = []
    slot_names: List[str] = []

    debug_mode = os.environ.get("OC_DEBUG") == "1"

    for slot in cs.slot_names:
        key = f"stl_{slot}"
        if key in outputs:
            stl_paths.append(Path(outputs[key]))
            slot_names.append(slot)

    if debug_mode:
        order_str = " -> ".join(
            [f"{slot}:{Path(outputs[f'stl_{slot}']).name}" for slot in slot_names]
        )
        logger.info(f"[调试] STL 输出顺序(按槽位): {order_str}")

    # Optional: export 3MFs
    export_fmt_raw = params.get("output_format")
    export_fmt = str(export_fmt_raw or "stl").lower()
    has_standard_flag = "export_3mf_standard" in params
    has_bambu_flag = "export_3mf_bambu" in params
    default_standard_3mf = export_fmt_raw is None
    want_standard_3mf = (
        bool(params.get("export_3mf_standard"))
        if has_standard_flag
        else default_standard_3mf
    ) or export_fmt in {"3mf", "mf3"}
    want_bambu_3mf = (
        bool(params.get("export_3mf_bambu")) if has_bambu_flag else False
    ) or export_fmt in {"3mf", "mf3"}

    standard_3mf_path = None
    bambu_3mf_path = None

    if want_standard_3mf:
        progress(0.75, "export_3mf", "导出标准 3MF")
        # 优先使用指定的路径，否则保存在 artifacts 目录下
        standard_3mf_path = params.get("standard_3mf_path")
        if standard_3mf_path:
            standard_3mf_path = Path(standard_3mf_path)
            standard_3mf_path = standard_3mf_path.parent / _build_3mf_name("s")
        else:
            standard_3mf_path = artifacts_dir / _build_3mf_name("s")

        standard_3mf_path.parent.mkdir(parents=True, exist_ok=True)
        standard_3mf_path = _unique_path(standard_3mf_path)
        export_standard_3mf(
            out_3mf=standard_3mf_path, stl_paths=stl_paths, slot_names=slot_names
        )

    if want_bambu_3mf:
        progress(0.85, "export_bambu", "导出拓竹项目 3MF")
        from oc_core_02.core.app_paths import get_data_path

        # 优先使用指定的路径，否则保存在 artifacts 目录下
        bambu_3mf_path = params.get("bambu_3mf_path")
        if bambu_3mf_path:
            bambu_3mf_path = Path(bambu_3mf_path)
            bambu_3mf_path = bambu_3mf_path.parent / _build_3mf_name("b")
        else:
            bambu_3mf_path = artifacts_dir / _build_3mf_name("b")

        bambu_3mf_path.parent.mkdir(parents=True, exist_ok=True)
        bambu_3mf_path = _unique_path(bambu_3mf_path)

        # 解析 extruder_map
        extruder_map = None
        extruder_map_raw = params.get("extruder_map")
        if extruder_map_raw:
            if isinstance(extruder_map_raw, dict):
                extruder_map = {str(k): int(v) for k, v in extruder_map_raw.items()}
            elif isinstance(extruder_map_raw, str):
                try:
                    # 格式 "White:1,Red:2,Yellow:3,Blue:4"
                    extruder_map = {}
                    for item in extruder_map_raw.split(","):
                        k, v = item.split(":")
                        extruder_map[k.strip()] = int(v.strip())
                except Exception as e:
                    logger.error(f"[调试] 解析 extruder_map 字符串失败: {e}")

        template_path_raw = params.get("template_3mf") or params.get("bambu_template")
        if template_path_raw:
            template_path = Path(template_path_raw)
        else:
            template_path = Path(get_data_path("bambu_3mf_template", "rgbw_cubes.3mf"))

        export_bambu_project_3mf(
            out_3mf=bambu_3mf_path,
            template_3mf=template_path,
            stl_paths=stl_paths,
            slot_names=slot_names,
            extruder_map=extruder_map,
        )

    # Write meta.json for UI consumption
    meta = {
        "kind": "bitmap.export",
        "job_id": job.job_id,
        "image_path": str(image_path),
        "lut_path": str(lut_path),
        "params": {
            "color_system": bp.color_system,
            "nozzle_width_mm": bp.nozzle_width_mm,
            "target_width_mm": bp.target_width_mm,
            "layer_height_mm": bp.layer_height_mm,
            "n_layers": bp.n_layers,
            "alpha_threshold": bp.alpha_threshold,
            "auto_bg_remove": bp.auto_bg_remove,
            "bg_tol": bp.bg_tol,
        },
        "artifacts": {
            "preview2d": str(outputs.get("preview_2d")),
            "preview3d": str(outputs.get("preview_3d")),
            "stls": [str(p) for p in stl_paths],
            "standard_3mf": str(standard_3mf_path) if standard_3mf_path else "",
            "bambu_3mf": str(bambu_3mf_path) if bambu_3mf_path else "",
        },
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    short_common = {
        "scheme": "oc1",
        "kind": "bm",
        "cs": bp.color_system,
        "n_layers": int(bp.n_layers),
        "width_mm": int(round(bp.target_width_mm)),
        "nozzle_width_mm": float(bp.nozzle_width_mm),
        "layer_height_mm": float(bp.layer_height_mm),
        "src_hash": src_hash,
    }
    long = {"method": "bitmap.export", "job_id": job.job_id, "meta": meta}
    if standard_3mf_path:
        upsert_library_item(
            file_path=Path(standard_3mf_path),
            kind="model",
            short={**short_common, "variant": "s"},
            long=long,
        )
    if bambu_3mf_path:
        upsert_library_item(
            file_path=Path(bambu_3mf_path),
            kind="model",
            short={**short_common, "variant": "b"},
            long=long,
        )

    progress(1.0, "done", "完成")

    return {
        "out_dir": str(out_dir),
        "meta": str(out_dir / "meta.json"),
        "preview2d": str(outputs.get("preview_2d")),
        "preview3d": str(outputs.get("preview_3d")),
        "stls": [str(p) for p in stl_paths],
        "standard_3mf": str(standard_3mf_path) if standard_3mf_path else "",
        "bambu_3mf": str(bambu_3mf_path) if bambu_3mf_path else "",
    }
