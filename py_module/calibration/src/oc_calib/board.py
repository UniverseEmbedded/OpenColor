from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Mapping, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from oc_calib.board_spec import BoardSpec
from oc_core_02.utils.logger import get_logger
from oc_core_02.core.color_systems import ColorSystem, ALL_SYSTEMS
from oc_core_02.core.mesh_export import VoxelGrid, voxel_grid_to_mesh, export_stl
from oc_core_02.core.recipes import int_to_recipe

from model_export.standard_3mf import export_standard_3mf_from_meshes

logger = get_logger(__name__)

# 默认8色材料定义
DEFAULT_MATERIALS_8: List[Dict[str, Any]] = [
    {"name": "White", "rgba": [245, 245, 245, 255]},
    {"name": "Black", "rgba": [25, 25, 25, 255]},
    {"name": "Red", "rgba": [230, 70, 70, 255]},
    {"name": "Green", "rgba": [70, 210, 120, 255]},
    {"name": "Blue", "rgba": [80, 140, 240, 255]},
    {"name": "Cyan", "rgba": [70, 210, 210, 255]},
    {"name": "Magenta", "rgba": [220, 90, 210, 255]},
    {"name": "Yellow", "rgba": [240, 210, 90, 255]},
]


def _normalize_materials(materials: Any) -> List[Dict[str, Any]]:
    """标准化材料定义，确保格式正确并限制RGBA值在0-255范围内"""
    if not isinstance(materials, list) or not materials:
        return list(DEFAULT_MATERIALS_8)
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(materials):
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or f"M{i}")
        rgba = m.get("rgba")
        if not (isinstance(rgba, list) and len(rgba) >= 4):
            rgba = [255, 255, 255, 255]
        try:
            r = int(rgba[0])
            g = int(rgba[1])
            b = int(rgba[2])
            a = int(rgba[3])
        except Exception as e:
            logger.error("材料RGBA解析失败: idx={}, err={}", i, e)
            raise
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        a = max(0, min(255, a))
        out.append({"name": name, "rgba": [r, g, b, a]})
    if not out:
        return list(DEFAULT_MATERIALS_8)
    return out


@dataclass
class BoardParams:
    """校准板参数"""

    color_system: str = "RYBW"
    n_layers: int = 5
    cell_size_mm: float = 0.42
    layer_height_mm: float = 0.2

    total_cells: int = 34  # 总单元格数（含边框）
    data_cells: int = 32  # 数据单元格数（不含边框）

    materials: List[Dict[str, Any]] | None = None  # 自定义材料列表

    # AprilTag 选项
    enable_apriltag: bool = False  # 默认关闭以保持兼容性
    primary_tag_id: int = 0
    secondary_tag_id: int = 1
    tag_module_size: int = 2  # 每个 Tag 像素占用 2x2 个单元格 (2 * 0.42 = 0.84mm)
    tag_padding: int = 1  # Tag 与核心数据区域之间的间隔

    @property
    def tag_total_cells(self) -> int:
        return 8 * self.tag_module_size

    @property
    def total_cells_with_tag(self) -> int:
        # 核心 34x34 + 额外的 Tag 空间
        if not self.enable_apriltag:
            return self.total_cells
        return 34 + self.tag_total_cells + self.tag_padding

    @property
    def data_offset(self) -> int:
        """数据区域在总网格中的起始偏移量"""
        if not self.enable_apriltag:
            return 0
        return self.tag_total_cells + self.tag_padding


def get_apriltag_36h11_pattern(tag_id: int) -> np.ndarray:
    """使用 cv2.aruco 返回 tag36h11 的 8x8 位矩阵 (0=黑, 1=白)"""
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    # drawMarker 生成的是黑底白码，我们需要确保包含 1 像素的黑色边框
    # tag36h11 的核心是 6x6，加上黑边是 8x8
    marker_img = dictionary.generateImageMarker(tag_id, 8)
    # 转换为 0/1 矩阵 (cv2 生成的是 0/255)
    pattern = (marker_img > 127).astype(np.int8)
    return pattern


