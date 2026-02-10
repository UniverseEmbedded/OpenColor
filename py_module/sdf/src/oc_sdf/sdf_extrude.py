"""SDF 挤出模块 - 将多边形挤出为 3D Mesh"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Any

import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon

from oc_core_02.utils.bin_loader import import_cpp_extension
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def extrude_layer_mesh(
    z: int,
    slot_name: str,
    poly: Any,
    layer_height_mm: float,
    simplify_mm: float = 0.0,
    debug_stats: dict = None,
    use_cpp: bool = True
) -> List[trimesh.Trimesh]:
    """将多边形挤出为 3D Mesh，带面积守恒三段式指标调试
    
    Args:
        use_cpp: 是否尝试使用 C++ 加速模块 (opencolor_geometry)
    """
    from time import perf_counter
    t_start = perf_counter()
    meshes = []
    z_start = z * layer_height_mm
    
    # 【排查手册步骤3】收集并统计多边形信息
    raw_polys = []
    if isinstance(poly, list):
        # load_svg_polygons返回的是List[Polygon]
        raw_polys.extend([p for p in poly if isinstance(p, (Polygon, MultiPolygon))])
    elif isinstance(poly, MultiPolygon):
        raw_polys.extend(list(poly.geoms))
    elif isinstance(poly, Polygon):
        raw_polys.append(poly)
    else:
        if hasattr(poly, "geoms"):
            for g in poly.geoms:
                if isinstance(g, (Polygon, MultiPolygon)):
                    if isinstance(g, MultiPolygon):
                        raw_polys.extend(list(g.geoms))
                    else:
                        raw_polys.append(g)
    
    # 【关键修复】使用C++或Python合并多边形组件，消除组件间隙
    # 这解决了slice_area > poly_area的问题（多组件间隙被错误填充）
    if len(raw_polys) > 1:
        try:
            # 先修复每个多边形的有效性
            fixed_polys = []
            for p in raw_polys:
                if not p.is_valid:
                    fixed = p.buffer(0)
                    if not fixed.is_empty:
                        if isinstance(fixed, MultiPolygon):
                            fixed_polys.extend(list(fixed.geoms))
                        else:
                            fixed_polys.append(fixed)
                else:
                    fixed_polys.append(p)
            
            # 使用C++合并多边形（默认）
            if use_cpp:
                try:
                    # 尝试导入并使用C++合并
                    cpp_geometry = import_cpp_extension("opencolor_geometry")
                    
                    union_fn = getattr(cpp_geometry, "clipper_union_all_to_polygons_nogil", None)
                    if union_fn is None:
                        raise RuntimeError("C++ 几何模块缺少 clipper_union_all_to_polygons_nogil")
                    
                    # 收集所有环
                    all_loops = []
                    for poly in fixed_polys:
                        if isinstance(poly, Polygon):
                            ext = np.asarray(poly.exterior.coords, dtype=np.float64)
                            if ext.ndim == 2 and ext.shape[0] >= 3 and ext.shape[1] == 2:
                                all_loops.append(ext)
                            for interior in poly.interiors:
                                arr = np.asarray(interior.coords, dtype=np.float64)
                                if arr.ndim == 2 and arr.shape[0] >= 3 and arr.shape[1] == 2:
                                    all_loops.append(arr)
                        elif isinstance(poly, MultiPolygon):
                            for p in poly.geoms:
                                if isinstance(p, Polygon):
                                    ext = np.asarray(p.exterior.coords, dtype=np.float64)
                                    if ext.ndim == 2 and ext.shape[0] >= 3 and ext.shape[1] == 2:
                                        all_loops.append(ext)
                                    for interior in p.interiors:
                                        arr = np.asarray(interior.coords, dtype=np.float64)
                                        if arr.ndim == 2 and arr.shape[0] >= 3 and arr.shape[1] == 2:
                                            all_loops.append(arr)
                    
                    if all_loops:
                        result_polys = union_fn(all_loops, scale=10000.0)
                        # 转换回Shapely
                        final_polys = []
                        for shell, holes in result_polys or []:
                            shell_arr = np.asarray(shell, dtype=np.float64)
                            if shell_arr.ndim != 2 or shell_arr.shape[0] < 3 or shell_arr.shape[1] != 2:
                                continue
                            holes_arr = []
                            for h in holes or []:
                                h_arr = np.asarray(h, dtype=np.float64)
                                if h_arr.ndim != 2 or h_arr.shape[0] < 3 or h_arr.shape[1] != 2:
                                    continue
                                holes_arr.append(h_arr)
                            p = Polygon(shell_arr, holes_arr)
                            if not p.is_valid:
                                p = p.buffer(0)
                            if p.is_empty:
                                continue
                            if p.geom_type == "Polygon":
                                final_polys.append(p)
                            else:
                                final_polys.extend([g for g in p.geoms if g.geom_type == "Polygon" and g.area > 1e-9])
                        
                        if len(final_polys) < len(fixed_polys):
                            logger.error(f"【C++合并组件】{slot_name} L{z:02d}: {len(fixed_polys)}个组件合并为{len(final_polys)}个")
                    else:
                        final_polys = fixed_polys
                except Exception as e:
                    logger.error(f"[错误] C++多边形合并失败(layer={z}, slot={slot_name}): {e}")
                    raise  # 默认使用C++，失败时报错退出
            else:
                # 使用Python unary_union合并多边形
                from shapely.ops import unary_union
                merge_buffer = 0.001  # 1微米
                merged = unary_union([p.buffer(merge_buffer) for p in fixed_polys]).buffer(-merge_buffer)
                
                final_polys = []
                if isinstance(merged, MultiPolygon):
                    final_polys.extend(list(merged.geoms))
                elif isinstance(merged, Polygon):
                    final_polys.append(merged)
                else:
                    final_polys = fixed_polys
                    
                if len(final_polys) < len(fixed_polys):
                    logger.info(f"【Python合并组件】{slot_name} L{z:02d}: {len(fixed_polys)}个组件合并为{len(final_polys)}个")
        except Exception as e:
            logger.error(f"[错误] 多边形合并失败(layer={z}, slot={slot_name}): {e}")
            raise  # 出错直接报错退出
    else:
        final_polys = raw_polys
    
    # 【排查手册步骤3】统计拓扑信息
    total_poly_area = 0.0
    total_rings = 0
    total_holes = 0
    component_count = len(final_polys)
    
    for p in final_polys:
        if isinstance(p, Polygon):
            total_poly_area += p.area
            total_rings += 1 + len(p.interiors)
            total_holes += len(p.interiors)
    
    # 【排查手册步骤2】poly_area
    poly_area = total_poly_area

    cpp_geometry = None
    try:
        cpp_geometry = import_cpp_extension("opencolor_geometry")
    except Exception as e:
        cpp_geometry = None
        if use_cpp:
            logger.error("C++几何模块导入失败(layer={}, slot={}): {}", z, slot_name, e)
            raise

    cpp_extrude_fn = None
    if use_cpp:
        if cpp_geometry is None:
            raise RuntimeError(f"已启用 C++ 挤出，但 opencolor_geometry 不可用(layer={z}, slot={slot_name})")
        cpp_extrude_fn = getattr(cpp_geometry, "extrude_rings_nogil", None)
        if cpp_extrude_fn is None:
            cpp_extrude_fn = getattr(cpp_geometry, "extrude_rings", None)
        if cpp_extrude_fn is None:
            raise RuntimeError(f"C++ 几何模块缺少 extrude_rings(_nogil)(layer={z}, slot={slot_name})")
    
    def _earcut_triangulate(poly_in: Polygon) -> tuple[np.ndarray, np.ndarray, list, float] | None:
        """使用 mapbox_earcut 对多边形进行三角剖分，正确处理孔洞，并对 ring 做防御性清洗。

        Returns:
            (verts_2d, faces, ring_end_indices, tri_area) 或 None
        """
        try:
            import mapbox_earcut as earcut
        except Exception as e:
            logger.error(f"earcut 导入失败(layer={z}, slot={slot_name}): {e}")
            return None

        # 根据几何尺度设置清洗阈值（单位：mm）
        minx, miny, maxx, maxy = poly_in.bounds
        scale = max(1.0, float(max(maxx - minx, maxy - miny)))
        eps = 1e-7 * scale  # 去重/短边阈值

        def _clean_ring(coords: np.ndarray) -> np.ndarray:
            """【排查手册步骤5】清洗 ring：去闭合重复点、去连续重复点、去极短边、去共线点。"""
            if coords.shape[0] < 3:
                return coords

            # 去掉闭合重复点
            if coords.shape[0] >= 2 and np.allclose(coords[0], coords[-1], atol=eps, rtol=0.0):
                coords = coords[:-1]
            if coords.shape[0] < 3:
                return coords

            # 去连续重复点
            out = [coords[0]]
            for k in range(1, coords.shape[0]):
                if np.linalg.norm(coords[k] - out[-1]) > eps:
                    out.append(coords[k])
            coords = np.asarray(out, dtype=np.float64)
            if coords.shape[0] < 3:
                return coords

            q = np.round(coords / eps).astype(np.int64)
            seen = set()
            out2 = []
            for p, qq in zip(coords.tolist(), q.tolist()):
                key = (int(qq[0]), int(qq[1]))
                if key in seen:
                    continue
                seen.add(key)
                out2.append(p)
            coords = np.asarray(out2, dtype=np.float64)
            if coords.shape[0] < 3:
                return coords

            # 去极短边点（如果某点与前后都极近，则删除）
            changed = True
            while changed and coords.shape[0] >= 3:
                changed = False
                keep = []
                n = coords.shape[0]
                for i in range(n):
                    prev = coords[(i - 1) % n]
                    cur = coords[i]
                    nxt = coords[(i + 1) % n]
                    if np.linalg.norm(cur - prev) <= eps and np.linalg.norm(nxt - cur) <= eps:
                        changed = True
                        continue
                    keep.append(cur)
                coords = np.asarray(keep, dtype=np.float64)

            if coords.shape[0] < 3:
                return coords

            # 去共线点（保守）
            def _is_collinear(a, b, c) -> bool:
                ab = b - a
                bc = c - b
                cross = abs(ab[0] * bc[1] - ab[1] * bc[0])
                return cross <= (1e-12 * (scale * scale))

            keep = []
            n = coords.shape[0]
            for i in range(n):
                a = coords[(i - 1) % n]
                b = coords[i]
                c = coords[(i + 1) % n]
                if _is_collinear(a, b, c):
                    continue
                keep.append(b)
            coords = np.asarray(keep, dtype=np.float64)
            return coords

        # 处理外轮廓
        ext = np.asarray(poly_in.exterior.coords, dtype=np.float64)
        ext = _clean_ring(ext)
        if ext.shape[0] < 3:
            return None

        rings = [ext]
        ring_end_indices = [len(ext)]

        # 处理孔洞（只保留顶点数>=3的孔洞）
        for interior in poly_in.interiors:
            h = np.asarray(interior.coords, dtype=np.float64)
            h = _clean_ring(h)
            if h.shape[0] >= 3:
                rings.append(h)
                ring_end_indices.append(ring_end_indices[-1] + len(h))

        verts = np.vstack(rings).astype(np.float64)
        if verts.shape[0] < 3:
            return None

        ring_idx = np.array(ring_end_indices, dtype=np.uint32)
        tri = earcut.triangulate_float64(verts, ring_idx)
        tri = np.asarray(tri, dtype=np.uint32).reshape(-1, 3)
        if tri.size == 0:
            return None
        
        # 【排查手册步骤2】计算tri_area
        tri_area = 0.0
        for face in tri:
            v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
            # 2D三角形面积 = 0.5 * |cross(v1-v0, v2-v0)|
            cross = abs((v1[0]-v0[0])*(v2[1]-v0[1]) - (v1[1]-v0[1])*(v2[0]-v0[0]))
            tri_area += 0.5 * cross
        
        return verts, tri, ring_end_indices, tri_area

    def _boundary_edges_count(mesh: trimesh.Trimesh) -> int:
        try:
            edges_inverse = mesh.edges_unique_inverse
            counts = np.bincount(edges_inverse)
            return int(np.sum(counts == 1))
        except Exception as e:
            logger.error("边界边统计失败(layer={}, slot={}): {}", z, slot_name, e)
            return 0

    def _repair_mesh_if_needed(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        if mesh.vertices is None or mesh.faces is None or len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            return mesh

        if bool(mesh.is_watertight):
            return mesh

        try:
            b = np.asarray(mesh.bounds, dtype=np.float64)
            if b.shape != (2, 3):
                raise RuntimeError(f"非法 bounds 形状: {b.shape}")
            dx = float(b[1, 0] - b[0, 0])
            dy = float(b[1, 1] - b[0, 1])
            scale = max(1.0, float(max(dx, dy)))
        except Exception as e:
            logger.error("bounds 解析失败(layer={}, slot={}): {}", z, slot_name, e)
            scale = 1.0
        eps_weld = 1e-7 * scale

        try:
            if hasattr(mesh, "remove_infinite_values"):
                mesh.remove_infinite_values()
            if hasattr(mesh, "remove_degenerate_faces"):
                mesh.remove_degenerate_faces()
            if hasattr(mesh, "remove_duplicate_faces"):
                mesh.remove_duplicate_faces()
            if hasattr(mesh, "remove_unreferenced_vertices"):
                mesh.remove_unreferenced_vertices()
        except Exception as e:
            logger.error("网格基础清理失败(layer={}, slot={}): {}", z, slot_name, e)

        if bool(mesh.is_watertight):
            return mesh

        try:
            if hasattr(mesh, "merge_vertices"):
                try:
                    mesh.merge_vertices(radius=float(eps_weld))
                except TypeError:
                    mesh.merge_vertices()
        except Exception as e:
            logger.error("网格焊接失败(layer={}, slot={}): {}", z, slot_name, e)

        if not bool(mesh.is_watertight):
            try:
                ok = bool(trimesh.repair.fill_holes(mesh))
                if ok:
                    try:
                        if hasattr(mesh, "remove_duplicate_faces"):
                            mesh.remove_duplicate_faces()
                        if hasattr(mesh, "remove_unreferenced_vertices"):
                            mesh.remove_unreferenced_vertices()
                    except Exception as e:
                        logger.error("补洞后清理失败(layer={}, slot={}): {}", z, slot_name, e)
            except Exception as e:
                logger.error("网格补洞失败(layer={}, slot={}): {}", z, slot_name, e)

        try:
            if hasattr(mesh, "remove_degenerate_faces"):
                mesh.remove_degenerate_faces()
            if hasattr(mesh, "remove_duplicate_faces"):
                mesh.remove_duplicate_faces()
            if hasattr(mesh, "remove_unreferenced_vertices"):
                mesh.remove_unreferenced_vertices()
        except Exception as e:
            logger.error("网格焊接后清理失败(layer={}, slot={}): {}", z, slot_name, e)

        if use_cpp:
            # 对于 C++ Manifold 流程，只要是封闭的（无边界边）通常就能处理
            # 即使 trimesh.is_watertight 为 False（通常是因为存在 pinch point 等非流形边）
            bc = _boundary_edges_count(mesh)
            if bc > 0:
                raise RuntimeError(
                    f"网格修复后仍非封闭(layer={z}, slot={slot_name}, boundary_edges={bc})"
                )
        elif not bool(mesh.is_watertight):
             # 非 C++ 流程（虽然本项目目前强依赖 C++），维持原有的严格检查
             raise RuntimeError(
                f"网格修复后仍非封闭(layer={z}, slot={slot_name}, boundary_edges={_boundary_edges_count(mesh)})"
            )

        return mesh

    total_tri_area = 0.0
    total_slice_area = 0.0
    
    z_end = z_start + layer_height_mm

    simplify_mm_f = float(simplify_mm or 0.0)
    if simplify_mm_f < 0:
        simplify_mm_f = 0.0

    cleaned_polys: List[Polygon] = []
    for p in final_polys:
        try:
            if use_cpp:
                try:
                    from shapely.validation import make_valid

                    cleaned = make_valid(p)
                except Exception as e:
                    logger.error("多边形 make_valid 失败(layer={}, slot={}): {}", z, slot_name, e)
                    try:
                        cleaned = p.buffer(0)
                    except Exception as e2:
                        logger.error("多边形 buffer(0) 失败(layer={}, slot={}): {}", z, slot_name, e2)
                        cleaned = p
            else:
                cleaned = p.buffer(0) if not p.is_valid else p

            if cleaned.is_empty:
                logger.info(f"多边形为空(layer={z}, slot={slot_name})")
                continue

            parts = [cleaned]
            if isinstance(cleaned, MultiPolygon):
                parts = list(cleaned.geoms)
            elif isinstance(cleaned, Polygon):
                parts = [cleaned]
            elif hasattr(cleaned, "geoms"):
                parts = []
                for g in list(cleaned.geoms):
                    if isinstance(g, Polygon):
                        parts.append(g)
                    elif isinstance(g, MultiPolygon):
                        parts.extend(list(g.geoms))

            for part in parts:
                if part.is_empty or (not isinstance(part, Polygon)):
                    continue

                if simplify_mm_f > 0:
                    try:
                        simplified = part.simplify(float(simplify_mm_f), preserve_topology=True)
                        if isinstance(simplified, Polygon) and (not simplified.is_empty):
                            if not simplified.is_valid:
                                simplified = simplified.buffer(0)
                            if not simplified.is_empty:
                                part = simplified
                    except Exception as e:
                        logger.error("多边形简化失败(layer={}, slot={}): {}", z, slot_name, e)

                cleaned_polys.append(part)
        except Exception as e:
            logger.error("多边形清理失败(layer={}, slot={}): {}", z, slot_name, e)

    parallel_cpp = (
        cpp_extrude_fn is not None
        and getattr(cpp_geometry, "extrude_rings_nogil", None) is cpp_extrude_fn
        and (os.cpu_count() or 1) > 1
        and len(cleaned_polys) >= 2
    )

    if use_cpp:
        def _extrude_one_cpp(cleaned: Polygon):
            outer_pts = len(cleaned.exterior.coords)
            holes_count = len(cleaned.interiors)

            if cpp_extrude_fn is None:
                raise RuntimeError(f"已启用 C++ 挤出，但 extrude 函数不可用(layer={z}, slot={slot_name})")

            try:
                from shapely.geometry.polygon import orient

                cleaned = orient(cleaned, sign=1.0)
            except Exception as e:
                logger.error("多边形方向统一失败(layer={}, slot={}): {}", z, slot_name, e)

            try:
                minx, miny, maxx, maxy = cleaned.bounds
                scale = max(1.0, float(max(maxx - minx, maxy - miny)))
            except Exception:
                scale = 1.0
            eps = 1e-7 * float(scale)

            def _clean_ring(coords: np.ndarray) -> np.ndarray:
                if coords.shape[0] < 3:
                    return coords
                if coords.shape[0] >= 2 and np.allclose(coords[0], coords[-1], atol=eps, rtol=0.0):
                    coords = coords[:-1]
                if coords.shape[0] < 3:
                    return coords
                out = [coords[0]]
                for k in range(1, coords.shape[0]):
                    if np.linalg.norm(coords[k] - out[-1]) > eps:
                        out.append(coords[k])
                coords = np.asarray(out, dtype=np.float64)
                if coords.shape[0] < 3:
                    return coords
                q = np.round(coords / eps).astype(np.int64)
                seen = set()
                out2 = []
                for p, qq in zip(coords.tolist(), q.tolist()):
                    key = (int(qq[0]), int(qq[1]))
                    if key in seen:
                        continue
                    seen.add(key)
                    out2.append(p)
                coords = np.asarray(out2, dtype=np.float64)
                return coords

            ext = _clean_ring(np.asarray(cleaned.exterior.coords, dtype=np.float64))
            if ext.shape[0] < 3:
                return None, 0.0, outer_pts, holes_count, "cpp_empty"

            rings = [ext]
            for interior in cleaned.interiors:
                h = _clean_ring(np.asarray(interior.coords, dtype=np.float64))
                if h.shape[0] >= 3:
                    rings.append(h)

            verts_3d, faces_3d, tri_area = cpp_extrude_fn(rings, float(z_start), float(z_end))
            if len(faces_3d) == 0 or len(verts_3d) == 0:
                return None, float(tri_area), outer_pts, holes_count, "cpp_empty"
            return (verts_3d, faces_3d), float(tri_area), outer_pts, holes_count, "cpp_ok"

        cpp_results = []
        if parallel_cpp:
            max_workers = max(1, min(len(cleaned_polys), int(os.cpu_count() or 1)))
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                fut_map = {ex.submit(_extrude_one_cpp, p): p for p in cleaned_polys}
                for fut in as_completed(fut_map):
                    try:
                        cpp_results.append((fut_map[fut], fut.result()))
                    except Exception as e:
                        logger.error("[错误] C++并行挤出失败(layer={}, slot={}): {}", z, slot_name, e)
                        raise
        else:
            for p in cleaned_polys:
                try:
                    cpp_results.append((p, _extrude_one_cpp(p)))
                except Exception as e:
                    logger.error("[错误] C++挤出失败(layer={}, slot={}): {}", z, slot_name, e)
                    raise

        fallback_polys: List[Polygon] = []
        skipped_tiny = 0
        skipped_tiny_area_max = 0.0
        for cleaned, (mesh_data, tri_area_cpp, outer_pts, holes_count, tag) in cpp_results:
            if tag == "cpp_ok" and mesh_data is not None:
                verts_3d, faces_3d = mesh_data
                total_tri_area += float(tri_area_cpp)
                total_slice_area += float(tri_area_cpp)
                m = trimesh.Trimesh(vertices=verts_3d, faces=faces_3d, process=False)
                m = _repair_mesh_if_needed(m)
                if debug_stats is not None:
                    debug_stats.setdefault(f"L{z:02d}_{slot_name}", {}).update({
                        "is_watertight": bool(m.is_watertight),
                        "boundary_edges": _boundary_edges_count(m),
                        "volume": float(m.volume),
                        "abs_volume": float(abs(m.volume)),
                    })
                meshes.append(m)
            else:
                if tag == "cpp_empty":
                    area_mm2 = float(getattr(cleaned, "area", 0.0))
                    if area_mm2 <= 1e-12:
                        skipped_tiny += 1
                        skipped_tiny_area_max = max(skipped_tiny_area_max, area_mm2)
                        logger.info(f"C++挤出返回空网格但面积极小，已忽略(layer={z}, slot={slot_name}, area={area_mm2:.3e}mm², outer_pts={outer_pts}, holes={holes_count})"
                        )
                        continue
                    logger.info(f"C++挤出返回空网格(layer={z}, slot={slot_name}, area={area_mm2:.6f}mm², outer_pts={outer_pts}, holes={holes_count})")
                fallback_polys.append(cleaned)

        if fallback_polys:
            raise RuntimeError(
                f"已启用 C++ 挤出，但存在 {len(fallback_polys)} 个多边形无法由 C++ 挤出(layer={z}, slot={slot_name})"
            )
    else:
        for cleaned in cleaned_polys:
            try:
                outer_pts = len(cleaned.exterior.coords)
                holes_count = len(cleaned.interiors)

                tri = _earcut_triangulate(cleaned)
                if tri is None:
                    logger.error(f"earcut 三角剖分失败(layer={z}, slot={slot_name}, outer_pts={outer_pts}, holes={holes_count})")
                    continue
                verts_2d, faces, ring_end_indices, tri_area = tri
                total_tri_area += tri_area

                tri_count = len(faces)
                if tri_count == 0:
                    logger.info(f"earcut 返回0个三角形(layer={z}, slot={slot_name})")
                    continue

                verts_bottom = np.column_stack([verts_2d, np.full(len(verts_2d), z_start)])
                verts_top = np.column_stack([verts_2d, np.full(len(verts_2d), z_end)])
                all_verts = np.vstack([verts_bottom, verts_top])
                faces_top = faces + len(verts_2d)
                faces_bottom = faces[:, ::-1]

                edge_faces = []
                for i, end_idx in enumerate(ring_end_indices):
                    start_idx = 0 if i == 0 else ring_end_indices[i-1]
                    for j in range(start_idx, end_idx):
                        j_next = start_idx if j == end_idx - 1 else j + 1
                        v0 = j
                        v1 = j_next
                        v2 = j_next + len(verts_2d)
                        v3 = j + len(verts_2d)
                        if i == 0:
                            edge_faces.append([v0, v1, v2])
                            edge_faces.append([v0, v2, v3])
                        else:
                            edge_faces.append([v0, v2, v1])
                            edge_faces.append([v0, v3, v2])

                faces_side = np.array(edge_faces, dtype=np.int32) if edge_faces else np.zeros((0, 3), dtype=np.int32)
                all_faces = np.vstack([faces_bottom, faces_top, faces_side])
                m = trimesh.Trimesh(vertices=all_verts, faces=all_faces, process=False)
                m = _repair_mesh_if_needed(m)
                total_slice_area += tri_area

                if debug_stats is not None:
                    debug_stats.setdefault(f"L{z:02d}_{slot_name}", {}).update({
                        "is_watertight": bool(m.is_watertight),
                        "boundary_edges": _boundary_edges_count(m),
                        "volume": float(m.volume),
                        "abs_volume": float(abs(m.volume)),
                    })

                meshes.append(m)
            except Exception as e:
                logger.error(f"earcut 挤出失败(layer={z}, slot={slot_name}): {e}")
                raise
    
    # 【排查手册步骤2】打印面积守恒三段式指标
    t_end = perf_counter()
    if component_count > 0:
        area_ratio = (total_tri_area / poly_area * 100) if poly_area > 0 else 0
        slice_ratio = (total_slice_area / poly_area * 100) if poly_area > 0 else 0
        logger.info(f"【面积守恒】{slot_name} L{z:02d}: poly={poly_area:.2f}mm², tri={total_tri_area:.2f}mm²({area_ratio:.1f}%), slice={total_slice_area:.2f}mm²({slice_ratio:.1f}%) | 组件={component_count}, 环={total_rings}, 洞={total_holes} | 用时={t_end - t_start:.3f}s")
    else:
        logger.info(f"[进度] extrude_layer_mesh({slot_name} L{z:02d}): 完成，生成 {len(meshes)} 个网格，用时={t_end - t_start:.3f}s")

    return meshes
