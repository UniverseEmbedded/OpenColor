from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import trimesh
from PIL import Image

from model_export.standard_3mf import _export_standard_3mf_from_meshes_lib3mf
from oc_core_02.utils.logger import get_logger
from .color_systems import ALL_SYSTEMS, ColorSystem
from .mesh_export import VoxelGrid, voxel_grid_to_mesh, export_stl, export_glb
from .model_analysis import analyze_mesh, analyze_3mf_lib3mf

logger = get_logger(__name__)


@dataclass
class BitmapParams:
    """位图处理参数"""

    color_system: str = "RYBW"
    nozzle_width_mm: float = 0.42
    target_width_mm: float = 60.0
    layer_height_mm: float = 0.2
    n_layers: int = 5
    alpha_threshold: int = 10
    auto_bg_remove: bool = False
    bg_tol: int = 15


def _resize_nearest_rgba(img_rgba: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
    """使用最近邻插值调整RGBA图像大小"""
    pil = Image.fromarray(img_rgba, mode="RGBA")
    pil = pil.resize((new_w, new_h), resample=Image.Resampling.NEAREST)
    return np.array(pil, dtype=np.uint8)


def _mask_transparency_and_bg(
    img_rgba: np.ndarray, alpha_threshold: int, auto_bg_remove: bool, bg_tol: int
) -> np.ndarray:
    """根据透明度和背景色创建遮罩。

    说明：
    - 透明度遮罩：a >= alpha_threshold
    - 背景去除：仅移除**与边界连通**且颜色接近背景参考色的区域（避免误删图形内部的“背景色相近”像素）
    """
    a = img_rgba[..., 3]
    mask = a >= alpha_threshold

    if not auto_bg_remove:
        return mask

    # 背景参考色：左上角像素
    bg = img_rgba[0, 0, :3].astype(np.int16)
    rgb = img_rgba[..., :3].astype(np.int16)
    diff = np.abs(rgb - bg)
    close = diff.max(axis=-1) <= int(bg_tol)

    # 仅移除与边界连通的 close 区域（Flood Fill）
    h, w = close.shape
    visited = np.zeros_like(close, dtype=bool)

    from collections import deque

    q: deque[tuple[int, int]] = deque()

    def try_push(y: int, x: int) -> None:
        if 0 <= y < h and 0 <= x < w and (not visited[y, x]) and close[y, x]:
            visited[y, x] = True
            q.append((y, x))

    # 从四条边界入队
    for x in range(w):
        try_push(0, x)
        try_push(h - 1, x)
    for y in range(h):
        try_push(y, 0)
        try_push(y, w - 1)

    while q:
        y, x = q.popleft()
        try_push(y - 1, x)
        try_push(y + 1, x)
        try_push(y, x - 1)
        try_push(y, x + 1)

    # visited == True 的 close 像素视为背景，剔除
    bg_connected = visited
    mask = mask & (~bg_connected)
    return mask


def _flatten_lut(lut: np.ndarray) -> np.ndarray:
    """将LUT展平为一维数组"""
    if lut.ndim != 3 or lut.shape[0] != 32 or lut.shape[1] != 32 or lut.shape[2] != 3:
        raise ValueError("LUT must be shape (32,32,3)")

    lut_f = lut.astype(np.float32, copy=False)
    max_v = float(np.nanmax(lut_f)) if lut_f.size else 0.0
    min_v = float(np.nanmin(lut_f)) if lut_f.size else 0.0
    if 0.0 <= min_v and max_v <= 1.01:
        if os.environ.get("OC_DEBUG") == "1":
            logger.debug(
                "检测到 LUT 可能是 0..1 范围，将自动缩放到 0..255：min={:.6f}, max={:.6f}, dtype={}",
                min_v,
                max_v,
                lut.dtype,
            )
        lut_f = lut_f * 255.0
    return lut_f.reshape(-1, 3)


def match_pixels_to_lut(
    rgb_pixels: np.ndarray, lut_flat_rgb: np.ndarray, chunk: int = 8000
) -> np.ndarray:
    """为每个像素匹配最近的LUT索引

    rgb_pixels: (N,3) float32
    lut_flat_rgb: (1024,3) float32
    """
    p = rgb_pixels.astype(np.float32)
    c = lut_flat_rgb.astype(np.float32)
    c2 = (c * c).sum(axis=1)[None, :]  # (1,1024)
    idxs = np.empty((p.shape[0],), dtype=np.int32)

    for i in range(0, p.shape[0], chunk):
        pp = p[i : i + chunk]
        p2 = (pp * pp).sum(axis=1)[:, None]  # (chunk,1)
        dot = pp @ c.T  # (chunk,1024)
        dist2 = p2 + c2 - 2.0 * dot
        idxs[i : i + chunk] = dist2.argmin(axis=1).astype(np.int32)

    return idxs


def _precompute_base_m_digits(n_layers: int, m: int) -> np.ndarray:
    """预计算所有可能的 M 进制数字组合

    digits[idx, z] 给出层 z 的材料索引 (0..M-1)。
    """
    n = m**n_layers
    if n > 1000000:  # 避免内存爆炸
        return np.zeros((0, n_layers), dtype=np.int8)
    digits = np.zeros((n, n_layers), dtype=np.int8)
    for idx in range(n):
        x = idx
        for z in range(n_layers - 1, -1, -1):
            digits[idx, z] = x % m
            x //= m
    return digits


def _precompute_base4_digits(n_layers: int) -> np.ndarray:
    return _precompute_base_m_digits(n_layers, 4)


def process_bitmap(
    image_path: str,
    lut_path: str,
    params: BitmapParams,
    out_dir: Path,
) -> Dict[str, Path]:
    """处理位图并导出预览图和按材料分类的STL文件

    返回输出文件路径的字典。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    cs: ColorSystem = ALL_SYSTEMS[params.color_system]

    pil = Image.open(image_path).convert("RGBA")
    rgba = np.array(pil, dtype=np.uint8)

    # determine target pixel width/height
    target_w_px = max(1, int(round(params.target_width_mm / params.nozzle_width_mm)))
    aspect = rgba.shape[0] / float(rgba.shape[1])
    target_h_px = max(1, int(round(target_w_px * aspect)))

    rgba_small = _resize_nearest_rgba(rgba, target_w_px, target_h_px)

    mask = _mask_transparency_and_bg(
        rgba_small, params.alpha_threshold, params.auto_bg_remove, params.bg_tol
    )

    lut = np.load(lut_path)
    lut_flat = _flatten_lut(lut)

    rgb = rgba_small[..., :3].astype(np.float32)

    # build a list of pixels to match
    ys, xs = np.where(mask)
    if ys.size == 0:
        raise ValueError("No non-transparent pixels after masking.")

    pix = rgb[ys, xs]
    idxs = match_pixels_to_lut(pix, lut_flat)

    # matched preview image
    matched_rgb = np.zeros_like(rgb, dtype=np.uint8)
    matched_rgb[ys, xs] = np.clip(lut_flat[idxs], 0, 255).astype(np.uint8)

    preview2d = Image.fromarray(matched_rgb.astype(np.uint8), mode="RGB")
    preview2d_path = out_dir / "preview_2d.png"
    preview2d.save(preview2d_path)

    # 3D preview (voxel columns with color)
    glb_path = out_dir / "preview_3d.glb"
    _export_glb_column_preview(matched_rgb, mask, params, glb_path)

    # per-material voxel volumes
    digits = _precompute_base4_digits(params.n_layers)
    h, w = target_h_px, target_w_px
    volumes: Dict[str, np.ndarray] = {
        name: np.zeros((params.n_layers, h, w), dtype=bool) for name in cs.slot_names
    }

    # fill volumes
    for k in range(ys.size):
        y = int(ys[k])
        x = int(xs[k])
        d = digits[int(idxs[k])]  # (n_layers,)
        for z in range(params.n_layers):
            slot = int(d[z])
            volumes[cs.slot_names[slot]][z, y, x] = True

    stl_paths: Dict[str, Path] = {}
    meshes_for_3mf: Dict[str, trimesh.Trimesh] = {}
    slot_colors_for_3mf: Dict[str, Tuple[int, int, int, int]] = {}

    voxel_size = (
        params.nozzle_width_mm,
        params.nozzle_width_mm,
        params.layer_height_mm,
    )
    for slot_name in cs.slot_names:
        grid = VoxelGrid(volume=volumes[slot_name], voxel_size=voxel_size)
        mesh = voxel_grid_to_mesh(grid)

        try:
            analyze_mesh(mesh, f"算法1/{cs.name}/{slot_name}")
        except Exception as e:
            logger.warning("模型分析(通用网格)失败: {}", e)

        stl_path = out_dir / f"model_{cs.name}_{slot_name}.stl"
        export_stl(mesh, stl_path)
        stl_paths[slot_name] = stl_path

        meshes_for_3mf[slot_name] = mesh
        # 获取该插槽的颜色
        if slot_name in cs.slot_preview_rgb:
            r, g, b = cs.slot_preview_rgb[slot_name]
            slot_colors_for_3mf[slot_name] = (r, g, b, 255)
        else:
            slot_colors_for_3mf[slot_name] = (255, 255, 255, 255)

    # 导出 3MF (如果模块可用)
    bambu_3mf_path = None
    if meshes_for_3mf:
        try:
            # 寻找模板文件
            # 假设在项目根目录下的特定位置
            template_path = (
                Path(__file__).parents[5]
                / "py_module"
                / "model_export"
                / "assets"
                / "type32_cubes.3mf"
            )
            if template_path.exists():
                bambu_3mf_path = out_dir / f"{Path(image_path).stem}_bambu.3mf"
                _export_standard_3mf_from_meshes_lib3mf(
                    out_3mf=bambu_3mf_path,
                    meshes=meshes_for_3mf,
                    slot_names=cs.slot_names,
                    colors=slot_colors_for_3mf,
                )
        except Exception as e:
            logger.warning("导出 3MF 失败: {}", e)

    results = {
        "preview_2d": preview2d_path,
        "preview_3d": glb_path,
        **{f"stl_{k}": v for k, v in stl_paths.items()},
    }
    if bambu_3mf_path:
        results["bambu_3mf"] = bambu_3mf_path
        try:
            analyze_3mf_lib3mf(bambu_3mf_path)
        except Exception as e:
            logger.warning("3MF分析(lib3mf)失败: {}", e)

    return results


def _export_glb_column_preview(
    matched_rgb: np.ndarray, mask: np.ndarray, params: BitmapParams, path: Path
) -> None:
    """创建 GLB 预览：每个像素一个柱体，带有顶点颜色"""
    h, w = matched_rgb.shape[:2]

    # 如果像素过多，跳过 GLB 导出以防止崩溃
    MAX_PIXELS = 100000  # 10万像素大概是上限了
    active_pixels = np.sum(mask)
    if active_pixels > MAX_PIXELS:
        logger.info("跳过 3D 预览导出: 像素过多 ({} > {})", active_pixels, MAX_PIXELS)
        return

    col_h = params.n_layers * params.layer_height_mm

    boxes = []
    colors = []
    # 每个像素一个盒子；对于小图像这没问题
    for y in range(h):
        for x in range(w):
            if not bool(mask[y, x]):
                continue
            color = matched_rgb[y, x]
            # trimesh 期望每个顶点有 RGBA (0..255)
            rgba = np.array([color[0], color[1], color[2], 255], dtype=np.uint8)
            box = trimesh.creation.box(
                extents=[params.nozzle_width_mm, params.nozzle_width_mm, col_h]
            )
            # 放置使底部位于 z=0，x 向右，y 向下
            tx = x * params.nozzle_width_mm
            ty = (h - 1 - y) * params.nozzle_width_mm
            tz = col_h / 2.0
            box.apply_translation(
                [
                    tx + params.nozzle_width_mm / 2.0,
                    ty + params.nozzle_width_mm / 2.0,
                    tz,
                ]
            )
            # 顶点颜色
            box.visual.vertex_colors = np.tile(rgba, (box.vertices.shape[0], 1))
            boxes.append(box)

    if not boxes:
        empty = trimesh.Trimesh(
            vertices=np.zeros((0, 3)),
            faces=np.zeros((0, 3), dtype=np.int64),
            process=False,
        )
        export_glb(empty, path)
        return

    mesh = trimesh.util.concatenate(boxes)
    export_glb(mesh, path)