def get_apriltag_16h5_pattern(tag_id: int) -> np.ndarray:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_16h5)
    marker_img = dictionary.generateImageMarker(tag_id, 6)
    pattern = (marker_img > 127).astype(np.int8)
    return pattern


def build_board_volumes(params: BoardParams) -> Dict[str, np.ndarray]:
    """构建校准板的体素体积数据

    如果指定了自定义材料，则使用自定义材料模式
    否则使用颜色系统模式（支持 AprilTag）
    """
    if params.materials is not None:
        return build_board_volumes_from_materials(params)

    cs: ColorSystem = ALL_SYSTEMS[params.color_system]
    n = params.n_layers
    total = params.total_cells
    data = params.data_cells
    offset = params.data_offset

    all_digits = np.zeros((4**n, n), dtype=np.int8)
    for idx in range(4**n):
        all_digits[idx] = np.array(int_to_recipe(idx, n).layers, dtype=np.int8)

    board_digits = np.zeros((total, total, n), dtype=np.int8)

    for y_in in range(34):
        for x_in in range(34):
            y, x = y_in + offset, x_in + offset
            if 1 <= x_in <= 32 and 1 <= y_in <= 32:
                idx = (y_in - 1) * 32 + (y_in - 1)
                board_digits[y, x] = all_digits[idx]
            else:
                board_digits[y, x] = 0

    corner_xy_relative = {
        "TL": (0, 0),
        "TR": (33, 0),
        "BR": (33, 33),
        "BL": (0, 33),
    }
    slot_index = {name: i for i, name in enumerate(cs.slot_names)}
    for corner, (rx, ry) in corner_xy_relative.items():
        slot_name = cs.corner_marker_by_corner[corner]
        d = slot_index[slot_name]
        board_digits[ry + offset, rx + offset] = d

    if params.enable_apriltag:
        black_slot = 3
        white_slot = 0

        ms = params.tag_module_size
        ts = params.tag_total_cells

        p_pattern = get_apriltag_36h11_pattern(params.primary_tag_id)
        s_pattern = get_apriltag_36h11_pattern(params.secondary_tag_id)

        for my in range(8):
            for mx in range(8):
                val = p_pattern[my, mx]
                slot = white_slot if val == 1 else black_slot
                for dy in range(ms):
                    for dx in range(ms):
                        board_digits[my * ms + dy, mx * ms + dx] = slot

        s_start = total - ts
        for my in range(8):
            for mx in range(8):
                val = s_pattern[my, mx]
                slot = white_slot if val == 1 else black_slot
                for dy in range(ms):
                    for dx in range(ms):
                        board_digits[s_start + my * ms + dy, s_start + mx * ms + dx] = (
                            slot
                        )

    volumes: Dict[str, np.ndarray] = {}
    for slot_name in cs.slot_names:
        volumes[slot_name] = np.zeros((n, total, total), dtype=bool)

    for y in range(total):
        for x in range(total):
            digits = board_digits[y, x]
            for z in range(n):
                slot = int(digits[z])
                volumes[cs.slot_names[slot]][z, y, x] = True

    return volumes


def build_board_volumes_from_materials(params: BoardParams) -> Dict[str, np.ndarray]:
    """根据自定义材料构建校准板的体素体积数据"""
    mats = _normalize_materials(params.materials)
    data = int(params.data_cells or 15)
    total = int(params.total_cells or (data + 2))
    n = int(params.n_layers or 5)

    base = max(2, len(mats))

    volumes: Dict[str, np.ndarray] = {}
    for i, m in enumerate(mats):
        volumes[m["name"]] = np.zeros((n, total, total), dtype=bool)

    for y in range(total):
        for x in range(total):
            if 1 <= x <= data and 1 <= y <= data:
                idx = (y - 1) * data + (x - 1)
                layers = []
                temp = idx
                for _ in range(n):
                    layers.append(temp % base)
                    temp //= base
                for z, slot_idx in enumerate(layers):
                    if slot_idx < len(mats):
                        volumes[mats[slot_idx]["name"]][z, y, x] = True
            else:
                if len(mats) > 0:
                    volumes[mats[0]["name"]][0, y, x] = True

    return volumes


