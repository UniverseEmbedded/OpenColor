from __future__ import annotations


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
"""
标准 3MF 导出模块。
提供将 STL 文件转换并打包为符合 3MF 核心规范的文件功能。
支持多对象和基于 BaseMaterials 的颜色分配。
"""

# 导入 XML 处理模块
import xml.etree.ElementTree as ET
# 导入转义工具
from xml.sax.saxutils import escape as _xml_escape
# 导入路径处理模块
from pathlib import Path
# 导入类型提示模块
from typing import Dict, List, Mapping, Sequence, Tuple

# 导入数值计算模块
import numpy as np
# 导入三角网格处理库
import trimesh

try:
    import lib3mf
    from lib3mf import get_wrapper
except Exception as e:
    lib3mf = None
    get_wrapper = None
    logger.warning(f"[警告] lib3mf 不可用，将使用XML方式导出3MF: {e}")
    import traceback

    traceback.print_exc()

# 导入原子性 ZIP 创建函数
from .atomic_io import atomic_zip_create
# 导入类型定义和工具函数
from .types import DEFAULT_SLOT_COLORS, rgba_to_hex


def _to_lib3mf_geometry(mesh: trimesh.Trimesh):
    v = np.asarray(mesh.vertices, dtype=np.float32)
    f = np.asarray(mesh.faces, dtype=np.int32)

    vertices = []
    for x, y, z in v:
        pos = lib3mf.Position()
        pos.Coordinates[0] = float(x)
        pos.Coordinates[1] = float(y)
        pos.Coordinates[2] = float(z)
        vertices.append(pos)

    triangles = []
    for i0, i1, i2 in f:
        tri = lib3mf.Triangle()
        tri.Indices[0] = int(i0)
        tri.Indices[1] = int(i1)
        tri.Indices[2] = int(i2)
        triangles.append(tri)

    return vertices, triangles


def _export_standard_3mf_from_meshes_lib3mf(
    *,
    out_3mf: Path,
    meshes: Mapping[str, trimesh.Trimesh],
    slot_names: Sequence[str],
    colors: Mapping[str, Tuple[int, int, int, int]],
) -> Path:
    wrapper = get_wrapper() if get_wrapper is not None else lib3mf.Wrapper()
    model = wrapper.CreateModel()

    try:
        if hasattr(model, "SetUnit") and hasattr(lib3mf, "ModelUnit"):
            unit = getattr(lib3mf.ModelUnit, "MilliMeter", None) or getattr(lib3mf.ModelUnit, "Millimeter", None)
            if unit is not None:
                model.SetUnit(unit)
    except Exception as e:
        logger.error(f"[警告] 设置3MF单位失败，将使用默认单位: {e}")
        import traceback

        traceback.print_exc()

    color_group = model.AddColorGroup()
    color_pids: Dict[str, int] = {}
    for slot in slot_names:
        rgba = colors.get(str(slot), (200, 200, 200, 255))
        color = wrapper.RGBAToColor(int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))
        pid = int(color_group.AddColor(color))
        color_pids[str(slot)] = pid
    color_group_rid = color_group.GetResourceID()

    for slot in slot_names:
        tm = meshes.get(slot)
        if tm is None or not isinstance(tm, trimesh.Trimesh) or tm.faces is None or len(tm.faces) == 0:
            continue
        mesh_object = model.AddMeshObject()
        mesh_object.SetName(str(slot))

        vertices, triangles = _to_lib3mf_geometry(tm)
        mesh_object.SetGeometry(vertices, triangles)

        pid = int(color_pids.get(str(slot), 0))
        mesh_object.SetObjectLevelProperty(color_group_rid, pid)
        model.AddBuildItem(mesh_object, wrapper.GetIdentityTransform())

    out_3mf.parent.mkdir(parents=True, exist_ok=True)
    writer = model.QueryWriter("3mf")
    writer.WriteToFile(str(out_3mf))
    return out_3mf

