"""SVG导出处理模块 - 提供SVG到3D模型的转换功能

该模块将SVG文件转换为3D打印可用的3MF/STL格式，主要功能包括：
- 解析SVG路径和填充颜色
- 将颜色分类到RGBW槽位
- 生成多材料3D模型
- 导出标准3MF和拓竹项目3MF
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

from oc_core_02.core.svg_processing import (
    get_viewbox,
    iter_svg_paths_with_group_transform,
    has_fill_spec,
    parse_fill_from_attrs,
    classify_rgb_to_rgbw_strict,
    classify_rgb_to_rgbw_nearest,
    approx_closed_rings_from_path,
    build_polygons_from_rings,
    transform_svg_units_to_mm,
    union_clean,
    extrude_polygon_to_mesh,
)
from oc_core_02.core.three_mf import export_bambu_project_3mf, export_standard_3mf
from . import upsert_library_item
from ..jobs import Job


def _unique_path(p: Path) -> Path:
    """生成唯一的文件路径，避免覆盖已有文件"""
    if not p.exists():
        return p
    for i in range(1, 1000):
        cand = p.with_name(f"{p.stem}_{i}{p.suffix}")
        if not cand.exists():
            return cand
    return p.with_name(f"{p.stem}_{int(time.time())}{p.suffix}")


def _get_float(params: Dict[str, Any], key: str, default: float) -> float:
    """从参数字典中获取浮点数值"""
    val = params.get(key, default)
    try:
        return float(val)
    except Exception as e:
        raise ValueError(f"{key} 参数无效: {val}") from e


def _get_int(params: Dict[str, Any], key: str, default: int) -> int:
    """从参数字典中获取整数值"""
    val = params.get(key, default)
    try:
        return int(val)
    except Exception as e:
        raise ValueError(f"{key} 参数无效: {val}") from e


def handle_svg_export(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
    """处理SVG导出任务

    参数:
        job: 任务对象
        params: 任务参数字典，包含svg_path、width_mm、thickness_mm等
        progress: 进度回调函数，接收(进度值, 阶段, 描述)

    返回:
        包含输出文件路径的结果字典
    """
    # 创建输出目录
    out_dir = Path(job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    stl_dir = out_dir / "stl"
    stl_dir.mkdir(parents=True, exist_ok=True)

    # 获取并验证SVG路径
    svg_path = params.get("svg_path") or params.get("input_path")
    if not svg_path:
        raise ValueError("缺少 svg_path")
    svg_path = str(svg_path)
    if not Path(svg_path).exists():
        raise FileNotFoundError(f"SVG 文件不存在: {svg_path}")

    # 获取处理参数
    width_mm = _get_float(params, "width_mm", 80.0)
    thickness_mm = _get_float(params, "thickness_mm", 0.8)
    tol_mm = _get_float(params, "tol_mm", 0.2)
    simplify_mm = _get_float(params, "simplify_mm", 0.15)
    min_area_mm2 = _get_float(params, "min_area_mm2", 0.2)
    palette_mode = str(params.get("palette_mode", "strict") or "strict").lower()
    palette_tol = _get_int(params, "palette_tol", 0)

    # 生成源文件哈希用于文件名
    src_hash = hashlib.md5(str(svg_path).encode("utf-8")).hexdigest()[:6]

    def _build_3mf_name(variant: str) -> str:
        """构建3MF文件名"""
        w = int(round(width_mm))
        t = int(round(thickness_mm * 100))
        return f"oc1_sv_{variant}_w{w}_t{t:03d}_i{src_hash}.3mf"

    progress(0.1, "prepare", "准备参数")

    # 解析SVG
    progress(0.25, "parse_svg", "解析 SVG")
    svg_attrs, paths = iter_svg_paths_with_group_transform(svg_path)
    vb_minx, vb_miny, vb_w, vb_h = get_viewbox(svg_attrs)
    if vb_w == 0 or vb_h == 0:
        raise ValueError("SVG 尺寸无效")

    # 计算缩放比例
    scale = width_mm / vb_w if vb_w != 0 else 1.0
    tol_units = tol_mm / scale if scale != 0 else tol_mm

    # 按颜色槽位分类路径
    buckets: Dict[str, List[Any]] = {"R": [], "G": [], "B": [], "W": []}
    skipped = 0
    auto_classified = 0

    for path, attrs, mat, fill_set, fill_value in paths:
        # 获取填充颜色
        if has_fill_spec(attrs):
            fill = parse_fill_from_attrs(attrs)
        else:
            fill = fill_value if fill_set else None
        if fill is None:
            skipped += 1
            continue

        # 根据调色板模式分类颜色
        key = None
        if palette_mode == "nearest":
            key = classify_rgb_to_rgbw_nearest(fill)
        elif palette_mode == "auto":
            key = classify_rgb_to_rgbw_strict(fill, tol=palette_tol)
            if key is None:
                key = classify_rgb_to_rgbw_nearest(fill)
                auto_classified += 1
        else:
            key = classify_rgb_to_rgbw_strict(fill, tol=palette_tol)

        if key is None:
            skipped += 1
            continue

        # 将路径转换为多边形并添加到对应槽位
        rings = approx_closed_rings_from_path(path, tol_units=tol_units, M=mat)
        polys_u = build_polygons_from_rings(rings)
        for p_u in polys_u:
            p_mm = transform_svg_units_to_mm(p_u, vb_minx, vb_miny, vb_h, scale)
            if p_mm.is_empty or p_mm.area < min_area_mm2:
                continue
            buckets[key].append(p_mm)

    # 生成网格
    progress(0.6, "mesh", "生成网格")
    base = params.get("name") or Path(svg_path).stem
    stl_paths: List[Path] = []
    slot_names: List[str] = []

    # 为每个槽位生成STL文件
    for key in ["R", "G", "B", "W"]:
        geom = union_clean(
            buckets[key], simplify_mm=simplify_mm, min_area_mm2=min_area_mm2
        )
        if geom is None:
            continue
        mesh = extrude_polygon_to_mesh(geom, thickness_mm)
        if mesh is None:
            continue
        out = stl_dir / f"{base}_{key}.stl"
        mesh.export(out)
        stl_paths.append(out)
        slot_names.append(key)

    if not stl_paths:
        raise ValueError("未生成任何 STL 输出")

    # 确定导出格式
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

    # 导出标准3MF
    if want_standard_3mf:
        progress(0.8, "export_3mf", "导出标准 3MF")
        standard_3mf_path_raw = params.get("standard_3mf_path")
        if standard_3mf_path_raw:
            standard_3mf_path = Path(standard_3mf_path_raw).parent / _build_3mf_name(
                "s"
            )
        else:
            standard_3mf_path = artifacts_dir / _build_3mf_name("s")
        standard_3mf_path.parent.mkdir(parents=True, exist_ok=True)
        standard_3mf_path = _unique_path(standard_3mf_path)
        export_standard_3mf(
            out_3mf=standard_3mf_path, stl_paths=stl_paths, slot_names=slot_names
        )

    # 导出拓竹项目3MF
    if want_bambu_3mf:
        progress(0.9, "export_bambu", "导出拓竹项目 3MF")
        from oc_core_02.core.app_paths import get_data_path

        template_path = Path(
            params.get("bambu_template")
            or get_data_path("bambu_3mf_template", "rgbw_cubes.3mf")
        )
        bambu_3mf_path_raw = params.get("bambu_3mf_path")
        if bambu_3mf_path_raw:
            bambu_3mf_path = Path(bambu_3mf_path_raw).parent / _build_3mf_name("b")
        else:
            bambu_3mf_path = artifacts_dir / _build_3mf_name("b")
        bambu_3mf_path.parent.mkdir(parents=True, exist_ok=True)
        bambu_3mf_path = _unique_path(bambu_3mf_path)
        export_bambu_project_3mf(
            out_3mf=bambu_3mf_path,
            template_3mf=template_path,
            stl_paths=stl_paths,
            slot_names=slot_names,
        )

    # 保存元数据
    meta = {
        "kind": "svg.export",
        "job_id": job.job_id,
        "svg_path": str(svg_path),
        "params": {
            "width_mm": width_mm,
            "thickness_mm": thickness_mm,
            "tol_mm": tol_mm,
            "simplify_mm": simplify_mm,
            "min_area_mm2": min_area_mm2,
            "palette_mode": palette_mode,
            "palette_tol": palette_tol,
        },
        "stats": {
            "skipped_paths": int(skipped),
            "auto_classified": int(auto_classified),
        },
        "artifacts": {
            "stls": [str(p) for p in stl_paths],
            "standard_3mf": str(standard_3mf_path) if standard_3mf_path else "",
            "bambu_3mf": str(bambu_3mf_path) if bambu_3mf_path else "",
        },
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 更新库项
    short_common = {
        "scheme": "oc1",
        "kind": "sv",
        "width_mm": int(round(width_mm)),
        "thickness_mm": float(thickness_mm),
        "src_hash": src_hash,
    }
    long = {"method": "svg.export", "job_id": job.job_id, "meta": meta}
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
        "stls": [str(p) for p in stl_paths],
        "standard_3mf": str(standard_3mf_path) if standard_3mf_path else "",
        "bambu_3mf": str(bambu_3mf_path) if bambu_3mf_path else "",
    }