def render_board_preview(params: BoardParams, px_per_cell: int = 18) -> Image.Image:
    """渲染 2D 预览图像，显示每个单元格的顶层颜色

    这只是一个 UI 提示；实际的 LUT 取决于打印的半透明性和光照。
    """

    cs: ColorSystem = ALL_SYSTEMS[params.color_system]
    total = params.total_cells
    data = params.data_cells
    n = params.n_layers

    # Use top layer digits for preview
    img = Image.new("RGB", (total * px_per_cell, total * px_per_cell), (30, 30, 30))
    draw = ImageDraw.Draw(img)

    slot_index = {name: i for i, name in enumerate(cs.slot_names)}

    for y in range(total):
        for x in range(total):
            # corner overrides
            if (x, y) == (0, 0):
                color = cs.slot_preview_rgb[cs.corner_marker_by_corner["TL"]]
            elif (x, y) == (total - 1, 0):
                color = cs.slot_preview_rgb[cs.corner_marker_by_corner["TR"]]
            elif (x, y) == (total - 1, total - 1):
                color = cs.slot_preview_rgb[cs.corner_marker_by_corner["BR"]]
            elif (x, y) == (0, total - 1):
                color = cs.slot_preview_rgb[cs.corner_marker_by_corner["BL"]]
            # AprilTag override (Top Layer)
            elif (
                params.enable_apriltag
                and 2 <= x < 2 + params.tag_size_cells
                and 2 <= y < 2 + params.tag_size_cells
            ):
                p_pattern = get_apriltag_36h11_pattern(params.primary_tag_id)
                val = p_pattern[y - 2, x - 2]
                # 在预览图中强制使用纯黑白，确保检测器能识别
                color = (255, 255, 255) if val == 1 else (0, 0, 0)
            elif (
                params.enable_apriltag
                and (total - 2 - params.tag_size_cells) <= x < (total - 2)
                and (total - 2 - params.tag_size_cells) <= y < (total - 2)
            ):
                s_pattern = get_apriltag_36h11_pattern(params.secondary_tag_id)
                ts = params.tag_size_cells
                start_s = total - 2 - ts
                val = s_pattern[y - start_s, x - start_s]
                # 在预览图中强制使用纯黑白
                color = (255, 255, 255) if val == 1 else (0, 0, 0)
            # inner data area: fill recipes row-major
            elif 1 <= x <= data and 1 <= y <= data:
                idx = (y - 1) * data + (x - 1)
                digits = int_to_recipe(idx, n).layers
                d = digits[-1]
                color = cs.slot_preview_rgb[cs.slot_names[d]]
            else:
                color = cs.slot_preview_rgb[cs.slot_names[0]]

            x0 = x * px_per_cell
            y0 = y * px_per_cell
            draw.rectangle(
                [x0, y0, x0 + px_per_cell - 1, y0 + px_per_cell - 1], fill=color
            )

    # grid (skip tag areas)
    ts = params.tag_size_cells
    p_start = 2
    p_end = 2 + ts
    s_start = total - 2 - ts
    s_end = total - 2

    for i in range(total + 1):
        pos = i * px_per_cell

        # Vertical lines
        if params.enable_apriltag:
            # Check if line i is within primary or secondary tag x-range
            in_p_x = p_start <= i <= p_end
            in_s_x = s_start <= i <= s_end

            if in_p_x:
                # Top part (above primary tag)
                draw.line([pos, 0, pos, p_start * px_per_cell], fill=(0, 0, 0), width=1)
                # Bottom part (below primary tag)
                draw.line(
                    [pos, p_end * px_per_cell, pos, total * px_per_cell],
                    fill=(0, 0, 0),
                    width=1,
                )
            elif in_s_x:
                # Top part (above secondary tag)
                draw.line([pos, 0, pos, s_start * px_per_cell], fill=(0, 0, 0), width=1)
                # Bottom part (below secondary tag)
                draw.line(
                    [pos, s_end * px_per_cell, pos, total * px_per_cell],
                    fill=(0, 0, 0),
                    width=1,
                )
            else:
                draw.line([pos, 0, pos, total * px_per_cell], fill=(0, 0, 0), width=1)
        else:
            draw.line([pos, 0, pos, total * px_per_cell], fill=(0, 0, 0), width=1)

        # Horizontal lines
        if params.enable_apriltag:
            in_p_y = p_start <= i <= p_end
            in_s_y = s_start <= i <= s_end

            if in_p_y:
                # Left part
                draw.line([0, pos, p_start * px_per_cell, pos], fill=(0, 0, 0), width=1)
                # Right part
                draw.line(
                    [p_end * px_per_cell, pos, total * px_per_cell, pos],
                    fill=(0, 0, 0),
                    width=1,
                )
            elif in_s_y:
                # Left part
                draw.line([0, pos, s_start * px_per_cell, pos], fill=(0, 0, 0), width=1)
                # Right part
                draw.line(
                    [s_end * px_per_cell, pos, total * px_per_cell, pos],
                    fill=(0, 0, 0),
                    width=1,
                )
            else:
                draw.line([0, pos, total * px_per_cell, pos], fill=(0, 0, 0), width=1)
        else:
            draw.line([0, pos, total * px_per_cell, pos], fill=(0, 0, 0), width=1)

    return img