def _load_trimesh_from_stl(stl_path: Path) -> trimesh.Trimesh:
    """
    从 STL 文件加载三角网格。
    
    如果加载失败，将返回一个包含微小三角形的占位网格，以确保后续流程不中断。
    
    参数:
        stl_path: STL 文件路径
    
    返回:
        trimesh.Trimesh: 加载或生成的三角网格对象
    """
    # 创建一个占位符网格，用于加载失败时
    def _placeholder() -> trimesh.Trimesh:
        # 一个微小的三角形，用于在某个通道为空时保持下游导出器/切片器正常工作
        return trimesh.Trimesh(
            vertices=np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.001], [0.001, 0.0, 0.0]], dtype=float),
            faces=np.array([[0, 1, 2]], dtype=int),
            process=False,
        )

    # 检查文件是否存在
    if not stl_path.exists():
        raise FileNotFoundError(f"找不到 STL 文件: {stl_path}")
    
    # 尝试加载 STL 文件
    try:
        tm = trimesh.load(str(stl_path), force="mesh")
    except Exception as e:
        logger.error(f"加载 STL 失败 ({stl_path}): {e}")
        return _placeholder()
    
    # 如果加载的是场景对象，则提取并合并网格
    if isinstance(tm, trimesh.Scene):
        dumped = tuple(tm.dump())
        if not dumped:
            return _placeholder()
        tm = trimesh.util.concatenate(dumped)
    
    # 检查是否为有效的三角网格
    if not isinstance(tm, trimesh.Trimesh):
        return _placeholder()
    if tm.faces is None or len(tm.faces) == 0:
        return _placeholder()
    
    # 处理网格（验证并修复）并返回
    tm = tm.copy()
    tm.process(validate=True)
    return tm

