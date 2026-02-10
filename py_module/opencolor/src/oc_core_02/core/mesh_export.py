"""网格导出模块 - 提供体素网格转换和文件导出功能

本模块提供3D网格生成功能，包括：
- 体素体积到三角形网格的转换
- STL格式导出（支持C++加速）
- GLB格式导出
- 多网格合并
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, Tuple

import numpy as np
import trimesh

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

_CPP_STL_IMPORT_TRIED = False
_CPP_WRITE_BINARY_STL = None


def _get_cpp_write_binary_stl():
    global _CPP_STL_IMPORT_TRIED
    global _CPP_WRITE_BINARY_STL

    if _CPP_STL_IMPORT_TRIED:
        return _CPP_WRITE_BINARY_STL

    _CPP_STL_IMPORT_TRIED = True
    try:
        import opencolor_geometry as cpp_geometry

        _CPP_WRITE_BINARY_STL = getattr(cpp_geometry, "write_binary_stl_nogil", None)
        if _CPP_WRITE_BINARY_STL is None:
            logger.warning("C++ 几何模块已加载，但缺少 write_binary_stl_nogil，STL 将回退到 Python 导出")
        return _CPP_WRITE_BINARY_STL
    except Exception as e:
        logger.warning("导入 C++ 几何模块失败，STL 将回退到 Python 导出: {}", e)
        _CPP_WRITE_BINARY_STL = None
        return None


@dataclass
class VoxelGrid:
    """体素网格数据类
    
    Attributes:
        volume: 布尔数组 (z,y,x)
        voxel_size: 体素尺寸 (sx, sy, sz)
    """
    volume: np.ndarray  # 布尔数组 (z,y,x)
    voxel_size: Tuple[float, float, float]  # (sx, sy, sz)


def voxel_grid_to_mesh(grid: VoxelGrid, shrink: float = 0.0, weld_vertices: bool = True) -> trimesh.Trimesh:
    """将布尔体素体积转换为三角形网格。

    使用整数平板网格（轴对齐的盒子）来避免材质之间的层错位，
    并保持对切片器友好的几何形状。
    """
    vol = grid.volume.astype(np.uint8)
    if vol.ndim != 3:
        raise ValueError("volume 必须是 3D 的 (z,y,x)")
    if vol.max() == 0:
        return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False)

    z_layers, height, width = vol.shape

    occ = vol > 0

    try:
        from scipy.ndimage import label as _cc_label
    except Exception as e:
        _cc_label = None
        logger.warning("无法导入 scipy.ndimage.label，将跳过体素连通域拆分: {}", e)

    if _cc_label is not None:
        structure = np.zeros((3, 3, 3), dtype=np.int8)
        structure[1, 1, 1] = 1
        structure[0, 1, 1] = 1
        structure[2, 1, 1] = 1
        structure[1, 0, 1] = 1
        structure[1, 2, 1] = 1
        structure[1, 1, 0] = 1
        structure[1, 1, 2] = 1
        labels, n_components = _cc_label(occ.astype(np.uint8), structure=structure)
    else:
        labels = occ.astype(np.int32)
        n_components = 1 if bool(np.any(occ)) else 0

    def _mk_quads(indices: np.ndarray, face: str) -> tuple[np.ndarray, np.ndarray]:
        if indices.size == 0:
            return np.zeros((0, 3), dtype=np.float64), np.zeros((0, 3), dtype=np.int64)

        z = indices[:, 0].astype(np.float64)
        y = indices[:, 1].astype(np.float64)
        x = indices[:, 2].astype(np.float64)

        world_y = (float(height - 1) - y)

        x0 = x + float(shrink)
        x1 = (x + 1.0) - float(shrink)
        y0 = world_y + float(shrink)
        y1 = (world_y + 1.0) - float(shrink)
        z0 = z + float(shrink)
        z1 = (z + 1.0) - float(shrink)

        valid = (x1 > x0) & (y1 > y0) & (z1 > z0)
        if not bool(np.any(valid)):
            return np.zeros((0, 3), dtype=np.float64), np.zeros((0, 3), dtype=np.int64)

        x0 = x0[valid]
        x1 = x1[valid]
        y0 = y0[valid]
        y1 = y1[valid]
        z0 = z0[valid]
        z1 = z1[valid]
        n = int(x0.shape[0])

        if face == "+x":
            quads = np.stack(
                [
                    np.stack([x1, y0, z0], axis=1),
                    np.stack([x1, y1, z0], axis=1),
                    np.stack([x1, y1, z1], axis=1),
                    np.stack([x1, y0, z1], axis=1),
                ],
                axis=1,
            )
        elif face == "-x":
            quads = np.stack(
                [
                    np.stack([x0, y0, z0], axis=1),
                    np.stack([x0, y0, z1], axis=1),
                    np.stack([x0, y1, z1], axis=1),
                    np.stack([x0, y1, z0], axis=1),
                ],
                axis=1,
            )
        elif face == "+y":
            quads = np.stack(
                [
                    np.stack([x0, y1, z0], axis=1),
                    np.stack([x0, y1, z1], axis=1),
                    np.stack([x1, y1, z1], axis=1),
                    np.stack([x1, y1, z0], axis=1),
                ],
                axis=1,
            )
        elif face == "-y":
            quads = np.stack(
                [
                    np.stack([x0, y0, z0], axis=1),
                    np.stack([x1, y0, z0], axis=1),
                    np.stack([x1, y0, z1], axis=1),
                    np.stack([x0, y0, z1], axis=1),
                ],
                axis=1,
            )
        elif face == "+z":
            quads = np.stack(
                [
                    np.stack([x0, y0, z1], axis=1),
                    np.stack([x1, y0, z1], axis=1),
                    np.stack([x1, y1, z1], axis=1),
                    np.stack([x0, y1, z1], axis=1),
                ],
                axis=1,
            )
        elif face == "-z":
            quads = np.stack(
                [
                    np.stack([x0, y0, z0], axis=1),
                    np.stack([x0, y1, z0], axis=1),
                    np.stack([x1, y1, z0], axis=1),
                    np.stack([x1, y0, z0], axis=1),
                ],
                axis=1,
            )
        else:
            raise ValueError(f"未知面类型: {face}")

        verts = quads.reshape((-1, 3)).astype(np.float64)
        base = (np.arange(n, dtype=np.int64) * 4)[:, None]
        f1 = base + np.array([[0, 1, 2]], dtype=np.int64)
        f2 = base + np.array([[0, 2, 3]], dtype=np.int64)
        faces = np.concatenate([f1, f2], axis=0).astype(np.int64)
        return verts, faces

    meshes = []
    for cid in range(1, int(n_components) + 1):
        comp = labels == int(cid)
        if not bool(np.any(comp)):
            continue

        parts_v = []
        parts_f = []
        vert_offset = 0

        pad_x = np.pad(comp, ((0, 0), (0, 0), (1, 1)), mode="constant", constant_values=False)
        neg_x = pad_x[:, :, 1:-1] & ~pad_x[:, :, :-2]
        pos_x = pad_x[:, :, 1:-1] & ~pad_x[:, :, 2:]

        pad_y = np.pad(comp, ((0, 0), (1, 1), (0, 0)), mode="constant", constant_values=False)
        neg_y = pad_y[:, 1:-1, :] & ~pad_y[:, :-2, :]
        pos_y = pad_y[:, 1:-1, :] & ~pad_y[:, 2:, :]

        pad_z = np.pad(comp, ((1, 1), (0, 0), (0, 0)), mode="constant", constant_values=False)
        neg_z = pad_z[1:-1, :, :] & ~pad_z[:-2, :, :]
        pos_z = pad_z[1:-1, :, :] & ~pad_z[2:, :, :]

        for face_name, mask in (
            ("-x", neg_x),
            ("+x", pos_x),
            ("+y", neg_y),
            ("-y", pos_y),
            ("-z", neg_z),
            ("+z", pos_z),
        ):
            idx = np.argwhere(mask)
            v_part, f_part = _mk_quads(idx, face_name)
            if v_part.shape[0] == 0 or f_part.shape[0] == 0:
                continue
            parts_v.append(v_part)
            parts_f.append(f_part + int(vert_offset))
            vert_offset += int(v_part.shape[0])

        if not parts_v:
            continue

        mesh = trimesh.Trimesh(
            vertices=np.concatenate(parts_v, axis=0),
            faces=np.concatenate(parts_f, axis=0),
            process=False,
        )
        if bool(weld_vertices):
            mesh.merge_vertices()
            mesh.update_faces(mesh.unique_faces())
            mesh.process(validate=True)
        else:
            try:
                if hasattr(mesh, "remove_duplicate_faces"):
                    mesh.remove_duplicate_faces()
                if hasattr(mesh, "remove_unreferenced_vertices"):
                    mesh.remove_unreferenced_vertices()
                if hasattr(mesh, "fix_normals"):
                    mesh.fix_normals()
            except Exception as e:
                logger.error("体素网格基础清理失败: {}", e)
                raise

        meshes.append(mesh)

    if not meshes:
        return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False)

    mesh = trimesh.util.concatenate(meshes)

    sx, sy, sz = grid.voxel_size
    mesh.apply_scale([sx, sy, sz])
    return mesh


def export_stl(mesh: trimesh.Trimesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t0 = perf_counter()

    cpp_write = _get_cpp_write_binary_stl()
    if cpp_write is not None:
        v = np.ascontiguousarray(np.asarray(mesh.vertices, dtype=np.float64))
        f = np.ascontiguousarray(np.asarray(mesh.faces, dtype=np.int64))
        t_prep = perf_counter()
        cpp_write(v, f, str(path))
        t_done = perf_counter()
        logger.info(
            "STL 导出(C++二进制) 完成: {} | tri={}, 用时={:.3f}s (准备={:.3f}s, 写入={:.3f}s)",
            path.name, int(f.shape[0]), t_done - t0, t_prep - t0, t_done - t_prep
        )
        return

    mesh.export(str(path), file_type="stl")
    t_done = perf_counter()
    logger.info("STL 导出(Python) 完成: {} | 用时={:.3f}s", path.name, t_done - t0)


def export_glb(mesh: trimesh.Trimesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(path), file_type="glb")


def combine_meshes(meshes: Dict[str, trimesh.Trimesh]) -> trimesh.Trimesh:
    non_empty = [m for m in meshes.values() if m.vertices.shape[0] > 0 and m.faces.shape[0] > 0]
    if not non_empty:
        return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False)
    return trimesh.util.concatenate(non_empty)