def export_board_stls(params: BoardParams, out_dir: Path) -> Dict[str, Any]:
    cs: ColorSystem = ALL_SYSTEMS[params.color_system]
    volumes = build_board_volumes(params)

    stl_paths: Dict[str, Path] = {}
    voxel_size = (params.cell_size_mm, params.cell_size_mm, params.layer_height_mm)

    for slot_name in cs.slot_names:
        grid = VoxelGrid(volume=volumes[slot_name], voxel_size=voxel_size)
        mesh = voxel_grid_to_mesh(grid)
        path = out_dir / f"calibration_board_{cs.name}_{slot_name}.stl"
        export_stl(mesh, path)
        stl_paths[slot_name] = path

    # 生成 BoardSpec
    spec = create_board_spec(params)
    spec_path = out_dir / "board_spec.json"
    spec.save(spec_path)

    return {"stls": stl_paths, "spec": spec_path}


def create_board_spec(params: BoardParams) -> BoardSpec:
    """根据参数创建 BoardSpec"""
    n = params.n_layers
    total = params.total_cells
    data = params.data_cells

    spec = BoardSpec(
        name=f"LBT Board {params.color_system} L{n}",
        rows=total,
        cols=total,
        cell_size_mm=params.cell_size_mm,
        markers={
            "TL": (0, 0),
            "TR": (total - 1, 0),
            "BR": (total - 1, total - 1),
            "BL": (0, total - 1),
        },
    )

    # 填充 cell_map
    for y in range(total):
        for x in range(total):
            if 1 <= x <= data and 1 <= y <= data:
                idx = (y - 1) * data + (x - 1)
                recipe = int_to_recipe(idx, n)
                spec.cell_map[f"{y},{x}"] = {
                    "recipe_index": idx,
                    "layers": recipe.layers,
                }

    # 添加 AprilTag 信息
    if params.enable_apriltag:
        cell_mm = params.cell_size_mm
        tag_size = params.tag_size_cells * cell_mm

        # Primary Tag (左上，靠近 TL marker 但留出静区)
        # 假设放在 (2, 2) 单元格开始
        p_x, p_y = 2.0 * cell_mm, 2.0 * cell_mm
        spec.apriltag["enabled"] = True
        spec.apriltag["primary"] = {
            "tag_id": params.primary_tag_id,
            "size_mm": tag_size,
            "board_corners_mm": [
                [p_x, p_y],
                [p_x + tag_size, p_y],
                [p_x + tag_size, p_y + tag_size],
                [p_x, p_y + tag_size],
            ],
        }

        # Secondary Tag (右下)
        s_x = (total - 2 - params.tag_size_cells) * cell_mm
        s_y = (total - 2 - params.tag_size_cells) * cell_mm
        spec.apriltag["secondary"] = {
            "tag_id": params.secondary_tag_id,
            "size_mm": tag_size,
            "board_corners_mm": [
                [s_x, s_y],
                [s_x + tag_size, s_y],
                [s_x + tag_size, s_y + tag_size],
                [s_x, s_y + tag_size],
            ],
        }
        spec.apriltag["id_encoding"] = {
            "scheme": "default",
            "primary_id": params.primary_tag_id,
            "secondary_id": params.secondary_tag_id,
        }

    return spec


