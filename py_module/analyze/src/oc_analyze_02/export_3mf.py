"""导出一个通用（标准）3MF：8 个立方体，每个对象一个颜色。

流水线：shapely（2D）-> trimesh（3D 网格）-> lib3mf（官方 3MF 写入）
"""

from __future__ import annotations

import numpy as np
import trimesh
from shapely.geometry import Polygon
from pathlib import Path

import lib3mf
from lib3mf import get_wrapper


def make_unit_square_with_boolean_demo() -> Polygon:
    """
    Create a 2D square. Also demo a boolean op (difference) in 2D stage.
    We will use the *outer square* for cube extrusion; the boolean result is
    returned just to show how you'd validate/repair 2D profiles.
    """
    outer = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    # punch a small hole (difference) to demonstrate shapely boolean usage
    hole = Polygon([(0.45, 0.45), (0.55, 0.45), (0.55, 0.55), (0.45, 0.55)])
    _profile_with_hole = outer.difference(hole)  # not used for cubes, just a demo
    return outer


def extrude_cube_mesh(edge: float) -> trimesh.Trimesh:
    """
    Make a cube by extruding a 2D square profile.
    trimesh.creation.extrude_polygon uses shapely polygon as input.
    """
    square = make_unit_square_with_boolean_demo()
    # scale square from unit to edge size
    scaled = Polygon([(x * edge, y * edge) for x, y in square.exterior.coords])
    mesh = trimesh.creation.extrude_polygon(scaled, height=edge)
    mesh = mesh.process(validate=True)
    if hasattr(mesh, "unique_faces"):
        mesh.update_faces(mesh.unique_faces())
    if hasattr(mesh, "nondegenerate_faces"):
        mesh.update_faces(mesh.nondegenerate_faces())
    if hasattr(mesh, "remove_unreferenced_vertices"):
        mesh.remove_unreferenced_vertices()
    if hasattr(mesh, "merge_vertices"):
        mesh.merge_vertices()
    return mesh


def to_lib3mf_geometry(mesh: trimesh.Trimesh):
    """
    Convert trimesh geometry arrays into lib3mf Position/Triangle arrays
    suitable for mesh_object.SetGeometry(vertices, triangles).

    The PyPI example shows Position().Coordinates[...] and Triangle().Indices[...] usage. :contentReference[oaicite:3]{index=3}
    """
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


def get_resource_id(resource) -> int:
    """
    lib3mf resources have GetResourceID() and/or GetUniqueResourceID().
    The docs indicate GetResourceID exists and may be replaced by GetUniqueResourceID later. :contentReference[oaicite:4]{index=4}
    """
    if hasattr(resource, "GetUniqueResourceID"):
        return int(resource.GetUniqueResourceID())
    return int(resource.GetResourceID())


def main(out_path: str = "colored_cubes.3mf"):
    wrapper = get_wrapper()

    model = wrapper.CreateModel()
    # model.SetUnit(...) is supported; omitted here to keep it minimal.
    # (If you want: model.SetUnit(lib3mf.ModelUnit.Millimeter) etc.) :contentReference[oaicite:5]{index=5}

    color_group = model.AddColorGroup()

    rgba_list = [
        (255, 0, 0, 255),      # red
        (0, 255, 0, 255),      # green
        (0, 0, 255, 255),      # blue
        (255, 255, 0, 255),    # yellow
        (255, 0, 255, 255),    # magenta
        (0, 255, 255, 255),    # cyan
        (255, 128, 0, 255),    # orange
        (160, 32, 240, 255),   # purple
    ]

    color_property_ids = []
    for idx, (r, g, b, a) in enumerate(rgba_list):
        color = wrapper.RGBAToColor(int(r), int(g), int(b), int(a))
        pid = color_group.AddColor(color)
        color_property_ids.append(int(pid))

    color_group_rid = get_resource_id(color_group)

    # ---- Build 8 cubes (2x2x2) with different object-level colors ----
    edge = 10.0
    gap = 2.0
    cube_mesh = extrude_cube_mesh(edge=edge)

    # positions for a 2x2x2 grid
    offsets = []
    for z in range(2):
        for y in range(2):
            for x in range(2):
                offsets.append(np.array([x, y, z], dtype=np.float32) * (edge + gap))

    for i, offset in enumerate(offsets):
        # trimesh is the "hub": copy + translate mesh
        m = cube_mesh.copy()
        m.apply_translation(offset)

        # lib3mf mesh object
        mesh_object = model.AddMeshObject()
        mesh_object.SetName(f"Cube_{i}")

        vertices, triangles = to_lib3mf_geometry(m)
        mesh_object.SetGeometry(vertices, triangles)  # same pattern as PyPI cube example :contentReference[oaicite:8]{index=8}

        color_pid = color_property_ids[i % len(color_property_ids)]
        mesh_object.SetObjectLevelProperty(color_group_rid, color_pid)

        # Add to build (identity transform is fine because we already baked translations into vertices)
        model.AddBuildItem(mesh_object, wrapper.GetIdentityTransform())

    out_file = Path(out_path)
    writer = model.QueryWriter("3mf")
    writer.WriteToFile(str(out_file))
    print(f"已写出：{out_file}")


if __name__ == "__main__":
    main()
