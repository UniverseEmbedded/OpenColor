from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Callable

import numpy as np
from tqdm import tqdm
from oc_xgb.color_space import lab_to_rgb01

# 导入色盘相关的核心功能
from oc_calib.board import (
    BoardParams,
    DEFAULT_MATERIALS_8,
    create_board_spec,
    export_board_stls,
    export_board_stls_from_spec,
    render_board_preview,
)
from oc_calib.board_spec import BoardSpec
from oc_scripts.stl.thick_grad_card import (
    build_thickness_gradient_plate,
    add_bezel_feet,
    add_back_ribs,
)
from . import upsert_library_item, _get_relative_path
from ..jobs import Job

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

# 导入 calib_board_gen 模块用于3MF导出
from oc_proto.calib_board_gen import generate_board as gen_bd


def _unique_path(p: Path) -> Path:
    """生成唯一的文件路径，避免文件名冲突

    如果目标路径已存在，则在文件名后添加字母后缀（_A, _B, ...）
    如果字母后缀用完（A-Z），则使用 AA, AB, ... 以此类推

    参数:
        p: 目标文件路径

    返回:
        唯一的文件路径
    """
    if not p.exists():
        return p
    
    # 生成字母后缀序列：A, B, C, ..., Z, AA, AB, ..., AZ, BA, BB, ...
    def _letter_suffix(n: int) -> str:
        """将数字转换为字母后缀（0->A, 1->B, ..., 25->Z, 26->AA, ...）"""
        suffix = ""
        while n >= 0:
            suffix = chr(ord('A') + (n % 26)) + suffix
            n = n // 26 - 1
            if n < 0:
                break
        return suffix
    
    for i in range(0, 1000):
        suffix = _letter_suffix(i)
        cand = p.with_name(f"{p.stem}_{suffix}{p.suffix}")
        if not cand.exists():
            return cand
    return p.with_name(f"{p.stem}_{int(time.time())}{p.suffix}")