def export_standard_3mf(
    *,
    out_3mf: Path,
    stl_paths: Sequence[Path],
    slot_names: Sequence[str],
    slot_colors: Mapping[str, Tuple[int, int, int, int]] | None = None,
) -> Path:
    """
    导出符合标准的 3MF 文件，包含多个网格对象。
    
    几何体取自 STL 文件；颜色通过 BaseMaterials 分配。
    
    参数:
        out_3mf: 输出的 3MF 文件路径
        stl_paths: STL 文件路径列表
        slot_names: 槽位名称列表，与 STL 文件一一对应
        slot_colors: 槽位颜色映射，键为槽位名，值为 (R, G, B, A) 元组（可选）
    
    返回:
        Path: 输出的 3MF 文件路径
    """
    # 检查 STL 路径和槽位名称数量是否一致
    if len(stl_paths) != len(slot_names):
        raise ValueError("stl_paths 与 slot_names 长度不一致")
    
    # 合并默认颜色和自定义颜色
    colors = dict(DEFAULT_SLOT_COLORS)
    if slot_colors:
        colors.update({k: tuple(v) for k, v in slot_colors.items()})
    
    # 创建输出目录
    out_3mf.parent.mkdir(parents=True, exist_ok=True)
    
    # 定义 XML 命名空间
    CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    MAT_NS = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
    REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
    CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
    
    # 注册命名空间
    ET.register_namespace("", CORE_NS)
    ET.register_namespace("m", MAT_NS)
    
    # 创建模型元素
    model = ET.Element(f"{{{CORE_NS}}}model", {"unit": "millimeter", f"{{http://www.w3.org/2000/xmlns/}}m": MAT_NS})
    resources = ET.SubElement(model, f"{{{CORE_NS}}}resources")

    # 资源 ID 计数器，确保全局唯一
    next_resource_id = 1

    # 创建基础材料组
    bmg_id = str(next_resource_id)
    next_resource_id += 1
    bmg = ET.SubElement(resources, f"{{{MAT_NS}}}basematerials", {"id": bmg_id})
    slot_index: Dict[str, int] = {}
    for idx, s in enumerate(slot_names):
        rgba = colors.get(s, (200, 200, 200, 255))
        slot_index[s] = idx
        # 为每个槽位创建基础材料
        ET.SubElement(
            bmg,
            f"{{{MAT_NS}}}base",
            {"name": str(s), "displaycolor": rgba_to_hex(rgba)},
        )

    # 创建网格对象
    object_ids: List[str] = []
    for stl_path, slot in zip(stl_paths, slot_names):
        tm = _load_trimesh_from_stl(stl_path)
        oid = str(next_resource_id)
        next_resource_id += 1
        object_ids.append(oid)

        # 创建对象元素
        obj = ET.SubElement(
            resources,
            f"{{{CORE_NS}}}object",
            {
                "id": oid,
                "type": "model",
                "name": str(slot)
            },
        )
        # 创建网格元素
        mesh = ET.SubElement(obj, f"{{{CORE_NS}}}mesh")
        # 创建顶点元素
        verts = ET.SubElement(mesh, f"{{{CORE_NS}}}vertices")
        for v in tm.vertices:
            ET.SubElement(
                verts,
                f"{{{CORE_NS}}}vertex",
                {"x": f"{float(v[0])}", "y": f"{float(v[1])}", "z": f"{float(v[2])}"},
            )
        # 创建三角形元素
        # 在 triangles 层级指定 pid 和 pindex 对于兼容性更好
        tris = ET.SubElement(
            mesh, 
            f"{{{CORE_NS}}}triangles",
            {
                "pid": bmg_id,
                "pindex": str(int(slot_index[slot]))
            }
        )
        for f in tm.faces:
            ET.SubElement(
                tris,
                f"{{{CORE_NS}}}triangle",
                {"v1": str(int(f[0])), "v2": str(int(f[1])), "v3": str(int(f[2]))},
            )

    # 创建构建元素
    build = ET.SubElement(model, f"{{{CORE_NS}}}build")
    for oid in object_ids:
        ET.SubElement(build, f"{{{CORE_NS}}}item", {"objectid": oid})

    # 生成模型 XML
    model_xml = ET.tostring(model, encoding="utf-8", xml_declaration=True)
    
    # 创建 [Content_Types].xml
    ET.register_namespace("", CT_NS)
    ct = ET.Element(f"{{{CT_NS}}}Types")
    ET.SubElement(
        ct,
        f"{{{CT_NS}}}Default",
        {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"},
    )
    ET.SubElement(
        ct,
        f"{{{CT_NS}}}Default",
        {"Extension": "model", "ContentType": "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"},
    )
    ct_xml = ET.tostring(ct, encoding="utf-8", xml_declaration=True)

    # 创建 _rels/.rels
    ET.register_namespace("", REL_NS)
    rels = ET.Element(f"{{{REL_NS}}}Relationships")
    ET.SubElement(
        rels,
        f"{{{REL_NS}}}Relationship",
        {
            "Id": "rel-1",
            "Type": "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel",
            "Target": "/3D/3dmodel.model",
        },
    )
    rels_xml = ET.tostring(rels, encoding="utf-8", xml_declaration=True)

    # 定义写入 ZIP 文件的函数
    def write_to_zip(zf):
        zf.writestr("[Content_Types].xml", ct_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("3D/3dmodel.model", model_xml)

    # 原子性地创建 ZIP 文件
    atomic_zip_create(out_3mf, write_to_zip)
    return out_3mf


def export_standard_3mf_from_meshes(
    *,
    out_3mf: Path,
    meshes: Mapping[str, trimesh.Trimesh],
    slot_names: Sequence[str],
    slot_colors: Mapping[str, Tuple[int, int, int, int]] | None = None,
) -> Path:
    if not slot_names:
        raise ValueError("slot_names 不能为空")

    colors = dict(DEFAULT_SLOT_COLORS)
    if slot_colors:
        colors.update({k: tuple(v) for k, v in slot_colors.items()})

    if lib3mf is not None:
        return _export_standard_3mf_from_meshes_lib3mf(
            out_3mf=out_3mf,
            meshes=meshes,
            slot_names=slot_names,
            colors=colors,
        )

    out_3mf.parent.mkdir(parents=True, exist_ok=True)

    CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    MAT_NS = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
    REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
    CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

    ET.register_namespace("", CT_NS)
    ct = ET.Element(f"{{{CT_NS}}}Types")
    ET.SubElement(
        ct,
        f"{{{CT_NS}}}Default",
        {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"},
    )
    ET.SubElement(
        ct,
        f"{{{CT_NS}}}Default",
        {"Extension": "model", "ContentType": "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"},
    )
    ct_xml = ET.tostring(ct, encoding="utf-8", xml_declaration=True)

    ET.register_namespace("", REL_NS)
    rels = ET.Element(f"{{{REL_NS}}}Relationships")
    ET.SubElement(
        rels,
        f"{{{REL_NS}}}Relationship",
        {
            "Id": "rel-1",
            "Type": "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel",
            "Target": "/3D/3dmodel.model",
        },
    )
    rels_xml = ET.tostring(rels, encoding="utf-8", xml_declaration=True)

    bmg_id = 1
    object_ids: List[int] = []
    next_object_id = 2

    def _write_mesh_xml(fp, tm: trimesh.Trimesh, *, pindex: int) -> None:
        v = np.asarray(tm.vertices, dtype=np.float64)
        f = np.asarray(tm.faces, dtype=np.int64)
        fp.write(b"<mesh><vertices>")

        chunk = 20000
        n = int(v.shape[0])
        for i in range(0, n, chunk):
            vs = v[i : i + chunk]
            parts = []
            for x, y, z in vs:
                parts.append(
                    f'<vertex x="{float(x)}" y="{float(y)}" z="{float(z)}"/>\n'
                )
            fp.write("".join(parts).encode("utf-8"))

        fp.write(b"</vertices>")

        fp.write(f'<triangles pid="{int(bmg_id)}" pindex="{int(pindex)}">'.encode("utf-8"))
        m = int(f.shape[0])
        for i in range(0, m, chunk):
            fs = f[i : i + chunk]
            parts = []
            for a, b, c in fs:
                parts.append(f'<triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}"/>\n')
            fp.write("".join(parts).encode("utf-8"))
        fp.write(b"</triangles></mesh>")

    def write_to_zip(zf):
        zf.writestr("[Content_Types].xml", ct_xml)
        zf.writestr("_rels/.rels", rels_xml)

        with zf.open("3D/3dmodel.model", "w") as fp:
            fp.write(b"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
            fp.write(
                f'<model unit="millimeter" xmlns="{CORE_NS}" xmlns:m="{MAT_NS}">'.encode("utf-8")
            )
            fp.write(b"<resources>")

            fp.write(f'<m:basematerials id="{int(bmg_id)}">'.encode("utf-8"))
            slot_index: Dict[str, int] = {}
            for idx, s in enumerate(slot_names):
                rgba = colors.get(s, (200, 200, 200, 255))
                slot_index[str(s)] = int(idx)
                name = _xml_escape(str(s))
                displaycolor = rgba_to_hex(rgba)
                fp.write(
                    f'<m:base name="{name}" displaycolor="{displaycolor}"/>'.encode("utf-8")
                )
            fp.write(b"</m:basematerials>")

            for slot in slot_names:
                tm = meshes.get(slot)
                if tm is None:
                    continue
                if not isinstance(tm, trimesh.Trimesh):
                    continue
                if tm.faces is None or len(tm.faces) == 0:
                    continue

                oid = int(next_object_id + len(object_ids))
                object_ids.append(oid)

                name = _xml_escape(str(slot))
                fp.write(
                    f'<object id="{oid}" type="model" name="{name}">'.encode("utf-8")
                )
                _write_mesh_xml(fp, tm, pindex=int(slot_index.get(str(slot), 0)))
                fp.write(b"</object>")

            fp.write(b"</resources><build>")
            for oid in object_ids:
                fp.write(f'<item objectid="{int(oid)}"/>'.encode("utf-8"))
            fp.write(b"</build></model>")

    atomic_zip_create(out_3mf, write_to_zip)
    return out_3mf