def build_board_meshes_from_volumes(
    *,
    volumes: Dict[str, np.ndarray],
    cell_size_mm: float,
    layer_height_mm: float,
) -> Dict[str, Any]:
    """将体素体积数据转换为三角网格"""
    voxel_size = (float(cell_size_mm), float(cell_size_mm), float(layer_height_mm))
    meshes: Dict[str, Any] = {}
    for slot_name, vol in volumes.items():
        grid = VoxelGrid(volume=vol, voxel_size=voxel_size)
        meshes[slot_name] = voxel_grid_to_mesh(grid)
    return meshes


def build_board_volumes_from_spec(
    spec: BoardSpec,
) -> tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    """根据校准板规格构建体素体积数据"""
    pp = spec.print_profile or {}
    materials = pp.get("materials")
    slot_names = pp.get("slot_names")
    cs: ColorSystem | None = None
    color_system = None
    if not (
        isinstance(materials, list)
        and isinstance(slot_names, list)
        and len(materials) == len(slot_names)
        and len(slot_names) > 0
    ):
        color_system = str(pp.get("color_system") or "RYBW")
        cs = ALL_SYSTEMS[color_system]
        slot_names = list(cs.slot_names)
    n = int(pp.get("layers") or 5)
    total = int(spec.rows or 34)
    cell_size_mm = float(spec.cell_size_mm or 0.42)
    layer_height_mm = float(pp.get("layer_height_mm") or 0.2)

    volumes: Dict[str, np.ndarray] = {
        str(name): np.zeros((n, total, total), dtype=bool) for name in slot_names
    }

    for slot_name in slot_names:
        volumes[slot_name][:, :, :] = False

    volumes[slot_names[0]][:, :, :] = True

    markers = spec.markers or {}
    if cs is not None:
        slot_index = {name: i for i, name in enumerate(cs.slot_names)}
        for corner in ("TL", "TR", "BR", "BL"):
            pos = markers.get(corner)
            if not pos:
                continue
            x, y = int(pos[0]), int(pos[1])
            if x < 0 or y < 0 or x >= total or y >= total:
                continue
            slot_name = cs.corner_marker_by_corner.get(corner)
            if not slot_name:
                continue
            d = slot_index.get(slot_name)
            if d is None:
                continue
            for sn in cs.slot_names:
                volumes[sn][:, y, x] = False
            volumes[cs.slot_names[d]][:, y, x] = True
    else:
        corner_materials = [1, 2, 3, 4]
        corner_xy = {
            "TL": (0, 0),
            "TR": (total - 1, 0),
            "BR": (total - 1, total - 1),
            "BL": (0, total - 1),
        }
        for i, corner in enumerate(("TL", "TR", "BR", "BL")):
            x, y = corner_xy[corner]
            di = int(corner_materials[i]) if i < len(corner_materials) else 0
            di = max(0, min(di, len(slot_names) - 1))
            for sn in slot_names:
                volumes[sn][:, y, x] = False
            volumes[slot_names[di]][:, y, x] = True

    for key, raw in (spec.cell_map or {}).items():
        try:
            parts = str(key).split(",")
            if len(parts) < 2:
                continue
            y = int(parts[0])
            x = int(parts[1])
        except Exception as e:
            logger.error("解析格子坐标失败: key={}, err={}", key, e)
            raise

        if x < 0 or y < 0 or x >= total or y >= total:
            continue

        layers = None
        if isinstance(raw, Mapping):
            layers = raw.get("layers")
        if not isinstance(layers, list) or len(layers) == 0:
            continue

        for sn in slot_names:
            volumes[sn][:, y, x] = False

        for z, d in enumerate(layers[:n]):
            try:
                di = int(d)
            except Exception:
                di = 0
            di = max(0, min(di, len(slot_names) - 1))
            volumes[slot_names[di]][z, y, x] = True

    info = {
        "color_system": color_system or "",
        "layers": n,
        "cell_size_mm": cell_size_mm,
        "layer_height_mm": layer_height_mm,
        "total_cells": total,
        "slot_names": slot_names,
        "materials": materials if isinstance(materials, list) else None,
    }
    return volumes, info


