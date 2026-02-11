"""网格工具模块 - 提供网格修复、简化和导出功能"""

import traceback
from pathlib import Path

import numpy as np
import trimesh


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _mesh_repair_manifold(m: trimesh.Trimesh) -> trimesh.Trimesh:
    mm = m.copy()
    try:
        if hasattr(mm, "remove_infinite_values"):
            mm.remove_infinite_values()
        if hasattr(mm, "remove_duplicate_faces"):
            mm.remove_duplicate_faces()
        if hasattr(mm, "remove_degenerate_faces"):
            mm.remove_degenerate_faces()
        if hasattr(mm, "remove_unreferenced_vertices"):
            mm.remove_unreferenced_vertices()
        if hasattr(mm, "merge_vertices"):
            mm.merge_vertices()
        if hasattr(mm, "fill_holes"):
            mm.fill_holes()
        if hasattr(mm, "fix_normals"):
            mm.fix_normals()
        mm.process(validate=True)
    except Exception as e:
        logger.info(f"  [孔洞填充] 网格修复异常: {e}")
        traceback.print_exc()
    return mm


def _mesh_simplify(m: trimesh.Trimesh, *, target_faces: int) -> trimesh.Trimesh:
    mm = m.copy()
    try:
        if hasattr(mm, "simplify_quadratic_decimation"):
            out = mm.simplify_quadratic_decimation(int(target_faces))
            if out is not None:
                out.process(validate=True)
                return out
    except Exception as e:
        logger.info(f"  [网格简化] 简化异常: {e}")
        traceback.print_exc()
    return mm


def _geom_to_polygons(geom) -> list:
    try:
        from shapely.geometry import Polygon, MultiPolygon
    except Exception:
        return []

    if geom is None:
        return []

    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)

    geoms = getattr(geom, "geoms", None)
    if geoms is None:
        return []
    out = []
    for g in geoms:
        if isinstance(g, Polygon):
            out.append(g)
        elif isinstance(g, MultiPolygon):
            out.extend(list(g.geoms))
    return out


def _mesh_extrude_2d_to_3d(
    geom, z_bottom: float, z_top: float
) -> trimesh.Trimesh | None:
    height = float(z_top) - float(z_bottom)
    if height <= 0:
        return None
    parts = _geom_to_polygons(getattr(geom, "buffer", lambda *_: geom)(0))
    if not parts:
        return None

    meshes = []
    for p in parts:
        if getattr(p, "is_empty", True):
            continue
        try:
            m = trimesh.creation.extrude_polygon(p, height=height, engine="earcut")
        except Exception:
            try:
                m = trimesh.creation.extrude_polygon(p, height=height)
            except Exception:
                continue
        if m is None or len(m.vertices) == 0:
            continue
        m.apply_translation([0.0, 0.0, float(z_bottom)])
        meshes.append(m)

    if not meshes:
        return None
    merged = trimesh.util.concatenate(meshes)
    merged.process(validate=True)
    return merged


def _mesh_voxel_fill_holes(
    m: trimesh.Trimesh, *, voxel_size: float
) -> trimesh.Trimesh | None:
    try:
        vox = m.voxelized(pitch=float(voxel_size))
        filled = vox.fill()
        out = filled.marching_cubes
        if out is None or len(out.vertices) == 0:
            return None
        out.process(validate=True)
        return out
    except Exception as e:
        logger.info(f"  [体素修复] 体素化异常: {e}")
        traceback.print_exc()
        return None


def _repair_mesh_by_voxel(
    m: trimesh.Trimesh, slot_name: str, *, voxel_size: float = 0.1
) -> trimesh.Trimesh:
    """使用体素化修复网格"""
    try:
        m2 = _mesh_voxel_fill_holes(m, voxel_size=float(voxel_size))
        if m2 is not None and len(m2.vertices) > 0:
            logger.info(
                f"  [体素修复] {slot_name}: 体素化修复成功，顶点数 {len(m.vertices)} -> {len(m2.vertices)}"
            )
            return m2
    except Exception as e:
        logger.error(f"  [体素修复] {slot_name}: 体素化修复失败: {e}")
        traceback.print_exc()
    return m


def _repair_mesh_by_fill(m: trimesh.Trimesh, slot_name: str) -> trimesh.Trimesh:
    """使用孔洞填充修复"""
    try:
        m2 = _mesh_repair_manifold(m)
        if m2 is not None and len(m2.vertices) > 0:
            logger.info(
                f"  [孔洞填充] {slot_name}: 孔洞填充修复成功，顶点数 {len(m.vertices)} -> {len(m2.vertices)}"
            )
            return m2
    except Exception as e:
        logger.error(f"  [孔洞填充] {slot_name}: 孔洞填充修复失败: {e}")
        traceback.print_exc()
    return m


def _repair_mesh(m: trimesh.Trimesh, slot_name: str) -> trimesh.Trimesh:
    """修复网格"""
    if m is None or len(m.vertices) == 0:
        return m

    is_watertight = m.is_watertight
    logger.info(
        f"  [网格检查] {slot_name}: watertight={is_watertight}, 顶点={len(m.vertices)}, 面={len(m.faces)}"
    )

    if is_watertight:
        return m

    # 尝试多种修复方法
    m2 = _repair_mesh_by_voxel(m, slot_name, voxel_size=0.1)
    if m2.is_watertight:
        return m2

    m2 = _repair_mesh_by_fill(m2, slot_name)
    return m2


