# 支持类型注解的导入（Python 3.7+）
from __future__ import annotations

# 导入路径处理模块
from pathlib import Path
# 导入类型提示模块
from typing import Dict, List, Tuple
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

# 颜色定义 (RGBA) —— 8槽位
COLOR_SYSTEM_8: Dict[str, Tuple[int, int, int, int]] = {
    "White": (255, 255, 255, 255),      # 白色
    "Red": (255, 0, 0, 255),            # 红色
    "Yellow": (255, 255, 0, 255),      # 黄色
    "Blue": (0, 0, 255, 255),           # 蓝色
    "Green": (0, 255, 0, 255),          # 绿色
    "Cyan": (0, 255, 255, 255),         # 青色
    "Magenta": (255, 0, 255, 255),      # 洋红色
    "Black": (0, 0, 0, 255),            # 黑色
}
# 槽位名称列表
SLOT_NAMES_8 = list(COLOR_SYSTEM_8.keys())


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


def _count_color_switches(recipe: List[int]) -> int:
    """计算配方中的颜色切换次数"""
    switches = 0
    for i in range(1, len(recipe)):
        if recipe[i] != recipe[i-1]:
            switches += 1
    return switches


def build_recipe_pool(layers: int, n_colors: int, target_count: int) -> List[List[int]]:
    """
    构建确定性的校准配方池（无随机）。
    按复杂度排序：1色 -> 2色 -> 3色 -> 4色 -> 5色 -> 穷举补充。

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

    # 1) 纯色 (1-Color)
    for i in range(n_colors):
        add([i] * layers)

    # 2) 两色组合 (2-Colors)
    # 比例 (a:b): 1:4, 2:3, 3:2, 4:1
    ratios = [(1, 4), (2, 3), (3, 2), (4, 1)]
    for i in range(n_colors):
        for j in range(i + 1, n_colors):
            for ca, cb in ratios:
                # 样式 1: 块状 (A上B下)
                add([i] * ca + [j] * cb)
                # 样式 2: 块状 (B上A下)
                add([j] * cb + [i] * ca)
                # 样式 3: 交错 (Interleaved)
                add(_alt_sequence(i, j, ca, cb, layers))

    # 3) 三色组合 (3-Colors)
    triplets = list(itertools.combinations(range(n_colors), 3))
    for (a, b, c) in triplets:
        partitions = [(1,1,3), (1,2,2), (1,3,1), (2,1,2), (2,2,1), (3,1,1)]
        for pa, pb, pc in partitions:
            base = [a]*pa + [b]*pb + [c]*pc
            add(base)
            add(base[::-1])
            if pa == 3: add([a, b, a, c, a])
            elif pb == 3: add([b, a, b, c, b])
            elif pc == 3: add([c, a, c, b, c])
            else: add([a, b, c, a, b])

    # 4) 四色组合 (4-Colors)
    quads = list(itertools.combinations(range(n_colors), 4))
    for (a, b, c, d) in quads:
        for i in range(4):
            counts = [1] * 4
            counts[i] = 2
            colors = [a, b, c, d]
            base = []
            for idx, count in enumerate(counts):
                base.extend([colors[idx]] * count)
            add(base)
            add(base[::-1])

    # 5) 五色组合 (5-Colors)
    quints = list(itertools.combinations(range(n_colors), 5))
    for combo in quints:
        a, b, c, d, e = combo
        add([a, b, c, d, e])
        add([e, d, c, b, a])
        add([a, c, e, b, d])

    # 6) 穷举补充：如果结构化配方不足，使用穷举法生成更多配方
    if len(recipes) < target_count:
        # 计算理论最大配方数
        max_possible = n_colors ** layers
        
        if max_possible > len(recipes):
            logger.info(f"结构化配方 {len(recipes)} 个，开始穷举补充至 {target_count} 个...")
            
            # 生成所有可能的配方
            all_possible = list(itertools.product(range(n_colors), repeat=layers))
            
            # 过滤掉已有的配方
            remaining = [list(r) for r in all_possible if r not in seen]
            
            # 按颜色种类数和切换次数排序
            # 优先级：颜色种类数少 > 切换次数少
            def sort_key(recipe):
                num_colors = len(set(recipe))
                switches = _count_color_switches(recipe)
                return (num_colors, switches)
            
            remaining.sort(key=sort_key)
            
            # 补充配方
            for r in remaining:
                if len(recipes) >= target_count:
                    break
                recipes.append(r)
                seen.add(tuple(r))
            
            logger.info(f"穷举补充完成，共生成 {len(recipes)} 个唯一配方")
        else:
            logger.warning(f"理论最大配方数 ({max_possible}) 不足，将重复部分配方")
            while len(recipes) < target_count:
                recipes.append(recipes[len(recipes) % len(recipes)])

    return recipes[:target_count]


def build_board_spec(
    board_name: str,
    recipes: List[List[int]],
    group_id: int,
    plate_index: int,
    slot_names: List[str] = None,
) -> BoardSpec:
    """
    构建校准板规格对象

    参数:
        board_name: 校准板名称
        recipes: 配方列表
        group_id: 组ID
        plate_index: 板子索引
        slot_names: 颜色名称列表，默认为8色配置

    返回:
        BoardSpec对象
    """
    # 使用默认的8色配置
    if slot_names is None:
        slot_names = SLOT_NAMES_8

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
    n_colors = len(slot_names)
    for r in range(1, CORE_SIZE - 1):
        for c in range(1, CORE_SIZE - 1):
            layers = recipes[idx] if idx < len(recipes) else [0] * DEFAULT_LAYERS
            # 使用提供的slot_names映射颜色索引
            spec.cell_map[f"{r},{c}"] = {
                "recipe_index": idx,
                "layers": layers,
                "slot_names": [slot_names[i] if i < n_colors else slot_names[0] for i in layers],
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


def _build_core_volumes(
    spec: BoardSpec,
    slot_names: List[str] = None,
    marker_colors: Dict[str, str] = None,
    default_border_color: str = None,
) -> Dict[str, np.ndarray]:
    """
    构建核心区域的体素数据

    参数:
        spec: 校准板规格对象
        slot_names: 颜色名称列表，默认为8色配置
        marker_colors: 标记颜色配置，默认为8色配置的标记颜色
        default_border_color: 边框默认颜色，默认为White

    返回:
        按颜色分类的体素数据字典
    """
    # 使用默认配置
    if slot_names is None:
        slot_names = SLOT_NAMES_8
    if marker_colors is None:
        marker_colors = {"TL": "Blue", "TR": "Red", "BR": "Blue", "BL": "Yellow"}
    if default_border_color is None:
        default_border_color = "White"

    # 初始化体素数据字典
    volumes: Dict[str, np.ndarray] = {
        name: np.zeros((DEFAULT_LAYERS, CORE_SIZE, CORE_SIZE), dtype=bool) for name in slot_names
    }

    n_colors = len(slot_names)

    for r_cell in range(CORE_SIZE):
        for c_cell in range(CORE_SIZE):
            cell_data = spec.cell_map.get(f"{r_cell},{c_cell}")
            if cell_data:
                # 处理数据区域的格子
                layers = cell_data["layers"]
                for z, color_idx in enumerate(layers):
                    if color_idx < n_colors:
                        color_name = slot_names[int(color_idx)]
                        if color_name in volumes:
                            volumes[color_name][z, r_cell, c_cell] = True
            else:
                # 处理标记区域的格子（边框）
                color_name = default_border_color if default_border_color in volumes else slot_names[0]
                for m_name, (mc, mr) in spec.markers.items():
                    if r_cell == mr and c_cell == mc:
                        marker_color = marker_colors.get(m_name)
                        if marker_color and marker_color in volumes:
                            color_name = marker_color
                        break
                if color_name in volumes:
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
    slot_names: List[str] = None,
    marker_colors: Dict[str, str] = None,
    default_border_color: str = None,
    include_apriltag: bool = False,
    include_side_triangles: bool = False,
) -> Dict[str, trimesh.Trimesh]:
    """
    将校准板规格转换为三角网格

    参数:
        spec: 校准板规格对象
        shrink: 缩进量
        slot_names: 颜色名称列表，默认为8色配置
        marker_colors: 标记颜色配置，默认为8色配置的标记颜色
        default_border_color: 边框默认颜色，默认为White
        include_apriltag: 是否包含AprilTag
        include_side_triangles: 是否包含侧边三角形

    返回:
        按颜色分类的合并后的三角网格字典
    """
    # 使用默认配置
    if slot_names is None:
        slot_names = SLOT_NAMES_8

    core_volumes = _build_core_volumes(
        spec,
        slot_names=slot_names,
        marker_colors=marker_colors,
        default_border_color=default_border_color,
    )
    voxel_size = (CELL_SIZE_MM, CELL_SIZE_MM, DEFAULT_LAYER_HEIGHT)

    meshes_by_slot: Dict[str, List[trimesh.Trimesh]] = {name: [] for name in slot_names}
    for slot_name in slot_names:
        vol = core_volumes.get(slot_name)
        if vol is not None and np.any(vol):
            m = _volume_to_core_mesh(vol, voxel_size, shrink, slot_name)
            info = _analyze_mesh_basic(m, f"{len(slot_names)}色板/{slot_name}/体素网格(已并集)")
            if int(info.get("non_manifold_edges", 0)) > 0 or int(info.get("boundary_edges", 0)) > 0:
                logger.warning(
                    f"体素网格质量警告(slot={slot_name}): 非流形边={info.get('non_manifold_edges')} 边界边={info.get('boundary_edges')}"
                )
            meshes_by_slot[slot_name].append(m)

    if bool(include_apriltag):
        pass

    if bool(include_side_triangles):
        # TODO: 需要修改 _build_triangle_meshes 支持自定义颜色
        pass

    # 合并每个颜色的所有网格
    merged: Dict[str, trimesh.Trimesh] = {}
    for slot_name in slot_names:
        merged_mesh = _union_meshes(meshes_by_slot[slot_name], slot_name)
        if merged_mesh.faces is not None and len(merged_mesh.faces) > 0:
            info = _analyze_mesh_basic(merged_mesh, f"{len(slot_names)}色板/{slot_name}/合并后")
            if int(info.get("non_manifold_edges", 0)) > 0 or int(info.get("boundary_edges", 0)) > 0:
                logger.warning(
                    f"合并后网格质量警告(slot={slot_name}): 非流形边={info.get('non_manifold_edges')} 边界边={info.get('boundary_edges')}"
                )
        merged[slot_name] = merged_mesh
    return merged


def export_standard_3mf(
    out_dir: Path,
    spec: BoardSpec,
    meshes_by_slot: Dict[str, trimesh.Trimesh],
    slot_names: List[str] = None,
    slot_colors: Dict[str, Tuple[int, int, int, int]] = None,
) -> Path:
    """
    导出为通用（标准）3MF格式文件

    参数:
        out_dir: 输出目录
        spec: 校准板规格对象
        meshes_by_slot: 按颜色分类的三角网格字典
        slot_names: 颜色名称列表，默认为8色配置
        slot_colors: 颜色定义字典，默认为8色配置
    返回:
        输出的3MF文件路径
    """
    # 使用默认配置
    if slot_names is None:
        slot_names = SLOT_NAMES_8
    if slot_colors is None:
        slot_colors = COLOR_SYSTEM_8

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
        _analyze_mesh_basic(tm_mesh, f"{len(slot_names)}色板/{slot_name}/导出前")

    export_standard_3mf_from_meshes(
        out_3mf=out_3mf,
        meshes=meshes_by_slot,
        slot_names=slot_names_used,
        slot_colors=slot_colors,
    )
    return out_3mf


def generate_8color_boards(
        num_boards: int = 8,
        shrink: float = DEFAULT_SHRINK,
        *,
        include_apriltag: bool = False,
        include_side_triangles: bool = False,
) -> None:
    """
    生成8色校准板

    参数:
        num_boards: 生成的板子数量
        shrink: 格子缩进量
    """
    out_dir = ROOT_DIR / "out_calibration_board_8"
    out_dir.mkdir(parents=True, exist_ok=True)

    num_cells = DATA_ROWS * DATA_COLS
    total_cells_needed = num_cells * num_boards

    # 构建全球统一的配方池
    recipes = build_recipe_pool(layers=DEFAULT_LAYERS, n_colors=8, target_count=total_cells_needed)

    for b_idx in range(num_boards):
        # 生成板子名称（A, B, C, ...）
        board_char = chr(65 + b_idx) if b_idx < 26 else str(b_idx)
        name = f"8-Color Board {board_char}"

        # 获取当前板子使用的配方
        start_idx = b_idx * num_cells
        recs = recipes[start_idx : start_idx + num_cells]

        # 构建校准板规格
        spec = build_board_spec(name, recs, DEFAULT_GROUP_ID, b_idx)
        spec_path = out_dir / f"{name.replace(' ', '_')}_board_spec.json"
        spec.save(spec_path)

        # 转换为网格并导出
        meshes_by_slot = spec_to_meshes(
            spec,
            shrink=shrink,
            include_apriltag=include_apriltag,
            include_side_triangles=include_side_triangles,
        )
        out_3mf = export_standard_3mf(out_dir, spec, meshes_by_slot)
        logger.info(f"[OK] {name}: recipes[{start_idx}:{start_idx+len(recs)}], 3mf={out_3mf.name}")

    logger.info(f"完成：已生成 {num_boards} 个 8 色校准盘，共计 {len(recipes)} 个唯一/结构化配方。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成 8 色校准板")
    parser.add_argument("--num_boards", type=int, default=8, help="生成的板子数量")
    parser.add_argument("--shrink", type=float, default=DEFAULT_SHRINK, help="格子缩进量 (shrink)")
    args = parser.parse_args()

    generate_8color_boards(num_boards=args.num_boards, shrink=args.shrink)