def export_board_standard_3mf(params: BoardParams, out_3mf: Path) -> Path:
    """导出校准板为标准3MF格式文件"""
    volumes = build_board_volumes(params)
    meshes = build_board_meshes_from_volumes(
        volumes=volumes,
        cell_size_mm=params.cell_size_mm,
        layer_height_mm=params.layer_height_mm,
    )

    materials = (
        _normalize_materials(params.materials) if params.materials is not None else None
    )
    if materials is not None:
        slot_names_all = [
            str(m.get("name") or f"M{i}") for i, m in enumerate(materials)
        ]
        slot_colors: Dict[str, Tuple[int, int, int, int]] = {}
        for i, m in enumerate(materials):
            name = slot_names_all[i]
            r, g, b, a = m.get("rgba") or [255, 255, 255, 255]
            slot_colors[name] = (int(r), int(g), int(b), int(a))
        slot_names_used = [
            sn
            for sn in slot_names_all
            if meshes.get(sn) is not None
            and getattr(meshes[sn], "faces", None) is not None
            and len(meshes[sn].faces) > 0
        ]

        export_standard_3mf_from_meshes(
            out_3mf=out_3mf,
            meshes=meshes,
            slot_names=slot_names_used,
            slot_colors=slot_colors,
        )
        return out_3mf

    cs: ColorSystem = ALL_SYSTEMS[params.color_system]

    slot_names_used = [
        sn
        for sn in cs.slot_names
        if meshes.get(sn) is not None
        and getattr(meshes[sn], "faces", None) is not None
        and len(meshes[sn].faces) > 0
    ]
    slot_colors: Dict[str, Tuple[int, int, int, int]] = {
        sn: (
            int(cs.slot_preview_rgb[sn][0]),
            int(cs.slot_preview_rgb[sn][1]),
            int(cs.slot_preview_rgb[sn][2]),
            255,
        )
        for sn in cs.slot_names
        if sn in cs.slot_preview_rgb
    }

    export_standard_3mf_from_meshes(
        out_3mf=out_3mf,
        meshes=meshes,
        slot_names=slot_names_used,
        slot_colors=slot_colors,
    )
    return out_3mf


