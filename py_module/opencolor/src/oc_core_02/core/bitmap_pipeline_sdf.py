"""SDF 位图处理管道 - 使用 SDF 轮廓重建 + 挤出算法处理位图

此模块已按功能拆分为以下子模块:
- sdf_data_prep.py: 数据准备和层体积生成
- sdf_polygon_gen.py: 多边形生成和处理
- sdf_extrude.py: 层网格挤出
- sdf_export.py: 网格导出和 3MF 导出
- sdf_quality.py: 质量分析报告
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
from PIL import Image
from shapely.geometry import GeometryCollection
from shapely.ops import unary_union

from oc_sdf.sdf_polygon_gen import generate_slot_layer_polygon
from .bitmap_pipeline import (
    BitmapParams,
    _export_glb_column_preview
)
from .color_systems import ALL_SYSTEMS, ColorSystem

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 从拆分后的模块导入功能
from oc_sdf.sdf_data_prep import prepare_data, generate_layer_volumes
from oc_sdf.sdf_export import finalize_slot_mesh, export_3mf
from oc_sdf.sdf_extrude import extrude_layer_mesh
from oc_sdf.sdf_quality import generate_quality_report
from oc_sdf.sdf_types import SDFParams
from oc_sdf.sdf_utils import fallback_extrude_from_pixels

from model_export.types import MeshData, rgba_to_hex


def process_bitmap_sdf(
    image_path: str,
    lut_path: str,
    params: BitmapParams,
    sdf_params: SDFParams,
    out_dir: Path,
) -> Dict[str, Path]:
    """使用 SDF 轮廓重建 + 挤出算法处理位图"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cs: ColorSystem = ALL_SYSTEMS[params.color_system]

    # 1. & 2. 前处理和预览
    pil = Image.open(image_path).convert("RGBA")
    data = prepare_data(pil, params, sdf_params, lut_path)
    
    # 标准化目录
    input_dir = out_dir / "00_input"
    mask_dir = out_dir / "02_masks"
    vtracer_dir = out_dir / "03_vtracer"
    poly_dir = out_dir / "04_polys"
    gap_dir = out_dir / "05_gap"
    export_dir = out_dir / "06_export"
    
    for d in [input_dir, mask_dir, vtracer_dir, poly_dir, gap_dir, export_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 拷贝输入到 00_input (如果 image_path 不是已经在里面的话)
    try:
        shutil.copy2(image_path, input_dir / Path(image_path).name)
        shutil.copy2(lut_path, input_dir / Path(lut_path).name)
        with open(input_dir / "params.json", "w", encoding="utf-8") as f:
            json.dump({
                "bitmap_params": params.__dict__,
                "sdf_params": {k: v for k, v in sdf_params.__dict__.items() if not k.startswith("_")}
            }, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"输入文件拷贝或参数保存失败: {e}")

    preview2d_path = out_dir / "preview_2d.png"
    Image.fromarray(data["matched_rgb"], mode="RGB").save(preview2d_path)
    
    # 为了兼容旧逻辑，我们暂时保留 debug_root 变量名，但指向 out_dir
    debug_root = out_dir 

    glb_path = out_dir / "preview_3d.glb"
    try:
        _export_glb_column_preview(data["matched_rgb"], data["mask"], params, glb_path)
    except Exception as e:
        logger.error(f"导出 3D 预览失败 (可能是图像太大): {e}")

    # 3. 按层生成多边形并挤出
    volumes = generate_layer_volumes(params, cs, data["ys"], data["xs"], data["idxs"], data["match_h_px"], data["match_w_px"])
    
    stl_paths: Dict[str, Path] = {}
    meshes_for_3mf: List[Any] = []
    slot_names_for_3mf: List[str] = []
    filament_hex_for_3mf: List[str] = []
    
    layer_clip_polys: List[Dict[str, Any]] = [dict() for _ in range(params.n_layers)]
    layer_final_polys: List[Dict[str, Any]] = [dict() for _ in range(params.n_layers)]
    mesh_report: Dict[str, Any] = {}
    used_backends = set()

    # 每一层维护一个 occupied 多边形集合，用于互斥裁剪
    layer_occupied: List[Any] = [GeometryCollection() for _ in range(params.n_layers)]

    for slot_name in cs.slot_names:
        layer_meshes = []
        for z in range(params.n_layers):
            layer_mask = volumes[slot_name][z]
            if not np.any(layer_mask):
                continue

            slot_layer_poly, clip_poly, used_backend = generate_slot_layer_polygon(
                z, slot_name, layer_mask, data["grid_scale"], 
                data["match_h_px"], data["match_w_px"],
                params, sdf_params, layer_occupied[z], debug_root
            )
            
            if used_backend and used_backend != "none" and used_backend not in used_backends:
                logger.info(f"轮廓后端: {used_backend}")
                used_backends.add(used_backend)

            if clip_poly is not None and not clip_poly.is_empty:
                layer_clip_polys[z][slot_name] = clip_poly

            if slot_layer_poly is None or slot_layer_poly.is_empty:
                fb = fallback_extrude_from_pixels(layer_mask, z, params.nozzle_width_mm, params.layer_height_mm)
                if fb is not None:
                    layer_meshes.append(fb)
                continue

            layer_final_polys[z][slot_name] = slot_layer_poly
            
            # 更新同层已占用的区域
            try:
                layer_occupied[z] = unary_union([layer_occupied[z], slot_layer_poly])
            except Exception:
                layer_occupied[z] = unary_union([layer_occupied[z].buffer(0), slot_layer_poly.buffer(0)])

            # 挤出生成 Mesh
            layer_meshes.extend(extrude_layer_mesh(z, slot_name, slot_layer_poly, params.layer_height_mm))

        # 合并层 Mesh 并清理导出
        cleaned_mesh, stl_path = finalize_slot_mesh(slot_name, layer_meshes, cs, out_dir, mesh_report)
        stl_paths[slot_name] = stl_path

        meshes_for_3mf.append(MeshData(vertices=cleaned_mesh.vertices, faces=cleaned_mesh.faces))
        slot_names_for_3mf.append(slot_name)
        if slot_name in cs.slot_preview_rgb:
            r, g, b = cs.slot_preview_rgb[slot_name]
            filament_hex_for_3mf.append(rgba_to_hex((r, g, b, 255)))
        else:
            filament_hex_for_3mf.append("#888888")

    # 4. 生成质量分析报告
    generate_quality_report(params, cs, layer_clip_polys, layer_final_polys, volumes, data, debug_root)

    # 5. 导出 3MF
    bambu_3mf_path = export_3mf(image_path, out_dir, cs, meshes_for_3mf, slot_names_for_3mf, filament_hex_for_3mf)

    # 6. 保存网格分析报告
    try:
        (out_dir / "mesh_report.json").write_text(json.dumps(mesh_report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception: pass

    results = {
        "preview_2d": preview2d_path,
        "preview_3d": glb_path,
        **{f"stl_{k}": v for k, v in stl_paths.items()},
    }
    if bambu_3mf_path:
        results["bambu_3mf"] = bambu_3mf_path

    return results
