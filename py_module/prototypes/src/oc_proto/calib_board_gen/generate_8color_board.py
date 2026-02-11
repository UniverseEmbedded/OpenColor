# 支持类型注解的导入（Python 3.7+）
from __future__ import annotations

# 导入路径处理模块
from pathlib import Path
# 导入类型提示模块
from typing import Dict, List, Tuple, TYPE_CHECKING
# 导入迭代工具模块
import itertools
# 导入数值计算模块
import numpy as np


# 导入校准板规格模块
from oc_calib.board_spec import BoardSpec
# 导入网格导出相关模块
from oc_core_02.core.mesh_export import VoxelGrid, voxel_grid_to_mesh
# 导入模型导出相关模块
from model_export.standard_3mf import export_standard_3mf_from_meshes
# 导入三角网格处理库
import trimesh

from oc_core_02.core.model_analysis import analyze_mesh as _analyze_mesh_cpp

from oc_sdf.sdf_mesh import clean_mesh as _clean_mesh

from oc_core_02.utils.bin_loader import import_cpp_extension

from oc_core_02.utils.logger import get_logger

if TYPE_CHECKING:
    from .color_profiles import ColorProfile

logger = get_logger(__name__)

_CPP_GEOM = None


def _get_cpp_geometry():
    global _CPP_GEOM
    if _CPP_GEOM is not None:
        return _CPP_GEOM
    try:
        _CPP_GEOM = import_cpp_extension("opencolor_geometry")
    except Exception as e:
        from oc_core_02.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.warning("导入 C++几何模块失败，将跳过3D并集合并: {}", e)
        _CPP_GEOM = None
        return None

    return _CPP_GEOM


def _union_meshes(meshes: List[trimesh.Trimesh], slot_name: str) -> trimesh.Trimesh:
    non_empty = [m for m in meshes if m.vertices.shape[0] > 0 and m.faces.shape[0] > 0]
    if not non_empty:
        return _empty_mesh()
    if len(non_empty) == 1:
        return non_empty[0]

    cpp_geometry = _get_cpp_geometry()
    if cpp_geometry is None:
        return trimesh.util.concatenate(non_empty)

    union_fn = getattr(cpp_geometry, "manifold_union_nogil", None) or getattr(cpp_geometry, "manifold_union", None)
    if union_fn is None:
        return trimesh.util.concatenate(non_empty)

    try:
        items = []
        for m in non_empty:
            v = np.asarray(m.vertices, dtype=np.float64)
            f = np.asarray(m.faces, dtype=np.int64)
            items.append((v, f))

        out_v, out_f = union_fn(items)
        out_v = np.asarray(out_v, dtype=np.float64)
        out_f = np.asarray(out_f, dtype=np.int64)
        if out_v.ndim != 2 or out_v.shape[0] == 0 or out_f.ndim != 2 or out_f.shape[0] == 0:
            total_in_faces = int(sum(int(np.asarray(m.faces).shape[0]) for m in non_empty))
            total_in_vertices = int(sum(int(np.asarray(m.vertices).shape[0]) for m in non_empty))
            logger.warning(f"[警告] 3D并集输出为空(slot={slot_name})，将回退到拼接："
                f"输入网格数={len(non_empty)} 输入顶点={total_in_vertices} 输入面={total_in_faces}"
            )
            return trimesh.util.concatenate(non_empty)

        max_index = int(out_f.max()) if out_f.size > 0 else -1
        if max_index >= int(out_v.shape[0]):
            logger.warning(f"[警告] 3D并集输出索引越界(slot={slot_name})，将回退到拼接："
                f"输出顶点={int(out_v.shape[0])} 输出面={int(out_f.shape[0])} 最大索引={max_index}"
            )
            return trimesh.util.concatenate(non_empty)

        return trimesh.Trimesh(vertices=out_v, faces=out_f, process=False)
    except Exception as e:
        logger.error(f"[错误] 3D并集合并失败(slot={slot_name}): {e}")
        import traceback

        traceback.print_exc()
        raise


