from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Callable

# 导入色盘相关的核心功能
from oc_calib.board import (
    BoardParams,
    DEFAULT_MATERIALS_8,
    create_board_spec,
    export_board_standard_3mf,
    export_board_stls,
    export_board_stls_from_spec,
    export_board_standard_3mf_from_spec,
    render_board_preview,
)
from oc_calib.calib_types import BoardSpec
from oc_scripts.stl.thick_grad_card import build_thickness_gradient_plate, add_bezel_feet, add_back_ribs
from . import upsert_library_item, _get_relative_path
from ..jobs import Job


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


def handle_board_generate(job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]) -> Dict[str, Any]:
    """处理色盘生成任务
    
    根据参数生成色盘规格文件、3MF模型、STL文件和预览图
    
    参数:
        job: 任务对象，包含输出目录等信息
        params: 任务参数字典，包含材料、行列数、单元格大小等
        progress: 进度回调函数，接收进度值(0-1)、状态和描述
        
    返回:
        包含生成文件路径的结果字典
    """
    out_dir = Path(job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    progress(0.05, "prepare", "准备参数")
    # 检查是否包含新格式的参数
    has_new_params = any(
        k in params
        for k in (
            "materials",
            "rows",
            "cols",
            "tileSizeMm",
            "tile_size_mm",
            "layerHeightMm",
            "layer_height_mm",
            "layers",
        )
    )

    # 根据参数格式创建 BoardParams 对象
    if has_new_params:
        rows = int(params.get("rows", 15))
        cols = int(params.get("cols", 15))
        data = max(1, min(15, int(min(rows, cols))))
        total = int(params.get("total_cells", data + 2))
        mats = params.get("materials")
        if not isinstance(mats, list) or not mats:
            mats = list(DEFAULT_MATERIALS_8)
        bp = BoardParams(
            n_layers=int(params.get("layers", params.get("n_layers", 5))),
            cell_size_mm=float(params.get("tileSizeMm", params.get("tile_size_mm", params.get("cell_size_mm", 6.0)))),
            layer_height_mm=float(params.get("layerHeightMm", params.get("layer_height_mm", params.get("layer_height_mm", 0.12)))),
            total_cells=int(total),
            data_cells=int(data),
            materials=mats,
        )
    else:
        bp = BoardParams(
            color_system=params.get("color_system", "RYBW"),
            n_layers=int(params.get("n_layers", 5)),
            cell_size_mm=float(params.get("cell_size_mm", 0.42)),
            layer_height_mm=float(params.get("layer_height_mm", 0.2)),
            total_cells=int(params.get("total_cells", 34)),
            data_cells=int(params.get("data_cells", 32)),
        )

    # 解析导出格式
    export_formats = params.get("export_formats")
    if not isinstance(export_formats, list) or not export_formats:
        export_formats = [params.get("export_format") or "3mf"]
    export_formats = [str(x).lower().strip() for x in export_formats if str(x).strip()]
    want_3mf = "3mf" in export_formats
    want_stl = "stl" in export_formats

    # 计算源哈希值，用于生成唯一标识
    extra_hash = ""
    if bp.materials is not None:
        try:
            extra_hash = json.dumps(bp.materials, ensure_ascii=False, sort_keys=True)
        except Exception:
            extra_hash = str(bp.materials)
    src_hash = hashlib.md5(
        f"{bp.color_system}|{bp.n_layers}|{bp.cell_size_mm}|{bp.layer_height_mm}|{bp.total_cells}|{bp.data_cells}|{extra_hash}".encode(
            "utf-8"
        )
    ).hexdigest()[:6]

    def _build_name(suffix: str) -> str:
        """构建文件名
        
        根据色盘参数生成规范的文件名
        
        参数:
            suffix: 文件后缀名
            
        返回:
            生成的文件名
        """
        if bp.materials is not None:
            m = len(bp.materials) if isinstance(bp.materials, list) else 0
            return f"oc1_bd_g_m{m}_d{bp.data_cells}_n{bp.n_layers}_i{src_hash}{suffix}"
        return f"oc1_bd_g_cs{bp.color_system}_n{bp.n_layers}_i{src_hash}{suffix}"

    progress(0.2, "spec", "生成色盘规格")
    spec = create_board_spec(bp)
    file_name = str(params.get("fileName") or params.get("file_name") or "").strip()
    if file_name:
        spec.name = file_name
    spec_path = _unique_path(out_dir / _build_name("_board_spec.json"))
    spec.save(spec_path)

    # 导出 3MF 文件
    out_3mf_path: Path | None = None
    if want_3mf:
        progress(0.35, "generate", "导出 3MF")
        out_3mf_path = _unique_path(out_dir / _build_name(".3mf"))
        export_board_standard_3mf(bp, out_3mf_path)

    # 导出 STL 文件
    renamed_stls: Dict[str, Path] = {}
    if want_stl:
        progress(0.55, "generate", "导出 STL")
        if bp.materials is not None:
            stls = export_board_stls_from_spec(spec, out_dir)
        else:
            stls = export_board_stls(bp, out_dir)
        for k, v in stls.items():
            p = Path(v)
            dst = _unique_path(p.with_name(_build_name(f"_{k}.stl")))
            p.rename(dst)
            renamed_stls[str(k)] = dst

    # 生成预览图
    progress(0.75, "preview", "生成预览")
    preview = render_board_preview(bp)
    preview_path = _unique_path(out_dir / _build_name("_preview.png"))
    preview.save(preview_path)

    # 使用相对路径存储文件路径
    meta = {
        "color_system": bp.color_system,
        "materials": bp.materials if isinstance(bp.materials, list) else None,
        "n_layers": bp.n_layers,
        "cell_size_mm": bp.cell_size_mm,
        "layer_height_mm": bp.layer_height_mm,
        "total_cells": bp.total_cells,
        "data_cells": bp.data_cells,
        "export_formats": export_formats,
        "board_spec": _get_relative_path(spec_path),
        "standard_3mf": _get_relative_path(out_3mf_path) if out_3mf_path else "",
        "stls": {k: _get_relative_path(v) for k, v in renamed_stls.items()},
        "preview": _get_relative_path(preview_path),
    }
    meta_path = out_dir / _build_name("_meta.json")
    meta_path = _unique_path(meta_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 构建简化的元数据
    short_common = {
        "scheme": "oc1",
        "kind": "bd",
        "variant": "g",
        "cs": bp.color_system,
        "n_layers": int(bp.n_layers),
        "src_hash": src_hash,
    }
    if bp.materials is not None and isinstance(bp.materials, list):
        short_common["m"] = int(len(bp.materials))
        short_common["data"] = int(bp.data_cells)
    long = {"method": "board.generate", "job_id": job.job_id, "meta": meta}

    # 将生成的文件添加到库中
    upsert_library_item(file_path=Path(spec_path), kind="json", short=short_common, long=long)
    upsert_library_item(
        file_path=Path(meta_path),
        kind="json",
        short={**short_common, "kind": "bd_meta"},
        long=long,
    )
    upsert_library_item(file_path=Path(preview_path), kind="color_plate", short=short_common, long=long)
    if out_3mf_path is not None:
        upsert_library_item(file_path=Path(out_3mf_path), kind="board_model", short=short_common, long=long)
    for _, p in renamed_stls.items():
        upsert_library_item(file_path=Path(p), kind="board_model", short=short_common, long=long)

    progress(1.0, "done", "完成")

    return {
        "out_dir": str(out_dir),
        "board_spec_path": str(spec_path),
        "standard_3mf": str(out_3mf_path) if out_3mf_path else "",
        "stls": [str(v) for v in renamed_stls.values()],
        "preview": str(preview_path),
        "meta": str(meta_path),
    }


def handle_board_export_from_spec(job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]) -> Dict[str, Any]:
    """从色盘规格文件导出模型
    
    读取已有的色盘规格文件，导出为 3MF 或 STL 格式
    
    参数:
        job: 任务对象，包含输出目录等信息
        params: 任务参数字典，包含规格文件路径和导出格式
        progress: 进度回调函数，接收进度值(0-1)、状态和描述
        
    返回:
        包含导出文件路径的结果字典
        
    异常:
        ValueError: 缺少 spec_path 参数
        FileNotFoundError: 规格文件不存在
    """
    out_dir = Path(job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spec_path = params.get("spec_path") or params.get("board_spec_path")
    if not spec_path:
        raise ValueError("缺少 spec_path 参数")
    spec_path = Path(str(spec_path))
    if not spec_path.exists():
        raise FileNotFoundError(spec_path)

    # 解析导出格式
    export_formats = params.get("export_formats")
    if not isinstance(export_formats, list) or not export_formats:
        export_formats = [params.get("export_format") or "3mf"]
    export_formats = [str(x).lower().strip() for x in export_formats if str(x).strip()]
    want_3mf = "3mf" in export_formats
    want_stl = "stl" in export_formats

    progress(0.1, "load", "读取色盘规格")
    spec = BoardSpec.load(spec_path)

    # 计算源哈希值
    src_hash = hashlib.md5(spec.to_json().encode("utf-8")).hexdigest()[:6]

    def _build_name(suffix: str) -> str:
        """构建文件名
        
        根据规格名称生成导出文件名
        
        参数:
            suffix: 文件后缀名
            
        返回:
            生成的文件名
        """
        safe = str(spec.name or "board").replace(" ", "_")
        return f"oc1_bd_export_{safe}_i{src_hash}{suffix}"

    # 导出 3MF 文件
    out_3mf_path: Path | None = None
    if want_3mf:
        progress(0.35, "export", "导出 3MF")
        out_3mf_path = _unique_path(out_dir / _build_name(".3mf"))
        export_board_standard_3mf_from_spec(spec, out_3mf_path)

    # 导出 STL 文件
    stls: Dict[str, Path] = {}
    if want_stl:
        progress(0.6, "export", "导出 STL")
        stls = export_board_stls_from_spec(spec, out_dir)
        renamed: Dict[str, Path] = {}
        for k, v in stls.items():
            p = Path(v)
            dst = _unique_path(p.with_name(_build_name(f"_{k}.stl")))
            p.rename(dst)
            renamed[k] = dst
        stls = renamed

    progress(1.0, "done", "完成")

    return {
        "out_dir": str(out_dir),
        "spec_path": str(spec_path),
        "standard_3mf": str(out_3mf_path) if out_3mf_path else "",
        "stls": [str(v) for v in stls.values()],
    }


def handle_quick_calib_card_generate(job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]) -> Dict[str, Any]:
    """生成快速校准卡
    
    生成一个厚度梯度板，用于打印机流量校准
    
    参数:
        job: 任务对象，包含输出目录等信息
        params: 任务参数字典，包含尺寸、厚度范围、网格密度等参数
        progress: 进度回调函数，接收进度值(0-1)、状态和描述
        
    返回:
        包含生成文件路径的结果字典
    """
    out_dir = Path(job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    progress(0.1, "prepare", "准备参数")
    # 解析参数
    w = float(params.get("w", 120.0))  # 板宽度（毫米）
    h = float(params.get("h", 80.0))   # 板高度（毫米）
    t_min = float(params.get("t_min", 0.20))  # 最小厚度（毫米）
    t_max = float(params.get("t_max", 1.20))  # 最大厚度（毫米）
    ny = int(params.get("ny", 220))    # Y方向网格数
    profile = params.get("profile", "ease")   # 厚度变化曲线类型
    reverse = bool(params.get("reverse", False))  # 是否反转厚度方向
    feet = bool(params.get("feet", True))   # 是否添加支脚
    ribs = bool(params.get("ribs", True))   # 是否添加加强筋

    progress(0.3, "generate", "生成基础梯度板")
    mesh = build_thickness_gradient_plate(
        W=w,
        H=h,
        t_min=t_min,
        t_max=t_max,
        ny=ny,
        thickness_profile=profile,
        reverse=reverse,
    )

    # 添加挡边支脚
    if feet:
        progress(0.6, "generate", "添加挡边支脚")
        top_t = t_max if not reverse else t_min
        mesh = add_bezel_feet(
            base=mesh,
            W=w,
            H=h,
            foot_depth=float(params.get("foot_depth", 2.5)),
            foot_thickness=float(params.get("foot_thickness", 10.0)),
            foot_height=float(params.get("foot_height", 10.0)),
            z_attach=top_t + 0.2,
        )

    # 添加加强筋
    if ribs:
        progress(0.8, "generate", "添加加强筋")
        mesh = add_back_ribs(
            base=mesh,
            W=w,
            H=h,
            rib_count=int(params.get("rib_count", 3)),
            rib_w=float(params.get("rib_w", 2.0)),
            rib_d=float(params.get("rib_d", 1.8)),
            rib_h=h,
            z0=max(t_min, 0.2) + 0.2,
            y_start=float(params.get("rib_y0", -40.0)),
            y_end=float(params.get("rib_y1", 10.0)),
        )

    # 导出 STL 文件
    out_path = out_dir / "thickness_gradient_card.stl"
    progress(0.9, "export", "导出 STL")
    mesh.export(str(out_path))

    progress(1.0, "done", "完成")
    return {
        "out_dir": str(out_dir),
        "stl": str(out_path),
    }