def _simplify_mesh(
    m: trimesh.Trimesh, slot_name: str, *, target_ratio: float = 0.5
) -> trimesh.Trimesh:
    """简化网格"""
    if m is None or len(m.vertices) == 0:
        return m

    target_faces = max(int(len(m.faces) * float(target_ratio)), 4)
    try:
        m2 = _mesh_simplify(m, target_faces=int(target_faces))
        if m2 is not None and len(m2.vertices) > 0:
            logger.info(
                f"  [网格简化] {slot_name}: {len(m.faces)} -> {len(m2.faces)} 面"
            )
            return m2
    except Exception as e:
        logger.error(f"  [网格简化] {slot_name}: 简化失败: {e}")
        traceback.print_exc()
    return m


def _extrude_2d_to_3d(
    geom,
    z_bottom: float,
    z_top: float,
    slot_name: str,
) -> trimesh.Trimesh | None:
    """将2D几何体拉伸为3D网格"""
    if geom is None or getattr(geom, "is_empty", True):
        return None

    try:
        m = _mesh_extrude_2d_to_3d(geom, float(z_bottom), float(z_top))
        if m is None or len(m.vertices) == 0:
            return None
        return m
    except Exception as e:
        logger.error(f"  [拉伸失败] {slot_name}: {e}")
        traceback.print_exc()
        return None


def _save_mesh(m: trimesh.Trimesh, path: Path, slot_name: str) -> bool:
    """保存网格到文件"""
    if m is None or len(m.vertices) == 0:
        logger.info(f"  [跳过] {slot_name}: 网格为空")
        return False

    try:
        m.export(str(path))
        logger.info(
            f"  [保存] {slot_name}: {path.name} ({len(m.vertices)} 顶点, {len(m.faces)} 面)"
        )
        return True
    except Exception as e:
        logger.error(f"  [保存失败] {slot_name}: {e}")
        traceback.print_exc()
        return False


def _check_mesh_quality(m: trimesh.Trimesh, slot_name: str) -> dict:
    """检查网格质量"""
    quality = {
        "vertices": len(m.vertices),
        "faces": len(m.faces),
        "watertight": m.is_watertight,
        "winding_consistent": m.is_winding_consistent,
        "bounds": m.bounds.tolist(),
        "volume": float(m.volume) if m.is_watertight else 0.0,
        "area": float(m.area),
    }

    # 检查退化面
    degenerate = 0
    for face in m.faces:
        v0, v1, v2 = m.vertices[face]
        # 计算边长
        e0 = np.linalg.norm(v1 - v0)
        e1 = np.linalg.norm(v2 - v1)
        e2 = np.linalg.norm(v0 - v2)
        # 检查是否退化（边长接近0）
        if e0 < 1e-6 or e1 < 1e-6 or e2 < 1e-6:
            degenerate += 1

    quality["degenerate_faces"] = degenerate
    quality["degenerate_ratio"] = degenerate / len(m.faces) if len(m.faces) > 0 else 0.0

    return quality


def _export_3mf(
    out_3mf: Path,
    slot_meshes: dict[str, trimesh.Trimesh],
    slot_preview_rgb: dict[str, tuple[int, int, int]],
) -> Path | None:
    """导出通用 3MF 格式（按对象颜色）

    将所有同色网格合并为一个对象，并设置对象级颜色
    """
    try:
        import lib3mf
        from lib3mf import get_wrapper
    except ImportError:
        logger.warning("  [警告] lib3mf 未安装，无法导出 3MF 格式")
        return None

    if not slot_meshes:
        logger.info("  [提示] 没有可用网格，跳过 3MF 导出")
        return None

    wrapper = get_wrapper()
    model = wrapper.CreateModel()
    try:
        model.SetUnit(lib3mf.ModelUnit.MilliMeter)
    except Exception as e:
        logger.error(f"  [警告] 设置 3MF 单位为毫米失败: {e}")

    # 创建颜色组
    color_group = model.AddColorGroup()
    # 获取资源ID：优先使用 GetUniqueResourceID，某些 lib3mf 版本需要此方法
    if hasattr(color_group, "GetUniqueResourceID"):
        color_group_rid = int(color_group.GetUniqueResourceID())
    else:
        color_group_rid = int(color_group.GetResourceID())

    # 为每个插槽分配颜色
    slot_color_pid: dict[str, int] = {}
    for slot_name in slot_meshes.keys():
        r, g, b = slot_preview_rgb.get(slot_name, (128, 128, 128))
        color = wrapper.RGBAToColor(int(r), int(g), int(b), 255)
        pid = int(color_group.AddColor(color))
        slot_color_pid[slot_name] = pid

    # 添加网格对象
    for slot_name, mesh in slot_meshes.items():
        if mesh is None or len(mesh.vertices) == 0:
            continue

        # 创建网格对象
        mesh_object = model.AddMeshObject()
        mesh_object.SetName(str(slot_name))

        # 转换顶点
        vertices = []
        for v in mesh.vertices:
            pos = lib3mf.Position()
            pos.Coordinates[0] = float(v[0])
            pos.Coordinates[1] = float(v[1])
            pos.Coordinates[2] = float(v[2])
            vertices.append(pos)

        # 转换三角形
        triangles = []
        for f in mesh.faces:
            tri = lib3mf.Triangle()
            tri.Indices[0] = int(f[0])
            tri.Indices[1] = int(f[1])
            tri.Indices[2] = int(f[2])
            triangles.append(tri)

        mesh_object.SetGeometry(vertices, triangles)

        # 设置对象级颜色
        pid = int(slot_color_pid.get(slot_name, 0))
        mesh_object.SetObjectLevelProperty(int(color_group_rid), int(pid))

        # 添加到构建项
        model.AddBuildItem(mesh_object, wrapper.GetIdentityTransform())

    # 写入文件
    writer = model.QueryWriter("3mf")
    writer.WriteToFile(str(out_3mf))
    logger.info(f"  [保存] 3MF: {out_3mf.name} ({len(slot_meshes)} 个对象)")
    return out_3mf