def _volume_to_core_mesh(vol: np.ndarray, voxel_size: Tuple[float, float, float], shrink: float, slot_name: str) -> trimesh.Trimesh:
    if vol is None or (not isinstance(vol, np.ndarray)):
        return _empty_mesh()
    if vol.ndim != 3:
        raise ValueError(f"体素体积必须是 3D 的 (z,y,x)，但收到: {vol.shape}")
    if not bool(np.any(vol)):
        return _empty_mesh()

    cpp_geometry = _get_cpp_geometry()
    union_fn = None
    if cpp_geometry is not None:
        union_fn = getattr(cpp_geometry, "manifold_union_nogil", None) or getattr(cpp_geometry, "manifold_union", None)

    if union_fn is None:
        logger.warning(f"[警告] C++并集不可用，将回退到Python体素网格生成(slot={slot_name})")
        grid = VoxelGrid(volume=vol, voxel_size=voxel_size)
        return voxel_grid_to_mesh(grid, shrink=shrink)

    sx, sy, sz = map(float, voxel_size)
    vol_u8 = (vol.astype(np.uint8) > 0)
    z_layers, height, width = vol_u8.shape

    def _box_vf(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float):
        v = np.array(
            [
                [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
            ],
            dtype=np.float64,
        )
        f = np.array(
            [
                [0, 3, 2], [0, 2, 1],
                [4, 5, 6], [4, 6, 7],
                [0, 1, 5], [0, 5, 4],
                [1, 2, 6], [1, 6, 5],
                [2, 3, 7], [2, 7, 6],
                [3, 0, 4], [3, 4, 7],
            ],
            dtype=np.int64,
        )
        return v, f

    items = []
    s = float(shrink)
    for z in range(z_layers):
        mask = vol_u8[z]
        if not bool(np.any(mask)):
            continue

        z0 = (float(z) + s) * sz
        z1 = (float(z + 1) - s) * sz
        if z1 <= z0:
            continue

        for y in range(height):
            row = mask[y]
            if not bool(np.any(row)):
                continue

            world_y = float(height - 1 - y)
            y0 = (world_y + s) * sy
            y1 = (world_y + 1.0 - s) * sy
            if y1 <= y0:
                continue

            padded = np.pad(row.astype(np.int8), (1, 1), mode="constant")
            diff = np.diff(padded)
            starts = np.where(diff == 1)[0]
            ends = np.where(diff == -1)[0]
            for start, end in zip(starts, ends):
                x0 = (float(start) + s) * sx
                x1 = (float(end) - s) * sx
                if x1 <= x0:
                    continue
                v, f = _box_vf(x0, x1, y0, y1, z0, z1)
                items.append((v, f))

    if not items:
        return _empty_mesh()

    try:
        out_v, out_f = union_fn(items)
    except Exception as e:
        logger.error(f"[错误] 体素C++并集失败(slot={slot_name}): {e}")
        import traceback

        traceback.print_exc()
        raise

    out_v = np.asarray(out_v, dtype=np.float64)
    out_f = np.asarray(out_f, dtype=np.int64)
    return trimesh.Trimesh(vertices=out_v, faces=out_f, process=False)

ROOT_DIR = Path(__file__).resolve().parent

# ---- 默认参数设置 ----
# 默认层数
DEFAULT_LAYERS = 5
# 默认层高（毫米）
DEFAULT_LAYER_HEIGHT = 0.12
# 默认格子尺寸（毫米）- 校准格子尺寸 6mm
DEFAULT_CELL_SIZE = 6.0
# 默认缩进量
DEFAULT_SHRINK = 0.0
# 数据区域行数
DATA_ROWS = 15
# 数据区域列数
DATA_COLS = 15
# 核心尺寸 - 15x15数据 + 1格边框 = 17x17格子
CORE_SIZE = 17

# 格子尺寸（毫米）
CELL_SIZE_MM = DEFAULT_CELL_SIZE
# Tag像素尺寸（毫米）
TAG_PIXEL_MM = 1.5

# 小Tag的模块数
SMALL_TAG_MODULES = 6
# 大Tag的模块数
BIG_TAG_MODULES = 8

# 默认组ID
DEFAULT_GROUP_ID = 0


def get_marker_colors_for_profile(profile: "ColorProfile") -> Dict[str, str]:
    """根据颜色配置获取标记颜色映射"""
    return profile.marker_colors


def _alt_sequence(a: int, b: int, count_a: int, count_b: int, layers: int) -> List[int]:
    """
    生成长度=layers的交错序列，尽量均匀分布两个颜色的层数

    参数:
        a: 第一个颜色的索引
        b: 第二个颜色的索引
        count_a: 第一个颜色的层数
        count_b: 第二个颜色的层数
        layers: 总层数

    返回:
        颜色索引的交错序列
    """
    seq: List[int] = []
    # 简单的贪心交错算法
    remaining = {a: count_a, b: count_b}
    last = None
    for _ in range(layers):
        # 选择剩余层数较多的颜色；如果可能，避免重复
        cand = a if remaining[a] >= remaining[b] else b
        if last is not None and cand == last and remaining[a] > 0 and remaining[b] > 0:
            cand = b if cand == a else a
        if remaining[cand] == 0:
            cand = b if cand == a else a
        seq.append(cand)
        remaining[cand] -= 1
        last = cand
    return seq


def build_recipe_pool(layers: int, n_colors: int, target_count: int) -> List[List[int]]:
    """
    构建确定性的校准配方池（无随机）。
    按复杂度排序：1色 -> 2色 -> 3色 -> 4色 -> 5色。

    参数:
        layers: 每个配方的层数
        n_colors: 可用颜色数量
        target_count: 目标配方总数

    返回:
        配方列表，每个配方是一个颜色索引列表
    """
    recipes: List[List[int]] = []
    seen = set()

    def add(r: List[int]):
        """添加配方，避免重复"""
        t = tuple(r)
        if t in seen:
            return
        seen.add(t)
        recipes.append(list(r))

    # 1) 纯色 (1-Color): 8 recipes
    for i in range(n_colors):
        add([i] * layers)

    # 2) 两色组合 (2-Colors): 28 pairs
    # 比例 (a:b): 1:4, 2:3, 3:2, 4:1
    ratios = [(1, 4), (2, 3), (3, 2), (4, 1)]
    for i in range(n_colors):
        for j in range(i + 1, n_colors):
            for ca, cb in ratios:
                # 样式 1: 块状 (A上B下)
                add([i] * ca + [j] * cb)
                # 样式 2: 块状 (B上A下) - 物理上对反射影响很大
                add([j] * cb + [i] * ca)
                # 样式 3: 交错 (Interleaved)
                add(_alt_sequence(i, j, ca, cb, layers))

    # 3) 三色组合 (3-Colors): 56 triplets
    triplets = list(itertools.combinations(range(n_colors), 3))
    for (a, b, c) in triplets:
        # 分配方式 (sum=5, each>=1): (1,1,3), (1,2,2), (1,3,1), (2,1,2), (2,2,1), (3,1,1)
        partitions = [(1,1,3), (1,2,2), (1,3,1), (2,1,2), (2,2,1), (3,1,1)]
        for pa, pb, pc in partitions:
            base = [a]*pa + [b]*pb + [c]*pc
            add(base)               # 顺序 1
            add(base[::-1])         # 顺序 2 (倒序)
            # 样式 3: 夹心/交错
            if pa == 3: add([a, b, a, c, a])
            elif pb == 3: add([b, a, b, c, b])
            elif pc == 3: add([c, a, c, b, c])
            else: add([a, b, c, a, b])

    # 4) 四色组合 (4-Colors): 70 quads
    quads = list(itertools.combinations(range(n_colors), 4))
    for (a, b, c, d) in quads:
        # 分配方式 (其中一个占2层): (2,1,1,1), (1,2,1,1), (1,1,2,1), (1,1,1,2)
        for i in range(4):
            counts = [1] * 4
            counts[i] = 2
            colors = [a, b, c, d]
            base = []
            for idx, count in enumerate(counts):
                base.extend([colors[idx]] * count)
            add(base)
            add(base[::-1])

    # 5) 五色组合 (5-Colors): 56 quints
    quints = list(itertools.combinations(range(n_colors), 5))
    for combo in quints:
        # 正序、倒序和一种交错
        a, b, c, d, e = combo
        add([a, b, c, d, e])
        add([e, d, c, b, a])
        add([a, c, e, b, d])

    if len(recipes) < target_count:
        logger.warning(f"警告：确定性配方不足 ({len(recipes)} < {target_count})，将重复部分配方。")
        while len(recipes) < target_count:
            recipes.append(recipes[len(recipes) % len(recipes)])

    return recipes[:target_count]


def build_board_spec(board_name: str, recipes: List[List[int]], group_id: int, plate_index: int, profile: "ColorProfile") -> BoardSpec:
    """
    构建校准板规格对象

    参数:
        board_name: 校准板名称
        recipes: 配方列表
        group_id: 组ID
        plate_index: 板子索引
        profile: 颜色配置对象

    返回:
        BoardSpec对象
    """
    slot_names = profile.color_names
    marker_colors = profile.marker_colors
    
    spec = BoardSpec(
        name=board_name,
        rows=CORE_SIZE,
        cols=CORE_SIZE,
        cell_size_mm=DEFAULT_CELL_SIZE,
        print_profile={
            "layers": DEFAULT_LAYERS,
            "layer_height_mm": DEFAULT_LAYER_HEIGHT,
            "total_size_mm": [CORE_SIZE * CELL_SIZE_MM, CORE_SIZE * CELL_SIZE_MM],
        },
        markers={
            "TL": (0, 0),                                      # 左上角标记
            "TR": (CORE_SIZE - 1, 0),                          # 右上角标记
            "BR": (CORE_SIZE - 1, CORE_SIZE - 1),              # 右下角标记
            "BL": (0, CORE_SIZE - 1),                          # 左下角标记
        },
    )

    # 填充核心数据区
    idx = 0
    for r in range(1, CORE_SIZE - 1):
        for c in range(1, CORE_SIZE - 1):
            layers = recipes[idx] if idx < len(recipes) else [0] * DEFAULT_LAYERS
            spec.cell_map[f"{r},{c}"] = {
                "recipe_index": idx,
                "layers": layers,
                "slot_names": [slot_names[i] for i in layers],
            }
            idx += 1

    # 计算尺寸参数
    core_w_mm = CORE_SIZE * CELL_SIZE_MM
    core_h_mm = CORE_SIZE * CELL_SIZE_MM
    small_tag_mm = SMALL_TAG_MODULES * TAG_PIXEL_MM
    big_tag_mm = BIG_TAG_MODULES * TAG_PIXEL_MM

    # 计算Tag ID
    big_tag_id = group_id * 100 + plate_index
    small_tag_id = plate_index

    # 配置AprilTag
    spec.apriltag["enabled"] = True
    spec.apriltag["families"] = ["tag36h11", "tag16h5"]
    # 大Tag移至右上角最外侧
    spec.apriltag["primary"] = {
        "tag_id": big_tag_id,
        "size_mm": big_tag_mm,
        "board_corners_mm": [
            [core_w_mm, core_h_mm],
            [core_w_mm + big_tag_mm, core_h_mm],
            [core_w_mm + big_tag_mm, core_h_mm + big_tag_mm],
            [core_w_mm, core_h_mm + big_tag_mm]
        ]
    }
    # 小Tag移至左下角最外侧
    spec.apriltag["secondary"] = {
        "tag_id": small_tag_id,
        "size_mm": small_tag_mm,
        "board_corners_mm": [
            [-small_tag_mm, -small_tag_mm],
            [0, -small_tag_mm],
            [0, 0],
            [-small_tag_mm, 0]
        ]
    }
    spec.apriltag["id_encoding"] = {
        "scheme": "group_plate_pack_v1",
        "group_mul": 100,
        "group_id": group_id,
        "plate_id": plate_index
    }
    return spec


def _empty_mesh() -> trimesh.Trimesh:
    """创建一个空的三角网格对象"""
    return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False)


