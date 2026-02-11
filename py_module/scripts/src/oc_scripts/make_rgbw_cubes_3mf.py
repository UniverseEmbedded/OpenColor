#!/usr/bin/env python3
"""
创建包含4个彩色立方体（RGBW）的3MF文件，使用标准3MF BaseMaterials。

- 几何体通过trimesh创建（可靠的绕序/流形立方体网格）
- 颜色通过lib3mf BaseMaterialGroup和对象级属性分配
- 输出：单个.3mf文件，包含4个独立的MeshObject，放置在构建平台上

已在PyPI lib3mf (2.4.1.post1)上测试通过。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import trimesh
import lib3mf


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def add_mesh_from_trimesh(
    model: lib3mf.Model, tm: trimesh.Trimesh, name: str
) -> lib3mf.MeshObject:
    """将trimesh网格添加到lib3mf模型中

    将trimesh创建的网格转换为lib3mf的MeshObject，
    包括顶点、三角面的转换

    Args:
        model: lib3mf模型对象
        tm: trimesh网格对象
        name: 网格对象的名称

    Returns:
        创建好的lib3mf MeshObject
    """
    mesh_obj = model.AddMeshObject()
    mesh_obj.SetName(name)

    # 添加顶点
    for v in tm.vertices:
        # lib3mf.Position期望单个元组/列表 (x, y, z)
        mesh_obj.AddVertex(lib3mf.Position((float(v[0]), float(v[1]), float(v[2]))))

    # 添加三角形
    for f in tm.faces:
        mesh_obj.AddTriangle(lib3mf.Triangle((int(f[0]), int(f[1]), int(f[2]))))

    return mesh_obj


def main() -> None:
    """主函数：生成RGBW彩色立方体的3MF文件

    解析命令行参数，创建4个彩色立方体（红、绿、蓝、白），
    并将它们保存为3MF文件
    """
    ap = argparse.ArgumentParser(description="生成RGBW彩色立方体的3MF文件")
    ap.add_argument(
        "--out",
        type=str,
        default="out_rgbw_cubes/rgbw_cubes.3mf",
        help="输出.3mf文件路径",
    )
    ap.add_argument("--size-mm", type=float, default=10.0, help="立方体边长（毫米）")
    ap.add_argument(
        "--gap-mm", type=float, default=2.0, help="立方体之间的间隙（毫米）"
    )
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建lib3mf包装器和模型
    w = lib3mf.get_wrapper()
    model = w.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)

    # ---- 材质（BaseMaterials）----
    bmg = model.AddBaseMaterialGroup()
    uid = bmg.GetUniqueResourceID()

    # 添加红、绿、蓝、白四种材质
    pid_r = bmg.AddMaterial("R", w.RGBAToColor(255, 0, 0, 255))
    pid_g = bmg.AddMaterial("G", w.RGBAToColor(0, 255, 0, 255))
    pid_b = bmg.AddMaterial("B", w.RGBAToColor(0, 0, 255, 255))
    pid_w = bmg.AddMaterial("W", w.RGBAToColor(255, 255, 255, 255))

    # ---- 几何体：4个立方体 ----
    size = float(args.size_mm)
    gap = float(args.gap_mm)
    step = size + gap

    # 在构建平台上以2x2布局放置（Z=0在构建平台上）
    placements = [
        ("Cube_R", pid_r, (0.0, 0.0, size / 2.0)),
        ("Cube_G", pid_g, (step, 0.0, size / 2.0)),
        ("Cube_B", pid_b, (0.0, step, size / 2.0)),
        ("Cube_W", pid_w, (step, step, size / 2.0)),
    ]

    # 创建以原点为中心的立方体，然后通过构建项变换放置
    base_cube = trimesh.creation.box(extents=(size, size, size))
    # base_cube以原点为中心；我们通过上面的变换将其提升size/2

    for name, pid, (tx, ty, tz) in placements:
        mesh_obj = add_mesh_from_trimesh(model, base_cube, name=name)
        mesh_obj.SetObjectLevelProperty(uid, pid)

        transform = w.GetTranslationTransform(float(tx), float(ty), float(tz))
        model.AddBuildItem(mesh_obj, transform)

    # ---- 写入文件 ----
    writer = model.QueryWriter("3mf")
    writer.WriteToFile(str(out_path))
    logger.info(f"已写入: {out_path.resolve()}")


if __name__ == "__main__":
    main()
