from __future__ import annotations

"""3MF 导出辅助函数（兼容层）。

此模块现在将所有实现委托给 `model_export`。
"""

# 导入操作系统相关模块
# 导入路径处理模块
from pathlib import Path

# 导入类型提示模块
from typing import List, Mapping, Sequence, Tuple

# 导入数值计算模块
import numpy as np

# 导入三角网格处理库
import trimesh

# 从新模块导入以保持兼容性
from model_export import (
    export_standard_3mf as _export_standard_impl,
    generate_bambu_project_from_template as _generate_bambu_impl,
    DEFAULT_SLOT_COLORS,
    rgba_to_hex,
    MeshData,
)


def _load_trimesh_from_stl(stl_path: Path) -> trimesh.Trimesh:
    """
    从 STL 文件加载三角网格

    参数:
        stl_path: STL 文件路径

    返回:
        加载的三角网格对象

    注意:
        我们保留这个辅助函数在这里，因为它可能被 core 的其他部分使用，
        但 standard_3mf 有自己的副本用于内部使用。
    """

    # 创建一个占位符网格，用于加载失败时
    def _placeholder() -> trimesh.Trimesh:
        return trimesh.Trimesh(
            vertices=np.array(
                [[0.0, 0.0, 0.0], [0.0, 0.0, 0.001], [0.001, 0.0, 0.0]], dtype=float
            ),
            faces=np.array([[0, 1, 2]], dtype=int),
            process=False,
        )

    # 检查文件是否存在
    if not stl_path.exists():
        raise FileNotFoundError(stl_path)

    # 尝试加载 STL 文件
    try:
        tm = trimesh.load(str(stl_path), force="mesh")
    except Exception:
        return _placeholder()

    # 如果加载的是场景对象，则提取网格
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

    # 处理网格并返回
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
    导出符合标准的 3MF 文件（委托给 opencolor_export.standard_3mf）

    参数:
        out_3mf: 输出的 3MF 文件路径
        stl_paths: STL 文件路径列表
        slot_names: 槽位名称列表
        slot_colors: 槽位颜色映射（可选）

    返回:
        输出的 3MF 文件路径
    """
    return _export_standard_impl(
        out_3mf=out_3mf,
        stl_paths=stl_paths,
        slot_names=slot_names,
        slot_colors=slot_colors,
    )


def export_bambu_project_3mf(
    *,
    out_3mf: Path,
    template_3mf: Path,
    stl_paths: Sequence[Path],
    slot_names: Sequence[str],
    slot_colors: Mapping[str, Tuple[int, int, int, int]] | None = None,
    extruder_map: Mapping[str, int] | None = None,
) -> Path:
    """
    导出 Bambu Studio 项目 3MF 文件（委托给 opencolor_export.bambu_project_3mf）

    参数:
        out_3mf: 输出的 3MF 文件路径
        template_3mf: 模板 3MF 文件路径
        stl_paths: STL 文件路径列表
        slot_names: 槽位名称列表
        slot_colors: 槽位颜色映射（可选）
        extruder_map: 槽位名称到挤出机编号的映射 (1-based)

    返回:
        输出的 3MF 文件路径
    """
    # 检查 STL 路径和槽位名称数量是否一致
    if len(stl_paths) != len(slot_names):
        raise ValueError("stl_paths 与 slot_names 长度不一致")

    # 合并默认颜色和自定义颜色
    colors = dict(DEFAULT_SLOT_COLORS)
    if slot_colors:
        colors.update({k: tuple(v) for k, v in slot_colors.items()})

    # 生成耗材十六进制颜色列表
    filament_hex = [
        rgba_to_hex(colors.get(sn, (200, 200, 200, 255))) for sn in slot_names
    ]

    # 加载 STL 文件并转换为 MeshData
    meshes: List[MeshData] = []
    for p in stl_paths:
        tm = _load_trimesh_from_stl(p)
        V = np.asarray(tm.vertices, dtype=float)
        F = np.asarray(tm.faces, dtype=int)
        meshes.append(MeshData(vertices=V, faces=F))

    # 创建输出目录
    out_3mf.parent.mkdir(parents=True, exist_ok=True)

    # 生成 Bambu 项目 3MF 文件
    _generate_bambu_impl(
        template_3mf=template_3mf,
        out_3mf=out_3mf,
        meshes=meshes,
        slot_names=slot_names,
        filament_hex=filament_hex,
        extruder_map=extruder_map,
    )
    return out_3mf