def _merge_meshes(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    合并多个三角网格为一个

    参数:
        meshes: 三角网格列表

    返回:
        合并后的三角网格
    """
    non_empty = [m for m in meshes if m.vertices.shape[0] > 0 and m.faces.shape[0] > 0]
    if not non_empty:
        return _empty_mesh()
    return trimesh.util.concatenate(non_empty)


def _analyze_mesh_basic(mesh: trimesh.Trimesh, label: str) -> Dict[str, int]:
    if _analyze_mesh_cpp is not None:
        return _analyze_mesh_cpp(mesh, label)

    if mesh.vertices is None or mesh.faces is None:
        logger.info(f"模型分析(trimesh): {label} 网格为空")
        return {
            "vertices": 0,
            "faces": 0,
            "non_manifold_edges": 0,
            "boundary_edges": 0,
            "degenerate_faces": 0,
            "duplicate_faces": 0,
            "watertight": 0,
        }

    v = mesh.vertices
    f = mesh.faces
    v_count = int(getattr(v, "shape", [0])[0] or 0)
    f_count = int(getattr(f, "shape", [0])[0] or 0)
    if v_count == 0 or f_count == 0:
        logger.info(f"模型分析(trimesh): {label} 顶点={v_count} 面={f_count}")
        return {
            "vertices": v_count,
            "faces": f_count,
            "non_manifold_edges": 0,
            "boundary_edges": 0,
            "degenerate_faces": 0,
            "duplicate_faces": 0,
            "watertight": 0,
        }

    try:
        unique_counts = np.asarray(mesh.edges_unique_counts, dtype=np.int64)
        boundary_edges = int(np.sum(unique_counts == 1))
        non_manifold_edges = int(np.sum(unique_counts > 2))
    except Exception as e:
        logger.error(f"[错误] 模型分析(trimesh)失败: {label}，原因={e}")
        import traceback

        traceback.print_exc()
        raise

    try:
        watertight = bool(getattr(mesh, "is_watertight", False))
    except Exception:
        watertight = False

    logger.info("模型分析(trimesh): "
        f"{label} 顶点={v_count} 面={f_count} "
        f"非流形边={non_manifold_edges} 边界边={boundary_edges} 封闭={watertight}"
    )
    return {
        "vertices": v_count,
        "faces": f_count,
        "non_manifold_edges": non_manifold_edges,
        "boundary_edges": boundary_edges,
        "degenerate_faces": 0,
        "duplicate_faces": 0,
        "watertight": int(watertight),
    }


def _repair_mesh_until_ok(mesh: trimesh.Trimesh, slot_name: str) -> trimesh.Trimesh:
    if mesh.vertices is None or mesh.faces is None or len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        return mesh

    current = mesh
    for attempt in range(1, 4):
        info = _analyze_mesh_basic(current, f"8色板/{slot_name}/修复前/第{attempt}次")
        if (
                int(info.get("non_manifold_edges", 0)) == 0
                and int(info.get("boundary_edges", 0)) == 0
                and int(info.get("watertight", 0)) == 1
        ):
            return current

        m = current.copy()
        try:
            if hasattr(m, "remove_infinite_values"):
                m.remove_infinite_values()
            if hasattr(m, "remove_degenerate_faces"):
                m.remove_degenerate_faces()
            if hasattr(m, "remove_duplicate_faces"):
                m.remove_duplicate_faces()
            if hasattr(m, "remove_unreferenced_vertices"):
                m.remove_unreferenced_vertices()
        except Exception as e:
            logger.error(f"[错误] 网格基础清理失败(slot={slot_name}): {e}")
            import traceback

            traceback.print_exc()
            raise

        if _clean_mesh is not None:
            try:
                m = _clean_mesh(m, slot_name)
            except Exception as e:
                logger.error(f"[错误] 网格保守清理失败(slot={slot_name}): {e}")
                import traceback

                traceback.print_exc()
                raise

        info_mid = _analyze_mesh_basic(m, f"8色板/{slot_name}/清理后/第{attempt}次")
        if (
                int(info_mid.get("non_manifold_edges", 0)) == 0
                and int(info_mid.get("boundary_edges", 0)) == 0
                and int(info_mid.get("watertight", 0)) == 1
        ):
            return m

        if int(info_mid.get("boundary_edges", 0)) > 0:
            try:
                ok = bool(trimesh.repair.fill_holes(m))
                if ok:
                    if hasattr(m, "remove_duplicate_faces"):
                        m.remove_duplicate_faces()
                    if hasattr(m, "remove_unreferenced_vertices"):
                        m.remove_unreferenced_vertices()
            except Exception as e:
                logger.error(f"[错误] 网格补洞失败(slot={slot_name}): {e}")
                import traceback

                traceback.print_exc()
                raise

        info_after = _analyze_mesh_basic(m, f"8色板/{slot_name}/修复后/第{attempt}次")
        if (
                int(info_after.get("non_manifold_edges", 0)) == 0
                and int(info_after.get("boundary_edges", 0)) == 0
                and int(info_after.get("watertight", 0)) == 1
        ):
            return m

        current = m

    final = _analyze_mesh_basic(current, f"8色板/{slot_name}/最终")
    raise RuntimeError(
        f"网格修复失败(slot={slot_name}): 非流形边={final.get('non_manifold_edges')} 边界边={final.get('boundary_edges')} 封闭={final.get('watertight')}"
    )


def _box_mesh(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> trimesh.Trimesh:
    """
    创建一个长方体网格

    参数:
        x0, x1: X轴范围
        y0, y1: Y轴范围
        z0, z1: Z轴范围

    返回:
        长方体三角网格
    """
    w = float(x1 - x0)
    d = float(y1 - y0)
    h = float(z1 - z0)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    cz = (z0 + z1) / 2.0
    mesh = trimesh.creation.box(extents=(w, d, h))
    mesh.apply_translation((cx, cy, cz))
    return mesh


def _triangle_prism_mesh(p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], z0: float, z1: float) -> trimesh.Trimesh:
    """
    创建一个三角棱柱网格

    参数:
        p0, p1, p2: 三角形的三个顶点（XY平面）
        z0, z1: Z轴范围

    返回:
        三角棱柱三角网格
    """
    v = np.array(
        [
            [p0[0], p0[1], z0],
            [p1[0], p1[1], z0],
            [p2[0], p2[1], z0],
            [p0[0], p0[1], z1],
            [p1[0], p1[1], z1],
            [p2[0], p2[1], z1],
        ],
        dtype=float,
    )
    f = np.array(
        [
            [0, 1, 2],
            [5, 4, 3],
            [0, 1, 4],
            [0, 4, 3],
            [1, 2, 5],
            [1, 5, 4],
            [2, 0, 3],
            [2, 3, 5],
        ],
        dtype=int,
    )
    m = trimesh.Trimesh(vertices=v, faces=f, process=False)
    try:
        if hasattr(m, "fix_normals"):
            m.fix_normals()
    except Exception as e:
        logger.error(f"[错误] 三角棱柱法线修复失败: {e}")
        import traceback

        traceback.print_exc()
        raise
    return m


def _build_core_volumes(spec: BoardSpec, profile: "ColorProfile") -> Dict[str, np.ndarray]:
    """
    构建核心区域的体素数据

    参数:
        spec: 校准板规格对象
        profile: 颜色配置对象

    返回:
        按颜色分类的体素数据字典
    """
    slot_names = profile.color_names
    marker_colors = profile.marker_colors
    
    volumes: Dict[str, np.ndarray] = {
        name: np.zeros((DEFAULT_LAYERS, CORE_SIZE, CORE_SIZE), dtype=bool) for name in slot_names
    }
    for r_cell in range(CORE_SIZE):
        for c_cell in range(CORE_SIZE):
            cell_data = spec.cell_map.get(f"{r_cell},{c_cell}")
            if cell_data:
                # 处理数据区域的格子
                layers = cell_data["layers"]
                for z, color_idx in enumerate(layers):
                    color_name = slot_names[int(color_idx)]
                    volumes[color_name][z, r_cell, c_cell] = True
            else:
                # 处理标记区域的格子
                # 使用配置中的第一个颜色作为默认标记颜色
                color_name = slot_names[0]
                for m_name, (mc, mr) in spec.markers.items():
                    if r_cell == mr and c_cell == mc:
                        # 从配置中获取标记颜色
                        marker_color_name = marker_colors.get(m_name, slot_names[0])
                        if marker_color_name in slot_names:
                            color_name = marker_color_name
                        break
                volumes[color_name][:, r_cell, c_cell] = True
    return volumes


def _build_triangle_meshes() -> Dict[str, List[trimesh.Trimesh]]:
    """
    构建连接Tag和色盘的三角形填充网格

    返回:
        按颜色分类的三角网格列表字典
    """
    meshes: Dict[str, List[trimesh.Trimesh]] = {name: [] for name in SLOT_NAMES_8}
    total_h = DEFAULT_LAYERS * DEFAULT_LAYER_HEIGHT
    core_w_mm = CORE_SIZE * CELL_SIZE_MM
    core_h_mm = CORE_SIZE * CELL_SIZE_MM
    small_tag_mm = SMALL_TAG_MODULES * TAG_PIXEL_MM
    big_tag_mm = BIG_TAG_MODULES * TAG_PIXEL_MM

    # 大Tag侧（右上角内侧连接处）
    # Tag位于[90, 102] x [78, 90]
    # 三角形应位于Tag下方，连接色盘右边缘：[90, 102] x [66, 78]
    # 顶点：(90, 78)直角, (102, 78), (90, 66)。斜边从(102, 78)到(90, 66)
    p0 = (core_w_mm, core_h_mm - big_tag_mm)
    p1 = (core_w_mm + big_tag_mm, core_h_mm - big_tag_mm)
    p2 = (core_w_mm, core_h_mm - big_tag_mm * 2)
    meshes["White"].append(_triangle_prism_mesh(p0, p1, p2, 0.0, total_h))

    # 小Tag侧（左下角内侧连接处）
    # Tag位于[-6, 0] x [0, 6]
    # 三角形应位于Tag上方，连接色盘左边缘：[-6, 0] x [6, 12]
    # 顶点：(0, 6)直角, (-6, 6), (0, 12)。斜边从(-6, 6)到(0, 12)
    q0 = (0.0, small_tag_mm)
    q1 = (-small_tag_mm, small_tag_mm)
    q2 = (0.0, small_tag_mm * 2)
    meshes["White"].append(_triangle_prism_mesh(q0, q1, q2, 0.0, total_h))
    return meshes


def spec_to_meshes(
        spec: BoardSpec,
        shrink: float = DEFAULT_SHRINK,
        *,
        include_apriltag: bool = False,
        include_side_triangles: bool = False,
        profile: "ColorProfile",
) -> Dict[str, trimesh.Trimesh]:
    """
    将校准板规格转换为三角网格

    参数:
        spec: 校准板规格对象
        shrink: 缩进量
        profile: 颜色配置对象

    返回:
        按颜色分类的合并后的三角网格字典
    """
    slot_names = profile.color_names
    num_colors = profile.num_colors
    core_volumes = _build_core_volumes(spec, profile)
    voxel_size = (CELL_SIZE_MM, CELL_SIZE_MM, DEFAULT_LAYER_HEIGHT)

    meshes_by_slot: Dict[str, List[trimesh.Trimesh]] = {name: [] for name in slot_names}
    for slot_name in slot_names:
        vol = core_volumes[slot_name]
        if np.any(vol):
            m = _volume_to_core_mesh(vol, voxel_size, shrink, slot_name)
            info = _analyze_mesh_basic(m, f"{num_colors}色板/{slot_name}/体素网格(已并集)")
            if int(info.get("non_manifold_edges", 0)) > 0 or int(info.get("boundary_edges", 0)) > 0:
                raise RuntimeError(
                    f"体素网格质量异常(slot={slot_name}): 非流形边={info.get('non_manifold_edges')} 边界边={info.get('boundary_edges')}"
                )
            meshes_by_slot[slot_name].append(m)

    if bool(include_apriltag):
        pass

    if bool(include_side_triangles):
        tri_meshes = _build_triangle_meshes()
        for slot_name in slot_names:
            meshes_by_slot[slot_name].extend(tri_meshes[slot_name])

    # 合并每个颜色的所有网格
    merged: Dict[str, trimesh.Trimesh] = {}
    for slot_name in slot_names:
        merged_mesh = _union_meshes(meshes_by_slot[slot_name], slot_name)
        if merged_mesh.faces is not None and len(merged_mesh.faces) > 0:
            info = _analyze_mesh_basic(merged_mesh, f"{num_colors}色板/{slot_name}/合并后")
            if int(info.get("non_manifold_edges", 0)) > 0 or int(info.get("boundary_edges", 0)) > 0:
                raise RuntimeError(
                    f"合并后网格质量异常(slot={slot_name}): 非流形边={info.get('non_manifold_edges')} 边界边={info.get('boundary_edges')}"
                )
        merged[slot_name] = merged_mesh
    return merged


def export_standard_3mf(
        out_dir: Path,
        spec: BoardSpec,
        meshes_by_slot: Dict[str, trimesh.Trimesh],
        profile: "ColorProfile",
) -> Path:
    """
    导出为通用（标准）3MF格式文件

    参数:
        out_dir: 输出目录
        spec: 校准板规格对象
        meshes_by_slot: 按颜色分类的三角网格字典
        profile: 颜色配置对象
    返回:
        输出的3MF文件路径
    """
    slot_names = profile.color_names
    num_colors = profile.num_colors
    color_system = {name: tuple(rgba) for name, rgba in profile.colors.items()}  # type: ignore
    
    out_3mf = out_dir / f"{spec.name.replace(' ', '_')}.3mf"
    slot_names_used: List[str] = []
    for slot_name in slot_names:
        tm_mesh = meshes_by_slot.get(slot_name)
        if tm_mesh is None:
            continue
        if tm_mesh.faces is None or len(tm_mesh.faces) == 0:
            continue
        slot_names_used.append(slot_name)

    for slot_name in slot_names_used:
        tm_mesh = meshes_by_slot.get(slot_name)
        if tm_mesh is None:
            continue
        _analyze_mesh_basic(tm_mesh, f"{num_colors}色板/{slot_name}/导出前")

    export_standard_3mf_from_meshes(
        out_3mf=out_3mf,
        meshes=meshes_by_slot,
        slot_names=slot_names_used,
        slot_colors=color_system,
    )
    return out_3mf


def generate_calibration_boards(
        num_boards: int = 8,
        shrink: float = DEFAULT_SHRINK,
        *,
        include_apriltag: bool = False,
        include_side_triangles: bool = False,
        profile: "ColorProfile",
) -> Path:
    """
    生成校准板（支持任意颜色数量）

    参数:
        num_boards: 生成的板子数量
        shrink: 格子缩进量
        profile: 颜色配置对象
    
    返回:
        输出目录路径
    """
    num_colors = profile.num_colors
    color_label = f"{num_colors}color"
    out_dir = ROOT_DIR / f"out_calibration_board_{color_label}"
    out_dir.mkdir(parents=True, exist_ok=True)

    num_cells = DATA_ROWS * DATA_COLS
    total_cells_needed = num_cells * num_boards

    # 构建全球统一的配方池
    recipes = build_recipe_pool(layers=DEFAULT_LAYERS, n_colors=num_colors, target_count=total_cells_needed)

    for b_idx in range(num_boards):
        # 生成板子名称（A, B, C, ...）
        board_char = chr(65 + b_idx) if b_idx < 26 else str(b_idx)
        name = f"{num_colors}-Color Board {board_char}"

        # 获取当前板子使用的配方
        start_idx = b_idx * num_cells
        recs = recipes[start_idx : start_idx + num_cells]

        # 构建校准板规格
        spec = build_board_spec(name, recs, DEFAULT_GROUP_ID, b_idx, profile=profile)
        spec_path = out_dir / f"{name.replace(' ', '_')}_board_spec.json"
        spec.save(spec_path)

        # 转换为网格并导出
        meshes_by_slot = spec_to_meshes(
            spec,
            shrink=shrink,
            include_apriltag=include_apriltag,
            include_side_triangles=include_side_triangles,
            profile=profile,
        )
        out_3mf = export_standard_3mf(out_dir, spec, meshes_by_slot, profile=profile)
        logger.info(f"[OK] {name}: recipes[{start_idx}:{start_idx+len(recs)}], 3mf={out_3mf.name}")

    logger.info(f"完成：已生成 {num_boards} 个 {num_colors} 色校准盘，共计 {len(recipes)} 个唯一/结构化配方。")
    logger.info(f"输出目录: {out_dir.absolute()}")
    return out_dir


# 保持向后兼容的别名
generate_8color_boards = generate_calibration_boards


if __name__ == "__main__":
    import argparse
    from .color_profiles import get_profile_manager, create_profile_from_args
    
    parser = argparse.ArgumentParser(description="生成校准板（支持任意颜色数量）")
    parser.add_argument("--num_boards", type=int, default=8, help="生成的板子数量")
    parser.add_argument("--shrink", type=float, default=DEFAULT_SHRINK, help="格子缩进量 (shrink)")
    parser.add_argument("--profile", type=str, default="full_8", help="颜色配置名称（如 rgb, rybw, rgbw, rgbwk, full_8）")
    parser.add_argument("--config", type=str, help="自定义配置文件路径")
    parser.add_argument("--colors", nargs="+", help="自定义颜色列表（格式: 名称:R,G,B,A）")
    args = parser.parse_args()
    
    manager = get_profile_manager()
    
    # 加载配置文件（如果提供）
    if args.config:
        manager.load_from_file(Path(args.config))
    
    # 从命令行创建配置（如果提供）
    if args.colors:
        profile = create_profile_from_args(args.colors)
    else:
        profile = manager.get_profile(args.profile)
    
    generate_calibration_boards(
        num_boards=args.num_boards,
        shrink=args.shrink,
        profile=profile,
    )