def export_board_standard_3mf_from_spec(spec: BoardSpec, out_3mf: Path) -> Path:
    """根据规格定义导出校准板为标准3MF格式文件"""
    volumes, info = build_board_volumes_from_spec(spec)
    mats = info.get("materials")
    slot_names_any = info.get("slot_names")
    if (
        isinstance(mats, list)
        and isinstance(slot_names_any, list)
        and len(mats) == len(slot_names_any)
        and len(slot_names_any) > 0
    ):
        slot_colors: Dict[str, Tuple[int, int, int, int]] = {}
        for i, m in enumerate(mats):
            name = str(slot_names_any[i])
            rgba = m.get("rgba") if isinstance(m, dict) else None
            if not (isinstance(rgba, list) and len(rgba) >= 4):
                rgba = [255, 255, 255, 255]
            slot_colors[name] = (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))
        meshes = build_board_meshes_from_volumes(
            volumes=volumes,
            cell_size_mm=float(info.get("cell_size_mm") or 0.42),
            layer_height_mm=float(info.get("layer_height_mm") or 0.2),
        )

        slot_names_used = [
            sn
            for sn in slot_names_any
            if meshes.get(sn) is not None
            and getattr(meshes[sn], "faces", None) is not None
            and len(meshes[sn].faces) > 0
        ]

        export_standard_3mf_from_meshes(
            out_3mf=out_3mf,
            meshes=meshes,
            slot_names=slot_names_used,
            slot_colors=slot_colors,
        )
        return out_3mf

    color_system = str(info.get("color_system") or "RYBW")
    cs: ColorSystem = ALL_SYSTEMS[color_system]
    meshes = build_board_meshes_from_volumes(
        volumes=volumes,
        cell_size_mm=float(info.get("cell_size_mm") or 0.42),
        layer_height_mm=float(info.get("layer_height_mm") or 0.2),
    )

    slot_names_used = [
        sn
        for sn in cs.slot_names
        if meshes.get(sn) is not None
        and getattr(meshes[sn], "faces", None) is not None
        and len(meshes[sn].faces) > 0
    ]
    slot_colors: Dict[str, Tuple[int, int, int, int]] = {
        sn: (
            int(cs.slot_preview_rgb[sn][0]),
            int(cs.slot_preview_rgb[sn][1]),
            int(cs.slot_preview_rgb[sn][2]),
            255,
        )
        for sn in cs.slot_names
        if sn in cs.slot_preview_rgb
    }

    export_standard_3mf_from_meshes(
        out_3mf=out_3mf,
        meshes=meshes,
        slot_names=slot_names_used,
        slot_colors=slot_colors,
    )
    return out_3mf


def export_board_stls_from_spec(spec: BoardSpec, out_dir: Path) -> Dict[str, Path]:
    """根据规格定义导出校准板各槽位的STL文件"""
    volumes, info = build_board_volumes_from_spec(spec)
    mats = info.get("materials")
    slot_names_any = info.get("slot_names")
    if (
        isinstance(mats, list)
        and isinstance(slot_names_any, list)
        and len(slot_names_any) > 0
    ):
        meshes = build_board_meshes_from_volumes(
            volumes=volumes,
            cell_size_mm=float(info.get("cell_size_mm") or 0.42),
            layer_height_mm=float(info.get("layer_height_mm") or 0.2),
        )

        stl_paths: Dict[str, Path] = {}
        for slot_name in slot_names_any:
            mesh = meshes.get(slot_name)
            path = out_dir / f"calibration_board_{slot_name}.stl"
            export_stl(mesh, path)
            stl_paths[str(slot_name)] = path
        return stl_paths

    color_system = str(info.get("color_system") or "RYBW")
    cs: ColorSystem = ALL_SYSTEMS[color_system]
    meshes = build_board_meshes_from_volumes(
        volumes=volumes,
        cell_size_mm=float(info.get("cell_size_mm") or 0.42),
        layer_height_mm=float(info.get("layer_height_mm") or 0.2),
    )

    stl_paths: Dict[str, Path] = {}
    for slot_name in cs.slot_names:
        mesh = meshes.get(slot_name)
        path = out_dir / f"calibration_board_{cs.name}_{slot_name}.stl"
        export_stl(mesh, path)
        stl_paths[slot_name] = path

    return stl_paths