def handle_board_generate(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
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
            "dataRows",
            "dataCols",
            "tileSizeMm",
            "tile_size_mm",
            "cellSizeMm",
            "layerHeightMm",
            "layer_height_mm",
            "layers",
        )
    )

    # 辅助函数：安全获取参数值，处理None情况
    def _get_float(params: Dict[str, Any], key: str, default: float) -> float:
        val = params.get(key)
        if val is None:
            return default
        return float(val)

    def _get_int(params: Dict[str, Any], key: str, default: int) -> int:
        val = params.get(key)
        if val is None:
            return default
        return int(val)

    # 根据参数格式创建 BoardParams 对象
    if has_new_params:
        # 支持新的参数格式：dataRows/dataCols 是数据格数量，总格子数需要+2（边框）
        data_rows = _get_int(params, "dataRows", 24)
        data_cols = _get_int(params, "dataCols", 24)
        rows = _get_int(params, "rows", data_rows + 2)
        cols = _get_int(params, "cols", data_cols + 2)
        data = min(data_rows, data_cols)
        total = max(rows, cols)
        mats = params.get("materials")
        if not isinstance(mats, list) or not mats:
            mats = list(DEFAULT_MATERIALS_8)
        bp = BoardParams(
            n_layers=_get_int(params, "layers", _get_int(params, "n_layers", 5)),
            cell_size_mm=_get_float(
                params, "cellSizeMm",
                _get_float(params, "tileSizeMm",
                _get_float(params, "tile_size_mm", _get_float(params, "cell_size_mm", 4.0)))
            ),
            layer_height_mm=_get_float(
                params, "layerHeightMm",
                _get_float(params, "layer_height_mm", _get_float(params, "layer_height_mm", 0.12))
            ),
            total_cells=int(total),
            data_cells=int(data),
            materials=mats,
        )
    else:
        bp = BoardParams(
            color_system=params.get("color_system", "RYBW"),
            n_layers=_get_int(params, "n_layers", 5),
            cell_size_mm=_get_float(params, "cell_size_mm", 4.0),
            layer_height_mm=_get_float(params, "layer_height_mm", 0.12),
            total_cells=_get_int(params, "total_cells", 26),
            data_cells=_get_int(params, "data_cells", 24),
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

    # 获取色盘编号（从file_name中提取，如 Board_A -> A）
    file_name = str(params.get("fileName") or params.get("file_name") or "").strip()
    board_letter = ""
    if file_name.startswith("Board_") and len(file_name) > 6:
        board_letter = f"_{file_name[6:]}"  # 提取 _A, _B, ...
    
    def _build_name(suffix: str) -> str:
        """构建文件名

        根据色盘参数生成规范的文件名，包含色盘编号后缀

        参数:
            suffix: 文件后缀名

        返回:
            生成的文件名
        """
        if bp.materials is not None:
            m = len(bp.materials) if isinstance(bp.materials, list) else 0
            return f"oc1_bd_g_m{m}_d{bp.data_cells}_n{bp.n_layers}_i{src_hash}{board_letter}{suffix}"
        return f"oc1_bd_g_cs{bp.color_system}_n{bp.n_layers}_i{src_hash}{board_letter}{suffix}"

    progress(0.2, "spec", "生成色盘规格")
    
    # 准备材料信息
    if bp.materials is not None:
        slot_names = [m["name"] for m in bp.materials]
        # 从 r, g, b 字段构建 rgba (webui传递的是r,g,b而不是rgba)
        slot_colors = {}
        for m in bp.materials:
            r = m.get("r", 255)
            g = m.get("g", 255)
            b = m.get("b", 255)
            slot_colors[m["name"]] = (r, g, b, 255)
    else:
        slot_names = [m["name"] for m in DEFAULT_MATERIALS_8]
        slot_colors = {m["name"]: tuple(m.get("rgba", [255, 255, 255, 255])) for m in DEFAULT_MATERIALS_8}
    
    # 构建配方池
    data_rows = bp.data_cells
    data_cols = bp.data_cells
    num_cells = data_rows * data_cols
    recipes = gen_bd.build_recipe_pool(
        layers=bp.n_layers,
        n_colors=len(slot_names),
        target_count=num_cells,
    )
    
    # 创建规格
    board_name = file_name if file_name else f"Board_{bp.color_system}"
    spec = gen_bd.build_board_spec(
        board_name=board_name,
        recipes=recipes,
        group_id=0,
        plate_index=0,
        slot_names=slot_names,
        layer_height_mm=bp.layer_height_mm,
        cell_size_mm=bp.cell_size_mm,
        data_rows=data_rows,
        data_cols=data_cols,
    )
    
    spec_path = _unique_path(out_dir / _build_name("_board_spec.json"))
    spec.save(spec_path)

    # 导出 3MF 文件 - 使用 oc_proto.calib_board_gen
    out_3mf_path: Path | None = None
    if want_3mf:
        progress(0.35, "generate", "导出 3MF")
        out_3mf_path = _unique_path(out_dir / _build_name(".3mf"))
        default_border_color = _get_default_border_color(slot_names)
        marker_colors = _build_marker_colors(slot_names)
        
        # 使用 calib_board_gen 的导出流程
        meshes_by_slot = gen_bd.spec_to_meshes(
            spec,
            shrink=float(params.get("shrink", 0.0)),
            slot_names=slot_names,
            marker_colors=marker_colors,
            default_border_color=default_border_color,
            include_apriltag=False,
            include_side_triangles=False,
            cell_size_mm=bp.cell_size_mm,
        )
        
        # 导出3MF
        gen_bd.export_standard_3mf(
            out_dir=out_dir,
            spec=spec,
            meshes_by_slot=meshes_by_slot,
            slot_names=slot_names,
            slot_colors=slot_colors,
        )
        
        # 重命名导出的文件以匹配预期名称
        expected_3mf = out_dir / f"{board_name.replace(' ', '_')}.3mf"
        if expected_3mf.exists() and expected_3mf != out_3mf_path:
            expected_3mf.rename(out_3mf_path)

    # 导出 STL 文件
    renamed_stls: Dict[str, Path] = {}
    if want_stl:
        progress(0.55, "generate", "导出 STL")
        if bp.materials is not None:
            stls = export_board_stls_from_spec(spec, out_dir)
        else:
            stls = export_board_stls(bp, out_dir)
        # 使用 tqdm 展示 STL 文件处理进度
        for k, v in tqdm(stls.items(), desc="  处理STL", total=len(stls), leave=False):
            p = Path(v)
            dst = _unique_path(p.with_name(_build_name(f"_{k}.stl")))
            p.rename(dst)
            renamed_stls[str(k)] = dst

    # 生成预览图
    progress(0.75, "preview", "生成预览")
    preview_params = {
        "profile_id": str(params.get("profile_id") or ""),
        "spec_path": str(spec_path),
    }
    preview_result = handle_board_preview(preview_params)
    preview = _render_preview_image(
        preview_result.get("cells", []),
        int(preview_result.get("rows", rows)),
        int(preview_result.get("cols", cols)),
        px_per_cell=18,
    )
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
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

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
    upsert_library_item(
        file_path=Path(spec_path), kind="json", short=short_common, long=long
    )
    upsert_library_item(
        file_path=Path(meta_path),
        kind="json",
        short={**short_common, "kind": "bd_meta"},
        long=long,
    )
    upsert_library_item(
        file_path=Path(preview_path), kind="color_plate", short=short_common, long=long
    )
    if out_3mf_path is not None:
        upsert_library_item(
            file_path=Path(out_3mf_path),
            kind="board_model",
            short=short_common,
            long=long,
        )
    for _, p in renamed_stls.items():
        upsert_library_item(
            file_path=Path(p), kind="board_model", short=short_common, long=long
        )

    progress(1.0, "done", "完成")

    return {
        "out_dir": str(out_dir),
        "board_spec_path": str(spec_path),
        "standard_3mf": str(out_3mf_path) if out_3mf_path else "",
        "stls": [str(v) for v in renamed_stls.values()],
        "preview": str(preview_path),
        "meta": str(meta_path),
    }


def handle_board_export_from_spec(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
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

    # 导出 3MF 文件 - 使用 oc_proto.calib_board_gen
    out_3mf_path: Path | None = None
    if want_3mf:
        progress(0.35, "export", "导出 3MF")
        out_3mf_path = _unique_path(out_dir / _build_name(".3mf"))
        
        # 从规格中提取材料信息
        slot_names = spec.slot_names if hasattr(spec, 'slot_names') else []
        if not slot_names and hasattr(spec, 'cell_map'):
            # 从cell_map推断slot_names
            all_colors = set()
            for cell in spec.cell_map.values():
                if hasattr(cell, 'layers'):
                    all_colors.update(cell.layers)
            slot_names = [f"Color_{i}" for i in sorted(all_colors)]
        
        # 构建slot_colors
        slot_colors = {}
        for i, name in enumerate(slot_names):
            # 使用默认颜色或从规格中读取
            slot_colors[name] = (255, 255, 255, 255)
        
        # 使用 calib_board_gen 的导出流程
        meshes_by_slot = gen_bd.spec_to_meshes(
            spec,
            shrink=float(params.get("shrink", 0.0)),
            slot_names=slot_names,
            marker_colors={"TL": slot_names[0] if slot_names else "White", 
                          "TR": slot_names[1 % len(slot_names)] if slot_names else "White",
                          "BR": slot_names[0] if slot_names else "White", 
                          "BL": slot_names[2 % len(slot_names)] if len(slot_names) > 2 else "White"},
            default_border_color=slot_names[0] if slot_names else "White",
            include_apriltag=False,
            include_side_triangles=False,
            cell_size_mm=float(getattr(spec, 'cell_size_mm', 4.0)),
        )
        
        # 导出3MF
        exported_path = gen_bd.export_standard_3mf(
            out_dir=out_dir,
            spec=spec,
            meshes_by_slot=meshes_by_slot,
            slot_names=slot_names,
            slot_colors=slot_colors,
        )
        
        # 重命名以匹配预期名称
        if exported_path.exists() and exported_path != out_3mf_path:
            exported_path.rename(out_3mf_path)

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


def handle_quick_calib_card_generate(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
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
    h = float(params.get("h", 80.0))  # 板高度（毫米）
    t_min = float(params.get("t_min", 0.20))  # 最小厚度（毫米）
    t_max = float(params.get("t_max", 1.20))  # 最大厚度（毫米）
    ny = int(params.get("ny", 220))  # Y方向网格数
    profile = params.get("profile", "ease")  # 厚度变化曲线类型
    reverse = bool(params.get("reverse", False))  # 是否反转厚度方向
    feet = bool(params.get("feet", True))  # 是否添加支脚
    ribs = bool(params.get("ribs", True))  # 是否添加加强筋

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


def handle_board_preview(
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """处理校准板预览请求

    从规格文件读取真实的校准板数据，包括每个格子的配方和预测颜色

    参数:
        params: 请求参数字典，包含profile_id和spec_path

    返回:
        包含格子数据的字典
    """
    import json
    from pathlib import Path

    # 解析参数
    profile_id = params.get("profile_id", "")
    spec_path = params.get("spec_path", "")

    if not spec_path:
        raise ValueError("必须提供spec_path参数")

    # 读取规格文件
    spec_file = Path(spec_path)
    if not spec_file.exists():
        raise FileNotFoundError(f"规格文件不存在: {spec_path}")

    with open(spec_file, 'r', encoding='utf-8') as f:
        spec = json.load(f)

    # 从规格文件读取配置
    rows = int(spec.get("rows", 26))
    cols = int(spec.get("cols", 26))
    cell_map = spec.get("cell_map", {})

    # 获取层数
    n_layers = 5
    for cell_data in cell_map.values():
        if isinstance(cell_data, dict) and "layers" in cell_data:
            layers_data = cell_data["layers"]
            if isinstance(layers_data, list) and len(layers_data) > 0:
                n_layers = len(layers_data)
                break

    # 获取标记颜色位置
    markers = spec.get("markers", {})
    corner_positions = {}
    for corner in ["TL", "TR", "BR", "BL"]:
        if corner in markers and isinstance(markers[corner], list) and len(markers[corner]) >= 2:
            x, y = markers[corner][0], markers[corner][1]
            corner_positions[(y, x)] = corner  # (row, col) -> corner

    color_names = _build_palette_from_cell_map(cell_map)
    if not color_names:
        from oc_proto.calib_board_gen.color_profiles import ColorProfileManager
        profile_manager = ColorProfileManager()
        profile = profile_manager.get_profile(profile_id)
        color_names = profile.color_names
    
    color_index = {name: idx for idx, name in enumerate(color_names)}
    default_border_color = _get_default_border_color(color_names)
    marker_colors = _build_marker_colors(color_names)

    # 生成格子数据
    cells = []

    for row in range(rows):
        for col in range(cols):
            key = f"{row},{col}"
            is_border = row == 0 or row == rows - 1 or col == 0 or col == cols - 1
            display_col = cols - 1 - col

            if key in cell_map:
                # 从规格文件读取真实配方
                cell_data = cell_map[key]
                if isinstance(cell_data, dict) and "layers" in cell_data:
                    recipe = [int(x) for x in cell_data["layers"]]
                else:
                    recipe = [0] * n_layers
            else:
                if is_border:
                    border_name = default_border_color
                    marker_name = None
                    corner = corner_positions.get((row, col))
                    if corner:
                        marker_name = marker_colors.get(corner)
                    if marker_name and marker_name in color_index:
                        recipe = [color_index[marker_name]] * n_layers
                    elif border_name in color_index:
                        recipe = [color_index[border_name]] * n_layers
                    else:
                        recipe = [0] * n_layers
                else:
                    recipe = [0] * n_layers

            # 使用RTS模型预测颜色（通过CPP模块）
            target_rgb = _predict_color_with_rts(recipe, profile_id, color_names)

            # 构建recipe字典
            recipe_dict = {str(i): float(idx) for i, idx in enumerate(recipe)}

            cells.append({
                "row": row,
                "col": display_col,
                "target_rgb": target_rgb,
                "recipe": recipe_dict,
            })

    return {
        "cells": cells,
        "rows": rows,
        "cols": cols,
        "dataRows": rows - 2,
        "dataCols": cols - 2,
    }


def _build_palette_from_cell_map(cell_map: Any) -> list[str] | None:
    if not isinstance(cell_map, dict):
        return None
    palette_candidate: list[str] | None = None
    palette_len = -1
    idx_to_name: Dict[int, str] = {}
    max_idx = -1
    for cell_data in cell_map.values():
        if not isinstance(cell_data, dict):
            continue
        layers = cell_data.get("layers")
        slot_names = cell_data.get("slot_names")
        if not isinstance(layers, list) or not isinstance(slot_names, list):
            continue
        layer_indices = []
        for v in layers:
            try:
                layer_indices.append(int(v))
            except Exception:
                continue
        if not layer_indices:
            continue
        max_layer_idx = max(layer_indices)
        if len(slot_names) != len(layer_indices) and len(slot_names) > max_layer_idx:
            if len(slot_names) > palette_len:
                palette_candidate = [str(n) for n in slot_names]
                palette_len = len(slot_names)
        for layer_pos, idx in enumerate(layer_indices):
            if layer_pos >= len(slot_names):
                continue
            name = str(slot_names[layer_pos])
            max_idx = max(max_idx, idx)
            existing = idx_to_name.get(idx)
            if existing is None:
                idx_to_name[idx] = name
            elif existing != name:
                logger.error("BoardSpec 材料索引冲突: {} -> {} / {}", idx, existing, name)
    if palette_candidate:
        return palette_candidate
    if max_idx >= 0:
        return [idx_to_name.get(i, "White") for i in range(max_idx + 1)]
    return None


def _get_default_border_color(slot_names: list[str]) -> str:
    if len(slot_names) == 3 and "Green" in slot_names:
        return "Green"
    if "White" in slot_names:
        return "White"
    return slot_names[0] if slot_names else "White"


def _build_marker_colors(slot_names: list[str]) -> dict:
    if all(name in slot_names for name in ["Blue", "Red", "Yellow"]):
        return {"TL": "Blue", "TR": "Red", "BR": "Blue", "BL": "Yellow"}
    if all(name in slot_names for name in ["Blue", "Red", "Green"]):
        return {"TL": "Blue", "TR": "Red", "BR": "Blue", "BL": "Green"}
    if slot_names:
        return {
            "TL": slot_names[0],
            "TR": slot_names[1 % len(slot_names)],
            "BR": slot_names[0],
            "BL": slot_names[2 % len(slot_names)],
        }
    return {"TL": "White", "TR": "White", "BR": "White", "BL": "White"}


def _predict_color_with_rts(recipe: list, profile_id: str, slot_names: list[str] | None = None) -> dict:
    """使用RTS模型预测配方颜色

    通过CPP模块的RTS预测功能计算颜色

    参数:
        recipe: 配方索引列表
        profile_id: 耗材组ID (如 "rgb", "rybw" 等)

    返回:
        RGB颜色字典
    """
    try:
        # 加载颜色配置获取材料信息
        from oc_proto.calib_board_gen.color_profiles import ColorProfileManager

        if slot_names is None:
            profile_manager = ColorProfileManager()
            profile = profile_manager.get_profile(profile_id)
            slot_names = profile.color_names
        rts_model = _load_rts_model_params()
        material_keys = rts_model["material_keys"]
        rts_index_map = {name.upper(): idx for idx, name in enumerate(material_keys)}
        mapped_recipe = []
        for idx in recipe:
            if idx < 0 or idx >= len(slot_names):
                raise ValueError(f"配方索引超出范围: {idx}")
            color_name = slot_names[idx]
            color_key = color_name.upper()
            if color_key not in rts_index_map:
                raise ValueError(f"RTS材料顺序不包含颜色: {color_name}")
            mapped_recipe.append(rts_index_map[color_key])

        # 尝试使用CPP模块进行RTS预测
        try:
            from oc_core_02.utils.bin_loader import import_cpp_extension

            opencolor_solver = import_cpp_extension("opencolor_solver")
            HillClimbingSolver = opencolor_solver.HillClimbingSolver

            optical = _build_default_optical_params(len(material_keys))
            n_layers = len(recipe)
            n_features = _calc_gpr_feature_count(len(material_keys), n_layers)
            gpr_L = _build_empty_gpr(n_features)
            gpr_a = _build_empty_gpr(n_features)
            gpr_b = _build_empty_gpr(n_features)
            feature_names = []

            solver = HillClimbingSolver(
                optical=optical,
                gpr_L=gpr_L,
                gpr_a=gpr_a,
                gpr_b=gpr_b,
                feature_names=feature_names,
                n_random_samples=100,
                hill_climb_iterations=10,
                n_layers=n_layers,
                layer_names_order=rts_model["layer_names_order"],
                use_vulkan=False
            )

            recipe_array = np.array([mapped_recipe], dtype=np.int32)
            predicted_lab = solver.predict_batch(recipe_array)

            # Lab -> RGB 0-1 -> RGB 0-255
            predicted_rgb01 = lab_to_rgb01(predicted_lab)
            r = int(predicted_rgb01[0][0] * 255)
            g = int(predicted_rgb01[0][1] * 255)
            b = int(predicted_rgb01[0][2] * 255)

            return {"r": r, "g": g, "b": b}

        except Exception as e:
            raise e

    except Exception as e:
        raise e


def _render_preview_image(cells: list, rows: int, cols: int, px_per_cell: int = 18) -> Image.Image:
    from PIL import Image, ImageDraw

    width = max(1, cols) * px_per_cell
    height = max(1, rows) * px_per_cell
    img = Image.new("RGB", (width, height), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        rgb = cell.get("target_rgb") or cell.get("targetRgb")
        if not isinstance(rgb, dict):
            continue
        try:
            r = int(rgb.get("r", 0))
            g = int(rgb.get("g", 0))
            b = int(rgb.get("b", 0))
            row = int(cell.get("row", 0))
            col = int(cell.get("col", 0))
        except Exception:
            continue
        x0 = col * px_per_cell
        y0 = row * px_per_cell
        x1 = x0 + px_per_cell - 1
        y1 = y0 + px_per_cell - 1
        draw.rectangle([x0, y0, x1, y1], fill=(r, g, b))
    return img


def _build_default_optical_params(n_materials: int) -> dict:
    rts_model = _load_rts_model_params()
    material_keys = rts_model["material_keys"]
    if n_materials != len(material_keys):
        raise ValueError(f"RTS材料数量不匹配: 请求={n_materials} 模型={len(material_keys)}")

    alpha_data = rts_model["alpha"]
    beta_data = rts_model["beta"]
    gamma_data = rts_model["gamma"]

    alpha_flat = []
    beta_flat = []
    for i in range(n_materials):
        alpha_flat.extend(alpha_data[i])
        beta_flat.extend(beta_data[i])

    return {
        "alpha": alpha_flat,
        "beta": beta_flat,
        "gamma": gamma_data,
        "n_layers": rts_model["n_layers"],
        "k1": 1.0,
        "k2": 1.0,
        "backing": 0.5,
        "material_keys": material_keys,
    }


@lru_cache(maxsize=1)
def _load_rts_model_params() -> dict:
    rts_path = Path(__file__).resolve().parents[5] / "py_module" / "prototypes" / "src" / "oc_proto" / "calib_color_rts" / "out" / "models" / "rts_vulkan" / "rts_model.json"
    data = json.loads(rts_path.read_text(encoding="utf-8"))
    params = data.get("params")
    if not params:
        raise ValueError("RTS模型缺少params")
    material_keys = data.get("material_keys")
    if not material_keys:
        raise ValueError("RTS模型缺少material_keys")
    layer_names_order = data.get("layer_names_order") or "bottom_first"
    return {
        "alpha": params.get("alpha"),
        "beta": params.get("beta"),
        "gamma": params.get("gamma"),
        "material_keys": material_keys,
        "layer_names_order": layer_names_order,
        "n_layers": data.get("n_layers", 5),
    }


def _calc_gpr_feature_count(n_materials: int, n_layers: int) -> int:
    n_classes = n_materials + 1
    seq_feat_dim = n_layers * n_classes + n_classes * n_classes + 2 + n_classes
    return n_materials + 1 + 1 + 1 + 3 + seq_feat_dim + 3


def _build_empty_gpr(n_features: int) -> dict:
    return {
        "X_train": np.zeros((1, n_features), dtype=np.float32),
        "alpha": np.zeros((1,), dtype=np.float32),
        "x_mean": np.zeros((n_features,), dtype=np.float32),
        "x_std": np.ones((n_features,), dtype=np.float32),
        "y_mean": 0.0,
        "y_std": 1.0,
        "lengthscale": 0.1,
        "signal_var": 1.0,
        "noise": 1e-7,
    }
